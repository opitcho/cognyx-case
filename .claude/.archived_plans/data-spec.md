# Data spec for the synthetic pilot export

What the synthetic Alstom-style data must contain, and why. This is the file to give to whoever generates the data.

## What the spec is based on

**1. The case statement.** It is the only direct evidence we have about the client's data:

> The data is dirtier than advertised: duplicated references with typos, mixed units, free-text fields switching between French and English.

These three defects are mandatory and must be the most visible ones.

**2. The use cases** in `docs/use-cases.md`. Each one needs specific things to exist in the data so that the tool has something true to find.

**3. Not external datasets.** We analysed four public datasets from other industries (`.experiments/findings.md`). Data quality depends on a company's systems, processes and culture, so those results do not predict what Alstom's data looks like. No rate in this spec is derived from them. `docs/real-data-patterns.md` keeps a few real examples of what such errors look like, as illustration only.

All rates below are **our choice**, set so that each use case has enough material to show in a 20-minute demo. They are dials, not estimates of the client's data.

## The product

A double-deck regional train family modelled on Regio 2N / Omneo, as `docs/use-cases.md` proposes.

- **Variants (6)**, on three axes: length (6, 7, 8 or 10 cars), speed class (160 or 200 km/h), interior (suburban, regional, intercity). Not every combination exists.
- **Four levels:** train > system (doors, HVAC, bogies, braking, interior...) > sub-assembly > component.
- **Size:** about 1,500 BOM rows, small enough to check by eye.

## The files

| File | Plays the role of | One row is | Columns |
|---|---|---|---|
| `variants.csv` | Reference list | One train variant | `variant_id`, `cars`, `speed_class_kmh`, `interior` |
| `plm_bom_export.csv` | Engineering BOM from the PLM | One parent-child link in one variant | `variant_id`, `level`, `parent_ref`, `child_ref`, `description`, `quantity`, `unit`, `revision`, `function`, `specs` |
| `erp_items.csv` | Purchasing data from the ERP | One item as used in one parent | `parent_ref`, `item_ref`, `description`, `quantity`, `purchasing_unit`, `supplier`, `unit_cost`, `revision`, `lead_time_days` |
| `technical_notes.jsonl` | Engineering change and quality notes | One note | `note_id`, `date`, `author_team`, `reference` (often empty), `text` |

How they relate:

- `plm_bom_export.child_ref` and `erp_items.item_ref` name the same parts, but each system writes references in its own format, so they do not join as-is.
- `function` and `specs` are filled on sub-assembly rows only. `function` is a label such as `passenger door leaf`. `specs` holds three or four key values, such as `opening_width_mm=1300; door_type=plug; speed_class=200`.
- A note points to a part through `reference` when filled, otherwise only through a reference written inside `text`.
- File formats differ on purpose: PLM in English headers, comma separated, UTF-8, decimal point; ERP in French locale, semicolon separated, decimal comma, `dd/mm/yyyy`, Latin-1.

## The dirt

### Named in the case statement (mandatory)

| Defect | What it means here | Example | Proposed amount |
|---|---|---|---|
| Duplicated references with typos | The same part exists under two references, one a mistyped or reformatted copy of the other. Also the same line imported twice | `DR-1042`, `DR 1042`, `DR-1O42`, `DR-10422` for one door leaf; a BOM line present twice, with quantity 4 and 6 | About 5% of references have a mistyped twin; about 2% of BOM rows are repeated, a third of them with a different quantity |
| Mixed units | The same quantity expressed in different units, between the two files or inside one | Seal: `2.4 m` in the PLM, `2400 mm` or `1 PCE` in the ERP; `kg` and `g`; `pcs`, `ea`, `U`, `PCE` | About 10% of items |
| Free text switching between French and English | Descriptions and notes in either language, sometimes both in one field | PLM `Door leaf assembly, left`; ERP `VANTAIL PORTE GAUCHE`; note `Actuator remplacé suite à NCR, do not reuse` | ERP descriptions mostly French, PLM mostly English, about 15% the other way round; notes roughly half French, a third English, the rest mixed |

### Needed by the use cases

