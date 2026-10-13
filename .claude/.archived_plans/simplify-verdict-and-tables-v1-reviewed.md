# Simplify the verdict, the duplicated tables and the replay options

Written 2026-10-13 against commit `a2bb935` (local `main`).

## What this plan changes

1. A test compares the build's verdicts with the answer key `data/truth/verdicts.csv`. It is added first.
2. The verdict of a sub-assembly says only whether its content is shared: `reused`, `reusable` or `specific`.
   Whether it holds an obsolete or superseded part moves to a separate column, `obsolete_parts`.
3. Five tables that are stored and then repeated by a view are stored once.
4. `build()` loses the two replay options `made_by` and `up_to`.
5. The `claim_effect` table and its view are removed.

Not changed: which claim wins a conflict (`statuses()`, `group()`, `_guard()`), `pipeline/compare.py`, the claim
checks in `pipeline/claims.py`, the two computations per build, the generator in `synth/` and its answer key.

> @Claude: **Overall: go ahead, after four corrections.** The split is right: it removes the case where `v_verdict`
> and `v_reuse_map` give two verdicts for one sub-assembly, and the list of obsolete parts is worked out in one place
> instead of three (`pipeline/verdict.py:31`, `pipeline/verdict.py:46`, `pipeline/reports.py:97`).
>
> Size, as an estimate: about 20 files touched; the pipeline code gets 30 to 50 lines shorter, the tests about 40
> lines longer.
>
> What I checked by running a build of the demo starting log
> (`.experiments/plan_review_simplify_verdict.py`, output in `.experiments/output/plan_review_simplify_verdict.txt`):
> the counts 197 / 15 / 25 / 3, the 25 holders (125 rows of `v_reuse_between` have `blocked_by` filled, 5 per
> sub-assembly), 568 claims in force, and one build taking 0.11 s.
>
> Changes, most important first:
>
> 1. **The example row for `KP-0457` is not what the plan's own definition gives**, and the text of `obsolete_parts`
>    does not say whether the obsolete part is the sub-assembly's own reference or a component. See the comment under
>    "Two real rows" and under `pipeline/verdict.py`.
> 2. **"Same rows as today" for `evidence()` is not true as written**, and today's rows already show an obsolete
>    claim on sub-assemblies that are not affected by it. See the comment under `pipeline/reports.py`.
> 3. **Stage 3 removes `v_claim_effect` while the app still reads it until stage 5.** See the comment under stage 3.
> 4. **The stage 2 rule of the answer-key test is true on this data only.** See the comment under stage 1.
> 5. `v_tender_start` says `replace` but no longer says which part. See the comment under "Other tables and views".
>
> Smaller points are under stage 3, stage 4 and the checks.

## Target: the database after the change

### `v_verdict`: one sub-assembly in one variant

| Column | Today | After |
|---|---|---|
| `variant_id`, `system_ref`, `subassembly_ref`, `description` | unchanged | unchanged |
| `verdict` | `reused`, `reusable`, `blocked` or `specific` | `reused`, `reusable` or `specific` |
| `verdict_bom_only` | the same four values | `reused`, `reusable` or `specific` |
| `reason` | for a blocked row: the part, then "(otherwise reused: ...)" | only why the content is or is not shared |
| `obsolete_parts` | does not exist | the sub-assembly's own reference and its components that a claim says are obsolete or superseded; empty when there are none |
| `counterpart_ref`, `design_id` | unchanged | unchanged |

Two real rows, today and after:

| Row | Today | After |
|---|---|---|
| `V1`, `KP-0457`, Door control unit | `verdict` = `blocked`, `reason` = "contains SN-573, superseded by SN-598 (otherwise reused: same content in V1, V2, V3, V4 under references DC-3001, KP-0457)" | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V4 under references DC-3001, KP-0457", `obsolete_parts` = "SN-573, superseded by SN-598" |
| `V1`, `SW-3510`, Side wall panel set | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V4, V5, V6" | the same, with `obsolete_parts` empty |

