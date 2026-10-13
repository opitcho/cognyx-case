# Demo pipeline architecture

How the three noisy files become a data model the use cases can be answered from. What the pipeline must answer is defined in `docs/use-case-selection.md`. This plan covers what the pipeline produces, the storage choice, the stages with their tables, and the code files.

## What the pipeline produces

One SQLite file, `out/pilot.db`, and a score printed against the answer key. The demo and any front end read only the views below, so no rule is written a second time in report code.

### Input

| File | One row is | Columns |
|---|---|---|
| `data/raw/plm_bom_export.csv` | One parent-child link in one variant | `variant_id`, `cars`, `speed_class_kmh`, `interior`, `level`, `parent_ref`, `child_ref`, `description`, `quantity`, `unit` |
| `data/raw/erp_items.csv` | One component reference | `item_ref`, `description`, `supplier`, `unit_cost_eur`, `price_unit` |
| `data/raw/technical_notes.jsonl` | One note | `note_id`, `date`, `reference`, `text` |

### Output views

| View | One row is | Columns | Example row |
|---|---|---|---|
| `v_verdict` | One sub-assembly in one variant | `variant_id`, `system_ref`, `subassembly_ref`, `description`, `verdict`, `verdict_bom_only`, `reason`, `counterpart_ref` | `V1`, `DOOR-SYS-01`, `DR-1042`, `Door leaf assembly, left`, `blocked`, `reused`, `contains AC-501, superseded by AC-560`, `PT-7731` |
| `v_evidence` | One fact behind a verdict | `variant_id`, `subassembly_ref`, `kind`, `detail`, `source_file`, `source_row` | `V1`, `DR-1042`, `note`, `Actuator AC-501 superseded by AC-560 since NCR 2291`, `technical_notes.jsonl`, `TN-0231` |
| `v_pair_diff` | One differing line between two near-identical sub-assemblies | `ref_a`, `ref_b`, `component_a`, `component_b`, `qty_a`, `qty_b`, `explanation`, `note_id`, `cost_gap_eur` | `DR-1042`, `DR-1077`, `JT-218`, `JT-220`, `2.4`, `2.4`, `interchangeable`, `TN-0102`, `340.00` |
| `v_reuse_map` | One sub-assembly design | `system_ref`, `refs`, `description`, `V1` to `V6` (reference used, or empty), `verdict` | `DOOR-SYS-01`, `DR-1042, PT-7731`, `Door leaf assembly, left`, `DR-1042`, `DR-1042`, `PT-7731`, `PT-7731`, empty, empty, `reused` |
| `v_tender_start` | One sub-assembly of `V1` | `subassembly_ref`, `action` (reuse, adapt, replace), `reason`, `cost_eur`, `priced_lines`, `total_lines` | `DR-1042`, `replace`, `contains superseded AC-501`, `1,840.00`, `6`, `6` |
| `v_purchasing` | One bought part | `canonical_ref`, `refs`, `suppliers`, `min_cost_eur`, `max_cost_eur`, `total_quantity` | `JT-218`, `JT218, JT 218`, `Faiveley; FAIVELEY TRANSPORT SAS`, `12.40`, `14.10`, `86.4` |
| `v_issue` | One inconsistency, or one thing the pipeline refused to decide | `type`, `detail`, `source_file`, `source_rows` | `two_prices`, `JT-218: 12.40 and 14.10`, `erp_items.csv`, `311, 312` |

### Score

`eval/score.py` prints counts per kind of finding, with the missed and extra ones listed by reference:

```
clones under another reference     4 of 5 found, 1 extra    missed: SE-2210/SE-2291   extra: HV-3001/HV-3010
look-alikes wrongly merged         0 of 8
note relations extracted           28 of 30
note relations resolved to a part  26 of 28
```

## Storage: one SQLite file

- **Why relational is enough:** the BOM has a fixed depth of four levels, about 1,500 rows, and every question is a join or a set comparison. Nothing needs path queries of unknown length.
- **Why SQLite:** one file, no server, ships with Python. Thomas can open it and query any intermediate table. It runs inside Alstom's network with nothing to install.
- **The two graph-like needs** are small and done in Python:
  - Groups of spellings that are one part are built from accepted links between two spellings (stage 3).
  - Chains of `superseded_by` (A replaced by B, B replaced by C) are followed with a loop that remembers the parts already visited. On a repeat it stops and writes a `supersede_cycle` issue.
