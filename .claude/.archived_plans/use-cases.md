# Use cases for the Alstom pilot

Short version of `docs/research/alstom-tender-reuse/README.md`, which holds the full evidence and source grading.

## The goal in one line

Fewer distinct sub-assemblies across train variants, so a tender starts from what already exists.

## Why Alstom cares (three facts from its own filings)

- **Price is fixed before the design exists.** "The tender phase is not a detailed design phase, some technical assumptions and choices are made during tender." ([URD 2025/26, section 4.2.2.2](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf))
- **Reuse assumptions fail.** "Existing references may become obsolete over time, requiring redesign or adaptation for new applications." (same section)
- **The margin leaks in execution.** Orders are priced at 18.0% gross margin, 13.3% was booked in 2025/26, and Alstom names "additional activities performed to implement engineering changes" as a cause. ([Equity Story Oct 2026, slide 51](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf))

No source gives a reuse rate or a savings percentage for any train maker. The demo shows what is in the data and does not quote a saving.

## Use cases

Door systems are the running example.

| # | Use case | Example finding | How the tool finds it | What the data must contain |
|---|---|---|---|---|
| 1 | **Same sub-assembly, different reference** | "Door leaf `DR-1042` on the 6-car and `PT-7731` on the 8-car have identical content." | Clean the references, then compare the content of each sub-assembly. Identical content under two references is a duplicate. | A sub-assembly cloned and renumbered in another variant. |
| 2 | **Nearly the same, could be one** | "These two door leaves differ by one seal and one bolt supplier. Merge candidate, €340 apart." | Score the overlap of components between sub-assemblies of the same family. List the lines that differ and the cost difference. | Pairs differing by 1 to 3 lines. Some differences justified by an option (speed class), some not. |
| 3 | **Different design, same function** | "Variant A uses a door from supplier X, variant B from supplier Y. Same opening width, same door type, same speed class." | Group sub-assemblies by function and key specifications, then flag groups with more than one design. | A function label and 3 to 4 specification fields per sub-assembly. |
| 4 | **Reuse map** | "38% of sub-assemblies are shared by all variants today. 55% could be, if the findings above are accepted." | Grid of sub-assemblies against variants, built from use cases 1 to 3. | Follows from the above. |
| 5 | **Inconsistencies** | "Same seal: 2.4 m in the engineering file, 2400 pcs in the purchasing file." | Rules for unit, quantity, revision and cost conflicts, each shown with its source rows. Nothing is auto-corrected. | Unit, quantity and revision mismatches between files. |
| 6 | **Warnings from notes** | "Note on `DR-1042`: actuator superseded, do not use on new designs." | Extract a small fixed set of flags from each note (obsolete, superseded, equivalent to, approved substitute) and attach them to the sub-assembly. | Notes that carry such facts, some contradicting the BOM. |

Use case 3 is the hardest and the most valuable. Comparing content cannot find it, because the two doors share no parts.

**Foundation, not a use case:** reference cleaning (typos, formats, French and English names). It gets shown to Thomas with a measured score against the answer key.

**Later in the pilot (one slide, not built):**
- **Tender starting point:** for a requested variant, list each sub-assembly as reuse, adapt or new, with cost.
- **Purchasing view:** the same bought-in item under several references, suppliers or prices. Alstom buys in 64% of its cost base ([URD 2025/26, section 4.2.2.3](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)).

## Build order

1. Reference cleaning
2. Use case 1 (exact duplicates)
3. Use case 2 (near matches)
4. Use case 5 (inconsistencies)
5. Use case 4 (the headline grid, once 1 and 2 feed it)
6. Use case 6 (note flags)
7. Use case 3 (functional equivalents)

Steps 1 to 5 answer the case question on their own. Steps 6 and 7 are cut first if time runs out.

## Changes to the synthetic data plan

- **Train family:** switch from Coradia Polyvalent to a double-deck regional family modelled on Regio 2N / Omneo. Régiolis was built at Reichshoffen; Valenciennes and Crespin build double-deck regional trains, RER and metros. (Site attribution rests partly on French Wikipedia; check before saying it to Thomas.)
- **Variant axes:** length (6, 7, 8, 10 cars), speed (160 or 200 km/h), interior (suburban, regional, intercity).
- **Add for use case 3:** a function label and a few specification fields per sub-assembly, plus two or three planted pairs with the same function and no shared parts.
- **Add look-alikes that must not merge:** for example the same seat frame in two lengths. They prove the tool does not over-merge.
- **Keep the answer key.** No published accuracy figure exists for this kind of matching, so the score on our own planted errors is the only defensible number.

## Evidence worth quoting

- **Method:** matching part names alone gave 743 candidates in a published test; requiring the parent to match too left 21. ([Tate et al., 2024](https://arxiv.org/pdf/2411.10384))
- **Cost of a new part:** about $27,500 over its life, per a US defence guide. Defence, not rail, so an order of magnitude only. ([SD-19, 2013](https://everyspec.com/DoD/DoD-PUBLICATIONS/SD-19_DEC2013_49300/))
- **Notes go unread:** change requests at a rail supplier are "often stored but not consulted". ([Pacella et al., 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5164909))
- **Commercial tools need 3D geometry**, which this data does not have. ([PTC documentation](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html))

Do not quote Cognyx's "up to 40%" or any "30% to 40% of parts are duplicates" figure. Neither could be traced to a source.
