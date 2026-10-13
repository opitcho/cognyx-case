# Use cases and data requirements

What the demo answers and the exact data it needs. This document is the input for generating the synthetic data. For file contents it takes precedence over `docs/data-spec.md`.

## The question

The demo answers the question the case asks: **which sub-assemblies are reused, and which are reusable?** The answer is one verdict per sub-assembly, built from three files:

- **The BOM** says what is shared today and what is nearly the same.
- **The ERP item list** says what each difference costs.
- **The technical notes** hold what the other two cannot: that two references are the same part, that two designs do the same job, that a part is obsolete or has been replaced.

The notes are read once, turned into a table of relations between references, and that table is used at every layer: cleaning, comparison and verdict. The notes are seeded so that each layer has something to find in them.

When a note and the BOM disagree, the note decides the verdict. The BOM is never corrected, and the verdict shows both.

## The verdict

Each sub-assembly in each variant gets one of four verdicts, shown with the BOM rows and the notes that justify it.

| Verdict | Meaning | Example | Decided by |
|---|---|---|---|
| **Reused** | The same content exists in two or more variants, under one reference or several. | "Door leaf `DR-1042` on the 6-car and `PT-7731` on the 8-car have identical content. A note confirms the renumbering." | BOM, notes |
| **Reusable** | Not shared today, but could be. Three routes: it differs from another by 1 to 3 lines that nothing explains; the differing parts are interchangeable; or a note says another design is functionally equivalent. | "These two door leaves differ by one seal, €340 apart. A note approves the seal as a substitute." | BOM, ERP, notes |
| **Blocked** | Reused or reusable on content, but it contains an obsolete or superseded part. | "`DR-1042` contains actuator `AC-501`, superseded by `AC-560`." | Notes |
| **Specific** | The difference is explained by a variant option, or there is no counterpart. | "The 200 km/h door leaf has a pressure seal required for homologation." | BOM, notes |

Alstom names the risk behind "blocked" in its own filing: "existing references may become obsolete over time, requiring redesign or adaptation for new applications" (URD 2025/26, section 4.2.2.2, PDF page 185).

## What the notes contain

Each note is free text. Reading a note produces zero or more relations, each about one or two references.

| Relation | Meaning | Example note text |
|---|---|---|
| `same_as` | Two references are one part: a renumbering or an alias | `PT-7731 = ex DR-1042, renuméroté pour la variante 8 caisses` |
| `not_same_as` | Two references that look alike are distinct parts | `DR-1043 is the RH leaf, do not confuse with DR-1042 (LH)` |
| `interchangeable_with` | Two components are equivalent, or one is an approved substitute for the other | `Joint JT-220 validé en substitution du JT-218` |
| `functionally_equivalent_to` | Two sub-assemblies do the same job with different designs | `Door leaf DR-1042 functionally equivalent to DL-3310 (supplier B), same opening width and speed class` |
| `superseded_by` | A part has been replaced by another | `Actuator AC-501 superseded by AC-560 since NCR 2291` |
| `obsolete` | A part must not be used on new designs, no replacement named | `AC-477 obsolète, ne plus utiliser` |
| `required_for` | A part is needed because of a variant option | `Pressure seal JT-305 required for 200 km/h homologation` |

Most notes carry no relation. The reference a note points to may itself be mistyped, in the `reference` field or inside the text, so every relation is resolved through reference cleaning before it is used.

## What the notes add at each layer

| Layer | From the BOM and ERP alone | What the notes add | Relations used |
|---|---|---|---|
| Reference cleaning | Candidate matches from normalisation and fuzzy matching | Confirmation that two references are one part. Protection for look-alikes that must not merge. | `same_as`, `not_same_as` |
| Exact comparison | Sub-assemblies with identical content | Which of the two references to keep | `obsolete`, `superseded_by` |
| Near comparison | Pairs that differ by 1 to 3 lines | The differing parts are interchangeable, so the pair is identical in practice. Or one replaced the other, so the direction of the merge is known. Or the difference is required by an option. | `interchangeable_with`, `superseded_by`, `required_for` |
| Functional equivalence | Nothing: the two designs share no parts | That the two sub-assemblies do the same job | `functionally_equivalent_to` |
| Verdict | A verdict based on content | A block on anything containing an obsolete or superseded part | `obsolete`, `superseded_by` |

