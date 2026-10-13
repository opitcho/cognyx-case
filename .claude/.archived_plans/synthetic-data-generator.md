# Synthetic data generator

Replaces `.claude/.plans/synthetic-pilot-data.md`. The use cases this data serves are in `docs/use-case-selection.md`.

The plan has six parts, in this order:

1. The three files we are building, column by column.
2. How the clean version of those files is generated.
3. How noise is added to the clean version.
4. The ground truth written alongside.
5. The code: each file, why it exists, and its functions.
6. The checks that prove the data is right.

## 1. What we are building

Three files in `data/raw/`. They are the only thing the demo pipeline will ever read.

### `plm_bom_export.csv`

The multi-variant engineering BOM. **One row is one parent-child link in one train variant.** Comma separated, UTF-8, decimal point.

| Column | Type | Meaning |
|---|---|---|
| `variant_id` | text | Which of the six train variants this row belongs to: `V1` to `V6` |
| `cars` | integer | Number of cars of that variant: 6, 7, 8 or 10 |
| `speed_class_kmh` | integer | 160 or 200 |
| `interior` | text | `suburban`, `regional` or `intercity` |
| `level` | integer | Level of the child: 2 system, 3 sub-assembly, 4 component |
| `parent_ref` | text | Reference of the parent. For level 2 rows, the variant id |
| `child_ref` | text | Reference of the child |
| `description` | free text | Name of the child |
| `quantity` | decimal | Quantity of the child in one parent |
| `unit` | text | Unit of the quantity |

Example, clean:

```
variant_id,cars,speed_class_kmh,interior,level,parent_ref,child_ref,description,quantity,unit
V1,6,160,suburban,2,V1,DOOR-SYS-01,Door system,1,pcs
V1,6,160,suburban,3,DOOR-SYS-01,DR-1042,"Door leaf assembly, left",12,pcs
V1,6,160,suburban,4,DR-1042,JT-218,Door seal,2.4,m
V1,6,160,suburban,4,DR-1042,AC-501,Door actuator,1,pcs
```

A part with several children has one row per child, with the parent repeated: above, `DR-1042` has two rows, one for the seal and one for the actuator. The content of a sub-assembly in a variant is every row with that `variant_id` and that `parent_ref`. A component used in several sub-assemblies likewise has one row under each parent.

### `erp_items.csv`

The purchasing item list. **One row is one component reference**, with who sells it and at what price. Sub-assemblies have no row. Semicolon separated, UTF-8, decimal comma.

| Column | Type | Meaning |
|---|---|---|
| `item_ref` | text | Reference of the component, in the ERP's format (no hyphen) |
| `description` | free text | Name of the component |
| `supplier` | text | Supplier name |
| `unit_cost_eur` | decimal | Price of one `price_unit` |
| `price_unit` | text | Unit the price applies to |

Example, clean:

```
item_ref;description;supplier;unit_cost_eur;price_unit
JT218;JOINT DE PORTE;Faiveley;38,50;m
AC501;ACTIONNEUR DE PORTE;Faiveley;412,00;pcs
```

### `technical_notes.jsonl`

Engineering change and quality notes. **One line is one note.** About 80 notes.

| Field | Type | Meaning |
|---|---|---|
| `note_id` | text | `TN-` and four digits |
| `date` | ISO date | When the note was written |
| `reference` | text | The part the note is about. Often empty |
| `text` | free text | The note. May name a second part |

Example, clean:

```
{"note_id": "TN-0231", "date": "2025-03-14", "reference": "AC-501", "text": "Actuator AC-501 superseded by AC-560 since NCR 2291."}
```

### How the three files connect

- A component's `child_ref` in the BOM and its `item_ref` in the ERP are the same part.
- A note points to a BOM part through `reference`, or through a reference written inside `text`.
- A note can state one of seven relations between parts. These relations are what make the notes useful at every layer of the demo.

| Relation | Meaning |
|---|---|
| `same_as` | Two references are one part |
| `not_same_as` | Two look-alike references are distinct parts |
| `interchangeable_with` | Two components are equivalent or approved substitutes |
| `functionally_equivalent_to` | Two sub-assemblies do the same job with different designs |
| `superseded_by` | A part has been replaced by another |
| `obsolete` | A part must not be used on new designs |
| `required_for` | A part is needed because of a variant option |

