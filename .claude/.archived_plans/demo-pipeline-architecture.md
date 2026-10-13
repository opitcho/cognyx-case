# Demo data architecture: raw files, a claim log, and an agent that appends to it

How the three noisy files become something an agent can query and progressively reconcile. What the demo must answer is defined in `docs/use-case-selection.md`.

The idea: every reconciliation is one row appended to a log, called a claim. The cleaned data set is not stored. A Python function computes it from the raw files and the claims, and runs again each time a claim is added.

## How it works

There are three stores. Two are kept, one is rebuilt.

```
data/raw/*.csv, *.jsonl           kept, never changed
        |
        |        rules ---+
        |        agent ---+--- append_claim() ---> data/claims.jsonl      kept, only ever appended to
        |        people --+                                 |
        v                                                   v
      build(): a Python function, no model involved.
               Loads the raw files and applies the claims in force to them
        |
        v
      out/pilot.db                rebuilt by build() every time, disposable
        raw tables, the claim table, the resolved model, the views
        ^
        |
      the agent reads it with SQL, read-only
```

1. **Raw.** The three files, loaded as text. Nothing ever edits them.
2. **Claim log.** One line per statement about the raw data: "these two spellings are one part", "this unit is 0.001 m", "this row repeats that row", "this part is superseded by that one". Rules, the agent and people all write to it through one function, and nobody can change or delete a line.
3. **Resolved model.** The parts, BOM lines, prices, designs and verdicts. `build()` computes them by applying the claims to the raw data. Nobody writes to them, the agent included. To change the resolved model, you append a claim and `build()` runs again.

One reference, start to end:

- The BOM writes `DR-1042`. The ERP writes `DR1042`. Note `TN-0132` says `PT-7731 left door leaf assy = DR-1042, same part, just renumbered`.
- A rule appends: `same_as(DR-1042, DR1042)`, because the two are equal once separators are removed.
- The agent reads the note and appends: `same_as(PT-7731, DR-1042)`, with the note's words as the quote.
- `build()` runs. The three spellings now stand for one part, so the BOM line finds its price, and the two door leaves compare as the same design.
- If a person later disagrees, they append `retract(claim 412)`. The next build leaves `PT-7731` on its own. Nothing was deleted, and the log shows who decided what.

## Names

| Name | What it is |
|---|---|
| **claim** | One line of the log: a statement about the raw data, with who made it and the evidence |
| **claim log** | `data/claims.jsonl`, the file of all claims |
| **resolution** | Computed lookup: one row per written value (a reference, a supplier name), with the part or supplier it stands for |
| **resolved model** | Every computed table and view in `out/pilot.db` |

