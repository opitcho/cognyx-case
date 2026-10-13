# Simplify the verdict, the duplicated tables and the replay options

Written 2026-10-13 against commit `a2bb935` (local `main`). Second version, after the review of the same day. The
reviewed first version is `.claude/.archived_plans/simplify-verdict-and-tables-v1-reviewed.md`.

## What this plan changes

1. A test compares the build's verdicts with the answer key `data/truth/verdicts.csv`. It is added first.
2. The verdict of a sub-assembly says only whether its content is shared: `reused`, `reusable` or `specific`.
   Whether it holds an obsolete or superseded part moves to a separate column, `obsolete_parts`. The answer key is
   regenerated with the same split.
3. The `claim_effect` table and its view are removed.
4. Four tables that are stored and then repeated by a view are stored once.
5. `build()` loses the two replay options `made_by` and `up_to`.

Not changed: which claim wins a conflict (`statuses()`, `group()`, `_guard()`), the comparison functions of
`pipeline/compare.py`, the claim checks in `pipeline/claims.py`, the two computations per build, and the raw and
clean files the generator writes.

## Target: the database after the change

### `v_verdict`: one sub-assembly in one variant

| Column | Today | After |
|---|---|---|
| `variant_id`, `system_ref`, `subassembly_ref`, `description` | unchanged | unchanged |
| `verdict` | `reused`, `reusable`, `blocked` or `specific` | `reused`, `reusable` or `specific` |
| `verdict_bom_only` | the same four values | `reused`, `reusable` or `specific` |
| `reason` | for a blocked row: the part, then "(otherwise reused: ...)" | only why the content is or is not shared |
| `obsolete_parts` | does not exist | text; `''` when the sub-assembly holds no obsolete or superseded part |
| `counterpart_ref`, `design_id` | unchanged | unchanged |

The text of `obsolete_parts` lists the sub-assembly's own reference first, when a claim says it is obsolete or
superseded, then each such component, separated by "; ":

- own reference: "own reference RG-0212, obsolete (same content under TC-8100)". The part in brackets is present
  when another reference carries the same content.
- component: "SN-573, superseded by SN-598", or "AC-477, obsolete".

The two cases are kept apart because they ask for different things: a component means the content has to change;
an own reference means the content is sound and is available under another reference.

Four real rows, today and after:

| Row | Today | After |
|---|---|---|
| `V1`, `KP-0457`, Door control unit | `verdict` = `blocked`, `reason` = "contains SN-573, superseded by SN-598 (otherwise reused: same content in V1, V2, V3, V4 under references DC-3001, KP-0457)" | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V4 under references DC-3001, KP-0457", `obsolete_parts` = "own reference KP-0457, superseded by DC-3001 (same content under DC-3001); SN-573, superseded by SN-598" |
| `V1`, `RG-0212` | `verdict` = `blocked`, `reason` = "the reference RG-0212 is obsolete; the same content is carried by TC-8100 (otherwise reused: ...)" | `verdict` = `reused`, `obsolete_parts` = "own reference RG-0212, obsolete (same content under TC-8100)" |
| `V2`, `DC-3001` | `verdict` = `blocked`, `reason` = "contains SN-573, superseded by SN-598 (otherwise reused: ...)" | `verdict` = `reused`, `obsolete_parts` = "SN-573, superseded by SN-598" |
| `V1`, `SW-3510`, Side wall panel set | `verdict` = `reused`, `reason` = "same content in V1, V2, V3, V4, V5, V6" | the same, with `obsolete_parts` = `''` |

What a person reads changes for `KP-0457` in `V1`: today's reason names only `SN-573`, because the own reference is
looked at only when the design is not already blocked (`pipeline/verdict.py:47`). Claim 443, from note `TN-0127`,
says "KP-0457 door control unit superseded by DC-3001". After the change the row names both.

Counts on the demo starting log (`data/claims.demo_start.jsonl`):

