# Pipeline file structure

Restructure `pipeline/` so that each file holds one step of the build, without changing what the build computes.
No rule, comparison, verdict, table, view or column changes. Only where code lives and how it is cut into functions.

## What is wrong today

All findings are in `pipeline/build.py` (650 lines) unless another file is named.

| # | Where | What |
|---|---|---|
| 1 | `compute()`, lines 109-327 | One function of 220 lines does eight things in a row: parts, cell overrides, suppliers, variants, units, BOM lines, prices, relations, then designs and verdicts. The steps talk to each other through three nested functions (`linked`, `cell`, `to_base`) and about fifteen local variables (`written`, `by_type`, `used`, `relations`, ...). No step can be read or tested alone. |
| 2 | `write()`, lines 524-593 | Each table is defined in three places: its columns as a string in `write()`, its rows as a list comprehension next to it, and its one-line description 30 lines above in `ABOUT`. Adding a column means editing two or three places that are not next to each other. |
| 3 | `queue`, `readiness`, `reuse_between`, `evidence`, `claim_effect`, lines 333-488 | Five tables that are computed from the finished model sit between `compute()` and `write()`. They are a separate step (nothing in `compute()` needs them) but the file does not say so. |
| 4 | `build()` and `write()` | `queue(model)` is computed twice per build: once in `write()` for the table, once in `build()` for the summary. `Relations(m.relations)` is built twice: in `compute()` and in `reuse_between()`. |
| 5 | `build()` → `write(model, bom_only, db_path)` | The verdict from the BOM alone is carried as a separate dict next to the model, keyed by `(variant, first raw row)`, and looked up again inside `write()`. |
| 6 | line 292 | `relations._dead` is read from outside its class (`compare.Relations`). |
| 7 | `build.py` and `rules.py` | Two functions are both named `to_base` and do different things: `rules.to_base(str, str)` uses the fixed `UNIT_LIST`, the one nested in `compute()` uses the `converts_to` claims. Number parsing (decimal comma) is written twice. `BASE_UNITS` is defined in `rules.py` and imported by `build.py`. |
| 8 | `rules.py` | `RefIndex` (the written references grouped by normalised key) is not a rule. `reconcile/tools.py` imports it from `rules`. |
| 9 | `ingest.py` | The file reads the raw files (`Raw`, `read_raw`) and also writes the three raw tables to SQLite (`ingest(conn, raw)`), which is the only database code outside `write()`. |
| 10 | `Model` | Parts, suppliers, lines, prices, relations and issues are plain dicts with string keys. Designs, occurrences, pairs and verdicts are dataclasses. Out of scope here (see "Not in this plan"). |

## Target

```
pipeline/
  raw.py        was ingest.py, minus ingest()
  refs.py       + RefIndex (from rules.py)
  units.py      new
  claims.py     unchanged
  rules.py      minus RefIndex, BASE_UNITS, number parsing
  model.py      new: Model
  resolve.py    new: steps 3 and 4 of the build
  compare.py    + Relations.dead_parts()
  verdict.py    + the per-occurrence verdict loop
  reports.py    new: the five derived tables
  tables.py     new: every table once, and write()
  views.sql     unchanged
  build.py      build(), Summary, the command line
  reset.py      unchanged
```

### Each file

