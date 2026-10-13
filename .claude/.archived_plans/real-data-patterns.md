# Examples of dirty data from other industries

**Illustration only.** These examples come from public datasets of other companies (aviation defect reports, Caterpillar tube assemblies, a 3D-printer parts list). Data quality depends on each company's systems, processes and culture, so nothing here predicts what Alstom's data looks like, and no rate should be taken from it. The spec is `docs/data-spec.md`.

What they are good for: showing what a given kind of error looks like when real people make it, so that synthetic errors do not look machine-made.

The case statement names three defects:

> The data is dirtier than advertised: duplicated references with typos, mixed units, free-text fields switching between French and English.

## Duplicated references with typos

| What happened | Real example |
|---|---|
| A character dropped, doubled or replaced | Correct `ADD71701100`; also seen `AD71701100`, `ADDD71701100`, `ADD7170110`, `AD071701100` |
| Look-alike characters | `20131ASM1` and `20131ASMI`; `0L3071BPEGPL` and `OL3071BPEGPL` |
| Same reference, with and without separators | `SH670330379` in a form field, `SH670-33037-9` in the note of the same record |
| Reference cut short | `114T2800` for `114T2800-165` |
| The same line twice with two quantities | `M3x6 FHCS` listed with 13 and with 8 in one parts list |
| Identical content under different ids | Tube assemblies `TA-10132`, `TA-10133`, `TA-10134`: same components, material and dimensions |
| Real, distinct parts one character apart (not typos) | `141A48001` and `141A48002`, two windshield parts |

## Mixed units

| What happened | Real example |
|---|---|
| Counted per piece in the BOM, bought by the pack | `EA` (each) in the BOM; `CTN` (carton), `CS` (case), `DZ` (dozen) from the supplier |
| A range or a unit typed into a quantity cell | `201-217`, `3m`, `7m` |
| Text in a numeric position field | `540`, `FR 69`, `500B + 10`, `N/A` in the same column |
| Unknown value entered as a number | Bend radius `9999`, length `0` |

## Free text

None of the sources mixes French and English, so there is no example of the case statement's third defect. What they do show about free text:

| What happened | Real example |
|---|---|
| One part, several names | Part `321431` called `BATTERY`, `EPSU`, `BATTERY PACK`, `POWER SUPPLY` |
| Name cut at a field length | `FLANGE-ONE PIEC` next to `FLANGE-ONE PIECE`; `AUTOTHROTTLE SYS` |
| Punctuation and spelling variants | `ELBOW-WELD` and `ELBOW WELD`; `SLEEEVE-REDUCER` |
| Company name variants | `HNYWL` and `HONEYWELL`; `BOEINX`; `BOMBDR` and `CNDAIR` after a merger |
| Filler word instead of an empty cell | `UNKNOWN`, `NOTREPORTED`, `NONE`, `NA`, and misspelled `UNKOWN` |
| The fact is only in the note | Part number field `UNKNOWN`; note: `FLOOR PANEL CRACK, P/N:453T1996-12` |
| A terse, abbreviated, misspelled note | `INSTALLED NEW GAUGE COVER GLASS ON L1 DOOR, INSALLED PACK AND CLOSED CONTAINER PER 25-66-01.RII ACCOPLISHED` |

Method and full results: `.experiments/findings.md`.