> @Claude: **Most important, with the `describe()` comment below. The "After" cell for `KP-0457` is incomplete.**
>
> Fact: the reference `KP-0457` is itself superseded. Claim 443, from note `TN-0127`: "KP-0457 door control unit
> superseded by DC-3001, same function. Use DC-3001 for all new orders, do not fit KP-0457 anymore." Today
> `v_reuse_between` already lists both for this row: `blocked_by` = "KP-0457, SN-573".
>
> The plan defines `obsolete_parts` as "the sub-assembly's own reference and its components", so the row will read
> "KP-0457, superseded by DC-3001; SN-573, superseded by SN-598", not "SN-573, superseded by SN-598".
>
> Today's `reason` hides the first half, because `occurrence_verdict()` only looks at the own reference when the
> design is not already blocked (`pipeline/verdict.py:47`). So this plan changes what a person reads for `KP-0457`
> in `V1`. That is an improvement, and it should be stated in the target section with the corrected row. The count
> of 25 does not change.

Counts on the demo starting log (`data/claims.demo_start.jsonl`):

| | Today (measured) | After (derived from the answer key, to be confirmed by the test) |
|---|---|---|
| `reused` | 197 | 222 |
| `reusable` | 15 | 15 |
| `specific` | 3 | 3 |
| `blocked` | 25 | not a verdict |
| rows with `obsolete_parts` filled | not stored | 25 |

`obsolete_parts` is filled for any sub-assembly that holds such a part, whatever its verdict. Today a `specific`
sub-assembly holding one is not marked. On the current data this changes nothing: all 25 holders are `reused` or
`reusable` on content.

### Other tables and views that change

| Object | Change |
|---|---|
| `occurrence` (table) | loses `verdict` and `reason`; gains `obsolete_parts`; keeps `verdict_bom_only` |
| `verdict` (table) | unchanged columns; it is now the only place a verdict is stored |
| `v_reuse_map` | unchanged. Its `verdict` column can no longer disagree with `v_verdict` (today `RG-0212` in `V1` is `blocked` in `v_verdict` and `reused` in `v_reuse_map`) |
| `v_tender_start` | `action` is `replace` when `obsolete_parts` is filled, otherwise `reuse`, `adapt` or `keep` from the verdict |
| `v_reuse_between` | column `blocked_by` renamed `obsolete_parts`. `blocked_by` keeps one meaning in the database: in `v_subassembly_cost`, the components with no agreed price |
| `v_queue`, `v_readiness`, `v_issue`, `v_reuse_between` | become stored tables with the same names and columns. The tables `queue`, `readiness`, `issue`, `reuse_between` and the four views over them are removed |
| `claim_effect`, `v_claim_effect` | removed |

The file goes from 39 objects (26 tables, 13 views) to 33 (25 tables, 8 views). The names the agent and the app
read stay the same, except `v_claim_effect`.

> @Claude: Three things missing from this table.
>
> 1. **`v_tender_start` needs the `obsolete_parts` column.** Its `reason` comes from `v_verdict`
>    (`pipeline/views.sql:102`). After the change, the row for `DR-1043` reads `action` = `replace`, `reason` = "same
>    content in V1, V2, V3, V4, V5, V6", and nothing names `AC-477`. The skill file sends the agent to this view for
>    the tender question (`skills/reconciliation/SKILL.md:24`).
> 2. **Two columns named `obsolete_parts` should hold the same text.** `v_reuse_between.blocked_by` holds names only
>    today ("KP-0457, SN-573"); `v_verdict.obsolete_parts` will hold "SN-573, superseded by SN-598". Say which text
>    `v_reuse_between` gets. I would use the `describe()` text in both: one format, and `reuse_between()` stops
>    building its own.
> 3. **Say what "empty" is: `''` or NULL.** Four readers test it: the `CASE` of `v_tender_start`, the count on the
>    Reconciled data page, the answer-key test and `changes()`. `blocked_by` in `reuse_between` is `''` today
>    (`pipeline/reports.py:100`); keeping `''` costs nothing.
>
> Also: a `specific` sub-assembly of `V1` that holds an obsolete part goes from `keep` to `replace`. No row today
> (the 3 `specific` rows are all in `V6`). The new behaviour is the one the answer key uses: `synth/check.py:286`
> calls a design blocked when it is or contains such a part, whatever its content.

## Facts this plan rests on

