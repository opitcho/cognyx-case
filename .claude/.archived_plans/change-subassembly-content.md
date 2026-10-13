# Let a person change the BOM of a variant: insert or delete a component or a sub-assembly

Written 2026-10-13 against commit `d368046`, reviewed the same day against `main` at `0e293c6`, then revised the
same day:

- The first version had two claim types that acted on components only (`set_component`, `remove_component`).
  It is kept with its review comments at `.claude/.archived_plans/change-subassembly-content-v1-reviewed.md`.
- This version has two general claim types, insert and delete, that act on a component or on a sub-assembly. The
  review's recommendations are integrated where they still apply.

Numbers are from the demo starting log (578 claims: 432 by a rule, 146 by the agent). Two experiments back them:

| Cited as | Script | Raw output |
|---|---|---|
| R-Q1 to R-Q5 (the review) | `.experiments/content_change_plan_check.py` | `.experiments/output/content_change_plan_check.txt` |
| Q1 to Q5 (this revision) | `.experiments/insert_delete_plan_check.py` | `.experiments/output/insert_delete_plan_check.txt` |

## What this plan adds

Today the database says which sub-assemblies could be shared (`verdict` = `reusable`) and stops there. A person
who answers "then reuse it" has nothing to record: all 15 claim types state what the raw files mean, none states
a decision to build something else than what the BOM lists.

The BOM file has four levels. The claims act on the last two:

| Level | What it is | Lines after the build | Distinct references |
|---|---|---|---|
| 1 | the train variant, `V1` to `V6` | none: it is the `variant_id` column | 6 |
| 2 | a system: `INTR-SYS-01` Interior | 42 (7 per variant) | 7 |
| 3 | a sub-assembly: `DD-2037` door drive | 240 | 76 |
| 4 | a component: `MT-745` motor | 1226 | 298 |

A "line" is one parent-child link in one variant, as the build keeps it (table `bom_line`), with the raw rows of
the BOM file it comes from.

This plan adds two claim types that only a person can make:

1. `insert_part`: in one variant, a parent holds a child it did not hold, in a given quantity.
2. `delete_part`: in one variant, a parent no longer holds a child.

The parent is a sub-assembly and the child a component, or the parent is a system and the child a sub-assembly.
Replacing is a delete and an insert. Changing a quantity by decision is a delete and an insert of the same
child.

The build applies these claims to the lines it compares, so verdicts, costs and obsolete parts follow. The raw
files are not edited. A line a person inserted has no raw row behind it; the database shows the claim it comes
from instead.

