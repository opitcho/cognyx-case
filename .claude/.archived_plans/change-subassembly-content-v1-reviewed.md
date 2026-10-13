# Let a person change the content of a sub-assembly: add, remove or replace a component

Written 2026-10-13 against commit `d368046` (branch `simplify-verdict-and-tables`), with the demo starting log of
the same day (578 claims: 432 by a rule, 146 by the agent).

> @Claude: **Overall.** The design is sound and small: apply the claims to `m.lines` after `fold_bom`, leave
> `compare.py` and `verdict.py` alone. A 15-line prototype of that reproduces every target number below (223 / 14 /
> 3, the reason text, 836.30 and 26761.60). The cited rows, costs and counts all still hold on `main` at `0e293c6`.
> What needs fixing is around the edges: who can put a claim in force, what happens on undo and redo, and what the
> agent is told. Size, as an estimate: about 150 lines of code and 120 of tests as written; the changes below
> remove more than they add.
>
> Checks are in `.experiments/content_change_plan_check.py`, raw output in
> `.experiments/output/content_change_plan_check.txt` (sections Q1 to Q5, cited below).
>
> Changes, most important first:
>
> 1. **The agent can put a content change in force alone**, by proposing it and confirming its own proposal. See
>    the comment under "Rules that go with the two types".
> 2. **A decision made, undone and made again is dropped without a word.** Same place.
> 3. **The tool tells the agent "No change" after the first claim of the plan's own example.** See Stage 4.
> 4. **Overriding is decided on the written text, applying on the resolved part**, so they disagree for 15
>    components. See Stage 1.
> 5. **`verdict_bom_only` changes meaning**, and differently depending on whether the claim carries a quote. See
>    the comment under the `v_verdict` target.

## What this plan adds

Today the database says which sub-assemblies could be shared (`verdict` = `reusable`) and stops there. A person
who answers "then reuse it" has nothing to record: all 15 claim types state what the raw files mean, none states
a decision to build something else than what the BOM lists.

This plan adds two claim types that only a person can put in force:

1. `set_component`: in one variant, a sub-assembly holds a given quantity of a component. The line is added if
   the sub-assembly does not have that component, otherwise its quantity is replaced.
2. `remove_component`: in one variant, a sub-assembly no longer holds a component.

Replacing one component by another is the two together: one `remove_component` and one `set_component`.

The build applies these claims to the content it compares, so verdicts, costs and obsolete parts follow. The raw
files are not edited. The database shows which lines come from such a claim, so a verdict that rests on a
person's decision is not confused with one that rests on a corrected spelling.

Not changed: the raw files, the 15 existing claim types, how designs are compared (`pipeline/compare.py`), how a
verdict is decided (`pipeline/verdict.py`), the answer key and its test (the demo starting log holds no person's
claim, so it holds none of the new claims).

Not included:

- Adding a sub-assembly to a variant or removing one. Only the components of an existing sub-assembly change.
- One claim that covers several variants. A sub-assembly listed in four variants takes four claims.
- A third verdict column giving the verdict before the content changes. The new count column and the evidence
  rows show that a verdict rests on them.
- The agent proposing content changes by itself during a batch run.

## Target: the two claim types

Both point at the sub-assembly through the BOM row that lists it in the variant (the level-3 row), and at the
component through its reference.

| Field | `set_component` | `remove_component` |
|---|---|---|
| `subject` | `bom:<row>`, a level-3 row: one sub-assembly in one variant | the same |
| `object` | `ref:<component>`, a reference written somewhere in the raw files | the same |
| `value` | quantity and unit, as the BOM writes them: `1 pcs`, `0.9 m`. Required | none |
| `standing` | `asserted` when `made_by` is `person`; an agent's can only be `proposed` | the same |
| `evidence` | the BOM rows of the lines concerned, and the note or rows that support it | the same |
| `reason` | the person's reason, in one sentence | the same |

Example on real rows. BOM row 536 lists the door drive `DD-2037` in `V3`. Its motor line is row 628, `MT-745`,
1 pcs. Note `TN-0470` says `MT-745` and `MT-701` are interchangeable. `DD-2010`, in `V1` and `V2`, has the same
five other lines and `MT-701`. The person says: use `MT-701` in `V3`. Two lines are appended to
`data/claims.jsonl`:

```
{"id": 579, "type": "remove_component", "subject": "bom:536", "object": "ref:MT-745", "value": "",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:628", "note:TN-0470"],
 "quote": "", "reason": "Use the V1 and V2 door drive in V3: MT-701 in place of MT-745.", "as_of": ""}
{"id": 580, "type": "set_component", "subject": "bom:536", "object": "ref:MT-701", "value": "1 pcs",
 "standing": "asserted", "made_by": "person", "maker": "Oscar", "evidence": ["bom:118", "note:TN-0470"],
 "quote": "", "reason": "Use the V1 and V2 door drive in V3: MT-701 in place of MT-745.", "as_of": ""}
```

A quantity change is one `set_component`. Example: the seat frame `SF-9064` in `V5` has 12 bolts `BL-482` where
`SF-9020` in `V1`, `V2`, `V3` has 16. `set_component`, subject the level-3 row of `SF-9064` in `V5`, object
`ref:BL-482`, value `16 pcs`.

Rules that go with the two types:

- **Who.** A person's claim is applied at once. The agent cannot assert one: the tool refuses and tells it to ask
  the person or to propose. A proposed one is applied when a person confirms it, as for every proposed claim.
- **Two claims on the same line.** When several claims in force name the same `subject` and `object`, the last
  one applies and the others are marked `overridden` in `claim_status`, with the same rule as for two values of
  one cell (a person's over an agent's, then the later id).
- **Undoing.** A `retract` of the claim, by a person. `pipeline.reset` removes them all, like every person's
  claim.
- **A claim that cannot be applied** is kept in the log and reported in `v_issue` as
  `content_change_not_applied`, with the reason: the component to remove is not in the sub-assembly, or the unit
  of the quantity cannot be converted.