| Fact | How it was checked |
|---|---|
| A build from `data/raw` and `data/claims.demo_start.jsonl` gives the answer key's verdict on all 240 sub-assembly and variant rows, for both `verdict_bom_only` and the final verdict | Probe `verdicts_vs_answer_key.py`, output: "240  bom_only equal, with_notes equal", no row unmatched |
| The key has 81 rows and the build 74 designs because the key has one row per reference and the build one design per content | Same probe: the 81 references cover exactly the 240 rows |
| The number of claims in force equals the rows of `v_claim_effect` (568 and 568) | Same probe |
| No test reads `data/truth/` today | `grep` over `tests/` and `pipeline/` |
| `made_by` and `up_to` are passed to `build()` only by tests and by the command line | `grep`; the README documents `--made-by rule` (line 56) |
| `v_readiness`, `v_tender_start` and `v_issue` are named in the agent's skill file as views to query | `skills/reconciliation/SKILL.md` lines 20, 24, 146, 147 |

## Stage 1: the answer-key test

Done first and committed alone, so every later stage runs against it.

### `tests/test_answer_key.py` (new)

Purpose: fail when the build's verdicts on the generated data stop matching `data/truth/verdicts.csv`.

- `built(tmp_path) -> dict[tuple[str, str], tuple[str, str]]`: builds `data/raw` with
  `data/claims.demo_start.jsonl` into `tmp_path`, and returns (variant, part id) -> (`verdict_bom_only`,
  `verdict`) read from `v_verdict` joined to `resolution`.
- `key() -> dict[tuple[str, str], tuple[str, str]]`: reads `data/truth/verdicts.csv`, one entry per variant
  listed in a row, the reference turned into a part id through `resolution`.
- `test_every_sub_assembly_has_the_verdict_of_the_answer_key`: both dicts have 240 entries and are equal.

In stage 2 the comparison of the final verdict becomes: where the key says `blocked`, `obsolete_parts` is filled
and `verdict` equals the key's `verdict_bom_only`; where the key says `reused` or `reusable`, `obsolete_parts` is
empty and `verdict` equals the key.

The test depends on `data/claims.demo_start.jsonl`. If that file is regenerated from another agent run, a failure
here means that run reached different verdicts.

> @Claude: Adding the test first and alone is the right order, and it is cheap: one build takes 0.11 s.
>
> **The stage 2 rule "where the key says `blocked`, `verdict` equals the key's `verdict_bom_only`" is a property of
> this data, not of the key.**
>
> - Fact: the key has no column for the content verdict with notes on a blocked row. It has `verdict_bom_only` and
>   `verdict_with_notes` = `blocked`.
> - Fact: on the demo log all 25 blocked rows are `reused` from the BOM alone and `reused` on content with notes
>   (probe output, section A: `{('reused', 'reused'): 25}`), so the rule passes.
> - When it fails for a wrong reason: a sub-assembly that is `specific` from the BOM alone, that a note makes
>   `reusable` (as for `RS-6620` and `GP-8805` today), and that also holds an obsolete part. The build would say
>   `reusable`, correctly, and the test would expect `specific`.
>
> Two ways to fix it:
>
> 1. Regenerate the key with the two columns the pipeline now has (the "other choice" of the last decision row).
>    The test becomes plain equality on three columns, with no translation. It removes the translation code from the
>    test and the word `blocked` from the key, `synth/check.py:283-289` and `docs/data-issues.md:66`, so the
>    generator and the pipeline use the same three words. Cost: `synth/generate.py` and `synth/check.py` change,
>    which "Not changed" excludes today.
> 2. Keep the key. For a `blocked` row assert only that `obsolete_parts` is filled, and assert nothing about
>    `verdict`. Cost: the content verdict of 25 of the 240 rows is no longer checked against the key.
>
> I would take 1. If 2, do not keep the `verdict_bom_only` comparison: it reads like a rule.
>
> Small: "both dicts have 240 entries" is implied by the equality. Asserting the number separately only adds a line
> that breaks when the data is regenerated.

## Stage 2: split the verdict

### `pipeline/verdict.py`

Purpose: the rule that says whether a design's content is shared, and the list of obsolete parts of a sub-assembly.

- `VERDICTS = ("reused", "reusable", "specific")`.
- `decide(design, pairs, name) -> Verdict`: today's `_on_content`, renamed. It no longer takes `relations`.
- `obsolete_parts(occurrence, relations) -> list[tuple[str, int, str | None]]`: (part id, claim id, replacement
  part id or None) for the sub-assembly's own reference, then for each component of its design, in order of part.
- `describe(obsolete, name) -> str`: the text of the `obsolete_parts` column, for example
  "SN-573, superseded by SN-598; AC-477, obsolete".