| | Today (measured) | After (derived from the answer key, confirmed by the test of stage 2) |
|---|---|---|
| `reused` | 197 | 222 |
| `reusable` | 15 | 15 |
| `specific` | 3 | 3 |
| `blocked` | 25 | not a verdict |
| rows with `obsolete_parts` filled | not stored | 25 |

`obsolete_parts` is filled for any sub-assembly that holds such a part, whatever its verdict. Today a `specific`
sub-assembly holding one is not marked. No row is in that case today: all 25 holders are `reused` on content. This
is the rule the generator's checker already uses (`synth/check.py:283-289`).

### Other tables and views that change

| Object | Change |
|---|---|
| `occurrence` (table) | loses `verdict` and `reason`; gains `obsolete_parts`; keeps `verdict_bom_only` |
| `verdict` (table) | same columns. It is the only place a verdict is stored. `claim_ids` no longer holds the claims about obsolete parts. Its description becomes "the verdict of one design: whether its content is shared" |
| `evidence` (table) | gains `variant_id` and `part_id`, filled only on a row about a sub-assembly's own reference, `''` otherwise |
| `v_evidence` | a row with `variant_id` filled is shown only for that sub-assembly. Today the claim "obsolete(RG-0212)" is shown under `TC-8100` in `V2`, `V3` and `V5`, which it does not concern; after the change it is shown under `RG-0212` in `V1` only. A component's claim stays shown once for each sub-assembly that carries the design |
| `v_reuse_map` | unchanged. Its `verdict` column can no longer disagree with `v_verdict` (today `RG-0212` in `V1` is `blocked` in `v_verdict` and `reused` in `v_reuse_map`) |
| `v_tender_start` | gains the column `obsolete_parts`. `action` is `replace` when `obsolete_parts <> ''`, otherwise `reuse`, `adapt` or `keep` from the verdict. A `specific` sub-assembly of `V1` holding an obsolete part would go from `keep` to `replace`; no row today |
| `v_reuse_between` | column `blocked_by` renamed `obsolete_parts`, holding the same text as `v_verdict.obsolete_parts` for the sub-assembly of `variant_from` (today it holds names only, "KP-0457, SN-573"). `blocked_by` keeps one meaning in the database: in `v_subassembly_cost`, the components with no agreed price |
| `v_queue`, `v_readiness`, `v_issue`, `v_reuse_between` | become stored tables with the same names and columns. The tables `queue`, `readiness`, `issue`, `reuse_between` and the four views over them are removed |
| `claim_effect`, `v_claim_effect` | removed |

The file goes from 39 objects (26 tables, 13 views) to 33 (25 tables, 8 views). The names the agent and the app
read stay the same, except `v_claim_effect`.

## Target: the answer key after the change

`data/truth/verdicts.csv`, one row per sub-assembly reference:

| Column | Today | After |
|---|---|---|
| `subassembly`, `variants`, `finding_ids` | unchanged | unchanged |
| `verdict_bom_only` | `reused`, `reusable` or `specific` | unchanged |
| `verdict_with_notes` | `reused`, `reusable`, `blocked` or `specific` | `reused`, `reusable` or `specific`: the verdict on content once the notes are read |
| `holds_obsolete_part` | does not exist | `yes` or `no`: the reference is, or its content contains, a part that a note not overridden calls obsolete or superseded |

Example: `KP-0457,V1,reused,blocked,F06 F17` becomes `KP-0457,V1,reused,reused,yes,F06 F17`. Seven rows change
this way: `KP-0457`, `RG-0212`, `DC-3001`, `HD-3475`, `DR-1043`, `HT-5300`, `FC-6100`. The other 74 rows gain `no`.

## Facts this plan rests on