| File | Purpose | Interface |
|---|---|---|
| `raw.py` | Read the three raw files, every value as text. | `Raw`, `read_raw(raw_dir)`, `BOM_FILE`, `ERP_FILE`, `NOTE_FILE`, `BOM_COLUMNS`, `ERP_COLUMNS`, `NOTE_FIELDS`, `COLUMNS` |
| `refs.py` | Everything about how a reference is written: its shape, its normalised key, near spellings, and the index of written references. | as today, plus `RefIndex` |
| `units.py` | Written numbers and units. | `BASE_UNITS`, `UNIT_LIST`, `number(text)`, `to_base_fixed(quantity, unit)` (today `rules.to_base`), `Units` with `Units.from_claims(claims)` and `Units.to_base(quantity, unit)` (today the nested `to_base` in `compute()`) |
| `claims.py` | The claim log, its checks, and which claims are in force. | unchanged |
| `rules.py` | The rules, `RULES`, `run_rules`, `--list`, `--show`. | unchanged, `to_base` re-exported until the test is updated |
| `model.py` | The resolved model in memory. | `Model` (same fields), plus `Model.by_type` (claims in force per type, computed once), `Model.cell(file, row, column)` (today the nested `cell`), `Model.open_items` (the queue, computed once) |
| `resolve.py` | Steps 3 and 4: from raw rows and claims in force to parts, suppliers, variants, units, BOM lines, prices and relations. One function per block of today's `compute()`, each taking the model and filling its own fields. | `group(values, links, vetoes)`, `resolve_parts(m)`, `resolve_suppliers(m)`, `read_variants(m)`, `fold_bom(m)`, `price_parts(m)`, `read_relations(m)`, and `resolve(m)` that calls them in this order |
| `compare.py` | Designs and pairs. | unchanged, plus `Relations.dead_parts()` in place of the outside read of `_dead` |
| `verdict.py` | The verdict of a design, and of each sub-assembly that carries it. | `decide(...)` unchanged, plus `occurrence_verdict(occurrence, verdict, relations, name)` (today lines 316-326) |
| `reports.py` | Tables computed from the finished model, for the agent and the app. | `queue(m)`, `readiness(m, open_items)`, `reuse_between(m)`, `evidence(m)`, `claim_effect(m)` (moved as they are) |
| `tables.py` | The database: each table defined once, and the write. | `TABLES`: a list of `Table(name, one_row_is, columns, rows)` where `rows` is a function of the model. `VIEW_ABOUT`: the descriptions of the views. `write(model, db_path)`. The raw tables (`ingest()` today) become three entries of `TABLES`. |
| `build.py` | The entry point. About 80 lines. | `compute(raw, claims, without_notes, made_by, up_to)`, `build(...)`, `Summary`, command line: all with today's signatures |

`compute()` in `build.py` becomes the list of steps, readable as the docstring at the top of the file:

```python
def compute(raw, all_claims, without_notes=False, made_by=None, up_to=None) -> Model:
    chosen = select(all_claims, without_notes, made_by, up_to)
    m = Model(raw, chosen, statuses(chosen))
    resolve(m)              # steps 3 and 4
    compare_and_decide(m)   # step 5
    return m
```

One table in `tables.py`:

```python
Table("part", "one real part: a system, a sub-assembly or a component",
      "part_id, kind, canonical_ref, description, known INTEGER, spellings",
      lambda m: [(i, p["kind"], p["canonical_ref"], p["description"], int(p["known"]), ", ".join(p["spellings"]))
                 for i, p in m.parts.items()]),
```

The BOM-only verdict moves onto the model: `build()` sets `occurrence.verdict_bom_only` on each occurrence after the
second replay, and `write()` takes the model alone.

## What other code has to follow

| File | Change |
|---|---|
| `reconcile/tools.py` | `from pipeline.refs import RefIndex, normalise`; `from pipeline.raw import read_raw` |
| `jean-code/src/claims_page.py` | `project("pipeline.ingest")` → `project("pipeline.raw")` (three places) |
| `tests/test_ingest.py` | renamed `test_raw.py`; the test of `ingest()` moves to a test of the raw tables in `test_build.py` |
| `tests/test_build.py` | `group` from `pipeline.resolve`, `queue` from `pipeline.reports` |
| `tests/test_rules.py`, `tests/conftest.py`, `tests/test_claims_page.py` | import paths only |
| `pipeline/reset.py` | none: it imports `Summary` and `build` from `pipeline.build`, which stay |

## How to know nothing changed

Before the first step, record the database for four builds: the default one, `--made-by rule`, `--without-notes`
and `--up-to 432`. For each, dump every table and view to text in a fixed order (`SELECT * FROM <name> ORDER BY 1, 2, 3, ...`
for every name in `sqlite_master`), into `.experiments/output/`. After each step, dump again and `diff`. The step is
accepted when the four diffs are empty and `uv run pytest` passes. The script goes in `.experiments/`, as the global
instructions ask.