## 2. Generating the clean data

Clean means: every reference is spelled one way, every unit is the base unit, BOM text is English, ERP text is French, and the three files join perfectly. Four steps produce it.

### Step 1: the train family

Build the six variants and their parts.

| `variant_id` | `cars` | `speed_class_kmh` | `interior` | Role |
|---|---|---|---|---|
| `V1` | 6 | 160 | suburban | Oldest variant. Gets most of the noise. Used for the tender view |
| `V2` | 7 | 160 | suburban | |
| `V3` | 8 | 160 | regional | Differs from `V4` by speed class only |
| `V4` | 8 | 200 | regional | |
| `V5` | 10 | 160 | regional | |
| `V6` | 10 | 200 | intercity | |

Each variant has the same shape:

- **7 systems:** car body, running gear, power, doors, HVAC, interior, braking. A system has the same reference in all variants.
- **40 positions for a sub-assembly:** 8 in each of doors, HVAC and interior, 4 in each of the other four systems. A position is a place in the train, such as "door leaf, left".
- **3 to 8 components per sub-assembly**, 5 on average.

That gives about 247 BOM rows per variant and about 1,480 in total.

References follow fixed patterns: `DOOR-SYS-01` for a system, two letters, a hyphen and three or four digits for a sub-assembly or component (`DR-1042`). The two letters are fixed per kind of part. Any two references differ by at least two characters, except the look-alike pairs planted in step 2.

Each component has one supplier, one price and one base unit (`pcs`, `m` or `kg`).

### Step 2: decide what is shared

This step creates the connections the demo must find. For each of the 40 positions, decide which design each variant uses.

The planted findings are not invented by code. They are written by hand, one entry each, in a data file (`synth/findings.json`, described in part 5). Each entry states what is planted, where, which note goes with it, and the expected verdict. Anyone can read that file and see exactly what the data is supposed to contain.

| Kind of position | Count | What goes in it |
|---|---|---|
| Common | 18 | One design under one reference in all six variants |
| Split by option | 10 | Two or three designs chosen by cars, speed class or interior, differing by 4 lines or more |
| Planted finding | 12, in doors, HVAC and interior | One or more of the findings below |

Definitions used here:

- **Content** of a sub-assembly: its components and their quantities.
- **Identical:** same components, same quantities.
- **A differing line:** a component on one side only, a component swapped for another, or the same component in a different quantity. A swap counts as one line.

The planted findings, with the minimum of each:

| Finding | How it is built | Min |
|---|---|---|
| Clone under another reference | Copy a design into another variant under a new reference | 5 |
| Clone with one dead reference | The same, and one of the two references is obsolete or superseded | 2 |
| Near pair, unexplained | Copy a design, change 1 to 3 lines, between variants with the same options | 5 |
| Near pair, interchangeable parts | The changed line is a swap between two components that are interchangeable | 3 |
| Near pair, one part replaced | The changed line is a swap where one component superseded the other | 2 |
| Near pair, required by option | Between a 160 and a 200 km/h variant, the extra part serves the speed class | 3 |
| Functional pair | Two designs in one position, no shared component, different suppliers | 2 |
| Blocked | A shared or nearly shared sub-assembly that contains an obsolete or superseded component | 3 |
| Look-alike sub-assemblies | Same name, 4 or more differing lines | 5 |
| Look-alike references | Two real parts one character apart, such as `DR-1042` and `DR-1043` | 5 |

Every entry carries its expected verdict (reused, reusable, blocked or specific) twice: from the BOM alone, and with the notes. Designs in common positions are reused; designs in positions split by option are specific.

`V1` hosts at least one finding of each kind.

### Step 3: write the notes

Each note starts as a list of facts, and its text is written from those facts.

**The facts.** About 30 notes carry one relation. Every relation needed by a finding of step 2 gets a note:

| Finding | Relation in its note |
|---|---|
| Clone under another reference | `same_as`, on at least 5 |
| Clone with one dead reference | `obsolete` or `superseded_by` |
| Near pair, interchangeable parts | `interchangeable_with` |
| Near pair, one part replaced | `superseded_by` |
| Near pair, required by option | `required_for`, on some |
| Functional pair | `functionally_equivalent_to` |
| Blocked | `obsolete` or `superseded_by` |
| Look-alike references | `not_same_as`, on at least 3 |

