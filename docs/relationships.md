# Relationships in the reconciled data

Every relationship the pipeline records or computes, with what it links, what it means, how many there are and one real example.

Counts and examples come from `out/pilot.db` as built from `data/raw/` and the 578 lines of `data/claims.jsonl`.

The last section lists the internal names that appear in the agent's answers today and a plain wording for each.

## What the relationships link

There are four kinds of things. Each relationship below links two of them.

| Thing | What it is | Example |
|---|---|---|
| Written value | A reference, a supplier name, a unit or a cell, exactly as one raw file writes it | `ST-4010`, written in note `TN-0315` |
| Part | One real part, whatever the spellings it is written under. A part is a system, a sub-assembly or a component. There are 7 systems, 76 sub-assemblies and 298 components | The sliding step, written as `ST-4100`, `ST-4010` and `MP-4418` |
| Sub-assembly in a variant | One sub-assembly as one of the six variants uses it, with its list of components and quantities (its content). There are 240 | `ST-4100` in `V3` |
| Design | One distinct content. Two sub-assemblies with the same components in the same quantities are one design, even under two references. There are 74 | `D011`, carried by `KP-0457` in `V1` and by `DC-3001` in `V2`, `V3` and `V4` |

The relationships build on each other in this order:

1. Statements say which written values are the same part, and what notes say about parts.
2. From those, each sub-assembly in each variant gets its content, and identical contents become one design.
3. Designs are compared two by two, and each difference gets a reason.
4. Each sub-assembly gets a verdict.

## Statements about the raw data

The code calls a statement a claim. A claim is one line of `data/claims.jsonl`: one thing someone says about the raw files, with who said it and the rows or the note it rests on. Example, line 516:

| Field | Value |
|---|---|
| What it says | `PB-2281` and `LR-1500` are the same part |
| Who said it | the agent |
| Rests on | note `TN-0418` |
| Words quoted from the note | "Porte-bagages PB-2281 = LR-1500, same luggage rack, juste renumérotation." |

### Types that say what the raw files mean

| Type in the code | Links | Meaning | Number | Example |
|---|---|---|---|---|
| `same_as` | two written references, or two written supplier names | They are one part, or one supplier | 351 | `PB-2281` and `LR-1500` |
| `not_same_as` | two written references that look alike | They are two parts | 8 | `JT-218` (door seal, Faiveley, 32,01) and `JT-281` (silicone seal, SOFRATEC INDUSTRIES SA, 15,60) |
| `converts_to` | a written unit and a base unit (`pcs`, `m`, `kg`) | One of the first is so many of the second | 5 | 1 `mm` is 0.001 `m` |
| `duplicate_of` | two rows of the BOM file | The first repeats the second | 20 | row 1517 repeats row 1516 |
| `value_is` | one cell of a raw file | The right value of the cell | 10 | the quantity in BOM row 1424 is 1, not 1.5 |
| `no_value` | one cell of a raw file | The cell holds a filler, not a value | 19 | the supplier in ERP row 255 is `N/A` |
| `mentions` | a note and a written reference | The note is about that part | 41 | note `TN-0506` is about `FB-791` |

### Types that say how two parts relate

These five come from the technical notes. The code calls them relations. 17 are applied today.

| Type in the code | Links | Meaning | Applied | Example | Effect |
|---|---|---|---|---|---|
| `interchangeable_with` | two components | Either can be fitted in place of the other. Both stay usable | 4 | `FB-791` and `FB-764`, note `TN-0506` | A difference between two sub-assemblies that is only this swap is explained |
| `superseded_by` | an old part and its replacement | The old part must no longer be used | 5 | `TH-415`, replaced by `TH-450` | Every sub-assembly that holds the old part names it in `obsolete_parts` |
| `obsolete` | one part | Not to be used on new designs. No replacement is named | 4 | `AC-477`, note `TN-0471` | Every sub-assembly that holds the part names it in `obsolete_parts` |
| `required_for` | a part and a variant option | The part is needed because of the option | 2 | `JT-305` is required for the 200 km/h speed class, note `TN-0393` | A difference between two sub-assemblies that is this part is justified by the option |
| `functionally_equivalent_to` | two sub-assemblies | Two different designs that do the same job | 2 | `RS-6620` and `ST-4100`, note `TN-0361` | The two are compared, whatever the number of differing lines |

### Types that act on another statement

| Type in the code | Links | Meaning | Number | Example |
|---|---|---|---|---|
| `confirm` | an earlier statement | A proposed statement is accepted | 25 | line 578 accepts line 329 |
| `retract` | an earlier statement | A statement is withdrawn | 2 | line 577 withdraws line 539 |
| `reviewed` | a note | The note was read and says nothing more about parts | 78 | note `TN-0506` |

### Who made a statement, and whether it is applied

A statement is made by a rule (`pipeline/rules.py`), by the agent or by a person. On a conflict, a person's statement wins over the agent's, and the agent's over a rule's.

A statement is either asserted (applied at once) or proposed (applied only once accepted). From that and from the later statements about it, each one has a status:

| Status in the code | Meaning | Number |
|---|---|---|
| `in force` | Asserted, and applied | 543 |
| `confirmed` | Proposed, then accepted. Applied | 25 |
| `proposed` | Waiting for someone to accept or reject it. Not applied | 7 |
| `retracted` | Withdrawn. Not applied | 2 |
| `overridden` | Another statement says the opposite and wins. Not applied | 1 |

## Relationships between two sub-assemblies

These are computed. Nobody states them.

