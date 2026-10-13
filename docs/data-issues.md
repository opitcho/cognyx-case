# Issues in the data and how each is resolved

The pilot export has three files: a multi-variant BOM (1,538 rows), an ERP item list (313 rows) and 80 technical notes. The data is synthetic: every issue below was introduced on purpose and logged, so each one can be counted and scored.

Issues are grouped by the step that resolves them.

## 1. Resolved by rules

Deterministic transformations. No judgement needed.

| Issue | Example | Count |
|---|---|---|
| Reference format differs between BOM and ERP | `DR-1042` in the BOM, `DR1042` in the ERP | Every reference |
| Same quantity or price in another unit | `1.6 m` and `1600 mm`; a price per `m` and a price per `mm`; `pcs`, `ea`, `U`, `PCE`, `EA` for a piece | 30 items |
| BOM line repeated with the same quantity | The same parent, child and quantity on two rows | 20 lines |
| Supplier name written in another form | `Sofratec`, `SOFRATEC INDUSTRIES SA`, `Sofra-Tec` | 2 suppliers, 3 spellings each |

One supplier spelling is not a variant of the name: `Wabtec` for `Faiveley`. It needs a lookup table, not a rule.

## 2. Resolved by matching references

A mistyped reference is matched to the closest valid reference.

| Issue | Example | Count |
|---|---|---|
| Mistyped reference in the BOM and ERP | `RL-025` for `RL-205`, `FC-6I00` for `FC-6100`, `RY 440` for `RY-440`, `TH-50` for `TH-450` | 19 references, 15 of them with their own ERP row |
| Mistyped reference in a note | `SN-5598` for `SN-598` | 7 notes |

Constraint: 5 pairs of valid references are one character apart and must not be matched to each other, for example left and right door leaves `DR-1042` and `DR-1043`. Both references of each pair exist in the BOM. For 3 pairs a note states that they are different parts.

## 3. Resolved by reading the notes

Extraction from free text.

| Issue | Example | Count |
|---|---|---|
| The part is named only in the text, the reference field is empty | `KP-0457 door control unit superseded by DC-3001` | 39 of 80 notes |
| French, English, or both in one note | `GP-8805 et PW-470 : two different designs de cloison vitrée, same function` | 40 French, 27 English, 13 mixed |
| A note states a relation between parts | Same part, not the same part, interchangeable, functionally equivalent, superseded, obsolete, required for an option | 28 of 80 notes |
| Two notes contradict each other | One note says `PB-2281` and `LR-1500` differ, a later note says they are the same part | 2 pairs. The later note applies |

Descriptions in the BOM and ERP also switch language (227 BOM rows, 47 ERP rows). References are the join key, so this does not block any step.

## 4. Resolved by comparing BOM content

Done after steps 1 and 2. The content of a sub-assembly is its list of components and quantities.

| Issue | Example | Count |
|---|---|---|
| Same content under two references | Door leaf `DR-1042` and `PT-7731` | 7 pairs |
| Content differs by 1 to 3 lines | Sliding steps `ST-4100` and `ST-4165`: 12 bolts and 16 bolts | 14 pairs |
| Same name, content differs by 4 lines or more | Two seat frames both called `Seat frame assembly`, a 2-seat and a 3-seat | 5 pairs. Must stay separate |

Dependence on earlier steps: 2 of the 7 pairs with the same content only match after a mistyped reference is corrected, and 3 only after a unit is converted.

## 5. Resolved by combining BOM content and notes

The BOM comparison alone gives an incomplete or wrong result.

| Issue | Example | Count |
|---|---|---|
| A sub-assembly used in several variants contains an obsolete or superseded part | The right door leaf is in all six variants; a note says its actuator `AC-477` is obsolete | 7 sub-assemblies |
| Two sub-assemblies with no component in common do the same job | Sliding steps `ST-4100` and `RS-6620`; a note says they are functionally equivalent | 2 pairs |
| A 1-to-3-line difference is explained by a note | Parts interchangeable (3 pairs), one part replaced the other (2 pairs), part required at 200 km/h (2 pairs) | 7 of the 14 pairs |

For 9 sub-assemblies the final answer changes once the notes are read: 7 go from reused to blocked, 2 from specific to reusable.

## 6. Not resolvable from the data

Flagged for a person. The data does not say which value is right.

| Issue | Example | Count |
|---|---|---|
| BOM line repeated with another quantity | Seal `JT-4924` in one roof panel set with quantity 4.3 and with 6.4 | 10 lines |
| One part at two prices | `RL205` at 87,53 and under its mistyped reference at 82,30 | 9 items |
| Missing supplier or price | Supplier empty or `N/A`; price empty | 12 suppliers, 7 prices |
| A 1-to-3-line difference with no explanation | Door drive units `DD-2200` and `DD-2268`: another bracket, 12 bolts and 10 | 7 pairs |

## Scoring

| Step | Scored against |
|---|---|
| 1 and 2 | `data/clean/` and `data/truth/changes.csv` (537 changed values) |
| 3 | `data/truth/relations.csv` (28 relations with the real references) |
| 4 and 5 | `data/truth/findings.csv` (36 planted cases) and `data/truth/verdicts.csv` (one result for each of the 81 sub-assembly designs) |