- Removed: `occurrence_verdict()`, the blocking branch of `decide()`, and the "(otherwise ...)" text.

> @Claude: **`describe()` loses a distinction that today's text makes, and that changes what the person has to do.**
>
> - A component is obsolete (`HT-5300` contains `TH-415`): the content has to change.
> - The sub-assembly's own reference is obsolete (`RG-0212` in `V1`): the content is sound, and the same content is
>   available under another reference. Today's reason says so: "the reference RG-0212 is obsolete; the same content
>   is carried by TC-8100". `tests/test_build.py:157` asserts that sentence.
>
> With the format given here both read "X, obsolete". Suggested text, which keeps the plan's format for components:
> "own reference RG-0212, obsolete (same content under TC-8100); SN-573, superseded by SN-598". The return value of
> `obsolete_parts()` already puts the own reference first, so `describe()` only needs to know which entry it is: add
> a boolean to the tuple, or return the own-reference entry separately. Keep one test for the "same content under"
> part, in place of `tests/test_build.py:152-157`.
>
> Small: after this change `Verdict.claim_ids` and the `claim_ids` column of the `verdict` table no longer hold the
> obsolete claims, and the description at `pipeline/tables.py:97` ("v_verdict has the final one per sub-assembly")
> is no longer true. The plan says "unchanged columns"; the content of one column changes.

### `pipeline/compare.py`

Only the `Occurrence` dataclass changes: the field `verdict` is replaced by `obsolete: list[tuple]`.
`verdict_bom_only` stays.

### `pipeline/build.py`

- `compare_and_decide(m)`: the last loop sets `occurrence.obsolete = obsolete_parts(occurrence, relations)`.
- `build()`: `verdict_bom_only` is read from the design verdict of the replay without notes.
- `Summary`: `verdicts` holds the design verdict of each (variant, reference); a new field
  `obsolete: dict[tuple[str, str], str]` holds the `obsolete_parts` text. `line()` prints the three verdict counts
  and the number of sub-assemblies holding an obsolete part.

### `pipeline/reports.py`

- `reuse_between(m)`: reads `occurrence.obsolete` instead of working the list out again; the key `blocked_by`
  becomes `obsolete_parts`.
- `evidence(m)`: the claim rows for obsolete parts come from `occurrence.obsolete` instead of
  `occurrence.verdict.claim_ids`. Same rows as today.

> @Claude: **"Same rows as today" needs a rule the plan does not give, and today's rows are already wrong for one
> case.**
>
> Facts:
>
> - `evidence` is stored per design, and `v_evidence` joins each row to every sub-assembly that carries the design
>   (`pipeline/views.sql:57-61`).
> - Today a component's claim is added once per design, from `verdict.claim_ids` (`pipeline/reports.py:143`). After
>   stage 2 that list no longer holds it. Read from each `occurrence.obsolete` without a rule, `HT-5300` (6
>   variants, 1 design) gives 6 rows in `evidence` and 36 in `v_evidence`, where there are 6 today.
> - Today the claim on an own reference is shown on sub-assemblies it does not concern. Probe output, section B:
>   `TC-8100` in `V2`, `V3` and `V5` is `reused` and shows "obsolete(RG-0212): RG-0212 (unité de commande HVAC)
>   obsolète...". After stage 2 the app's detail panel (`jean-code/src/db_page.py:107`) would show that line under a
>   row whose `obsolete_parts` is empty.
> - The own-reference rows also have an empty `source_row` where the component rows have the note id
>   (`pipeline/reports.py:133` against `:149`).
>
> Recommendation: store the obsolete parts as rows, not only as text. One table `obsolete_part`: `variant_id`,
> `part_id`, `obsolete_part_id`, `own_reference INTEGER`, `replacement_part_id`, `claim_id`. One row is one obsolete
> part of one sub-assembly in one variant (26 rows on the demo log: 25 sub-assemblies, `KP-0457` twice). Then:
>
> - `v_evidence` takes its obsolete claim rows from this table, joined on variant and part, so each sub-assembly
>   shows only its own. This removes lines 128-133 of `reports.py` and the wrong rows for `TC-8100`.
> - the agent can ask "which sub-assemblies hold `SN-573`" with `=` instead of `LIKE` on a sentence, and gets the
>   claim id.
> - `obsolete_parts` in `v_verdict` stays as the text for people.
>
> Cost: one more table (34 objects, not 33), and `Occurrence.obsolete` feeds a table as well as a text column.
>
> The minimum, if you prefer no new table: state that component claims are added once per design, and add the
> variant and part to the own-reference rows so `v_evidence` can join them to that sub-assembly alone.