| Name in the code | Links | Meaning | Number | Example |
|---|---|---|---|---|
| same design | two sub-assemblies in two variants | Same components in the same quantities, under one reference or two | 74 designs for 240 sub-assemblies in variants | `KP-0457` in `V1` and `DC-3001` in `V2` |
| `near` pair | two designs of the same system | They share at least 4 components and differ by 1 to 3 lines | 14 | `DR-1042` and `DR-1090`: one line differs |
| `functional` pair | two designs | A note says they do the same job (`functionally_equivalent_to`) | 2 | `PW-4700` and `GP-8805` |

### Reason given to each differing line

A differing line is one component that the two designs do not have in common, or have in different quantities. There are 29 across the 16 pairs.

| Reason in the code | Meaning | Number | Example |
|---|---|---|---|
| `interchangeable` | The two components are interchangeable (a statement says so) | 3 | `MT-701` in `DD-2010`, `MT-745` in `DD-2037` |
| `superseded` | One component replaces the other (a statement says so) | 2 | `SN-573` in `DC-3001`, `SN-598` in `DC-3020` |
| `required_by_option` | The component is required for an option (a statement says so) | 2 | `JT-305` is in `DR-1090` and not in `DR-1042` |
| `unexplained` | No statement accounts for the difference | 22 | `DD-2200` has 12 `BL-371`, `DD-2268` has 10 |

## Verdict of a sub-assembly

Each sub-assembly in each variant gets one of three verdicts, with a sentence that says why. The verdict says only whether the content is shared.

| Verdict | Meaning | Number | Example |
|---|---|---|---|
| `reused` | The same content is in two or more variants | 222 | `AD-7300`: same content in `V1`, `V2`, `V3`, `V5` |
| `reusable` | Not shared today. It differs from another design by 1 to 3 lines that no option requires, or a note says another design does the same job | 15 | `DD-2037` differs from `DD-2010` by one line, an interchangeable component |
| `specific` | Its difference from the nearest design is required by an option, or nothing in another variant resembles it | 3 | `ER-321` in `V6` |

Whether a sub-assembly holds an obsolete or superseded part is kept apart from the verdict, in the column `obsolete_parts`. It is filled for 25 sub-assemblies, all `reused` on content, and empty for the others.

| Case | Text of `obsolete_parts` | What it asks for |
|---|---|---|
| A component is obsolete or superseded | `HT-5300`: "TH-415, superseded by TH-450" | The content has to change |
| The sub-assembly's own reference is | `RG-0212` in `V1`: "own reference RG-0212, obsolete (same content under TC-8100)" | The content is sound and is available under another reference |

A second verdict is kept beside the first: the verdict from the BOM alone, computed without any statement that rests on a note. `GP-8805` is `specific` from the BOM alone and `reusable` once note `TN-0183` is read.

## One variant seen from another

For a sub-assembly of one variant, what the other variant has in its place. There is one row per sub-assembly and per ordered pair of variants: 1,200 rows.

| Status in the code | Meaning | Number | Example, from `V3` to `V4` |
|---|---|---|---|
| `same reference` | Same content, same reference | 794 | `LR-1500` |
| `same content under another reference` | Same content, under a different reference | 12 | none between `V3` and `V4`. `KP-0457` in `V1` is `DC-3001` in `V2` |
| `near` | The other variant has a design that differs by 1 to 3 lines | 112 | `ST-4100`, against `ST-4165`: one line |
| `functionally equivalent` | The other variant has a design that a note says does the same job | 16 | none between `V3` and `V4` |
| `no counterpart` | Nothing in the other variant matches | 266 | `FE-4259` |

## Price of a part

| Status in the code | Meaning | Number | Example |
|---|---|---|---|
| `agreed` | One price, or several rows that agree | 284 | |
| `disputed` | Two different prices in the purchasing file. The cost is left empty | 8 | `AL-6065`: 2842.07 EUR in row 9, 2985.81 EUR in row 10 |
| `missing` | Used in the BOM, no price | 6 | `CV-547` |

The cost of a sub-assembly is empty while one of its components is `disputed` or `missing`. Only a person can say which price holds.

## Names that appear in the agent's answers, and a plain wording

The left column is what the agent writes today. The right column is a proposed wording. It is not in use yet.

| In the agent's answers today | Plain wording |
|---|---|
| claim 466, claim 508 | "recorded from note TN-0226" (name the source, not the line number) |
| `required_for VL-905 → option:speed_class_kmh=200` | "VL-905 is required for 200 km/h" |
| `interchangeable_with` | "can be fitted in place of each other" |
| `superseded_by` | "replaced by", "must no longer be used" |
| `obsolete` | "not to be used on new designs" |
| `functionally_equivalent_to`, functional pair | "a different design that does the same job" |
| `same_as`, `not_same_as` | "the same part written two ways", "two different parts" |
| near pair | "almost identical: N lines differ" |
| design, `D011` | "the same content", with the references that carry it |
| `unexplained` | "no note explains this difference" |
| `required_by_option` | "required for" the option, named |
| `reused`, `reusable`, `specific` | "shared today", "could be shared", "particular to this variant", each followed by the reason |
| `obsolete_parts` filled | "cannot be reused as is", with the part that prevents it |
| `no counterpart` | "nothing equivalent in the other variant" |
| proposed, in force, retracted, overridden | "waiting for your decision", "applied", "withdrawn", "replaced by a later decision" |
| `disputed`, `missing` | "two different prices", "no price" |
| `v_pair_diff`, `v_reuse_between`, `v_reuse_map`, any table or column name | not named. The answer cites raw rows and notes instead: "BOM row 803", "note TN-0393" |