Not changed: the raw files, the 15 existing claim types, how designs are compared (`pipeline/compare.py`), how a
verdict is decided (`pipeline/verdict.py`), which claims override each other (`statuses` in
`pipeline/claims.py`), the answer key and its test (the demo starting log holds no person's claim).

Not included:

- Inserting or deleting a system. All six variants list the same seven systems, so nothing at that level is
  "reusable but not reused", and the build has no verdict or cost per system.
- One claim that covers several variants. A sub-assembly listed in four variants takes four claims.
- Changing a component of a sub-assembly that a claim inserted. A component claim points at the BOM row that
  lists the sub-assembly, and an inserted sub-assembly has none.
- A third verdict column giving the verdict before the changes.
- The agent making, proposing or confirming one of these claims. The log refuses one that is not a person's.

## Target: the two claim types

The subject is the BOM row that lists the parent in the variant. One row names one parent in one variant: no
level-2 or level-3 line is folded from more than one raw row (Q2: 0 of 42, 0 of 240).

| Field | `insert_part` | `delete_part` |
|---|---|---|
| `subject` | `bom:<row>`: a level-3 row (a sub-assembly, to act on a component) or a level-2 row (a system, to act on a sub-assembly) | the same |
| `object`, subject at level 3 | `ref:<component>` | `ref:<component>` |
| `object`, subject at level 2 | `bom:<row>`: the level-3 row of the sub-assembly to copy, in the variant to copy it from. Its reference and its components are taken from there | `ref:<sub-assembly>` |
| `value` | a positive quantity and a unit: `1 pcs`, `0.9 m`; for a sub-assembly, the number per train: `20 pcs`. Required | none |
| `made_by` | `person`. Any other is refused | the same |
| `quote` | empty. A quote is refused; the note goes in `evidence` | the same |
| `evidence` | the BOM rows concerned, and the note or rows that support it | the same |
| `reason` | the person's reason, in one sentence | the same |

### Example 1: replace a component

BOM row 536 lists the door drive `DD-2037` in `V3`. Its motor line is row 628, `MT-745`, 1 pcs. Note `TN-0470`
says `MT-745` and `MT-701` are interchangeable. `DD-2010`, in `V1` and `V2`, has the same five other lines and
`MT-701`. The person says: use `MT-701` in `V3`. Two lines are appended to `data/claims.jsonl`:

```
{"id": 579, "type": "delete_part", "subject": "bom:536", "object": "ref:MT-745", "value": "",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:628", "note:TN-0470"],
 "quote": "", "reason": "Use the V1 and V2 door drive in V3: MT-701 in place of MT-745.", "as_of": ""}
{"id": 580, "type": "insert_part", "subject": "bom:536", "object": "ref:MT-701", "value": "1 pcs",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:118", "note:TN-0470"],
 "quote": "", "reason": "Use the V1 and V2 door drive in V3: MT-701 in place of MT-745.", "as_of": ""}
```

### Example 2: replace a sub-assembly

BOM row 1286 lists the system `INTR-SYS-01` in `V6`. Under it, row 1319 lists `GP-8805`, 20 per train, 5
components. Its verdict is `reusable`, reason "a note says it does the same job as PW-4700". The two share no
component. `PW-4700` is listed in `V1`, `V2`, `V3` and `V5` (rows 39, 302, 553, 1066), with the same 5
components in each. The person says: use `PW-4700` in `V6`. Starting again from the demo log:

```
{"id": 579, "type": "delete_part", "subject": "bom:1286", "object": "ref:GP-8805", "value": "",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:1319"],
 "quote": "", "reason": "Use PW-4700 in V6 as in V1, V2, V3 and V5.", "as_of": ""}
{"id": 580, "type": "insert_part", "subject": "bom:1286", "object": "bom:39", "value": "20 pcs",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:39", "bom:1319"],
 "quote": "", "reason": "Use PW-4700 in V6 as in V1, V2, V3 and V5.", "as_of": ""}
```

### Example 3: change a quantity by decision

The seat frame `SF-9064` in `V5` has 12 bolts `BL-482` where `SF-9020` in `V1`, `V2`, `V3` has 16. Two claims
with the level-3 row of `SF-9064` in `V5` as subject: `delete_part` of `ref:BL-482`, then `insert_part` of
`ref:BL-482` with value `16 pcs`.

`value_is` on a quantity cell stays what it is today: the file has the quantity wrong (rows 52 and 53 give 4 and
6, the other variants agree on 4). The agent can assert it and it counts as a correction. A person choosing
another quantity than the one the BOM rightly lists is a delete and an insert.

### Rules that go with the two types

- **Who.** Only a person's claim is accepted, and it is applied at once. The log itself refuses any other
  `made_by` (rule or agent, asserted or proposed), so no path that writes to the log can skip the check. Without
  this, the agent could propose a change and confirm its own proposal: `_guard` in `reconcile/tools.py` has no
  case for `confirm` (R-Q4).
- **No quote.** A decision is the person's, not the note's. A claim with a quote is left out of the replay that
  gives `verdict_bom_only`, and gets the note's date as `as_of`; refusing the quote gives one behaviour for every
  one of these claims and keeps `as_of` empty.
- **Insert and delete are strict.** An insert of a child the parent already holds is not applied; a delete of a
  child the parent does not hold is not applied. A claim never turns into another kind of change because of what
  the build finds.
- **Order.** The build applies the claims in force in order of id, each to the lines as the claims before it
  left them. An inserted sub-assembly takes the components its source holds at that moment.
- **A deleted sub-assembly** takes its component lines with it.
- **Undoing.** A `retract` of the claim, by a person. `pipeline.reset` removes them all, like every person's
  claim.
- **Deciding the same thing again.** A person's claim that was retracted can be made again and is written as a
  new claim. Today `ClaimLog.append` returns the old id for a claim with the same type, subject, object, value
  and maker whatever its status, so decide, undo, decide again writes nothing (R-Q5).
- **A claim that cannot be applied** is kept in the log and reported in `v_issue` as
  `content_change_not_applied`, with one of these reasons:

  | Case | Reason given |
  |---|---|
  | `insert_part` of a child the parent already holds | already there; delete it first to change its quantity |
  | `insert_part` of a sub-assembly the variant already lists, under any system | the variant already lists it. A variant never lists a sub-assembly twice today (Q2: 0), and the database identifies a sub-assembly by variant and part |
  | `insert_part` of a sub-assembly whose source was deleted by an earlier claim | the row to copy from is no longer in the BOM |
  | `insert_part` of a component: the reference is a sub-assembly or a system (76 and 7 references, R-Q3) | the reference is not a component |
  | `insert_part` of a component: the unit is not one the build converts | the unit cannot be converted |
  | `insert_part` of a component counted in another base unit on its other lines (`0.9 m` for a part listed in `pcs`). No component has two units today (Q2: 0 of 298) | the component is counted in another unit |
  | `delete_part` of a child the parent does not hold | not there |
  | `delete_part` of the only component left | a sub-assembly cannot be left with no component. Otherwise it gets "not comparable" as reason and has no row in `v_content` or `v_subassembly_cost` (R-Q2). The smallest sub-assembly has 3 components (Q2), so a replacement or a quantity change never meets this |

## Target: the database after example 1 (a component)

### `v_verdict`: one new column, `content_changes`

`content_changes` counts the claims of the two types applied to the sub-assembly in this variant, or in a
variant it shares its content with: inserts and deletes of its components, and the insert of the sub-assembly
itself. It sits next to `corrections` and is 0 on every row of the demo starting log.

| Row | Today | After claims 579 and 580 |
|---|---|---|
| `V3`, `DD-2037` | `verdict` = `reusable`, `verdict_bom_only` = `reusable`, `reason` = "differs from DD-2010 by 1 line(s): interchangeable", `shared_with` = `''`, `counterpart_ref` = `DD-2010` | `verdict` = `reused`, `verdict_bom_only` = `reused`, `reason` = "same content in V1, V2, V3 under references DD-2010, DD-2037", `shared_with` = `V1 V2`, `content_changes` = 2 |
| `V1`, `DD-2010` | `verdict` = `reused`, `verdict_bom_only` = `reused`, `reason` = "same content in V1, V2", `shared_with` = `V2` | `reason` = "same content in V1, V2, V3 under references DD-2010, DD-2037", `shared_with` = `V2 V3`, `content_changes` = 2 |
| `V2`, `DD-2010` | as `V1` | as `V1` |

Counts move from 222 reused, 15 reusable, 3 specific to 223, 14, 3 (R-Q2).

`verdict_bom_only` moves with `verdict`: these claims quote no note, so they are also applied in the replay that
leaves out the claims resting on a note. The column no longer means "the verdict the BOM alone gives" (the BOM
alone lists `MT-745`). It means: the verdict without any claim that rests on a note. When it differs from
`verdict`, a note changed the verdict; a person's insert or delete never makes the two differ.

### `v_evidence`: a new kind of row, `content change`

For `DD-2037` in `V3`, and for `DD-2010` in `V1` and `V2`, since they now share the content:

| kind | detail | claim_id | source_file | source_row |
|---|---|---|---|---|
| content change | V3: MT-745 deleted from DD-2037 (was 1 pcs) | 579 | plm_bom_export.csv | 628 |
| content change | V3: MT-701 inserted in DD-2037, 1 pcs | 580 | | |

### `v_content`: one new column, `changed_by_claim`

The view lists the content after the changes. `changed_by_claim` holds the id of the claim that inserted the
line, or that inserted the sub-assembly the line belongs to. It is empty on a line as the BOM lists it. A
deleted line is not in the view; it is in `content_change` and in `v_evidence`.

`DD-2037` in `V3`, the motor line:

| | component_ref | quantity | unit | unit_cost_eur | changed_by_claim |
|---|---|---|---|---|---|
| Today | `MT-745` | 1 | pcs | 879.16 | |
| After | `MT-701` | 1 | pcs | 419.72 | 580 |

The five other lines are unchanged.

### `v_subassembly_cost`: no new column, the cost follows the content

| Row | Today | After |
|---|---|---|
| `V3`, `DD-2037`, 32 per train | `unit_cost_eur` = 1295.74, `train_cost_eur` = 41463.68 | `unit_cost_eur` = 836.30, `train_cost_eur` = 26761.60 |

After claim 579 alone the unit cost is 416.58 (R-Q2).

## Target: the database after example 2 (a sub-assembly)

All values below are from Q3.

### `v_verdict`

| Row | Today | After claims 579 and 580 |
|---|---|---|
| `V6`, `GP-8805` | `verdict` = `reusable`, `reason` = "a note says it does the same job as PW-4700" | no row: `V6` no longer lists it |
| `V6`, `PW-4700` | no row | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V5, V6", `shared_with` = `V1 V2 V3 V5`, `content_changes` = 1 |
| `V1`, `PW-4700` (and `V2`, `V3`, `V5`) | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V5" | `reason` = "same content in V1, V2, V3, V5, V6", `shared_with` gains `V6`, `content_changes` = 1 |
| `V4`, `PW-4792` | `reusable`, "differs from PW-4700 by 1 line(s): unexplained" | unchanged |

Counts move from 222 / 15 / 3 to 223 / 14 / 3, designs from 74 to 73. After claim 579 alone: 222 / 14 / 3, 239
sub-assembly rows, no new issue.

The deletion of `GP-8805` is not counted in `content_changes` of any row, because `v_verdict` has no row left
for it. It is in `content_change`.

### `v_evidence`, for `PW-4700` in the five variants

| kind | detail | claim_id | source_file | source_row |
|---|---|---|---|---|
| content change | V6: PW-4700 inserted in INTR-SYS-01, 20 per train, 5 components copied from V1 (BOM row 39) | 580 | | |

The existing row of kind `bom row` ("V6: PW-4700, 5 lines") has an empty `source_row` for `V6`.

### `v_content` and `v_subassembly_cost`

`PW-4700` in `V6` has the 5 component lines of `V1`, each with `changed_by_claim` = 580.

| Row | Today | After |
|---|---|---|
| `V6`, `GP-8805`, 20 per train | `unit_cost_eur` = 723.19, `train_cost_eur` = 14463.72 | no row |
| `V6`, `PW-4700`, 20 per train | no row | `unit_cost_eur` empty, `blocked_by` = `PF-253`, 5 lines |

The cost becomes empty: one component of `PW-4700`, `PF-253`, has no agreed price, in `V6` as in the four other
variants. The tool's reply and the SKILL section say so before the person decides.

### `occurrence`

The row of `PW-4700` in `V6` has `raw_rows` = `''`. Every other row is as today.

## Target: the new table and the views that follow

### `content_change`: a new table, one row per claim applied

The table is the only place where the claim on a line is stored. `v_content` and `v_evidence` read it; the lines
in memory and the `bom_line` table get no new field. It stores part ids, as `occurrence` and `bom_line` do. A new
view, `v_content_change`, gives the same rows with references and the sentence shown in `v_evidence`.

| Column | Example 1, claim 579 | Example 1, claim 580 | Example 2, claim 579 | Example 2, claim 580 |
|---|---|---|---|---|
| `claim_id` | 579 | 580 | 579 | 580 |
| `variant_id` | `V3` | `V3` | `V6` | `V6` |
| `level` | 4 | 4 | 3 | 3 |
| `parent_part_id` | part id of `DD-2037` | the same | part id of `INTR-SYS-01` | the same |
| `child_part_id` | part id of `MT-745` | part id of `MT-701` | part id of `GP-8805` | part id of `PW-4700` |
| `change` | `deleted` | `inserted` | `deleted` | `inserted` |
| `quantity` | 1 | 1 | 20 | 20 |
| `unit` | `pcs` | `pcs` | `pcs` | `pcs` |
| `raw_rows`: the rows of a deleted line | 628 | empty | 1319 | empty |
| `n_components`: for a sub-assembly, the components deleted or copied | empty | empty | 5 | 5 |
| `copied_from_row` | empty | empty | empty | 39 |

`v_content_change` has `claim_id`, `variant_id`, `level`, `parent_ref`, `child_ref`, the last six columns as they
are, and `detail`:

| Claim | `detail` |
|---|---|
| example 1, 579 | V3: MT-745 deleted from DD-2037 (was 1 pcs) |
| example 1, 580 | V3: MT-701 inserted in DD-2037, 1 pcs |
| example 2, 579 | V6: GP-8805 deleted from INTR-SYS-01 (was 20 per train, 5 components) |
| example 2, 580 | V6: PW-4700 inserted in INTR-SYS-01, 20 per train, 5 components copied from V1 (BOM row 39) |

### `obsolete_parts` follows

`SN-573`, superseded by `SN-598`, is held by `KP-0457` in `V1` and `DC-3001` in `V2`, `V3`, `V4` (rows 125, 384,
635, 890, 2 pcs each). `DC-3020` in `V5` and `V6` has `SN-598`. Deleting `SN-573` and inserting `SN-598` in the
four variants (eight claims) gives (Q5):

- `obsolete_parts` empty for `DC-3001` in `V2`, `V3`, `V4`;
- the same content in the six variants, under references `DC-3001`, `DC-3020`, `KP-0457`;
- `KP-0457` in `V1` still has "own reference KP-0457, superseded by DC-3001", and its `action` in
  `v_tender_start` stays `replace`. The earlier version of this plan said it moves to `reuse`; it does not.
  Putting `DC-3001` in `V1` in place of `KP-0457` is a sub-assembly delete and insert. That step was not run.

### Other views that follow, with nothing to build

`v_purchasing.total_quantity`, `v_reuse_between` and `v_tender_start` are worked out from the lines and the
verdicts, so they move too. In example 2 the `PW-4700` row of `v_tender_start` keeps `action` = `reuse` and its
reason gains `V6` (Q3).

## Stages

The work follows the path of a claim: it is checked and written, applied by the build, written to the database,
then offered to the agent and shown in the app. Each stage ends with its tests passing.

### Stage 1. The two claim types and their checks

`pipeline/claims.py` — the list of claim types and the checks a claim passes before it is written.

- `TYPES` gets `insert_part`: `Shape(("bom",), ("ref", "bom"), value=True, says="in this variant, this parent
  holds this quantity of this child")` and `delete_part`: `Shape(("bom",), ("ref",), says="in this variant, this
  parent no longer holds this child")`.
- A new constant `CONTENT_CHANGES = {"insert_part", "delete_part"}`.
- `ClaimLog._checked(claim) -> dict` refuses, for these two types:
  - a `made_by` other than `person` ("changing what a variant is built from is a design decision: only a person
    can record it");
  - a claim with a `quote` ("put the note in evidence; this is the person's decision");
  - a subject row that is not a level-2 or level-3 row ("row 628 is a component line; point at the row that
    lists its parent in the variant");
  - for `insert_part` with a level-3 subject, an object that is not `ref:`; with a level-2 subject, an object
    that is not `bom:` of a level-3 row ("to insert a sub-assembly, point at the row that lists it in the
    variant to copy it from");
  - for `insert_part`, a value that is not a positive number followed by a unit. Whether the unit converts is
    not checked here: conversions come from the claims (`converts_to`), so the build decides, with `m.to_base`.
- `ClaimLog.append(claim) -> int` changes which earlier claim counts as "already in the log":
  - a rule's or the agent's claim: any claim with the same type, subject, object, value and maker, whatever its
    status. As today. This is what stops a re-run of the rules from writing again a claim a person retracted.
  - a person's claim: only such a claim that is in force (one call to `statuses(self.claims)`).
  - a person's claim of the two new types: only such a claim that is in force and has no later claim in force of
    the two types on the same `subject`. Needed because no claim overrides another: after delete A, insert A at
    16, the first claim is still in force, and a second "delete A" has to be written to apply.
- `statuses(claims)` is not changed. The build applies the claims in order of id and finds each line by resolved
  part, so two spellings of one component (15 are written in more than one, R-Q3) name the same line.

`tests/test_claims.py` — new cases:

- each refusal above, including an agent's claim with `standing` = `proposed` and a rule's claim;
- a person's claim, its `retract`, the same claim again: three lines in the log, the third in force;
- delete A, insert A at 16, delete A, insert A at 16 on the same subject: four lines in the log;
- the same person's claim twice in a row: one line, the old id returned;
- a rule's claim, a person's `retract` of it, the rule's claim again: nothing written, as today.

### Stage 2. The build applies them

`pipeline/resolve.py` — steps 3 and 4 of the build, from raw rows and claims to parts, lines and prices.

- New function `change_content(m: Model) -> None`, called by `resolve()` after `fold_bom(m)` and before
  `price_parts(m)`. The place matters: `missing_price` and `note_contradicts_bom` both read
  `m.used_components()`, so they follow the changed lines with no edit.
  It goes through `m.by_type["insert_part"] + m.by_type["delete_part"]` sorted by id. For each claim it reads
  the variant, the parent part and the level of the child (the subject row's level plus one) from the subject
  row, the child part from the object (for a sub-assembly insert, from the source row), and:
  - checks the cases of the "cannot be applied" table. In any of them: `m.issue("content_change_not_applied",
    ...)`, the reason kept in `m.not_applied[claim id]`, and nothing else;
  - insert of a component: converts the value with `m.to_base` and appends a level-4 line with `rows` = `[]`;
  - insert of a sub-assembly: appends a level-3 line with `rows` = `[]` and the value as quantity, and a copy of
    each level-4 line the source holds at that moment, with the new variant and `rows` = `[]`;
  - delete of a component: removes the level-4 line;
  - delete of a sub-assembly: removes the level-3 line and the level-4 lines under it in that variant;
  - appends one dict to `m.content_changes`: the columns of the `content_change` table, plus `detail`, the
    sentence of the `v_content_change` target, written here once with `m.name`.
- `fold_bom` is not changed.

`pipeline/model.py` — the model in memory. `Model` gets `content_changes: list[dict]` and
`not_applied: dict[int, str]`.

`pipeline/build.py` — the build.

- `build()` matches a sub-assembly between the two replays by `(variant, part)` in place of
  `(variant, min(raw_rows))` (lines 98 and 100). With an inserted sub-assembly the present key fails: "min()
  iterable argument is empty" (Q4).
- `compare_and_decide` is not changed: it makes one `Occurrence` per level-3 line, so an inserted sub-assembly
  gets one with `raw_rows` = `[]`.

Nothing changes in `compare.py` or `verdict.py`: they read the lines and the occurrences.

`tests/test_build.py` — on the tiny fixture already used there:

- replacing a component makes two designs one and moves the verdict to `reused`; the cost follows;
- a delete and an insert of the same component at another quantity does the same;
- replacing a sub-assembly by a copy of another variant's: the old one has no row, the new one is `reused` with
  the source, its components are those of the source;
- a sub-assembly inserted after a claim changed its source takes the changed content;
- deleting the only obsolete component empties `obsolete_parts`;
- each "cannot be applied" case gives the issue and changes nothing;
- a delete written under another spelling of the component finds the line;
- the same build without the claims is unchanged.

`tests/test_answer_key.py` — three new tests on the generated files, each on a copy of the log, next to the
answer key test, which stays untouched. A build takes 0.10 s.

- example 1: `reused` and `verdict_bom_only` = `reused` for the door drive in `V1`, `V2`, `V3`; counts
  223 / 14 / 3; unit cost 836.30;
- example 2: no row for `GP-8805`; `PW-4700` in `V6` `reused` with `shared_with` = `V1 V2 V3 V5`; counts
  223 / 14 / 3; 73 designs; cost empty and blocked by `PF-253`;
- the eight `SN-573` claims: `obsolete_parts` empty for `DC-3001` in `V2`, `V3`, `V4`.

### Stage 3. The database shows them

`pipeline/tables.py` — one entry per stored table.

- New `Table("content_change", "one insert or delete a person made in the BOM of one variant", ...)` with the
  columns of the target, from `m.content_changes`. `detail` is not stored in it.
- `VIEW_ABOUT`: an entry for `v_content_change`; the descriptions of `v_verdict`, `v_content` and `v_evidence`
  mention the new column or kind.

`pipeline/views.sql` — the views.

- New `v_content_change`: `content_change` joined to `part` twice, for the two references, with `detail`.
- `v_content` adds `changed_by_claim`: the highest `claim_id` in `content_change` with `change` = `inserted`, in
  the same variant, for this component under this sub-assembly or for this sub-assembly itself. A subquery, not
  a join, so that two claims on one line do not give two rows.
- `v_verdict` adds `content_changes`, counted from `evidence` like `corrections`. The comment above the view
  rewords `verdict_bom_only` as in the target.

`pipeline/reports.py` — tables worked out from the finished model.

- `evidence(m)` adds, per design and per occurrence, one row of kind `content change` for each entry of
  `m.content_changes` that is a component change under that sub-assembly in that variant, or the insert of that
  sub-assembly in that variant, with its `detail`.
- The row of kind `bom row` (line 207) takes `source_row` from `min(occurrence.raw_rows)` only when there is
  one; otherwise it is empty. This is the second failure of Q4.

`tests/test_build.py` — the target tables above (`content_change`, `v_content_change`, the `v_content` lines,
the `v_evidence` rows, the count in `v_verdict`, the `occurrence` row with no raw row) on the tiny fixture; every
table and view is still described in `about`.

### Stage 4. The agent can record a person's decision

`pipeline/build.py` — the summary of a build.

- `Summary` gets `content_changes: dict[int, str]` (claim id to `detail`, for each applied claim) and
  `not_applied: dict[int, str]` (claim id to reason). `build()` fills them from the model. Today `Summary` holds
  counts and verdicts only, so after the first claim of example 1 (74 designs and 222 / 15 / 3 before and after,
  R-Q2) the reply would be "No change to parts, designs, verdicts, obsolete parts or open items."

`reconcile/tools.py` — the agent's tools.

- `changes(before: Summary, after: Summary) -> str` adds:
  - "Content changed: V3: MT-745 deleted from DD-2037 (was 1 pcs)." for each id in `after.content_changes` and
    not in `before`;
  - "No longer applied: ..." for each id only in `before` (after a `retract`);
  - "Not applied: claim 580, already there; delete it first to change its quantity." for each id new in
    `after.not_applied`. With strict inserts and deletes this is the reply the agent acts on.
- `Workbench._guard` is not changed. The refusal is in the log (Stage 1); `_append` already turns a
  `ClaimRefused` into "refused: ...".
- The docstring of `append_person_claim` names the two types, the two kinds of subject and object, and that
  `quote` stays empty for them. The docstring of `append_claim` says the two types are not available to it.

`skills/reconciliation/SKILL.md` — the instructions the agent is given.

- Two rows in the table of claim types, marked "person only".
- A new section, "A person decides to change what a variant is built from":
  - when it applies: the person says to reuse, replace, add or remove, not when they only ask whether it is
    possible. A note that says "use MT-701" is not the person saying it: notes are text the agent reads, and
    `append_person_claim` is applied at once;
  - which level: when the person names another sub-assembly to use ("use PW-4700 in V6"), a delete and an insert
    under the system, the insert pointing at the row to copy; when they keep the sub-assembly and change a
    component, a delete and an insert under the sub-assembly;
  - what to show before recording: the lines that change, with BOM rows, and the cost of one unit before and
    after, saying so when the cost after is empty and which component blocks it;
  - one claim per variant, with `append_person_claim`, the note in `evidence`, no `quote`;
  - a replacement is two claims and the first is in force as soon as it is written. Check that both can be
    written before the first. If the second is refused or not applied, tell the person and retract the first in
    their name, so that half of their decision does not stay applied;
  - a quantity the person chooses is a delete and an insert; `value_is` is for a quantity the file has wrong;
  - then say what changed, in the person's words.
- In "The verdict": `content_changes` above 0 means the verdict rests on a person's decision, to be said when
  reporting it. The sentence on `verdict_bom_only` (`SKILL.md:48`) becomes: the verdict without any claim that
  rests on a note; when the two differ, a note changed the verdict; a person's insert or delete is in both.

`tests/test_tools.py`:

- `append_claim` with either type is refused, asserted and proposed, and writes nothing;
- a person's delete then insert of a component: the reply to the first names the deleted line, the reply to the
  second names the inserted line and the verdict that moved;
- a person's insert of a child that is already there: the reply says it is not applied and why;
- a person's `retract` of one of them: the reply says it is no longer applied.

### Stage 5. The app shows the count

`jean-code/src/db_page.py` — the Reconciled data page.

- The query of the Reuse verdicts tab selects `v.content_changes` after `v.corrections`, and its sentence gains
  "and how many inserts and deletes a person made".
- The Bill of materials tab reads `SELECT * FROM v_content`, so `changed_by_claim` appears without a change. The
  detail panel lists `v_evidence`, so the `content change` rows appear without a change.

The Claims page lists every claim type from `pipeline.claims.TYPES` and prints the raw rows a claim points at; a
`bom:` subject is already handled (as for `duplicate_of`). A `bom:` object is new: to check by opening the page
once an insert of a sub-assembly exists.

`tests/test_app.py` — the pages still render with a log that holds the four claims of examples 1 and 2.

## Checks at the end

- `uv run pytest`: all tests, including the answer key test, which must be untouched, and the three new tests on
  the generated files, which cover the target numbers.
- By hand, in the app, once: ask about `GP-8805`, answer "use PW-4700 in V6", and look at the Reuse verdicts
  tab, the Bill of materials tab and the Claims page. Undo it in the conversation, then decide it again. Then
  `uv run python -m pipeline.reset` and check the rows are back to today's values.

## Choices made here, to change if wrong

- **Two types for both levels.** A third type, "replace this sub-assembly by that one", would be one claim per
  decision and one type more. A delete and an insert say the same and also cover adding or removing alone.
- **Strict insert, no quantity type.** An insert of a child that is there is not applied. JSON Patch (RFC 6902)
  keeps `add` and `remove` strict for the same reason: a claim does what its type says or fails. A quantity
  change by decision costs two claims; `value_is` stays for an error in the file.
- **An inserted sub-assembly points at the row to copy.** The alternative is to point at its reference and take
  the content it has elsewhere. No reference has two contents today (Q2: 0 of 76), so both give the same result;
  the row leaves nothing to resolve if that changes, and it is cited in the evidence.
- **Per variant.** One claim changes one variant, because a BOM row is in one variant.
- **A replacement is two claims.** Between the two, the database is rebuilt once with the child deleted and not
  yet replaced. That state is what the tool's reply to the first claim describes, and what stays if the second
  fails; the SKILL section of Stage 4 covers it.
- **Only a person, no proposal.** The agent cannot leave a suggested insert or delete in the queue for a person
  to confirm later. Nothing in this plan reads such a proposal.
- **The raw files stay as they are.** Odoo's engineering change orders edit a draft revision of the BOM that
  replaces the live one when approved, and ERPNext's BOM Update Tool replaces one BOM by another everywhere in
  one action. Replaying claims over untouched files keeps every decision reversible, which fits a claim log.