The cost layer takes nothing from the notes.

## Steps to the verdict

| # | Step | What it produces | How | Files |
|---|---|---|---|---|
| 0a | Reference cleaning and unit normalisation | One reference per part across the BOM and ERP. Scored against the answer key. | Normalisation rules plus fuzzy matching, checked against the parent. | BOM, ERP |
| 0b | Note reading | A table of relations: note, relation, first reference, second reference | One extraction per note into the seven relations, then each reference resolved against the cleaned list. | Notes |
| 0c | Cleaning, second pass | `same_as` pairs merged, `not_same_as` pairs kept apart | Apply the relations to the result of 0a. | |
| 1 | Exact comparison | Sub-assemblies with identical content, and which reference to keep | Compare the set of children of each sub-assembly. | BOM, relations |
| 2 | Near comparison | Pairs that differ by 1 to 3 lines, and for each differing line whether it is interchangeable, replaced, required by an option, or unexplained | Overlap score between sub-assemblies under the same system. | BOM, relations |
| 3 | Functional equivalence | Pairs of sub-assemblies declared equivalent that share no content | A lookup in the relations table. | Relations |
| 4 | Verdict | One verdict per sub-assembly with its evidence | A rule table over steps 1 to 3. | |
| 5 | Cost | The euro gap on each reusable pair | A price lookup with unit conversion. | ERP |

Cleaning runs before note reading so that the two do not depend on each other: references in notes are resolved against the list from 0a, and only then do the notes adjust it.

In step 3 the tool does not discover functional equivalence. It finds the statement in a mixed-language note, resolves a possibly mistyped reference, and attaches it to the right sub-assembly.

## Views built on the verdict

| View | What it shows | How |
|---|---|---|
| Reuse map | Grid of sub-assemblies against variants: shared today, and shared if the reusable ones are accepted | A pivot of the verdicts |
| Tender starting point | The oldest variant, each sub-assembly marked reuse, adapt or replace, with the reason and the cost. Closes the demo. | A relabelling of the verdicts for one variant |
| Purchasing view | One bought item under several references, suppliers or prices | Group ERP rows by cleaned reference |

If time runs out, the purchasing view goes first, then the tender starting point, then cost. Steps 0 to 4 and the reuse map are never cut.

## The product

A double-deck regional train family modelled on Regio 2N / Omneo.

- **Four levels:** train > system (doors, HVAC, bogies, braking, interior...) > sub-assembly > component.
- **Size:** about 1,500 BOM rows across the six variants.
- **Detail:** planted findings sit in three systems (doors, HVAC, seats). The other systems are clean filler.

| `variant_id` | `cars` | `speed_class_kmh` | `interior` | Role |
|---|---|---|---|---|
| `V1` | 6 | 160 | suburban | The oldest variant, presented as migrated from a legacy system. Carries most of the errors. Used for the tender starting point. |
| `V2` | 7 | 160 | suburban | |
| `V3` | 8 | 160 | regional | Differs from `V4` by speed class only |
| `V4` | 8 | 200 | regional | |
| `V5` | 10 | 160 | regional | |
| `V6` | 10 | 200 | intercity | |

## The files

Three client files with 19 columns in total, plus an answer key the pipeline never reads.

### File 1: `plm_bom_export.csv`

One row is one parent-child link in one variant. Comma separated, UTF-8, decimal point, English headers.