About 50 notes carry no relation: inspection result, torque check, drawing update, delivery delay, closed non-conformity, test report. They also mention part references. Three of them use a relation word in another sense, such as `not obsolete, keep in stock`.

Two pairs of notes contradict each other on the same part at different dates. The later one wins.

**The text.** An LLM writes one text per note from its facts and a style sheet. This is done once; the texts are saved in the repo and the generator only reads them. Each text is checked: the references in the facts must appear in it exactly, and no other reference may appear.

The notes are the one file with no clean version. A note is written once, already in its final language and with its final spelling, because rewriting a text twice adds work and no information. The ground truth records, for each relation, the real references next to the references as written.

### Step 4: write the clean files

Turn steps 1 and 2 into rows in the formats of part 1, and write them to `data/clean/`: a clean `plm_bom_export.csv` and a clean `erp_items.csv`, same columns as the final files. Nothing is decided here.

## 3. Adding the noise

Noise is applied to the clean BOM and ERP rows of step 4, one kind at a time, and the result is written to `data/raw/`. Every changed value is logged with its clean value. The files in `data/clean/` are never touched.

| # | Noise | What changes | Example | Amount |
|---|---|---|---|---|
| 1 | Mistyped twin of a reference | BOM `child_ref` and `parent_ref`: some occurrences of a part use a wrong spelling. The twin gets its own ERP row | `DR-1042` becomes `DR 1042`, `DR-1O42`, `DR-10422` | 5% of references |
| 2 | Repeated BOM line | A BOM row is written twice, sometimes with another quantity | quantity 4 and 6 | 2% of rows, a third with another quantity |
| 3 | Mixed units | BOM `quantity` and `unit`, ERP `price_unit` and `unit_cost_eur`, converted together | `2.4 m` becomes `2400 mm`; `pcs` becomes `ea`, `U`, `PCE` | 10% of items |
| 4 | Language | BOM `description` to French, ERP `description` to English, note text to the other language or mixed | `Door seal` becomes `JOINT DE PORTE` | 15% of descriptions; notes half French, a third English, rest mixed |
| 5 | Cost conflict | ERP `unit_cost_eur` of a twin row | 38,50 and 41,20 | 3% of items |
| 6 | Supplier name variants | ERP `supplier` | `Faiveley`, `FAIVELEY TRANSPORT SAS`, `Wabtec` | Two suppliers, three spellings each |
| 7 | Missing values | ERP `supplier` or `unit_cost_eur` emptied or set to `UNKNOWN` | | 3% of cells |
| 8 | Reference only in the note text | Notes `reference` emptied | | Half of the notes with a relation |
| 9 | Mistyped reference in a note | Notes `reference` or a reference inside `text` | `DL-331O` for `DL-3310` | A quarter of the relations |

Noise 8 and 9, and the language of a note, are decided in step 3 when the note is written. Noise 1 to 7 are applied by code to the clean rows.

The same rows as in part 1, after noise:

```
V1,6,160,suburban,3,DOOR-SYS-01,DR-1O42,"Door leaf assembly, left",12,pcs
V1,6,160,suburban,4,DR-1O42,JT-218,JOINT DE PORTE,2400,mm
V1,6,160,suburban,4,DR-1O42,AC-501,Door actuator,1,ea
```

### Rules so that noise does not destroy the findings

| Rule | Why |
|---|---|
| A twin never equals another real reference or another twin | Otherwise two parts become one and the answer key is wrong |
| A twin is never made from either member of a look-alike pair | The look-alikes test that the tool does not over-merge |
| When a sub-assembly gets a twin in a variant, the twin is used on its own row and as the parent of its components | The tree stays readable inside a variant |
| System references are never changed | Near pairs are compared within a system |
| A repeated line with another quantity is never placed inside a planted sub-assembly | It would make a clone no longer identical |
| Units are only converted to convertible units | The clean quantity must be recoverable |
| No missing price on a component of `V1`, or on the differing lines of a near pair, except one pair | The tender view and the cost gaps need prices |
| A mistyped reference in a note stays closer to its real part than to any other | The relation must resolve to one part |

### Things the noise must do

- At least 2 clones are identical only after references are cleaned.
- At least 2 clones are identical only after units are converted.
- `V1` receives at least 40% of all changes, and two suppliers carry most of the supplier and cost noise.

## 4. The ground truth