- **When a graph database would be justified:** BOMs of unknown depth across many product families, with "where is this part used, at any level" as a daily question. That is production scale, and is said as such in the demo.

## Rules for every stage

- **Raw is never changed.** Every later row points back to the raw rows it came from.
- **One stage writes each table, and rebuilds it from scratch.** No stage edits a table another stage wrote, so any stage can be rerun alone.
- **`issue` is the one shared table.** Each row carries the stage that wrote it, and a stage replaces only its own rows.
- **Nothing is dropped silently.** A value the pipeline can't parse stops the run. A decision it can't make becomes an `issue` row.
- **The pipeline never reads `data/truth/` or imports `synth/`.** Only the scoring script does.

## Stages

```
files -> 1 ingest -> 2 read notes -> 3 resolve references -> 4 build BOM and prices -> 5 compare -> 6 decide -> views
```

### Stage 1: ingest

Loads each file as written.

| Table | One row is | Columns |
|---|---|---|
| `raw_bom`, `raw_erp`, `raw_note` | One line of the file | The file's columns, all as text, plus `row_no` |

- Values stay as text, so `412,50` survives as written.
- A line that can't be parsed stops the run.
- Prints rows read against rows stored for each file.

### Stage 2: read notes

Turns each note into zero or more statements. This is the only stage that uses an LLM.

| Table | One row is | Columns |
|---|---|---|
| `relation` | One statement found in one note | `relation_id`, `note_id`, `date`, `type`, `ref_a_written`, `ref_b_written`, `option`, `value`, `negated`, `quote` |

- **`type`** is one of the seven relations in `docs/use-case-selection.md`. The output shape is fixed and the type is limited to those seven values.
- **References are stored as written in the note.** They reach parts later through `alias`, so this table never points at a part that has since changed.
- **`option` and `value`** hold the target of `required_for`, which links a part to an option (`speed_class_kmh`, `200`) and not to a second part.
- **`negated`** is true for a statement such as `AC-477 not obsolete, keep in stock`. It lets a later note cancel an earlier one. See open decision 1.
- **Every extraction is checked against its note.** The quote and both references must appear character for character in the note text. A relation that fails is rejected and written as an `unverified_relation` issue. The check is deterministic and runs in the tests.
- **The cache is keyed on prompt, model and note text together**, so a prompt change can't return old extractions. The cache file is committed, which makes reruns free and offline.
- Prints notes read, relations found, relations rejected.

### Stage 3: resolve references

Decides which written references are the same part.

| Table | One row is | Columns |
|---|---|---|
| `ref_link` | One pair of spellings the pipeline considered | `ref_a`, `ref_b`, `method` (exact, rule, edit_distance, note), `distance`, `note_id`, `decision` (accepted, vetoed, skipped, tied) |
| `part` | One real part | `part_id`, `kind` (system, sub-assembly, component), `canonical_ref`, `description` |
| `alias` | One reference as written somewhere | `written_ref`, `source` (bom, erp, note), `part_id` |
| `variant` | One train variant | `variant_id`, `cars`, `speed_class_kmh`, `interior` |

How links are made:

1. **Rule:** two spellings equal after normalising case, separators and `O`/`0`.
2. **Edit distance:** two normalised spellings one character apart (one added, dropped or changed). This replaces a similarity ratio, which shifts with the length of the reference and can't be explained to Thomas.
3. **Note:** a `same_as` relation adds an accepted link. A `not_same_as` relation adds a vetoed link.

How links become parts:

1. Accepted links are added strongest first: exact, rule, note, then edit distance.
2. **Sibling check:** two spellings that are children of the same parent in the same variant are two parts, such as the left and right door leaves. Their link is marked `vetoed`.
3. A link that would put a vetoed pair in the same group is marked `skipped` and written as an issue.
4. A spelling one character from two different groups is marked `tied`, left on its own, and written as an issue. It is never given to the first candidate.
5. `part` and `alias` are rebuilt from the accepted links on every run. `canonical_ref` is the spelling used most often in the BOM.

What this gives:

- Any merge can be explained: `ref_link` names both spellings, the method and the note.
- Any merge can be undone by changing one row's decision and rerunning.
- "Which merges did the notes cause" is a query on `method = note`.

### Stage 4: build the clean BOM and prices