| Column | Type | Example | Notes |
|---|---|---|---|
| `variant_id` | text | `V3` | One of the six variants |
| `cars` | integer | `8` | Same value on every row of a variant |
| `speed_class_kmh` | integer | `160` | Same value on every row of a variant |
| `interior` | text | `regional` | Same value on every row of a variant |
| `level` | integer | `3` | Level of the child: 2 system, 3 sub-assembly, 4 component |
| `parent_ref` | text | `DOOR-SYS-01` | The variant id for level 2 rows |
| `child_ref` | text | `DR-1042` | Carries the typos and format variants |
| `description` | free text | `Door leaf assembly, left` | Mostly English, about 15% French |
| `quantity` | decimal | `2.4` | Quantity of the child in one parent |
| `unit` | text | `m` | `pcs`, `ea`, `U`, `PCE`, `m`, `mm`, `kg`, `g` |

Every row says which kind of train it belongs to. The tool needs this when two sub-assemblies differ: if one is on a 160 km/h train and the other on a 200 km/h train, the speed class may be the reason.

A system keeps the same reference in every variant, so that sub-assemblies under it can be compared.

### File 2: `erp_items.csv`

One row is one item reference, components only. Semicolon separated, UTF-8, decimal comma. A sub-assembly has no row: its cost is the sum of its components.

| Column | Type | Example | Notes |
|---|---|---|---|
| `item_ref` | text | `DR1042` | Same parts as `child_ref`, written without separators |
| `description` | free text | `VANTAIL PORTE GAUCHE` | Mostly French, about 15% English |
| `supplier` | text | `FAIVELEY TRANSPORT SAS` | Carries the supplier name variants. Sometimes empty |
| `unit_cost_eur` | decimal | `412,50` | Price of one `price_unit`. Sometimes empty |
| `price_unit` | text | `PCE` | Unit the price applies to. May differ from the BOM `unit` |

A mistyped twin of a reference has its own row, sometimes with a different price or supplier spelling.

### File 3: `technical_notes.jsonl`

One line is one note. About 80 notes, of which about 30 carry a relation.

| Field | Type | Example | Notes |
|---|---|---|---|
| `note_id` | text | `TN-0231` | |
| `date` | ISO date | `2025-03-14` | The latest note wins when two disagree |
| `reference` | text | `DR-1042` | A component or a sub-assembly. Often empty. May be mistyped |
| `text` | free text | `Actuator AC-501 remplacé par AC-560 suite à NCR, do not reuse` | French, English or mixed. Holds the relation and the second reference, which may also be mistyped |

The relations are not a column. They exist only in the text.

### How the files join

- `plm_bom_export.child_ref` to `erp_items.item_ref`, after reference cleaning. They do not join as written.
- `technical_notes.reference`, and references found in `text`, to `child_ref` or `parent_ref`, after reference cleaning.
- A relation about a component applies to every sub-assembly that contains it.

### Which step reads which fields

| Step or view | BOM | ERP | Notes |
|---|---|---|---|
| 0a Cleaning | `parent_ref`, `child_ref`, `description`, `quantity`, `unit` | `item_ref`, `description`, `price_unit` | |
| 0b Note reading | Cleaned reference list | | All four fields |
| 1 Exact comparison | `variant_id`, `level`, `parent_ref`, `child_ref`, `quantity`, `unit` | | Relations |
| 2 Near comparison | Same as 1, plus `cars`, `speed_class_kmh`, `interior` | | Relations |
| 3 Functional equivalence | `level`, `child_ref` | | Relations |
| 5 Cost | `child_ref`, `quantity`, `unit` | `item_ref`, `unit_cost_eur`, `price_unit` | |
| Reuse map | `variant_id`, `level`, `child_ref` | | |
| Tender starting point | The rows of `V1` | `unit_cost_eur` | Relations |
| Purchasing view | `child_ref`, `quantity` for usage | All five columns | |

## Noise

Ten kinds of noise, each tied to a column above. The amounts are our choices, set so that each layer has enough to show in a 20-minute demo. They are not estimates of Alstom's data.