### `pipeline/tables.py`

The `occurrence` entry of `TABLES`: columns `variant_id, part_id, system_part_id, design_id, per_train, raw_rows,
obsolete_parts, verdict_bom_only`.

### `pipeline/views.sql`

- `v_verdict`: `verdict` and `reason` come from the `verdict` table; `obsolete_parts` from `occurrence`.
- `v_tender_start`: the `action` rule given in the target section.

### `reconcile/tools.py`

- `changes(before, after)`: also reports sub-assemblies whose `obsolete_parts` changed, in the same sentence form
  as the verdicts.
- `verdict_counts(summary)`: three verdicts, then the count with an obsolete part.

### `jean-code/src/db_page.py`

The "Reuse verdicts" entry of `SECTIONS`: the sentence names three verdicts and the number of sub-assemblies with
an obsolete or superseded part; the query adds `v.obsolete_parts`. `app.py`, which has uncommitted changes, is not
touched.

### Text that describes the verdicts

| File | Lines | Change |
|---|---|---|
| `skills/reconciliation/SKILL.md` | 36 to 45, 167, 175 | three verdicts; `obsolete_parts` described; the wording for a person "cannot be reused as is" attached to `obsolete_parts` |
| `docs/relationships.md` | 57, 58, 113, 157 | same |
| `docs/data-issues.md` | 66 | "7 go from reused to blocked" restated as 7 that hold an obsolete or superseded part |
| `README.md` | 15 | same |

### Tests

| File | Change |
|---|---|
| `tests/test_verdict.py` | the three blocking tests are replaced by tests of `obsolete_parts()`: a component, the own reference, a `specific` design |
| `tests/test_build.py` | lines 62 to 69 and 152 to 157 assert `verdict` and `obsolete_parts` separately |
| `tests/test_tools.py` | the expected text of `changes()` and `verdict_counts()` |
| `tests/test_answer_key.py` | the comparison described in stage 1 |

## Stage 3: store the duplicated tables once

### `pipeline/tables.py`

The entries `queue`, `readiness`, `reuse_between` and `issue` of `TABLES` are renamed `v_queue`, `v_readiness`,
`v_reuse_between` and `v_issue`, and each takes its description from `VIEW_ABOUT`, where the four entries are
removed. The module docstring states that a name starting with `v_` is made for reading, whether it is a view or a
stored table.

The alternative, keeping the plain names and removing the views, was not chosen: `reconcile/batch.py`,
`jean-code/src/db_page.py`, the skill file, two test files and `docs/relationships.md` read the `v_` names.

> @Claude: Keeping the `v_` names is the cheaper choice, agreed. But four texts say that `v_` means "view", and the
> plan only updates the docstring of `tables.py`:
>
> 1. `reconcile/tools.py:62`, the tool description the model reads: "Views (names starting with v_) are the ones to
>    query first."
> 2. `reconcile/tools.py:66`: `ORDER BY type DESC, name` lists views first. The four stored `v_` tables would come
>    after all the views, among `bom_line`, `pair_diff` and the other tables. Order on the `v_` prefix instead.
> 3. `skills/reconciliation/SKILL.md:16`: "Query the views (`v_...`) first".
> 4. `pipeline/tables.py:29`: "empty: the table is read through its view". After this stage only `evidence` is in
>    that case.
>
> Also, the list at the bottom of the Reconciled data page will show `is_a` = `table` for these four
> (`jean-code/src/db_page.py:143`). Harmless, but it belongs with the "Not covered" note.
>
> For the record: `.claude/.archived_plans/pipeline-file-structure.md:120`, written the same day, kept these five
> views because "they are the agent's interface". This stage keeps the interface (the names) and drops the views,
> so the two are consistent. What the stage saves is 4 objects and 5 lines of SQL. It is fine to do, and it is the
> stage to drop if the plan needs to be shorter.

### `pipeline/views.sql`

The last five `CREATE VIEW` statements are removed.