| Fact | How it was checked |
|---|---|
| A build from `data/raw` and `data/claims.demo_start.jsonl` gives the answer key's verdict on all 240 sub-assembly and variant rows, for both `verdict_bom_only` and the final verdict | `.experiments/verdicts_vs_answer_key.py`, output: "240  bom_only equal, with_notes equal", no row unmatched |
| The key has 81 rows and the build 74 designs because the key has one row per reference and the build one design per content | Same probe: the 81 references cover exactly the 240 rows |
| The number of claims in force equals the rows of `v_claim_effect` (568 and 568) | Same probe |
| The reference `KP-0457` is itself superseded (claim 443) | Query on the built database |
| `v_evidence` shows "obsolete(RG-0212)" under `TC-8100` in `V2` | Query on the built database |
| `synth/inputs/findings.json` states `blocked` in 8 entries of 7 findings: F06, F07, F17 (twice), F18, F24, F25, F26 | Read with a script |
| No test reads `data/truth/` today | `grep` over `tests/` and `pipeline/` |
| `made_by` and `up_to` are passed to `build()` only by tests and by the command line | `grep`; the README documents `--made-by rule` (line 56) |
| `v_readiness`, `v_tender_start` and `v_issue` are named in the agent's skill file as views to query | `skills/reconciliation/SKILL.md` lines 20, 24, 146, 147 |

Not checked: that running `synth/generate.py` again rewrites `data/raw/` and `data/clean/` byte for byte. Stage 2
checks it before going further.

## Stage 1: the answer-key test

Done first and committed alone, so every later stage runs against it.

### `tests/test_answer_key.py` (new)

Purpose: fail when the build's verdicts on the generated data stop matching `data/truth/verdicts.csv`.

- `built(tmp_path) -> dict[tuple[str, str], tuple]`: builds `data/raw` with `data/claims.demo_start.jsonl` into
  `tmp_path`, and returns (variant, part id) -> (`verdict_bom_only`, `verdict`) read from `v_verdict` joined to
  `resolution`.
- `key(db) -> dict[tuple[str, str], tuple]`: reads `data/truth/verdicts.csv`, one entry per variant listed in a
  row, the reference turned into a part id through `resolution`.
- `test_every_sub_assembly_has_the_verdict_of_the_answer_key`: the two dicts are equal.

In stage 2 each value gains a third element: `obsolete_parts <> ''` on the build side, `holds_obsolete_part ==
"yes"` on the key side. The test stays one equality, with no translation of `blocked`.

The test depends on `data/claims.demo_start.jsonl`. If that file is regenerated from another agent run, a failure
here means that run reached different verdicts.

## Stage 2: split the verdict

### `pipeline/verdict.py`

Purpose: the rule that says whether a design's content is shared, and the obsolete parts of a sub-assembly.

- `VERDICTS = ("reused", "reusable", "specific")`.
- `decide(design, pairs, name) -> Verdict`: today's `_on_content`, renamed. It no longer takes `relations`.
- `obsolete_components(design, relations) -> list[tuple[str, int, str | None]]`: (part id, claim id, replacement
  part id or None) for each component of the design that is obsolete or superseded, in order of part. The same
  for every sub-assembly that carries the design.
- `describe_obsolete(occurrence, relations, name) -> str`: the text of the `obsolete_parts` column, in the format
  of the target section. It reads the own reference from `relations.dead(occurrence.part)` and the components
  from `obsolete_components(occurrence.design, relations)`. Returns `''` when there is none.
- Removed: `occurrence_verdict()`, the blocking branch of `decide()`, and the "(otherwise ...)" text.

### `pipeline/compare.py`

Only the `Occurrence` dataclass changes: the field `verdict` is replaced by `obsolete_parts: str = ""`.
`verdict_bom_only` stays.

### `pipeline/build.py`

- `compare_and_decide(m)`: the last loop sets `occurrence.obsolete_parts = describe_obsolete(occurrence,
  relations, m.name)`.