| Defect | Example | Needed for | Proposed amount |
|---|---|---|---|
| Revision out of date in the ERP | PLM revision `C`, ERP still `B` | Inconsistencies | About 5% of items |
| Cost conflict | The same item at two unit costs under its two references | Inconsistencies, purchasing view | About 3% of items |
| Quantity conflict between files | PLM says 4 per door, ERP says 6 | Inconsistencies | About 3% of lines |
| Supplier name variants | `Faiveley`, `FAIVELEY TRANSPORT SAS`, `Wabtec` | Purchasing view | Two suppliers, three spellings each |
| Note contradicts the BOM | Note says the actuator is superseded; the BOM still lists it | Warnings from notes | About 10 notes |
| Missing values | Empty supplier or cost | Realism of the review queue | About 3% of optional cells |

Errors are concentrated: one variant (presented as migrated from a legacy system) and two suppliers carry most of them. This is a design choice for a readable demo.

## What each use case needs

Checked against `docs/use-cases.md`. "Planted" is the number of cases recorded in the answer key.

| Use case | The data must contain | Where it lives | Planted |
|---|---|---|---|
| Foundation: reference cleaning | Typos, format variants, French and English names for the same part | `child_ref`, `item_ref`, `description` in both files | Every corrupted value logged |
| 1. Same sub-assembly, different reference | A sub-assembly cloned into another variant and renumbered, content unchanged | `plm_bom_export`: two `parent_ref` with the same children | At least 5 |
| 2. Nearly the same, could be one | Pairs of sub-assemblies with the same `function` that differ by 1 to 3 lines. Some differences explained by a variant option (speed class), some not. A cost for each line | `plm_bom_export` for content; `erp_items.unit_cost` for the gap; `variants.csv` for the option | At least 5 unjustified, 3 justified |
| 3. Different design, same function | Sub-assemblies with the same `function` and matching `specs` but no shared components, from different suppliers | `function`, `specs`; `erp_items.supplier` | 2 or 3 pairs |
| 4. Reuse map | Nothing extra: built from 1 to 3. Needs every sub-assembly tied to its variants | `variant_id` | n/a |
| 5. Inconsistencies | Unit, quantity, revision and cost conflicts between the two files, each traceable to its rows | `quantity`, `unit` / `purchasing_unit`, `revision`, `unit_cost` in both files | At least 5 of each kind |
| 6. Warnings from notes | Notes stating one of: obsolete, superseded by, equivalent to, approved substitute. Some contradict the BOM. Some name the part only in the text | `technical_notes.text`, `reference` | At least 5 per flag |
| Later: purchasing view | The same bought item under several references, suppliers or prices | `erp_items` | Follows from the duplicated references |
| Later: tender starting point | A cost for every component, so a variant can be rolled up | `erp_items.unit_cost` | n/a |

### Things that must not be merged

Without these, a tool that merges everything would look perfect.

- **Look-alike sub-assemblies:** same name, different content, for example the same seat frame in two lengths. At least 5.
- **Look-alike references:** real, distinct parts one character apart, for example left and right door leaves `DR-1042` and `DR-1043`. A few per system.

## Answer key

Kept apart from the client files and never read by the pipeline.

- The clean model: every variant, sub-assembly, component and supplier with its one true reference.
- One row per planted finding: use case, the references involved, the expected conclusion, and for use case 2 the reason for the difference and the cost gap.
- One row per corrupted value: file, row, field, true value, written value, error type.

## Gaps found when checking against the use cases

These are differences between this spec and `.claude/.plans/synthetic-pilot-data.md` as originally written. The plan now defers to this spec for file contents.

1. **Use case 3 needs `function` and `specs`.** The plan had neither. Added to the PLM file.
2. **Use case 5 needs a quantity on the purchasing side.** Its example compares `2.4 m` in engineering with `2400 pcs` in purchasing. The plan's ERP file was one row per item with no quantity. This spec makes it one row per item per parent, with `quantity` and `purchasing_unit`. **Decision needed:** confirm, or keep a plain item list and show quantity conflicts only inside the PLM file.
3. **Use case 2 justifies differences by option**, so variant attributes must be readable. Added `variants.csv`.
4. **Train family.** The plan used Coradia Polyvalent; `docs/use-cases.md` switches to a double-deck regional family. This spec follows the use cases.
5. **Rates.** The plan took them from an analysis of external data. They are now our own choices, listed above.