The demo pipeline never reads any of this. Only the scoring does.

| File | One row is | What it is used for |
|---|---|---|
| `data/clean/plm_bom_export.csv` | Same as the raw BOM, before noise | The true BOM. Content comparisons are checked against it |
| `data/clean/erp_items.csv` | Same as the raw ERP file, before noise | The true list of parts, suppliers and prices |
| `data/truth/changes.csv` | One changed value: file, row, field, clean value, written value, kind of noise | Shows exactly what was dirtied. Scoring reference cleaning and unit conversion |
| `data/truth/relations.csv` | One relation in a note: note, relation, the real references, the references as written | Scoring note reading |
| `data/truth/findings.csv` | One planted finding: kind, the two sub-assemblies and their variants, the differing lines, the notes involved, the cost gap, the two expected verdicts | Scoring the comparisons and the final answer |
| `data/truth/verdicts.csv` | One sub-assembly design: its variants, the verdict from the BOM alone, the verdict with the notes | The reuse map, and showing what the notes changed |

The clean files have the same columns as the raw ones. "Here is the clean file, here is the dirty file, here is the list of differences" is the whole ground truth for the BOM and the ERP.

## 5. The code

The idea in one sentence: two hand-written data files say what the train is and what is planted in it; one script turns them into clean files; one script dirties them and logs every change; one script checks the result.

All in `synth/`. Python 3.12, standard library only. Rows are plain dictionaries with the same keys as the columns of part 1, so the data in the code looks like the data in the files.

### Data files

| File | What it holds | Why it is data and not code |
|---|---|---|
| `train.json` | The six variants, the seven systems, the 40 positions, the kinds of part (prefix, English name, French name, base unit, price range), the suppliers and their spellings | It is content, not logic. It can be read and corrected without reading Python |
| `findings.json` | One entry per planted finding | It is the list of what the demo must find. It must be readable on its own |
| `settings.json` | The seed and the amount of each kind of noise | So that no rate is buried in the code |
| `notes_text.jsonl` | The written note texts, one per note | Written once by an LLM, then fixed |

One entry of `findings.json`:

```json
{
  "id": "F07",
  "kind": "near_pair_interchangeable",
  "position": "door leaf, left",
  "a": {"variant": "V3", "ref": "DR-1042"},
  "b": {"variant": "V5", "ref": "DR-1077"},
  "change": {"swap": "JT-218", "for": "JT-220"},
  "note": {"relation": "interchangeable_with", "refs": ["JT-220", "JT-218"]},
  "verdict_bom_only": "reusable",
  "verdict_with_notes": "reusable"
}
```

### `clean.py`

Builds the clean rows from `train.json` and `findings.json`. It decides nothing about findings: it fills the 28 ordinary positions with random components, and applies the entries of `findings.json` to the other 12.

```python
def build_bom(train, findings, rng) -> list[dict]
    """Clean BOM rows, with the columns of plm_bom_export.csv."""

def build_erp(bom, train, rng) -> list[dict]
    """One clean row per component found in the BOM, with the columns of erp_items.csv."""

def build_note_facts(findings, train, settings, rng) -> list[dict]
    """One fact list per note: relation, real references, references as written,
    reference in the field or only in the text, language. Covers the notes
    required by the findings, the plain notes and the contradicting pairs."""
```

### `noise.py`

One small function per kind of noise, numbered as in part 3. Each takes rows, changes some of them in place, and returns the list of changes. None of them knows about findings: they are given a set of things to leave alone.

```python
def protected(findings, bom) -> dict
    """Computed once from findings.json: the references that must not get a twin,
    the rows that must not get a different quantity, the items that must keep a price.
    This is where the rules of part 3 live."""

def reference_twins(bom, erp, rate, skip, rng) -> list[dict]
def repeated_lines(bom, rate, skip, rng) -> list[dict]
def mixed_units(bom, erp, rate, rng) -> list[dict]
def language_switch(bom, erp, train, rate, rng) -> list[dict]
def cost_conflicts(erp, rate, rng) -> list[dict]
def supplier_variants(erp, train, rng) -> list[dict]
def missing_values(erp, rate, skip, rng) -> list[dict]
```

Every change is one dictionary: `file`, `row`, `field`, `clean_value`, `written_value`, `kind`.

### `write_note_texts.py`