| Table | One row is | Columns |
|---|---|---|
| `unit` | One written unit | `written_unit`, `base_unit`, `factor` |
| `bom_line` | One parent-child link in one variant, cleaned | `variant_id`, `parent_part_id`, `child_part_id`, `quantity_base`, `base_unit`, `raw_rows` |
| `price` | One ERP row, cleaned | `part_id`, `supplier_written`, `cost_per_base_unit_eur`, `raw_row` |
| `supplier` | One real supplier | `supplier_id`, `name`, `spellings` |

- **`unit`** is a small fixed list (`mm` to `m` with factor 0.001, `PCE` to `pcs` with factor 1, and so on). A unit that is not in it stops the run.
- **Repeated lines with the same quantity** are folded into one.
- **Repeated lines with two quantities** keep `quantity_base` empty and write a `two_quantities` issue. The pipeline does not pick one.
- **`price` keeps several rows per part.** Two prices for one part is a `two_prices` issue. A missing price leaves the cost empty, never 0, and writes a `missing_price` issue.
- **`supplier` is built last and only for the purchasing view.** `Faiveley` and `Wabtec` are one supplier by ownership, not by spelling, so the grouping is a hand-written list.

### Stage 5: compare

| Table | One row is | Columns |
|---|---|---|
| `design` | One distinct content: a set of (component, quantity) | `design_id`, `content_hash`, `n_lines`, `comparable` |
| `occurrence` | One sub-assembly in one variant | `variant_id`, `part_id`, `system_part_id`, `design_id` |
| `pair` | Two designs worth comparing | `pair_id`, `design_a`, `design_b`, `kind` (near, functional), `n_shared`, `n_differing`, `separating_options` |
| `pair_diff` | One differing line of a near pair | `pair_id`, `part_a`, `part_b`, `qty_a`, `qty_b`, `explanation`, `relation_id` |

- **`design` separates content from reference.** Two sub-assemblies with the same content share one `design_id` whatever their references. "Reused under two references" is one design with several parts.
- **`content_hash`** is computed on quantities as rounded decimals in the base unit, so `2.4 m` and `2400 mm` give the same hash.
- **`comparable`** is false for a design holding a line with an empty quantity. Such designs are left out of comparison and counted.
- **Near pairs** are searched between designs under the same system: 1 to 3 differing lines and at least 4 shared components.
- **Functional pairs** come from `functionally_equivalent_to` relations.
- **`explanation`** on a differing line is one of: `interchangeable`, `superseded`, `required_by_option`, `unexplained`. Each of the first three needs a note relation, pointed to by `relation_id`.
- **`separating_options`** lists the options that split the two designs cleanly: for example `speed_class_kmh` when every variant using one design is 160 and every variant using the other is 200. It is shown as a fact beside the pair. It does not change the verdict on its own, which matches the answer key: a speed-class pair with no `required_for` note is expected as `reusable`.
- Also writes `note_contradicts_bom` issues (a part a note calls obsolete or superseded is still in the BOM) and `supersede_cycle` issues.

### Stage 6: decide

| Table | One row is | Columns |
|---|---|---|
| `verdict` | The verdict for one design | `design_id`, `verdict`, `verdict_bom_only`, `reason`, `counterpart_design_id` |

- **Verdicts are decided per design**, the same grain as `data/truth/verdicts.csv`. `v_verdict` copies them to each occurrence.
- **One rule function**, applied in this order: blocked, reused, reusable, specific.
- **`verdict_bom_only`** is the same function called with no relations. It uses the same parts as `verdict`, including merges that came from notes. The demo number "verdicts changed by notes" therefore counts changes at the verdict step. Merges caused by notes are counted separately from `ref_link`.

### Views

| View | Built from |
|---|---|
| `relation_resolved` | `relation` joined to `alias`. A reference that matches no alias leaves the part empty and appears in `v_issue` as `unresolved_note_reference` |
| `relation_current` | `relation_resolved`, keeping for each group of statements about the same parts only the latest by `date`, and dropping it if `negated` |
| `v_pair_diff` | `pair_diff` with the cost gap from `price`. The gap is empty when either side has no price |
| `v_evidence` | `pair`, `pair_diff`, `relation_current` and `bom_line.raw_rows` |
| `v_verdict`, `v_reuse_map`, `v_tender_start`, `v_purchasing`, `v_issue` | As described under "Output views". Every cost total carries `priced_lines` and `total_lines` |