| Noise | File and column | Example | Serves | Amount |
|---|---|---|---|---|
| Mistyped or reformatted twin of a reference | BOM `child_ref`, `parent_ref`; ERP `item_ref` | `DR-1042`, `DR 1042`, `DR-1O42`, `DR-10422` | Case statement, cleaning | About 5% of references |
| Same BOM line twice | BOM, whole row | One line present with quantity 4 and with 6 | Case statement, cleaning | About 2% of rows, a third with a different quantity |
| Mixed units | BOM `unit`; ERP `price_unit` | `2.4 m` and `2400 mm`; `pcs`, `ea`, `U`, `PCE` | Case statement, cleaning, cost | About 10% of items |
| French and English free text | BOM and ERP `description`; notes `text` | `Door leaf assembly, left` and `VANTAIL PORTE GAUCHE` | Case statement, cleaning, note reading | 15% of descriptions in the other language; notes half French, a third English, rest mixed |
| Cost conflict | ERP `unit_cost_eur` | One item at two prices under its two references | Purchasing view | About 3% of items |
| Supplier name variants | ERP `supplier` | `Faiveley`, `FAIVELEY TRANSPORT SAS`, `Wabtec` | Purchasing view | Two suppliers, three spellings each |
| Missing values | ERP `supplier`, `unit_cost_eur` | Empty cell, or a filler such as `UNKNOWN` | Some cost gaps cannot be priced | About 3% of cells, none on components of `V1` |
| Note contradicts the BOM | Notes `text` | Note says the actuator is superseded; the BOM still lists it | Verdict | About 10 notes |
| Reference only inside the note text | Notes `reference` empty | `FLOOR PANEL CRACK, P/N:453T1996-12` | Note reading | About half of the notes that carry a relation |
| Mistyped reference in a note | Notes `reference` and `text` | Note says `equivalent to DL-331O`; the BOM has `DL-3310` | Note reading, cleaning | About a quarter of the seeded relations |

Errors are concentrated: `V1` and two suppliers carry most of them.

The typo styles copy the real ones in `docs/real-data-patterns.md`: a dropped or doubled character, `O` for `0`, separators added or removed, a reference cut short.

### What must not be merged

Without these, a tool that merges everything would score perfectly.

- **Look-alike sub-assemblies:** same name, different content, such as one seat frame in two lengths. At least 5.
- **Look-alike references:** distinct parts one character apart, such as left and right door leaves `DR-1042` and `DR-1043`. Some are protected by a `not_same_as` note, some are not.
- **Notes that change nothing:** routine notes with no relation, about 50 of the 80.

## Planted findings

| Layer | Finding | Seeded relation | Planted |
|---|---|---|---|
| Cleaning | Two references confirmed as one part | `same_as` | At least 5 |
| Cleaning | Look-alike references kept apart | `not_same_as` | At least 3 |
| Exact comparison | Reused under two references | none | At least 5 cloned and renumbered sub-assemblies |
| Exact comparison | Reused, and a note says which reference to keep | `obsolete` or `superseded_by` | At least 2 |
| Near comparison | Reusable, difference not explained | none | At least 5 pairs |
| Near comparison | Reusable, the differing parts are interchangeable | `interchangeable_with` | At least 3 pairs |
| Near comparison | Reusable, one part replaced the other | `superseded_by` | At least 2 pairs |
| Near comparison | Specific, difference required by speed class | `required_for` on some, none on others | At least 3 pairs |
| Functional equivalence | Reusable, different design and no shared parts | `functionally_equivalent_to` | 2 or 3 pairs, from different suppliers |
| Verdict | Blocked | `obsolete` or `superseded_by` | At least 3, one with a replacement that exists in a newer variant |

Near-comparison pairs sit under the same system reference. `V1` carries at least one finding from each layer.

## Answer key

Kept apart from the three files and never read by the pipeline.

- **The clean model:** every variant, system, sub-assembly, component and supplier with its one true reference.
- **One row per corrupted value:** file, row, field, true value, written value, error type.
- **One row per seeded relation:** note, relation, the true references, and the references as written in the note.
- **One row per planted finding:** layer, the references involved, the verdict expected from the BOM alone, the verdict expected with the notes, and the cost gap where there is one.