Run by hand, once. For each note fact it asks an LLM for a text, using `notes_prompt.md`, checks that the text contains the references of the fact and no others, and saves the result to `notes_text.jsonl`. It is separate so that normal generation needs no API key and gives the same notes every time.

```python
def write_texts(facts, prompt_path, out_path) -> None
def check_text(fact, text, all_refs) -> list[str]   # problems found, empty if none
```

### `generate.py`

The only script to run: `python -m synth.generate`. It reads top to bottom as the plan does.

```python
def main():
    train, findings, settings = load("train.json"), load("findings.json"), load("settings.json")
    rng = random.Random(settings["seed"])

    # part 2: clean
    bom = build_bom(train, findings, rng)
    erp = build_erp(bom, train, rng)
    facts = build_note_facts(findings, train, settings, rng)
    write_csv("data/clean/plm_bom_export.csv", bom)
    write_csv("data/clean/erp_items.csv", erp, french=True)

    # part 3: noise
    skip = protected(findings, bom)
    changes = []
    changes += reference_twins(bom, erp, settings["twins"], skip, rng)
    changes += repeated_lines(bom, settings["repeats"], skip, rng)
    ...  # the five others, in the order of part 3
    write_csv("data/raw/plm_bom_export.csv", bom)
    write_csv("data/raw/erp_items.csv", erp, french=True)
    write_jsonl("data/raw/technical_notes.jsonl", notes_from(facts, load_texts()))

    # part 4: ground truth
    write_csv("data/truth/changes.csv", changes)
    write_csv("data/truth/relations.csv", relations_from(facts))
    write_csv("data/truth/findings.csv", findings)
    write_csv("data/truth/verdicts.csv", verdicts_from(train, findings))
```

### `check.py`

Run after generation: `python -m synth.check`. It reads only files on disk, so it tests what was written. It prints a report and exits with an error if a check fails.

```python
def check_formats(raw_dir) -> list[dict]
def check_changes_explain_everything(clean_dir, raw_dir, changes) -> list[dict]
def check_findings_are_in_clean_data(clean_bom, findings) -> list[dict]
def check_noise(changes, settings, findings) -> list[dict]
def check_notes(notes, relations, clean_bom) -> list[dict]
```

Each returns a list of results: `name`, `expected`, `found`, `passed`.

## 6. Checks

The report prints, for each check, what is tested, what is expected, what was found, and pass or fail.

**The files are what part 1 says**

1. Each raw file parses with its separator and decimal mark and has exactly the listed columns.
2. In every variant, every parent of a sub-assembly or component row exists one level up.

**The ground truth matches the files**

3. The clean files plus `changes.csv` give exactly the raw files.
4. No written reference equals the real reference of another part.

**The findings are really in the data**

5. Comparing the content of sub-assemblies in the clean BOM gives exactly the clones and the near pairs listed in `findings.json`, and no others.
6. Each functional pair shares no component. Each look-alike pair of sub-assemblies differs by 4 lines or more.
7. Each kind of finding meets its minimum. `V1` has one of each and a price on every component.

**The noise and the notes matter**

8. Each kind of noise is within a quarter of its amount. `V1` has at least 40% of the changes.
9. At least 2 clones are no longer identical in the raw BOM because of a mistyped reference, and at least 2 because of a unit.
10. At least 12 designs have a different verdict with the notes than without.
11. Every note text contains the references of its facts and no others, and every written reference is closer to its real part than to any other.

**Repeatable**

12. Two runs give identical files.

The report ends with 10 random notes and 10 random changes, for a read-through.

## Order of work

1. `train.json`, with the doors system written in full first, then `findings.json`.
2. `clean.py` and the clean half of `generate.py`. Checks 2, 5, 6, 7.
3. Note facts, `notes_prompt.md`, `write_note_texts.py`, then run it. Check 11.
4. `noise.py` and the rest of `generate.py`. Checks 1, 3, 4, 8, 9.
5. `check.py` complete, full run, read the report, adjust `settings.json`.
6. Change `.gitignore` so that `data/clean/`, `data/raw/` and `data/truth/` are committed. It currently ignores all of `data/`.

## Defaults to confirm

1. 18 of the 40 positions are common to all six variants. This sets the headline number of the reuse map.
2. Identical content includes quantities.
3. Two pairs of contradicting notes are planted.
4. Note texts are written by an LLM once and committed.