Stages 3, 5 and 6 read notes through the same definition of "current". Stage 3 runs before `alias` exists, so it applies the latest-wins rule to `same_as` and `not_same_as` on normalised written references.

## Scoring

`eval/score.py` compares `out/pilot.db` with `data/truth/`.

- **Counts, not only percentages.** The planted minimums are 2 to 5 per kind of finding, so one miss moves a percentage by 20 to 50 points. Each line reads "4 of 5 found, 1 extra", with the missed and extra ones listed.
- **Look-alikes wrongly merged** is its own line. It is the error that would cost most in front of Thomas.
- **Notes are scored in two parts:** relations extracted, and relations resolved to the right part. A missed sentence and a mistyped reference are then told apart.
- **It runs as a test.** With the extraction cache committed, the score is deterministic, offline and free.

## Code files

| File | Why it exists | Interface |
|---|---|---|
| `pipeline/db.py` | Holds the schema in one place, so every stage and the scorer agree on the tables | `connect(path) -> Connection`; `create_schema(conn)`; `replace_table(conn, table, rows)`; `replace_issues(conn, stage, rows)` |
| `pipeline/ingest.py` | Stage 1 | `ingest(conn, raw_dir) -> dict[file, row_count]` |
| `pipeline/notes.py` | Stage 2. Keeps the prompt, the cache and the quote check together | `read_notes(conn, extractor, cache_path) -> counts`; `verify(relation, note_text) -> bool`; `cache_key(prompt, model, text) -> str` |
| `pipeline/extractor.py` | The only file that calls a model. Swapping the model for one hosted inside Alstom changes this file alone | `extract(note_text) -> list[dict]`; `PROMPT`; `MODEL` |
| `pipeline/refs.py` | Stage 3 | `normalise(ref) -> str`; `edit_distance(a, b) -> int`; `propose_links(conn) -> list[link]`; `build_parts(conn, links)` |
| `pipeline/bom.py` | Stage 4 | `to_base(quantity, unit, unit_table) -> (Decimal, str)`; `build_bom(conn)`; `build_prices(conn)`; `build_suppliers(conn, groups)` |
| `pipeline/compare.py` | Stage 5 | `content_hash(lines) -> str`; `build_designs(conn)`; `find_near_pairs(conn, max_diff=3, min_shared=4)`; `explain_diff(diff, relations) -> str`; `follow_superseded(part_id, relations) -> (part_id, cycle)` |
| `pipeline/verdict.py` | Stage 6. One rule function used for both verdict columns | `decide(design, pairs, relations) -> (verdict, reason, counterpart)`; `build_verdicts(conn)` |
| `pipeline/views.sql` | Every view. The single place where output columns are defined | Run by `create_schema` |
| `pipeline/run.py` | Runs the stages in order, or one stage alone | `python -m pipeline.run [--stage N] [--out out/pilot.db]` |
| `eval/score.py` | Scoring. The only code allowed to read `data/truth/` | `python -m eval.score out/pilot.db data/truth` |
| `tests/` | The quote check, edit distance, unit conversion, the content hash, and the score on the committed data | `pytest` |

No dependency outside the standard library, apart from the model client in `extractor.py`.

## Changes needed in other documents

- **`docs/use-case-selection.md`:** add the rule for `separating_options` and say that it does not change a verdict without a `required_for` note.
- **`docs/use-case-selection.md`:** quote the full case question, including "and where are the inconsistencies?", and name `v_issue` as its answer.
- **`.claude/.plans/synthetic-data-generator.md`:** say which two statements count as a contradiction in the two planted pairs, so that `negated` and latest-wins can reproduce the answer key.

## Open decisions

1. **How a note cancels an earlier one.** This plan adds a `negated` flag and lets the latest statement about the same parts win. The seven relation types can't express "not obsolete after all", and the generator plants two contradicting pairs without saying what they contain. The alternative is to drop `negated` and handle only opposite pairs (`same_as` against `not_same_as`, `superseded_by` in both directions).
2. **What "BOM only" means.** This plan keeps note-driven merges in `verdict_bom_only` and removes notes only at the verdict step. The alternative is a second full run with no notes at all, which gives a larger "changed by notes" number and doubles the run.
3. **Front end.** A static HTML report generated from the views, or a small web app. Not covered here.