Why "claim": a row is something a source says is true. It can be wrong, another claim can contradict it, and it can be withdrawn. "Fact" and "decision" both suggest it is settled. Wikidata works the same way under the word "statement": one known to be wrong is kept and marked deprecated, not deleted, so that others know not to add it again ([Help:Ranking](https://www.wikidata.org/wiki/Help:Ranking)).

## The claim log

### One claim

| Field | Meaning | Example |
|---|---|---|
| `id` | Position in the log, starting at 1 | `412` |
| `type` | One of the fixed types below | `same_as` |
| `subject` | What the claim is about | `ref:PT-7731` |
| `object` | The second thing, when the type needs one | `ref:DR-1042` |
| `value` | A number or a text, when the type needs one | `0.001` |
| `standing` | `asserted`: applied by the next build. `proposed`: a candidate, not applied until confirmed | `asserted` |
| `made_by` | `rule`, `agent` or `person`. Set by the code that calls the append function, never by the model | `agent` |
| `maker` | The rule's name, the model's id, or the person's name | `deepseek/deepseek-v4.1-flash` |
| `evidence` | The raw rows the claim rests on | `["note:TN-0132"]` |
| `quote` | The exact words, when the evidence is a note | `PT-7731 left door leaf assy = DR-1042, same part` |
| `reason` | One sentence in plain words | `The note says it was renumbered` |
| `as_of` | The date the claim speaks for: the note's date when it rests on a note | `2019-10-24` |

Subjects and objects point at raw data, never at computed parts. The forms are `ref:` and the reference as written, `supplier:` and the name as written, `unit:`, `bom:` or `erp:` and a row number, `cell:` with file, row and column, `note:` and a note id, `claim:` and a claim id, `option:` such as `option:speed_class_kmh=200`. Because nothing points at a computed part, a claim never goes stale when parts are regrouped.

### Claim types

The list is fixed in code. Each type has one check and one place where `build()` applies it. A claim of any other type is refused.

| Type | It says | Subject, object, value | Noise it handles |
|---|---|---|---|
| `same_as` | Two written values are one thing | Two `ref:`, or two `supplier:` | Mistyped twins, the two reference formats, supplier spellings, mistyped references in notes |
| `not_same_as` | Two written values that look alike are two things | Two `ref:`, or two `supplier:` | Look-alikes that must not merge |
| `converts_to` | One of this unit is `value` of that unit | `unit:mm`, `unit:m`, `0.001` | Mixed units |
| `duplicate_of` | This row repeats that row | Two `bom:` rows | Repeated lines |
| `value_is` | The right value of this cell is `value` | A `cell:`, a value | Repeated lines with two quantities, cost conflicts |
| `no_value` | This cell holds a filler, not a value | A `cell:` | `UNKNOWN`, `N/A`, empty |
| `mentions` | This note is about this part | A `note:`, a `ref:` | Reference only in the note text |
| `interchangeable_with` | Two components can replace each other | Two `ref:` | From notes |
| `functionally_equivalent_to` | Two sub-assemblies do the same job | Two `ref:` | From notes |
| `superseded_by` | The first part was replaced by the second | Two `ref:` | From notes |
| `obsolete` | Not to be used on new designs | A `ref:` | From notes |
| `required_for` | The part is needed because of an option | A `ref:`, an `option:` | From notes |
| `confirm` | A proposed claim should be applied | A `claim:` | |
| `retract` | A claim should no longer be applied | A `claim:` | |
| `reviewed` | This note was read and holds nothing more to claim | A `note:` | Tells "read, nothing found" from "not read yet" |

A new kind of reconciliation is a new row in this table: one type, one check, one apply step. No table changes.

### Which claims are in force

A claim is in force when it is `asserted`, or `proposed` and confirmed, and no `retract` targets it. `build()` applies only claims in force. When two claims in force say opposite things about the same pair (`same_as` against `not_same_as`), one is applied:

1. If both have an `as_of` date, the later date is applied. The generated notes contain exactly this: `TN-0191` says `BK-121` and `BK-120` are the same part, and `TN-0331`, two years later, says they are not.
2. Otherwise a person's is applied over an agent's, an agent's over a rule's, then the later `id`.

The other one is listed in `v_issue` as `claim_overridden`, with both ids. The same order settles two `value_is` claims on one cell.

### One function writes the log

`append_claim()` is the only code that opens `data/claims.jsonl`, and it opens it for appending. It takes one claim per call. Rules, the agent's tools and the command line for people all call it. Before writing, it checks:

1. The type is in the fixed list, and the subject, object and value have the shape that type needs.
2. Every `ref:`, `supplier:` and `unit:` appears, character for character, somewhere in the raw files. Every row, cell, note and claim pointed at exists.
3. A `quote` appears character for character in the text of a note listed in `evidence`.
4. The same claim (type, subject, object, value, maker) is not already in the log. If it is, the existing id is returned and nothing is written. This makes rerunning the rules harmless.

A claim that fails a check is refused with a sentence saying why, which the agent can act on. Checks 2 and 3 are how a made-up reference or a paraphrased quote is kept out of the log.

The log is a file so that `out/pilot.db` can be deleted and rebuilt from `data/raw/` and `data/claims.jsonl` with no model call, the same every time. The file is committed, so `git diff` shows exactly what a batch run of the agent added. Inside the database the log appears as the table `claim`, for querying.

## Reading the claim log in the app

This is the first thing to work. Before any agent is trusted to write claims, a person must be able to read every claim in the app, with its evidence.

The `jean-code` app has two pages today, Agent and Data. A third page, Claims, is added. It reads `data/claims.jsonl` from the folder the app was started in, the same way the Data page reads `data/raw/`. It therefore works as soon as the log exists, before `build()` or the agent do.

| Part of the page | What it shows |
|---|---|
| Header | The number of claims, split by who made them (rule, agent, person), and how many are proposed and waiting |
| Table, newest first | One row per claim: `id`, `type`, `subject`, `object`, `value`, `standing`, `made_by`, `maker`, `reason` |
| Filters | By `made_by`, `type` and `standing`, plus a text search over every field, so "everything about `DR-1042`" is one search |
| Status column | In force, proposed, confirmed by claim N, retracted by claim N, or overridden by claim N. Worked out from the log alone |
| Detail of the selected claim | Every field in full. Each item of `evidence` is shown as the raw row it points at: the BOM or ERP line, or the note's text with the `quote` highlighted |

- **It refreshes when the file changes.** The page rereads the log when the file's modification time changes, as the Data page does. While the agent works on the Agent page, its claims appear here.
- **It only reads.** There is no edit or delete on the page. A person's claims go through the approval card on the Agent page.
- **One reader for the log.** The page is part of the `jean-code` app (`jean-code/src/claims_page.py`), so this repo holds no interface code. It imports `load()` and the status logic from this repo's `pipeline/claims.py`, the same code `build()` uses, so the page and the database cannot disagree about which claims are in force.
- **Later, once `build()` exists:** a column with what each claim changed, from `v_claim_effect`.

The Agent page needs nothing new: each `append_claim` call already shows in the timeline with its arguments and its result.

## The resolved model

### How it is built

`build()` is ordinary Python and SQL. It starts from an empty database every time and does five things in order:

1. **Load the raw files** into `raw_bom`, `raw_erp` and `raw_note`, every value as text.
2. **Load the claim log** into `claim`, and work out which claims are in force.
3. **Group the written values.** Every `same_as` claim links two spellings. Linked spellings form a group, each group becomes one row of `part` (or `supplier`), and each spelling gets a row in `resolution` pointing at it.
4. **Rewrite the BOM and the prices through those groups.** For each raw BOM row it looks up the parent and the child in `resolution`, converts the quantity with the `converts_to` claims, and leaves out rows that a `duplicate_of` claim marks as repeats. That gives `bom_line`. `price` is made the same way from the ERP rows.
5. **Compare and decide** on the cleaned tables: identical and near-identical sub-assemblies, then one verdict per design.

A small example. Two raw BOM rows:

| row | `parent_ref` | `child_ref` | `quantity` | `unit` |
|---|---|---|---|---|
| 12 | `DR-1042` | `JT-218` | 2.4 | m |
| 97 | `PT-7731` | `JT 218` | 2400 | mm |

Three claims in force: `same_as(JT-218, JT 218)`, `same_as(PT-7731, DR-1042)`, `converts_to(mm, m, 0.001)`.

What `build()` writes to `bom_line`:

| parent part | child part | quantity | unit | from raw rows |
|---|---|---|---|---|
| `P17` | `P52` | 2.4 | m | 12 |
| `P17` | `P52` | 2.4 | m | 97 |

Both lines now say the same thing, so step 5 sees one design used in two variants.

`build()` runs in two situations: from the command line, and inside the agent's claim tools, which call it after each append and before answering the agent. The agent's next query therefore sees the result of its own claim. The agent never combines claims itself.

Rebuilding everything each time is affordable because the data is small: 1,538 BOM rows, 313 ERP rows, 80 notes. I expect well under a second per build. That is an estimate, measured in step 3 of the order of work. If it is too slow, the tools rebuild once per agent turn.

### Tables

| Table | One row is | Computed from |
|---|---|---|
| `raw_bom`, `raw_erp`, `raw_note` | One line of a file, all values as text, plus `row_no` | The files |
| `claim`, `claim_status` | One claim, and whether it is in force | `data/claims.jsonl` |
| `resolution` | One written value, and the part or supplier it stands for | `same_as` and `not_same_as` |
| `part` | One real part: system, sub-assembly or component | Groups of references linked by `same_as` |
| `supplier` | One real supplier | Groups of supplier names linked by `same_as` |
| `variant` | One train variant | The four repeated BOM columns |
| `unit` | One written unit, its base unit and factor | `converts_to` |
| `bom_line` | One parent-child link in one variant, quantity in the base unit | `raw_bom` through `resolution`, `unit`, `duplicate_of`, `value_is` |
| `price` | One ERP row, cost per base unit | `raw_erp` through `resolution`, `unit`, `no_value`, `value_is` |
| `relation` | One relation between parts, with the claim it comes from | The five relation types through `resolution` |
| `design` | One distinct content: a set of (component, quantity in base unit) | `bom_line` |
| `occurrence` | One sub-assembly in one variant, with its design | `bom_line`, `design` |
| `pair` | Two designs worth comparing | `design`, `relation` |
| `pair_diff` | One differing line of a near pair, with its explanation | `pair`, `relation` |
| `verdict` | The verdict for one design | `pair`, `pair_diff`, `relation` |
| `issue` | One thing that is inconsistent or undecided | Every step above |

How things that cannot be resolved are handled, so that nothing is dropped silently:

- **Groups.** `same_as` claims are added in order (person, agent, rule). A claim that would put a `not_same_as` pair in one group is skipped and listed as an issue.
- **A reference that stands for no part.** A relation whose reference resolves to nothing keeps its part empty and is listed as `unresolved_reference`.
- **A unit with no `converts_to` claim.** The quantity stays empty, an `unknown_unit` issue is listed, and the design is marked not comparable and counted.
- **A line written twice with two quantities and no `value_is` claim.** The quantity stays empty, a `two_quantities` issue is listed, and the design is marked not comparable.
- **A missing price, or two prices for one part.** The part's cost stays empty, never 0, and the build does not pick between two prices. A cost total is blocked while any of its lines has no agreed price: `v_subassembly_cost.unit_cost_eur` is empty, `blocked_by` names the components, and `known_cost_eur` gives the sum of the priced lines as a lower bound. Each such part is an open item for a person, because which price holds is not in the data.

### Comparison and verdict

- **Identical content.** A design's content is hashed on its components and quantities, as rounded decimals in the base unit, so `2.4 m` and `2400 mm` give the same hash. Two sub-assemblies with the same hash share one design, whatever their references.
- **Near pairs.** Two designs under the same system with 1 to 3 differing lines and at least 4 shared components. Each differing line gets an explanation: `interchangeable`, `superseded` or `required_by_option` when a relation says so, otherwise `unexplained`.
- **Functional pairs.** Two sub-assemblies linked by a `functionally_equivalent_to` relation.
- **Options that separate a pair.** When every variant using one design is 160 km/h and every variant using the other is 200 km/h, the pair records `speed_class_kmh`. It is shown as a fact and does not change the verdict on its own.
- **Verdict.** One per design, from one rule function applied in this order: blocked, reused, reusable, specific.

### Replays

Because everything is computed, the same `build()` answers three questions by leaving claims out:

- **What did the notes change?** `verdict_bom_only` is the verdict from a build without any claim whose evidence cites a note.
- **What did the agent add?** A build with only the rules' claims, compared with a build with all of them.
- **What did it look like at claim N?** A build with the first N claims. The reuse map before and after the agent's batch run is two builds.

### Views

The demo, the agent and any front end read these. No rule is written a second time outside them.

| View | One row is | Columns |
|---|---|---|
| `v_verdict` | One sub-assembly in one variant | `variant_id`, `system_ref`, `subassembly_ref`, `description`, `verdict`, `verdict_bom_only`, `reason`, `counterpart_ref` |
| `v_evidence` | One fact behind a verdict | `variant_id`, `subassembly_ref`, `kind`, `detail`, `claim_id`, `source_file`, `source_row` |
| `v_pair_diff` | One differing line between two near-identical sub-assemblies | `ref_a`, `ref_b`, `component_a`, `component_b`, `qty_a`, `qty_b`, `explanation`, `claim_id`, `cost_gap_eur` |
| `v_reuse_map` | One sub-assembly design | `system_ref`, `refs`, `description`, `V1` to `V6` (reference used, or empty), `verdict` |
| `v_tender_start` | One sub-assembly of `V1` | `subassembly_ref`, `action` (reuse, adapt, replace), `reason`, `cost_eur`, `priced_lines`, `total_lines` |
| `v_purchasing` | One bought part | `canonical_ref`, `refs`, `suppliers`, `min_cost_eur`, `max_cost_eur`, `total_quantity` |
| `v_content` | One line of one sub-assembly in one variant | `variant_id`, `system_ref`, `subassembly_ref`, `per_train`, `component_ref`, `quantity`, `unit`, `unit_cost_eur` |
| `v_subassembly_cost` | One sub-assembly in one variant | `variant_id`, `system_ref`, `subassembly_ref`, `per_train`, `unit_cost_eur` (empty while a line has no agreed price), `known_cost_eur`, `priced_lines`, `total_lines`, `blocked_by` |
| `v_reuse_between` | One sub-assembly of one variant, seen from another variant | `variant_from`, `variant_to`, `subassembly_ref`, `status` (same reference, same content under another reference, near, functionally equivalent, no counterpart), `counterpart_ref`, `differing_lines`, `cost_gap_eur`, `blocked_by` |
| `v_issue` | One inconsistency, or one thing left undecided | `type`, `detail`, `source_file`, `source_rows` |
| `v_queue` | One open item | `kind` (near pair, supplier names, unread note, two quantities, unresolved reference, two prices, missing price, for a person), `detail`, `claim_id`, `source_rows` |
| `v_readiness` | One count | `what` (references resolved, components with a price, quantities in a base unit, notes reviewed, open items by kind, designs not comparable), `n`, `of` |
| `v_claim_effect` | One claim in force | `claim_id`, `type`, `made_by`, `spellings_merged`, `lines_affected`, `verdicts_involved` |

## The programmatic first pass

Rules settle what is mechanical and propose the rest. A rule asserts only what needs no judgement. Counts are measured on the generated files by `.experiments/40_reconciliation_workload.py` (output in `.experiments/output/`), except where marked.

| Rule | It appends | Standing | Count |
|---|---|---|---|
| `same_key` | `same_as` for two references equal after normalising: upper case, separators removed, `O` read as `0` after the two-letter prefix | asserted | 313 links (section B). After it, all 310 BOM components find an ERP row |
| `near_key` | `same_as` for two normalised references one character apart, or with two neighbouring characters swapped | proposed | 20 + 8 = 28 pairs (sections C and G) |
| `sibling` | `not_same_as` for a near pair whose two references are children of the same parent in the same variant | asserted | 2: `DR-1042`/`DR-1043` and `VL-905`/`VL-906` (section C) |
| `unit_list` | `converts_to` from a short fixed list: `U`, `PCE`, `ea`, `EA` to `pcs`, `mm` to `m`, `g` to `kg` | asserted | 5 spellings to convert, out of 8 seen (section D) |
| `same_row` | `duplicate_of` for a BOM line written twice with the same quantity once units are converted | asserted | 19 lines the same as written (section E), plus 1 that differs only in the unit spelling (probe 42, part 2: `1 PCE` and `1 U`) |
| `filler` | `no_value` for an ERP cell holding nothing, `N/A` or `UNKNOWN` | asserted | 12 supplier cells and 7 cost cells (section D) |
| `supplier_key` | `same_as` for two supplier names equal after removing case and punctuation. Proposed when one name starts with the other | asserted, proposed | 1 asserted (`Sofra-Tec`, `Sofratec`) and 2 proposed, read by eye from the 12 spellings in section D |
| `note_field` | `mentions` for a note whose `reference` field is filled | asserted | 41 notes (section F: 80 minus 39 empty) |

The swap half of `near_key` is there because 5 of the 19 planted twins are two swapped characters (`RL-205` written `RL-025`), which "one character apart" never reaches (`.experiments/41_twins_missed_by_distance_one.py`, section A).

## What the rules leave open, and whether the agent can settle it

The rules leave about 120 items: 80 notes, 28 near pairs, 10 lines with two quantities, and the supplier names.

`.experiments/42_evidence_for_open_cases.py` checks, for each item that can be checked without a model, whether the raw files hold evidence that points to the right answer. It computes the evidence from `data/raw/` only and uses the answer key only to label each case afterwards.

| Open item | Count | What the agent can query | What the probe shows |
|---|---|---|---|
| Near pairs with both references in the BOM | 22 | BOM descriptions of each, the parents that use each, whether they are siblings, ERP description, supplier and price, notes naming both | **The evidence separates all 22.** The 16 planted twins: none are siblings, and each shares a BOM description or a parent with its original (14 share a description, 14 a parent). The 5 look-alikes and 1 other pair share no description and no parent, and where both have an ERP row, no ERP description, supplier or price either (part 1 summary) |
| Near pairs where one reference exists only in a note | 6 | The note's text, which names the part in words, and the one real reference it is near | Not measured as columns. The reference appears in no BOM or ERP row, which is itself the sign of a typo |
| Lines with two quantities | 10 | The same parent and child in the other variants | **Other variants point to the clean value in all 10.** 9 as written. The tenth has `4.3 m` in four variants and `4300 mm` in one, the same once converted, which is my reading of that line (part 2) |
| Supplier names | 3 groupings | ERP rows of two references that turned out to be one part | Merging a twin puts two names on one part: `Sofratec` and `SOFRATEC INDUSTRIES SA` on two twins, `FAIVELEY TRANSPORT SAS` and `Wabtec` on one (`SN-6050`). One row is thin evidence for `Wabtec`, so that one goes to a person |
| Notes to read | 80, of which 28 carry a relation | The note text | **Run with the agent: 28 of 28 found, in four runs out of four.** One extra claim each time, `not_same_as(RS-6620, ST-4100)` from `TN-0361`, which the note does state (`Not the same part`) and the answer key does not list. No claim on the 5 notes that use a relation word without stating a relation (`.experiments/43_agent_reads_notes.py`) |

What this does and does not establish:

- **Established:** for the near pairs and the quantities, the answer is in the data, and a handful of columns is enough to see it. An agent that queries those columns has what it needs. The evidence a twin shows and the evidence a look-alike shows do not overlap on any of the 22 pairs.
- **Established for the notes:** the agent, reading each note alone with one claim tool, records every planted relation with the right type, direction and references as written. Probe 43 ran two prompts twice each on `deepseek/deepseek-v4.1-flash`, for $0.05 in total. The prompt with only the seven definitions did as well as the one with extra guidance. The 7 mistyped references were copied as written, which is what the design needs. Linking them to their real parts needs the database and was not tested.
- **Not established:** that the agent queries the right columns and concludes correctly on the near pairs and the quantities. Only a run on the built pipeline shows that. Measuring it against the answer key is a later step.
- **Limits:** this is our generated data. The generator plants twins that copy the original's description and parent, and its notes were written by a model from a list of facts, one relation per note. Alstom's typos and notes may not be that tidy. The notes result rests on 28 relations and one model.

The probe's columns become the bar the skill gives the agent for a near pair (see "When the agent does not decide").

## The agentic layer

The agent does the judgement, one item at a time, and writes each result as a claim. It is the `Agent` class of the `jean-code` submodule, given four tools and one skill.

### Tools

`Agent` takes tools as a dict of functions and builds each tool's description from the type hints and the docstring (`jean-code/src/llm.py`, `tool_schema`). The tools are methods of one object that holds the paths and the makers' names.

| Tool | What it does | Limits |
|---|---|---|
| `describe_tables()` | Lists every table and view with one line of meaning, its columns and its row count | None needed |
| `run_sql(query)` | Runs one query and returns the rows as text | Read-only connection, so no query can change anything. At most 200 rows returned, with the number left out stated. 5 second timeout |
| `append_claim(type, subject, object, value, standing, evidence, quote, reason)` | Appends one claim in the agent's name, rebuilds, and returns the claim's id and what changed | One claim per call. The checks of "One function writes the log". `made_by = agent` is filled by the tool |
| `append_person_claim(type, subject, object, value, evidence, reason)` | Appends one claim in the person's name, rebuilds, and returns the same | Needs the person's approval before every call. Live sessions only |

`append_claim` returns the effect in words, for example: `claim 412 in force. PT-7731 and DR-1042 are now one part. Designs: 81 to 80. Verdicts changed: DR-1042 in V3, specific to reused.` A refusal returns the reason, for example: `refused: the quote is not in note TN-0132`. The agent sees the result of its own claim before deciding the next one.

There is no tool to update or delete. To undo, a `retract` is appended.

### When the agent does not decide

The agent's own claims are applied at once: they are `asserted` and marked `made_by = agent`. What it cannot decide goes to a person, in three steps.

1. **The agent appends its best guess as `proposed`**, with the evidence for and against in `reason`. A proposed claim is not applied. It shows in `v_queue` with kind `for a person`.
2. **In a live session the agent asks.** It states the question and shows the rows on both sides. This happens when the person asks what needs their decision, or when an open item blocks the answer to their question.
3. **The person answers in words, and signs with one click.** The agent turns the answer into a claim and calls `append_person_claim`. That tool is on the `Agent`'s `needs_approval` list, so the turn stops and the interface shows the exact claim with Approve and Deny, the same card the app shows today before running a shell command. On Approve the claim is logged with `made_by = person`. On Deny nothing is logged and the agent gets the person's reason.

The model can therefore never write a claim in a person's name: only an approval does.

What sends an item to a person:

| Trigger | Enforced by | Example on the generated data |
|---|---|---|
| The claim would contradict a claim in force made by a person or resting on a note | The tool refuses the asserted claim and says to propose it | The agent wants `same_as(BK-120, BK-121)` while `TN-0331` says they differ |
| A `same_as` between two siblings | The tool, same way | `VL-905` and `VL-906` |
| The evidence does not meet the bar | The skill | A near pair that shares no description and no parent, yet has the same supplier and price |
| The claim rests on outside knowledge, not on rows | The skill | `Wabtec` and `Faiveley` are one supplier by ownership |
| The claim settles a price | The tool refuses a `value_is` on an ERP price cell from the agent | A part with two prices under its two references: the agent shows both rows and asks, and the person's answer is recorded through `append_person_claim` |

The bar for a near pair, taken from probe 42:

- Assert `confirm` on the proposed `same_as` when the two references are not siblings and share a BOM description or a parent, or when a note says they are one part. All 16 planted twins meet this.
- Assert `not_same_as` when they are siblings, or a note says they are two parts, or they share nothing: no description, no parent, and a different ERP description, supplier and price. All 5 look-alikes and the other pair meet this.
- Otherwise propose, and leave it for a person. This is the mixed case: no shared description or parent, yet the same supplier or price.

To demonstrate this, the batch run is expected to leave at least the `Wabtec` question open. That is one case, and it depends on the agent following the skill. See "Changes needed in other documents" for planting cases that are ambiguous by construction.

### Skill

One skill, `skills/reconciliation/SKILL.md`, loaded like any `jean-code` skill. It holds:

- what each table and view means, and which to query for which question
- the claim types with one example each
- how to settle each kind of item in `v_queue`, with the bar above for near pairs. For a line with two quantities: look at the same parent and child in the other variants, and append `value_is` citing those rows when they agree
- when to propose and ask a person
- the rule that an answer names the rows it rests on and states what `v_readiness` leaves unresolved

### Two ways to run it

| | Batch | Live |
|---|---|---|
| Started by | `python -m reconcile.batch` | A question in the terminal or the Streamlit app |
| Works on | Each item of `v_queue`, notes oldest first. One item per agent turn, each with a fresh conversation | Whatever the question touches |
| Its own claims | Applied at once | Applied at once |
| What it cannot decide | Left as `proposed`, for a person | Asked, then signed by the person through `append_person_claim` |
| Output | New lines in `data/claims.jsonl`, reviewed with `git diff` and committed | An answer that cites rows |

Both use the same agent, tools and skill, except that the batch agent is not given `append_person_claim`. Before the demo, the batch run settles what it can, so the headline numbers come from a committed log. During the demo, the items left for a person are settled live.

### Limits

- **Cost.** The batch run takes a `Budget` with a limit in dollars (`jean-code/src/usage.py`). When it is spent, the run stops and prints how many items were left.
- **Calls.** One turn allows at most 10 rounds of tool calls (`max_tool_rounds`, the `Agent` default). With about 120 items, the worst case is about 1,200 model calls. My estimate is 3 to 4 per item, so about 400.
- **Input size.** The 80 notes total about 10,000 characters (probe 40, section F), so reading them is not what costs.
- **One writer.** The batch run works items one after another. Two processes appending at once are not supported.

### Where it is reached from

| Entry point | How |
|---|---|
| Batch | `python -m reconcile.batch --max-cost 2` |
| Terminal | `python -m reconcile.chat`, which hands `reconciliation_agent()` to the REPL loop of `jean-code` |
| Streamlit app | The `jean-code` app, started from this repo, with the agent on the Agent page and the log on the Claims page. See "Changes in jean-code" |
| Tests | `reconciliation_agent(client=...)` with a scripted client, as `jean-code`'s own tests do with `FakeClient` |

`reconciliation_agent()` is a function that returns an `Agent`, the same form as `coding_agent()`.

## Questions that take several steps

Five questions that one row of one view cannot answer. Each needs a comparison across variants, a walk from a component up to the variants that use it, or a cost roll-up. The answers below are computed from `data/clean/`, the generator's files before noise, by `.experiments/44_multi_step_questions.py`. They are what the resolved model should give once every claim is in. On the real database the agent must also say what `v_readiness` still leaves open.

| Question | Steps the agent takes | Answer on the generated data |
|---|---|---|
| Which sub-assemblies of `V1` can I reuse in `V2`? | `v_reuse_between` from `V1` to `V2`. For each row that is not "same reference", the content on both sides. For each blocked row, the claim behind it | All 40 have the same content in `V2`. 36 under the same reference, 4 under another: `HC-6001` as `CL-0931`, `KP-0457` as `DC-3001`, `RG-0212` as `TC-8100`, `ST-4100` as `MP-4418`. 4 contain an obsolete or superseded part: `DR-1043`, `FC-6100`, `HT-5300`, `KP-0457` |
| `V3` and `V4` differ only by speed class. What differs, and is each difference justified? | `v_reuse_between` from `V3` to `V4`. `v_pair_diff` for the near ones. The relations on the differing parts | 26 are the same. `LR-1500` has the same content as `PB-2281`. 4 are near: the air duct (`VL-905` added) and the left door leaf (`JT-305` added), both required for 200 km/h by a note, and the glazed partition (`BK-367` added) and the sliding step (12 bolts against 16), with no note. The other 9 are different designs |
| `TH-415` is superseded. What is affected, and is the replacement already in use? | The `superseded_by` relation. `v_content` for every sub-assembly holding `TH-415`. The same for `TH-450`. Both prices | It is in `HT-5300` on all six variants. `TH-450` is already used in `TC-8437` on `V4` and `V6`. Unit cost goes from 59.43 to 78.88 EUR |
| What does the door system cost in each variant? | `v_subassembly_cost` for the system, times the quantity per train, summed. The count of unpriced lines | From 229,555.56 EUR on `V1` to 515,070.20 EUR on `V6`, with every line priced |
| What would `V5` save by using seat frame `SF-9020` in place of `SF-9064`? | `v_pair_diff` for the pair. The quantity of the sub-assembly per train on `V5` | 11.48 EUR per unit, 200 per train: 2,296.00 EUR per train |

What they need:

- **Three more views**, listed under "Views": `v_content`, `v_subassembly_cost` and `v_reuse_between`. The first question is the one you asked, and `v_reuse_between` exists for it.
- **No new tool.** I estimate 2 to 5 `run_sql` calls per question, inside the 10 rounds a turn allows.
- **A possible fifth tool later.** If comparing two arbitrary sub-assemblies line by line proves unreliable in SQL when the agent is first tried, add `compare_subassemblies(a, b)`, which returns the differing lines with prices and the relations on them.

## Changes in jean-code

Two changes are needed, both in `jean-code/src/app.py`.

1. **The agent.** `new_chat()` builds its agent by calling `coding_agent()` directly. It should build the agent named by the environment variable `JEAN_AGENT` (a module and a function), and fall back to `coding_agent` when the variable is not set. The app passes the same arguments it passes today. The approval card already shows any tool's name and arguments with Approve, Deny and a reason, so it needs nothing.
2. **The Claims page.** A third page, added to the app itself: `jean-code/src/claims_page.py`, next to `data_page.py`, and `PAGES = ("Agent", "Data", "Claims")`. All interface code stays in `jean-code`. The page reads `data/claims.jsonl` under the directory the app is started in and imports that project's `pipeline` package for the log's logic.

The app is started from this repo with the variable set. It looks for the named agent in the directory it is started in:

```
JEAN_AGENT=reconcile.agent:reconciliation_agent uv run --env-file .env streamlit run jean-code/src/app.py
```

Where the change lives:

- The submodule `jean-code/` is on a local branch named `alstom`, at the same commit as `main` of `opitcho/jean-code`, with uncommitted edits. That branch is the project's version of `jean-code`. No separate fork is needed, since it is the same repository.
- To save work: commit inside `jean-code/`, push with `git push -u origin alstom`, then in this repo run `git add jean-code` and commit. This repo then records which commit of `jean-code` it uses.
- Adding `branch = alstom` under the submodule in `.gitmodules` makes `git submodule update --remote` follow that branch.
- A change that is useful to `jean-code` in general, such as `JEAN_AGENT`, reaches `main` by merging or cherry-picking it there. Changes that only make sense for this demo stay on `alstom`.

## Later steps, not in this plan

- **Scoring against the answer key.** Counting, per kind of case, what the rules and the agent got right against `data/truth/`, and showing it in the app.
- **A set of questions with known answers**, run automatically.

## Code files

| File | Why it exists | Interface |
|---|---|---|
| `pipeline/claims.py` | The claim types, their checks, and the only code that writes the log | `TYPES`, `append_claim(log_path, raw, claim) -> int` raising `ClaimRefused`, `load(log_path) -> list[Claim]`, `in_force(claims, without_notes=False, made_by=None, up_to=None) -> list[Claim]` |
| `pipeline/ingest.py` | Loads the three files as text, stops on a line it cannot parse | `ingest(conn, raw_dir) -> dict[file, row_count]` |
| `pipeline/rules.py` | The eight rules. Each returns claims and writes nothing | `RULES`, `run_rules(log_path, raw_dir) -> dict[rule, count]` |
| `pipeline/refs.py` | Normalising and the two closeness tests | `normalise(ref) -> str`, `one_apart(a, b) -> bool`, `swapped(a, b) -> bool` |
| `pipeline/build.py` | The five steps of "How it is built" | `build(raw_dir, log_path, out_db, without_notes=False, made_by=None, up_to=None)` |
| `pipeline/compare.py` | Step 5, first half: designs, pairs and differing lines | `content_hash(lines) -> str`, `build_designs(conn)`, `find_near_pairs(conn, max_diff=3, min_shared=4)`, `explain_diff(diff, relations) -> str` |
| `pipeline/verdict.py` | Step 5, second half: one rule function for every verdict | `decide(design, pairs, relations) -> (verdict, reason, counterpart)`, `build_verdicts(conn)` |
| `pipeline/views.sql` | Every view. The single place where output columns are defined | Run by `build()` |
| `reconcile/tools.py` | The four tools | `Workbench(db_path, log_path, raw_dir, agent_name, person_name)` with `describe_tables()`, `run_sql(query)`, `append_claim(...)`, `append_person_claim(...)` |
| `reconcile/agent.py` | Builds the agent. It accepts the arguments the app passes to `coding_agent` (`sandbox`, `reasoning`) and has no shell, so `sandbox` is ignored | `reconciliation_agent(model, sandbox=False, reasoning=None, budget=None, client=None, live=True) -> Agent` |
| `reconcile/batch.py`, `reconcile/chat.py` | The two entry points | `python -m reconcile.batch [--max-cost N]`, `python -m reconcile.chat` |
| `skills/reconciliation/SKILL.md` | What the agent is told | |
| `tests/` | The append checks, which claims are in force, the rules' counts, unit conversion and the content hash | `pytest` |

Two facts about the submodule shape the layout:

- `jean-code/src` holds plain modules named `agent`, `tools`, `skills`, `config` and `usage`, with no package around them. Our folders are therefore `pipeline/` and `reconcile/`, never `agent/` or `tools/`, or the imports would collide.
- `pipeline/` needs only the standard library. `reconcile/` needs `jean-code`'s dependencies, so this repo gets a `pyproject.toml` that lists them. It has none today.

Size, as an estimate: about 1,000 to 1,200 lines of Python and SQL, of which about 300 are the agent layer. The Claims page, about 150 lines, is in `jean-code`.

## Order of work

1. `claims.py` with its tests: the checks, which claims are in force, opposite claims.
2. The Claims page in `jean-code`. Append a few claims by hand from the command line and read them in the app.
3. `ingest.py`, `refs.py` and `rules.py`. Run the rules and compare each count with probe 40. A difference means the rule or the probe is wrong. Read the rules' claims in the app.
4. `build.py` up to `bom_line` and `price`, and `v_readiness`. Time one build.
5. `compare.py`, `verdict.py` and the views.
6. `reconcile/tools.py`, the skill, `reconciliation_agent()` and `JEAN_AGENT`. Settle five queue items in the app and watch the claims arrive on the Claims page.
7. The batch run. Review the new claims in the app and with `git diff`, then commit the log.
8. The person's path in the app: ask, answer, approve.
9. The five questions of "Questions that take several steps", asked in the app and compared by eye with probe 44.

Steps 1 to 3 give a claim log that can be read in the app, with no model involved. Steps 4 and 5 add a queryable database.

## Changes needed in other documents

- **`docs/use-case-selection.md`:** steps 0a to 0c (cleaning, note reading, second pass) become "rules append claims, the agent appends claims, build". The seven relations stay as they are.
- **`docs/use-case-selection.md`:** add the rule for options that separate a pair, and quote the full case question including "and where are the inconsistencies?", with `v_issue` named as its answer.
- **The generator (`synth/`):** plant two or three cases that are ambiguous by construction, with the expected outcome "left for a person". For example a near pair with the same supplier and price, no shared description and no shared parent. Today probe 42 finds no such case, so the only item sure to reach a person is `Wabtec`.

## Open decisions

1. **Where the log lives.** This plan uses a file, `data/claims.jsonl`, copied into the table `claim` at each build. The alternative is a table only, which is one store instead of two but makes the database something that cannot be deleted.
2. **How many ambiguous cases to plant, and of which kinds.** See the generator change above. Each one is a moment in the demo where the agent stops and asks.