> @Claude: **Remove four here, not five.** The fifth is `v_claim_effect`, and `jean-code/src/db_page.py:163` reads it
> for the page header until stage 5 changes that query. Between the two stages `claims_in_force()` raises "no such
> table", and "Checks after each stage" would only catch it if a test opens that page. Either remove
> `v_claim_effect` in stage 5 with its table (the stage 5 row "already removed in stage 3" then goes), or do stage 5
> before stage 3.

### `pipeline/reports.py`

`reuse_between(m)` rounds `cost_gap_eur` to 2 places, which the removed view did.

### Tests

`tests/test_build.py` line 105 keeps passing as written: it reads every table and view and checks that each `v_`
name has a description.

## Stage 4: remove `made_by` and `up_to`

| File | Change |
|---|---|
| `pipeline/claims.py` | `select(claims, without_notes=False)` and `in_force(claims, without_notes=False)` |
| `pipeline/build.py` | `compute(raw, all_claims, without_notes=False)`, `build(raw_dir, log_path, out_db, without_notes=False)`; the arguments `--made-by` and `--up-to` are removed |
| `README.md` | line 56 (`--made-by rule`) is removed |
| `tests/test_claims.py` | lines 124 and 125 are removed |
| `tests/test_build.py` | line 119: the parametrised test keeps only `without_notes` |

`without_notes` stays: it produces `verdict_bom_only`.

> @Claude: Agreed, remove both. Checked: no caller in `pipeline/`, `reconcile/` or `jean-code/src/` passes `made_by`
> or `up_to` to `build()`, `compute()`, `select()` or `in_force()`.
>
> What is lost: the README command that rebuilds with the rules alone (`README.md:56`). If that step of the demo
> matters, the same database comes from `--log` with a log that holds only the rules' claims, which is what the
> `rules_log` fixture of the tests builds.
>
> Small: three probes under `.experiments/` use these options or `v_claim_effect`
> (`45_built_database_against_answer_key.py`, `60_refactor_keeps_database.py`, `verdicts_vs_answer_key.py`). They
> are not tracked and are records of past runs, but `run_all.sh` will fail on them.

## Stage 5: remove `claim_effect`

| File | Change |
|---|---|
| `pipeline/reports.py` | `claim_effect()` is removed |
| `pipeline/tables.py` | its `TABLES` entry, its `VIEW_ABOUT` entry and its import are removed |
| `pipeline/views.sql` | already removed in stage 3 |
| `jean-code/src/db_page.py` | `claims_in_force()` reads `SELECT COUNT(*) FROM claim_status WHERE in_force = 1` |
| `skills/reconciliation/SKILL.md` | line 22 ("What one claim touches") is removed |

`v_readiness`, `v_tender_start` and `v_issue` stay: the skill file tells the agent to query them.

## Checks after each stage

1. `uv run pytest`.
2. `PYTHONPATH=. uv run python -m pipeline.build --log data/claims.demo_start.jsonl --out <a temp file>`, and the
   summary line compared with the counts in the target section.
3. After stage 2: open the Reconciled data page and read the "Reuse verdicts" tab on `KP-0457` in `V1`.

> @Claude: Check 2 is a comparison by eye of numbers the stage 1 test already asserts row by row. Drop it, or keep
> it for stage 2 only. For check 3, look at `RG-0212` in `V1` and `TC-8100` in `V2` as well: they are the two rows
> where the own-reference case and the evidence panel can go wrong (see the comments under `pipeline/verdict.py` and
> `pipeline/reports.py`).
>
> Good, and worth protecting: `changes()` reporting sub-assemblies whose `obsolete_parts` changed. Without it, an
> agent that appends `superseded_by` would be told "No change to parts, designs, verdicts or open items", since no
> verdict moves any more.

## Decisions to confirm before implementing

| Decision | What this plan assumes | The other choice |
|---|---|---|
| Name of the new column | `obsolete_parts` | another name; `blocked_by` is already used for prices |
| `--made-by rule` is documented in the README as a demo command | removed with `--up-to` | keep `made_by`, remove only `up_to` |
| Names of the four tables stored once | `v_queue`, `v_readiness`, `v_issue`, `v_reuse_between` | plain names, and six files updated |
| `data/truth/verdicts.csv` still says `blocked` | the key and the generator are left as they are; the test translates | regenerate the key with two columns |

## Not covered

The list "Every table and view of the SQLite file" at the bottom of the Reconciled data page. It will show 31
described entries instead of 33 after this plan. What to do with that list is a separate question.