> @Claude: **Most important: "Who" is not enforced by what the plan builds.**
>
> - Fact: an agent's `confirm` of its own proposed claim is accepted. Q4 of the experiment, with `value_is`
>   standing in: "claim 579 recorded as proposed. It is not applied until a person confirms it.", then the agent's
>   `confirm` gives "claim 580 recorded and in force", status "confirmed by claim 580", `made_by` = `agent`.
>   `_guard` (`reconcile/tools.py:171`) has no case for `confirm`, and `SKILL.md:128` tells the agent to append
>   `confirm` itself on near pairs.
> - Fact: the plan puts the refusal of `rule` in `ClaimLog._checked` and the refusal of an asserting agent in
>   `Workbench._guard`. Anything that writes through `ClaimLog` directly (`reconcile/batch.py`, a test, a script)
>   skips the second.
> - Recommendation: in `_checked`, refuse the two types unless `made_by` is `person`. One rule in one place.
> - This removes: the `_guard` branch of Stage 4, the "proposed, it is written and not applied" test, the
>   `standing` row of the target table, and "a person's over an agent's" in the next rule (every claim in force is
>   a person's).
> - Cost: the agent cannot leave a suggested change in the queue for later. The plan already lists that as not
>   included, and nothing in it reads such a proposal.

> @Claude: **Undoing, then deciding the same thing again, writes nothing.** `ClaimLog.append`
> (`pipeline/claims.py:118`) returns the old id when a claim with the same type, subject, object, value and maker
> exists, whatever its status. Q5: a person's claim, its `retract`, then the same claim again gives "Nothing
> written: the same claim is already in the log as claim 579", and 579 stays "retracted by claim 580". The same
> happens for set 16, set 12, set 16: the third is "already in the log" and overridden. The demo's hand check
> (decide, undo) is one step away from this.
>
> Recommendation: for a person's claim, compare only with claims that are in force. Keep today's behaviour for
> rules, where it is what stops a re-run from re-applying a claim a person retracted. Add the three-step case to
> `tests/test_claims.py`. Cost: a `statuses()` call in `append`.

> @Claude: **Three states the "cannot be applied" rule should also cover**, each a one-line check in
> `change_content`:
>
> - Removing the last component. Q2: with every line of `DD-2037` in `V3` removed, the verdict is `specific` with
>   reason "not comparable: a line has no agreed quantity", and the sub-assembly has no row in `v_content` or
>   `v_subassembly_cost` (both use an inner join on its lines).
> - An object that is not a component. `ref:` accepts any written reference: 76 sub-assemblies and 7 systems (Q3),
>   including the sub-assembly itself.
> - A quantity whose base unit differs from the line it replaces (`0.9 m` on a `pcs` line). The cost is quantity
>   times a price per base unit, so the result is a number with nothing wrong on screen.
>
> Smaller: the write check accepts "a unit written in the BOM file", which today includes `U`, `PCE`, `ea` and
> `mm` (Q3). Accepting only what `m.to_base` converts is checked at build anyway; say which one is the rule.

## Target: the database after the two claims of the example

### `v_verdict`: one new column, `content_changes`

`content_changes` counts the claims of the two new types applied to the sub-assembly's content, or to that of a
variant it shares its content with. It sits next to `corrections` and is 0 on every row of the demo starting
log.

| Row | Today | After claims 579 and 580 |
|---|---|---|
| `V3`, `DD-2037` | `verdict` = `reusable`, `reason` = "differs from DD-2010 by 1 line(s): interchangeable", `shared_with` = `''`, `counterpart_ref` = `DD-2010` | `verdict` = `reused`, `reason` = "same content in V1, V2, V3 under references DD-2010, DD-2037", `shared_with` = `V1 V2`, `content_changes` = 2 |
| `V1`, `DD-2010` | `verdict` = `reused`, `reason` = "same content in V1, V2", `shared_with` = `V2` | `reason` = "same content in V1, V2, V3 under references DD-2010, DD-2037", `shared_with` = `V2 V3`, `content_changes` = 2 |
| `V2`, `DD-2010` | as `V1` | as `V1` |

Counts move from 222 reused, 15 reusable, 3 specific to 223, 14, 3.

> @Claude: **`verdict_bom_only` is missing from this table, and it moves.** Today it is `reusable` for `DD-2037`
> in `V3`. With the two claims as written (no quote) they are also applied in the replay without notes
> (`rests_on_note`, `pipeline/claims.py:86`), so it becomes `reused` (Q2). `SKILL.md:48` describes the column as
> "the verdict the BOM alone gives" and says "when the two differ, a note changed the verdict". The BOM alone
> lists `MT-745`.
>
> The same decision recorded with a `quote` from `TN-0470` is left out of that replay, so the column stays
> `reusable`, and the agent then reports that a note changed the verdict. `append_person_claim` offers `quote`.
>
> Recommendation: refuse a `quote` on the two types (the note goes in `evidence`, as in the example), so there is
> one behaviour, and add the column to this table with the sentence of `SKILL.md:48` reworded. Refusing the quote
> also keeps `as_of` empty, see Stage 1. Cost: none that I can see; a decision is the person's, not the note's.

> @Claude: Other views follow the content and are not named in the targets: `v_purchasing.total_quantity`,
> `v_reuse_between`, and `v_tender_start`, where the `DC-3001` example moves `action` from `replace` to `reuse`.
> Nothing to build. Worth one line in the plan and one assertion, since `v_tender_start` is the view a tender
> reads.

### `v_evidence`: a new kind of row, `content change`

For `DD-2037` in `V3`, and for `DD-2010` in `V1` and `V2`, since they now share the content:

| kind | detail | claim_id | source_file | source_row |
|---|---|---|---|---|
| content change | V3: MT-745 removed (was 1 pcs) | 579 | plm_bom_export.csv | 628 |
| content change | V3: MT-701 added, 1 pcs | 580 | | |

A quantity change reads "V5: BL-482 from 12 pcs to 16 pcs".

### `v_content`: one new column, `changed_by_claim`

The view lists the content after the changes. `changed_by_claim` holds the claim id on a line that a
`set_component` added or changed, and is empty on a line as the BOM lists it. A removed line is not in the view;
it is in `content_change` and in `v_evidence`.

`DD-2037` in `V3`, the motor line:

| | component_ref | quantity | unit | unit_cost_eur | changed_by_claim |
|---|---|---|---|---|---|
| Today | `MT-745` | 1 | pcs | 879.16 | |
| After | `MT-701` | 1 | pcs | 419.72 | 580 |

The five other lines are unchanged.

> @Claude: The claim on a line is recorded three times: `changed_by` on the line and `bom_line.claim_id`, the
> `content_change` row, and the `evidence` row. `v_content` can take `changed_by_claim` from a `LEFT JOIN
> content_change` on variant, sub-assembly and component. That removes `changed_by`, the edit to `fold_bom` and
> the `bom_line` column. It needs `content_change` to store part ids, as `occurrence` and `bom_line` do, with the
> references shown by a view; the target below stores references. Cost: one join.

### `v_subassembly_cost`: no new column, the cost follows the content

| Row | Today | After |
|---|---|---|
| `V3`, `DD-2037`, 32 per train | `unit_cost_eur` = 1295.74, `train_cost_eur` = 41463.68 | `unit_cost_eur` = 836.30, `train_cost_eur` = 26761.60 |

### `content_change`: a new table, one row per claim applied

| Column | Example (claim 579) | Example (claim 580) |
|---|---|---|
| `claim_id` | 579 | 580 |
| `variant_id` | `V3` | `V3` |
| `subassembly_ref` | `DD-2037` | `DD-2037` |
| `component_ref` | `MT-745` | `MT-701` |
| `change` | `removed` | `added` (or `quantity changed`) |
| `quantity_before` | 1 | empty |
| `quantity_after` | empty | 1 |
| `unit` | `pcs` | `pcs` |
| `raw_rows` | 628 | empty |

### `obsolete_parts` follows too

The same two claims are the way to act on an obsolete part. `DC-3001` / `KP-0457` in `V1` to `V4` hold `SN-573`,
superseded by `SN-598`; `DC-3020` in `V5` and `V6` has `SN-598`. Removing `SN-573` and setting `SN-598` in each
of the four variants (eight claims) empties `obsolete_parts` for the component on those rows and makes the
content identical in the six variants.

## Stages

The work follows the path of a claim: it is checked and written, applied by the build, written to the database,
then offered to the agent and shown in the app. Each stage ends with its tests passing.

### Stage 1. The two claim types and their checks

`pipeline/claims.py` — the list of claim types and the checks a claim passes before it is written.

- `TYPES` gets `set_component`: `Shape(("bom",), ("ref",), value=True, says="in this variant, this sub-assembly
  holds this quantity of this component")` and `remove_component`: `Shape(("bom",), ("ref",), says="in this
  variant, this sub-assembly no longer holds this component")`.
- A new constant `CONTENT_CHANGES = {"set_component", "remove_component"}`.
- `ClaimLog._checked(claim) -> dict` refuses, for these two types: a subject row that is not a level-3 row ("row
  628 is a component line; point at the row that lists the sub-assembly in the variant"); for `set_component`, a
  value that is not a positive number followed by a unit written in the BOM file; a claim with `made_by` =
  `rule`.
- `statuses(claims) -> dict[int, Status]` gets a third group of claims that can override each other: the claims
  in force of the two types with the same `subject` and `object`. The winner is chosen by the rule already used
  for two values of one cell.

`tests/test_claims.py` — new cases: each refusal above; a `remove_component` after a `set_component` on the same
line marks the first `overridden`; a retracted one is not in force.

> @Claude: **The third group in `statuses` and `change_content` identify a line differently.**
>
> - Fact: `statuses` sees only the claims, so "same `subject` and `object`" compares text. `change_content` finds
>   the line by resolved part. 15 BOM components are written in more than one spelling (Q3: `PC 4983` and
>   `PC-4983`, `BE-628` and `BE-6281`). A `set_component` on `ref:PC 4983` and a later one on `ref:PC-4983` are the
>   same line, are not grouped, and both show as in force.
> - Fact: the existing rule is not "a person's over an agent's, then the later id". It first takes the later
>   `as_of` when every claim of the group has one (`pipeline/claims.py:274`), and `_append` sets `as_of` to the
>   note's date on a claim that quotes a note (`reconcile/tools.py:154`). An earlier decision quoting a newer note
>   would beat a later decision.
> - Fact: Stage 2 already applies the claims in order of id, so the later claim on a line wins there without any
>   grouping, on the right identity.
> - Recommendation: drop the third group. Let `change_content` apply in id order and write one `content_change`
>   row per claim, so on a line the BOM lists at 12, set 14 then set 16 reads "from 12 pcs to 14 pcs", then "from 14 pcs to 16 pcs".
> - This removes: the `statuses` change, its test, and the two rules about ties.
> - Cost: `claim_status` shows the earlier claim as in force, not `overridden`, and `content_changes` counts
>   both. If that matters on the Claims page, keep the group but say in the plan that it misses spellings.
>
> Good as it is: the level-3 row as subject. No level-3 line is folded from more than one row (Q3: 0 of 240), so
> one row is one sub-assembly in one variant.

### Stage 2. The build applies them

`pipeline/resolve.py` — steps 3 and 4 of the build, from raw rows and claims to parts, lines and prices.

- New function `change_content(m: Model) -> None`, called by `resolve()` after `fold_bom(m)` and before
  `price_parts(m)`, so that an added component counts as used when prices and missing prices are worked out.
  It goes through `m.by_type["set_component"] + m.by_type["remove_component"]` in order of id. For each claim it
  finds the variant and the sub-assembly part from the subject row, the component part from the object, and:
  - `set_component`: converts the value with `m.to_base`; replaces the quantity of the level-4 line if there is
    one, otherwise appends a line with `rows` = `[]`. Sets `changed_by` = claim id on the line.
  - `remove_component`: deletes the level-4 line.
  - Appends one dict to `m.content_changes` (the columns of the `content_change` table above).
  - When the line to remove is missing or the unit does not convert: `m.issue("content_change_not_applied",
    ...)` and nothing else.
- `fold_bom` gives every line `changed_by` = `None`.

`pipeline/model.py` — the model in memory. `Model` gets `content_changes: list[dict]`.

Nothing changes in `pipeline/build.py`, `compare.py` or `verdict.py`: they read `m.lines`, which now holds the
changed content. One thing to check while doing it: a line with `rows` = `[]` must not break code that reads the
raw rows of a line (`tables.py` joins them, `reports.evidence` adds them up; neither takes a minimum).

`tests/test_build.py` — on the tiny fixture already used there: replacing a component makes two designs one and
moves the verdict to `reused`; a quantity change does the same; the cost follows; removing the only obsolete
component empties `obsolete_parts`; a removal of a component that is not there gives the issue and changes
nothing; the same build without the claims is unchanged.

> @Claude: Good as it is, worth protecting: the call between `fold_bom` and `price_parts`. `missing_price`
> (`pipeline/resolve.py:186`) and `note_contradicts_bom` (`pipeline/resolve.py:216`) both read
> `m.used_components()`, so they follow the changed content with no edit. The `rows` = `[]` check holds: the only
> `min()` over raw rows is on occurrences (`pipeline/build.py:98`, `pipeline/reports.py:207`), which are level 3.
>
> One case to decide: a `set_component` on a line whose quantity is empty because of `two_quantities` or
> `unknown_unit`. `fold_bom` has already raised the issue, so it stays in `v_issue` and `v_queue` after the line
> has a quantity. No such line exists today (Q3: 0). Cheapest: not applied, with "settle the quantity first".
>
> Add the plan's own example as a test on the generated files, next to the answer key test: the two claims on
> `bom:536` give `reused` in `V1`, `V2`, `V3` and 836.30. A build takes 0.10 s. This replaces most of the hand
> check at the end.

### Stage 3. The database shows them

`pipeline/tables.py` — one entry per stored table.

- New `Table("content_change", "one change a person made to the content of a sub-assembly in one variant", ...)`
  with the columns of the target, from `m.content_changes`.
- `bom_line` gets the column `claim_id INTEGER`, from `changed_by`.
- `VIEW_ABOUT`: the descriptions of `v_verdict`, `v_content` and `v_evidence` mention the new column or kind.

`pipeline/views.sql` — the views.

- `v_content` adds `l.claim_id AS changed_by_claim`.
- `v_verdict` adds `content_changes`, counted from `evidence` like `corrections`.

`pipeline/reports.py` — tables worked out from the finished model.

- `evidence(m)` adds, per design and per occurrence, one row of kind `content change` for each entry of
  `m.content_changes` on that variant and sub-assembly, with the wording of the target.

`tests/test_build.py` — the three target tables above (`content_change`, the `v_content` line, the `v_evidence`
rows and the count in `v_verdict`) on the tiny fixture; every table and view is still described in `about`.

### Stage 4. The agent can record a person's decision

`reconcile/tools.py` — the agent's tools.

- `Workbench._guard(claim, claims) -> str` returns, for an asserted claim of the two types made by the agent:
  "changing what a sub-assembly holds is a design decision." The existing text then tells it to ask the person
  or to propose.
- The docstrings of `append_claim` and `append_person_claim` name the two types and the `bom:<row>` subject.
- `changes(before, after)` already reports the verdicts and obsolete parts that moved. No change.

`skills/reconciliation/SKILL.md` — the instructions the agent is given.

- Two rows in the table of claim types.
- A new section, "A person decides to change a sub-assembly": when it applies (the person says to reuse, replace,
  add or remove, not when they only ask whether it is possible); what to show before recording (the lines that
  change, with BOM rows, and the cost of one unit before and after); one claim per variant and per component,
  with `append_person_claim`; then say what changed, in the person's words. The existing `value_is` on a
  quantity stays for a quantity the file has wrong.
- In "The verdict": `content_changes` above 0 means the verdict rests on a person's decision, to be said when
  reporting it.

`tests/test_tools.py` — the agent's asserted `set_component` is refused and writes nothing; proposed, it is
written and not applied; a person's is applied and the reply names the verdict that moved.

> @Claude: **"`changes(before, after)` ... No change" is wrong for this plan's own example.** `Summary`
> (`pipeline/build.py:68`) holds counts of parts and designs, verdicts, obsolete parts, issues and open items. It
> holds no content and no cost.
>
> - Q2, after claim 579 alone: 74 designs before and after, verdicts 222 / 15 / 3 before and after, unit cost
>   1295.74 to 416.58. The reply would be "claim 579 recorded and in force. No change to parts, designs, verdicts,
>   obsolete parts or open items."
> - Any quantity change that moves no verdict gets the same reply (Q5, reply 1).
> - An agent told "No change" after a person's decision will either report that nothing happened or try again.
>
> Recommendation: `Summary` carries the `detail` text of each applied content change, keyed by claim id, and
> `changes` prints the new ones ("V3: MT-745 removed (was 1 pcs)"). The text exists already for `evidence`. The
> test above then asserts the reply to each of the two claims, not only the second.

> @Claude: One line for the new SKILL section: a note that says "use MT-701" is not the person saying it. Notes
> are text the agent reads, and `append_person_claim` is applied at once.

### Stage 5. The app shows the count

`jean-code/src/db_page.py` — the Reconciled data page.

- The query of the Reuse verdicts tab selects `v.content_changes` after `v.corrections`, and its sentence gains
  "and how many changes a person made to the content".
- The Bill of materials tab reads `SELECT * FROM v_content`, so `changed_by_claim` appears without a change. The
  detail panel lists `v_evidence`, so the `content change` rows appear without a change.

The Claims page lists every claim type from `pipeline.claims.TYPES` and prints the raw rows a claim points at; a
`bom:` subject is already handled (as for `duplicate_of`). To check by opening the page once a claim exists.

`tests/test_app.py` — the page still renders with a log that holds the two claims.

## Checks at the end

- `uv run pytest`: all tests, including the answer key test, which must be untouched.
- By hand, in the app: ask about `DD-2037`, answer "use MT-701 in V3", and compare the Reuse verdicts tab, the
  Bill of materials tab and the Claims page with the target tables above. Then `uv run python -m pipeline.reset`
  and check the three rows are back to today's values.

## Choices made here, to change if wrong

- **Names.** `set_component` and `remove_component`. One type with a quantity of 0 for a removal would be one
  type fewer and harder to read in the log.
- **Per variant.** One claim changes one variant, because a BOM row is in one variant. Changing the four
  variants of `DC-3001` takes eight claims; the agent writes them, the person states the decision once.
- **A replacement is two claims.** Between the two, the database is rebuilt once with the component removed and
  not yet replaced. Nothing reads that state except the tool's reply to the agent.

> @Claude: On the last choice. The state between the two claims is also what stays if the second is refused (a
> mistyped value, a reference not in the raw files): the component is removed, in force, in the person's name,
> and the sub-assembly costs 416.58. The agent cannot retract a person's claim on its own (`_guard`,
> `reconcile/tools.py:191`). The SKILL section should say: check both claims can be written before the first, and
> if the second is refused, tell the person and retract the first in their name.
>
> On names. `set_component` adds or changes depending on what the build finds. JSON Patch (RFC 6902) keeps the
> two apart for a reason that applies here: `add` creates, `replace` and `remove` fail when the target is missing.
> If a `same_as` behind the line is later retracted, a quantity change turns into an addition with no error. The
> `change` column of `content_change` shows it (`added` where it was `quantity changed`). I would keep one type and
> rely on that column; say so here.
>
> For comparison, Odoo's engineering change orders edit a draft revision of the BOM that replaces the live one
> when approved, and ERPNext's BOM Update Tool replaces one BOM by another everywhere in one action. This plan's replay
> keeps the raw files untouched and every decision reversible, which is the better fit for a claim log.
