# Building trains more efficiently with AI at Alstom

**Alstom loses about 3 points of gross margin to project execution and industrial inefficiencies: 13.3% booked in FY 2025/26, against 16.0–16.5% without them.**

![Alstom slide: Rolling Stock execution and industrial inefficiencies impacting margins for too long](docs/images/alstom-margin-slide.png)

*Source: Alstom investor presentation, slide 51.*

The slide names three causes: poor end-to-end coordination across supply chain and logistics, late engineering changes that slow the ramp-up to serial production, and frequent production rescheduling.

This repo explores how AI can help recover that margin.

## The demo

Three noisy files describe a family of six train variants, `V1` to `V6`: an engineering BOM, a purchasing item list and free-text technical notes. Rules reconcile what can be settled mechanically, and an agent settles the rest by reading the notes, asking a person when the data does not decide.

### Run it

The agent needs an OpenRouter key: copy `.env.example` to `.env` and fill in `OPENROUTER_API_KEY`.

```
git clone git@github.com:opitcho/cognyx-case.git
cd cognyx-case
uv sync
uv run --env-file .env streamlit run jean-code/src/app.py
```

The reconciled database `out/pilot.db` comes with the repo, so there is nothing to build first.

## Example questions

| Question | Answer |
|---|---|
| Which sub-assemblies of `V1` can I reuse in `V2`? | All 40 have the same content in `V2`. 36 keep the same reference. 4 are under another one: `HC-6001` as `CL-0931`, `KP-0457` as `DC-3001`, `RG-0212` as `TC-8100`, `ST-4100` as `MP-4418`. 4 contain an obsolete or superseded part: `DR-1043`, `FC-6100`, `HT-5300`, `KP-0457`. |
| `V3` and `V4` differ only by speed class (160 against 200 km/h). What differs, and is each difference justified? | 26 sub-assemblies are the same. `LR-1500` has the same content as `PB-2281`. 4 are nearly the same: the air duct (`VL-905` added) and the left door leaf (`JT-305` added) are both required for 200 km/h by a note, while the glazed partition (`BK-367` added) and the sliding step (12 bolts against 16) have no note. The other 9 are different designs. |
| `TH-415` is superseded. What is affected, and is the replacement already in use? | It is in `HT-5300` on all six variants. Its replacement `TH-450` is already used in `TC-8437` on `V4` and `V6`. The unit cost goes from 59.43 to 78.88 EUR. |
| What does the door system cost in each variant? | `V1` 229,555.56 EUR, `V2` 267,814.82, `V3` 331,683.36, `V4` 356,572.22, `V5` 439,188.24, `V6` 515,070.20. Every line has a price. |
| What would `V5` save by using seat frame `SF-9020` in place of `SF-9064`? | 11.48 EUR per unit, at 200 per train: 2,296.00 EUR per train. |

## Appendix: rebuild the database

`out/pilot.db` is computed from the raw files in `data/raw/` and the claims in `data/claims.jsonl`. The app rebuilds it after every claim. To rebuild it by hand, for example after changing the code in `pipeline/`:

```
uv run python -m pipeline.build
```