- `build()`: `verdict_bom_only` is read from the design verdict of the replay without notes.
- `Summary`: `verdicts` holds the design verdict of each (variant, reference); a new field
  `obsolete: dict[tuple[str, str], str]` holds the `obsolete_parts` text of the sub-assemblies where it is filled.
  `line()` prints the three verdict counts and the number of sub-assemblies holding an obsolete part.

### `pipeline/reports.py`

- `reuse_between(m)`: writes `occurrence.obsolete_parts` instead of working the list out again; the key
  `blocked_by` becomes `obsolete_parts`.
- `evidence(m)`: each row gains `variant_id` and `part_id`. For a design, one claim row per entry of
  `obsolete_components()`, with both empty. For a sub-assembly whose own reference is obsolete or superseded, one
  claim row with both filled, and with the note id in `source_row`, which is empty today (`reports.py:133`).

### `pipeline/tables.py`

- The `occurrence` entry of `TABLES`: columns `variant_id, part_id, system_part_id, design_id, per_train, raw_rows,
  obsolete_parts, verdict_bom_only`.
- The `evidence` entry: columns `design_id, variant_id, part_id, kind, detail, claim_id INTEGER, source_file,
  source_row`.
- The description of `verdict` (line 97) and of `v_verdict` in `VIEW_ABOUT`.

### `pipeline/views.sql`

- `v_verdict`: `verdict` and `reason` come from the `verdict` table; `obsolete_parts` from `occurrence`.
- `v_evidence`: the join to `occurrence` adds `AND (e.variant_id = '' OR (e.variant_id = o.variant_id AND e.part_id
  = o.part_id))`.
- `v_tender_start`: the column `obsolete_parts` and the `action` rule of the target section.

### `reconcile/tools.py`

- `changes(before, after)`: also reports sub-assemblies whose `obsolete_parts` changed, in the same sentence form
  as the verdicts. Without it, an agent that appends a `superseded_by` claim would be told "No change to parts,
  designs, verdicts or open items", since no verdict moves any more.
- `verdict_counts(summary)`: three verdicts, then the count with an obsolete part.

### `jean-code/src/db_page.py`

The "Reuse verdicts" entry of `SECTIONS`: the sentence names three verdicts and the number of sub-assemblies with
an obsolete or superseded part (`obsolete_parts <> ''`); the query adds `v.obsolete_parts`. `app.py`, which has
uncommitted changes, is not touched.

### The answer key and its generator

| File | Change |
|---|---|
| `synth/inputs/findings.json` | in the 8 entries that say `blocked`, the second value becomes the verdict on content: `reused` in F06, F07, F24, F25, F26; `reusable` in F17 and F18 |
| `synth/generate.py` | `VERDICT_ORDER` loses `blocked`. `verdicts_from(findings, model, relations)` adds `holds_obsolete_part`, worked out from the relations not overridden and the clean content, as `synth/check.py:285-287` does today |
| `synth/check.py` | check 10a counts the references whose verdict differs with the notes or that hold an obsolete part (9 today, same 9 after; the setting asks for at least 8). Check 10b compares `holds_obsolete_part` with its own computation from the files on disk |
| `data/truth/verdicts.csv`, `data/truth/check_report.txt` | regenerated with `uv run python -m synth.generate`, then `uv run python -m synth.check` |

Before going further: `git diff --stat data/raw data/clean data/truth` after regenerating must list only the two
files above. If a raw or clean file changes, the regeneration is undone and the other choice of the last decision
row applies.

### Text that describes the verdicts

| File | Lines | Change |
|---|---|---|
| `skills/reconciliation/SKILL.md` | 36 to 45, 167, 175 | three verdicts; `obsolete_parts` described with its two cases; the wording for a person "cannot be reused as is" attached to `obsolete_parts` |
| `docs/relationships.md` | 57, 58, 113, 157 | same |
| `docs/data-issues.md` | 66 | "7 go from reused to blocked" restated as 7 that are or hold an obsolete or superseded part |
| `README.md` | 15 | same |