`sqlite3 .dump` is not used for this: table creation order changes when `write()` is reorganised, and that is allowed.

## Steps

Each step is one commit, checked as above.

1. Write the dump script and record the four reference dumps.
2. `units.py`: move `BASE_UNITS`, `UNIT_LIST`, `number`, the two `to_base`. Smallest move, no caller outside `pipeline/`.
3. `RefIndex` to `refs.py`; `ingest.py` renamed `raw.py`. Update the callers listed above.
4. `model.py` and `reports.py`: move `Model` and the five derived-table functions as they are.
5. `tables.py`: `TABLES`, `VIEW_ABOUT`, `write()`. The raw tables join the list. `queue` computed once.
6. `resolve.py`: cut `compute()` into the functions listed. This is the step with the most risk of an accidental change, so it comes last, when the dumps and the other files are already stable.
7. `verdict.py` and `compare.py`: `occurrence_verdict`, `Relations.dead_parts()`, `verdict_bom_only` on the occurrence.

## Not in this plan

- **Turning the dict rows of `Model` into dataclasses** (finding 10). It touches every line that reads a part, a line or a price, including the five report functions. Worth doing after this plan, on its own.
- **`views.sql`**. `v_reuse_map` lists `V1` to `V6` as columns and `v_tender_start` names `V1`: both are fixed to this data set. Changing that is a change of behaviour.
- **The five views that only repeat a table** (`v_issue`, `v_queue`, `v_readiness`, `v_claim_effect`, `v_reuse_between`). They are the agent's interface, so they stay.
- **`claims.py`** (293 lines: the log, then the statuses). It reads in order and has one subject.

## Outside `pipeline/`, smaller and independent

| Item | Proposal |
|---|---|
| `tests/claim_detail_app.py`, `tests/claims_page_app.py` | Move to `tests/apps/`: they are one-page Streamlit apps the tests start, not tests. |
| `synth/` | Its inputs (`train.json`, `findings.json`, `settings.json`, `notes_prompt.md`, `notes_text.jsonl`, `notes_facts.json`) sit among the code. Move them to `synth/inputs/`; every read already goes through `HERE` in `generate.py` and `write_note_texts.py`. |
| `reconcile/__init__.py`, `reconcile/agent.py` | Docstrings still say "submodule". |
| `jean-code/` | `coding.py`, `research.py`, `repl.py`, the `research` and `unit-conversion` skills, `sandbox/`, `TODO_RESEARCH.md` and most of its tests belong to the general coding agent, not to this demo. Decide whether to keep the whole framework or cut it down to what `reconcile/` and the app import. Its `README.md` describes a standalone project and needs rewriting either way. |
| `jean-code/.streamlit/config.toml` | The root `.streamlit/config.toml` is a link to it. Make the root file the real one and delete the other. |
| `jean-code/.streamlit/config.toml~` | Editor backup file, untracked. Delete, and add `*~` to `.gitignore`. |
| Uncommitted work | `pipeline/reset.py`, `tests/test_reset.py`, `data/claims.demo_start.jsonl` and edits to `data/claims.jsonl` and `README.md` are not committed. Commit them before step 1 so the reference dumps match a commit. |

## As implemented

Differences from the plan above:

- `ingest.py` keeps its name and its `ingest()` function, because `jean-code/src/claims_page.py` imports `pipeline.ingest` and `jean-code/` was not to be changed. The raw tables are still written by `ingest()`, called from `tables.write()`.
- `units.py` holds functions, not a `Units` class: `to_base_by_list` (the rules) and `to_base_by_claims` (the build), with `Model.to_base()` calling the second.
- Step 5 stays in `build.py` as `compare_and_decide(m)`; only the per-occurrence part moved to `verdict.occurrence_verdict()`.
- The queue is worked out at the end of `compute()` and kept as `Model.open_items`.
- Nothing under `jean-code/` was changed, so the items of the last table that concern it are still open.
- The comparison script is `.experiments/60_refactor_keeps_database.py`. Tables are compared in stored row order, views sorted.