### Tests

| File | Change |
|---|---|
| `tests/test_verdict.py` | the three blocking tests are replaced by tests of `obsolete_components()` and `describe_obsolete()`: a component, the own reference with and without another reference carrying the content, both at once, a `specific` design |
| `tests/test_build.py` | lines 62 to 69 assert `verdict` and `obsolete_parts` separately. Lines 152 to 157 assert `obsolete_parts` = "own reference PT-7731, obsolete (same content under DR-1042)" and that `v_evidence` shows the claim under `PT-7731` and not under `DR-1042` |
| `tests/test_tools.py` | the expected text of `changes()` and `verdict_counts()` |
| `tests/test_answer_key.py` | the third element described in stage 1 |

## Stage 3: remove `claim_effect`

Done before stage 4, so the app never reads a view that is gone.

| File | Change |
|---|---|
| `jean-code/src/db_page.py` | `claims_in_force()` reads `SELECT COUNT(*) FROM claim_status WHERE in_force = 1` |
| `pipeline/reports.py` | `claim_effect()` is removed |
| `pipeline/tables.py` | its `TABLES` entry, its `VIEW_ABOUT` entry and its import are removed |
| `pipeline/views.sql` | `v_claim_effect` is removed |
| `skills/reconciliation/SKILL.md` | line 22 ("What one claim touches") is removed |

`v_readiness`, `v_tender_start` and `v_issue` stay: the skill file tells the agent to query them.

## Stage 4: store the duplicated tables once

This stage saves 4 objects and 6 lines of SQL. It is the one to leave out if the plan has to be shorter.

### `pipeline/tables.py`

The entries `queue`, `readiness`, `reuse_between` and `issue` of `TABLES` are renamed `v_queue`, `v_readiness`,
`v_reuse_between` and `v_issue`, and each takes its description from `VIEW_ABOUT`, where the four entries are
removed. The module docstring states that a name starting with `v_` is made for reading, whether it is a view or a
stored table. The comment on `Table.one_row_is` (line 29) names `evidence`, the only table left that is read
through a view.

The alternative, keeping the plain names and removing the views, was not chosen: `reconcile/batch.py`,
`jean-code/src/db_page.py`, the skill file, two test files and `docs/relationships.md` read the `v_` names.

### `pipeline/views.sql`

The four `CREATE VIEW` statements for `v_issue`, `v_queue`, `v_readiness` and `v_reuse_between` are removed.

### `pipeline/reports.py`

`reuse_between(m)` rounds `cost_gap_eur` to 2 places, which the removed view did.

### Texts that say `v_` means view

| File | Line | Change |
|---|---|---|
| `reconcile/tools.py` | 62, the tool description the model reads | "Names starting with v_ are the ones to query first." |
| `reconcile/tools.py` | 66 | the list is ordered with the `v_` names first, then the others, each by name. Today `ORDER BY type DESC` puts views first, which would leave the four stored `v_` tables among `bom_line` and `pair_diff` |
| `skills/reconciliation/SKILL.md` | 16 | "Query the `v_...` names first" |

### Tests

`tests/test_build.py` line 105 keeps passing as written: it reads every table and view and checks that each `v_`
name has a description. `tests/test_tools.py` gains one assertion that `describe_tables()` lists `v_queue` before
`bom_line`.

## Stage 5: remove `made_by` and `up_to`

| File | Change |
|---|---|
| `pipeline/claims.py` | `select(claims, without_notes=False)` and `in_force(claims, without_notes=False)` |
| `pipeline/build.py` | `compute(raw, all_claims, without_notes=False)`, `build(raw_dir, log_path, out_db, without_notes=False)`; the arguments `--made-by` and `--up-to` are removed |
| `README.md` | line 56 (`--made-by rule`) is removed |
| `tests/test_claims.py` | lines 124 and 125 are removed |
| `tests/test_build.py` | line 119: the parametrised test keeps only `without_notes` |

`without_notes` stays: it produces `verdict_bom_only`. A database built with the rules alone can still be made
with `--log` and a log that holds only the rules' claims, which is what the `rules_log` fixture of the tests builds.

## Checks

1. After each stage: `uv run pytest`.
2. After stage 2: `uv run python -m synth.check` reports every check as passed, and the `git diff --stat` check of
   that stage.
3. After stage 2: open the Reconciled data page, "Reuse verdicts" tab, and read three rows. `KP-0457` in `V1`
   names its own reference and `SN-573`. `RG-0212` in `V1` reads "own reference RG-0212, obsolete (same content
   under TC-8100)". `TC-8100` in `V2` has `obsolete_parts` empty and no obsolete claim in the panel under it.

## Decisions to confirm before implementing

| Decision | What this plan assumes | The other choice |
|---|---|---|
| Name of the new column | `obsolete_parts` | another name; `blocked_by` is already used for prices |
| The answer key | regenerated with `holds_obsolete_part`, which changes `synth/inputs/findings.json`, `synth/generate.py` and `synth/check.py` | keep the key. The test then asserts, for a row the key calls `blocked`, only that `obsolete_parts` is filled; the verdict on content of 25 of the 240 rows is not checked against the key |
| Where the obsolete parts are stored | as text in `occurrence.obsolete_parts`, and as claim rows in `evidence` | also as rows of a new table `obsolete_part` (variant, sub-assembly, part, own reference or component, replacement, claim), as the review suggested. 34 objects instead of 33. Not chosen because `v_content` and `relation` already answer "which sub-assemblies hold `SN-573`" |
| `--made-by rule` is documented in the README as a demo command | removed with `--up-to` | keep `made_by`, remove only `up_to` |
| Names of the four tables stored once | `v_queue`, `v_readiness`, `v_issue`, `v_reuse_between` | plain names, and six files updated |

## Not covered

- The list "Every table and view of the SQLite file" at the bottom of the Reconciled data page. After this plan it
  shows 31 described entries instead of 33, and `is_a` = `table` for the four `v_` names of stage 4. What to do
  with that list is a separate question.
- Three probes under `.experiments/` use `made_by`, `up_to` or `v_claim_effect`
  (`45_built_database_against_answer_key.py`, `60_refactor_keeps_database.py`, `verdicts_vs_answer_key.py`). They
  are records of past runs and are not tracked; `run_all.sh` will fail on them after stages 3 and 5.

## What changed after the review

| Review comment | What this version does |
|---|---|
| The example row for `KP-0457` left out its own reference | Row corrected; the change in what a person reads is stated in the target section |
| The text did not tell an own reference from a component | Format with "own reference ..." and "(same content under ...)"; one test for it |
| "Same rows as today" for `evidence()` was not true, and today's rows show an obsolete claim under sub-assemblies it does not concern | `evidence` gains `variant_id` and `part_id`; `v_evidence` shows an own-reference claim under that sub-assembly only. The new table the review suggested is listed as the other choice |
| Stage 3 removed `v_claim_effect` while the app read it until stage 5 | `claim_effect` is removed first, in its own stage, starting with the app's query |
| The stage 2 rule of the answer-key test held on this data only | The key is regenerated; the test is one equality |
| `v_tender_start` said `replace` without naming the part | It gains `obsolete_parts` |
| Two columns named `obsolete_parts` with two formats; "empty" not defined | One text in both; empty is `''` |
| Four texts say `v_` means view | The three outside `tables.py` are listed in stage 4, with the ordering of `describe_tables()` |
| The description of the `verdict` table and the content of `claim_ids` change | Stated in the target section |
| Check 2 repeated by eye what the test asserts; check 3 looked at one row | Check 2 replaced by the generator's checker; check 3 reads three rows |
| The test asserted 240 entries separately | Removed |
