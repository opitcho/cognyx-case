# Show reuse first, then price it

**Bottom line.** The pilot should demonstrate five things inside the 4-hour build: (1) clean, traceable part references, (2) a map of which sub-assemblies are shared across train variants, (3) a ranked list of near-identical sub-assemblies that could be merged, (4) a review queue of inconsistencies, and (5) free-text notes attached to the sub-assembly they concern. Three further use cases belong to pilot weeks 2 and 3: a carry-over estimate for a new tender, a purchasing consolidation view, and a draft master structure covering all variants. The business reason is in Alstom's own filings. Alstom holds a backlog priced at an 18.0% gross margin but booked 13.3% in fiscal year 2025/26, and it blames rolling-stock execution, including "additional activities performed to implement engineering changes" ([Alstom Equity Story, Oct 2026, slide 51](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)). Its 2025/26 risk factors add a new sentence: at tender time "existing references may become obsolete over time, requiring redesign or adaptation for new applications" ([Alstom URD 2025/26, section 4.2.2.2, PDF p185](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)). The evidence for the size of the benefit is weaker than the evidence for the problem. No source gives a reuse rate, a bid cost in euros or a win rate for any train maker, and most savings figures are vendor claims or come from other sectors. The honest demo claim is therefore "here is what is shared, what is nearly shared and what does not add up in your data", not "this saves X%". One correction matters for the dataset: Régiolis (Coradia Polyvalent) is not built at Valenciennes or Crespin. The families tied to those sites are Regio 2N / Omneo, RER NG and MF19. The pilot itself is a fictional recruitment exercise and must not be presented as a real Cognyx customer reference ([case statement repository](https://github.com/leopoldlacroix/Cognyx_case)).

## How to read this report

- **"Quote"** means the words are the source's own. Read status of each source is in section 6.
- **"Inference"** means reasoning by the note-takers or by this report. It is not a statement by any source.
- **"Vendor claim"** means the number comes from a seller of software or from its customer in the seller's material. Nobody independent checked it.
- A figure tagged **"snippet only"** was seen only in a search-engine summary. Do not quote it without opening the page.

### Words used in this report

| Term | Plain meaning |
|---|---|
| Rolling stock | Trains, metros and trams (the vehicles, not the track). |
| Tender | A formal competition run by a buyer. Suppliers submit a priced offer, called a bid. |
| RFQ | Request for quotation. Another word for the buyer's request for a priced offer. |
| BOM (bill of materials) | The list of parts and sub-assemblies that make up a product, usually as a tree. |
| Sub-assembly | A group of parts built as one unit, for example a door system or a seat. |
| Variant | One version of a train family, for example a different length, voltage or interior. |
| Platform | A shared base design from which variants are derived. |
| PLM | Product lifecycle management software. Holds engineering data such as designs and BOMs. |
| ERP | Enterprise resource planning software. Holds purchasing, stock and cost data. |
| EBOM / MBOM | The BOM as engineering designed it / the BOM as the factory builds it. |
| ETO (engineer-to-order) | A business where each order needs some new engineering. Train building is one. |
| NRE (non-recurring engineering) | One-off design and engineering cost for an order, as opposed to the recurring cost of building each unit. |
| Backlog | Orders signed but not yet delivered. |
| Gross margin | Sales minus the direct cost of what was sold, as a share of sales. |
| Adjusted EBIT margin | Operating profit as a share of sales, after Alstom's own adjustments. |
| bps (basis points) | Hundredths of a percentage point. 60 bps = 0.6 points. |
| Homologation / authorisation | Official approval that a vehicle type may run on a network. |
| Framework contract | A contract that fixes terms once and lets the buyer place several orders ("call-offs") later. |
| URD | Universal Registration Document. Alstom's annual regulated filing. |
| 150% BOM | A master BOM that contains every possible option for a family. Each real variant ("100% BOM") is a subset. |
| Configurator | Software that builds a valid variant from stored rules and modules. |
| Fuzzy matching | Matching text strings that are close but not identical, for example with a typo. |
| Commonality index | A score for how much a product family shares parts. |
| Clone-and-own | Copying an existing design or BOM and then changing the copy, with no link kept to the original. A software term used here by analogy. |

## 1. Tenders take two years and lock in costs before the design exists

### The process in brief

| Step | What happens | Typical duration in the documented cases | Source |
|---|---|---|---|
| Market sounding and pre-qualification | Buyer tests the market and shortlists bidders. | Part of the 1.5 to 2 years below. | [ARA Tendering Framework 2020, p.1 and p.3](https://ara.net.au/wp-content/uploads/Tendering-Framework-2020-2.pdf) |
| Bid preparation | Supplier reads the specification, defines the offered train and prices every requirement. | About 3.5 months (NSW New Intercity Fleet: tender issued 4 Sep 2015, responses 23 Dec 2015) to about 6 months (NSW Regional Rail Fleet, with extensions). Durations are arithmetic on the dated milestones. | [NSW Audit Office, Oct 2025, sections 2, 4.1, 5](https://www.audit.nsw.gov.au/our-work/reports/rail-rolling-stock-procurement) |
| Evaluation, negotiation, award | Often a preferred bidder, then a best and final offer. | Call to contract: about 18 to 24 months when it goes to plan (NSW). In the UK, Thameslink was planned at "around 16 months" and "took over four and a half years". | [NSW Audit Office 2025](https://www.audit.nsw.gov.au/our-work/reports/rail-rolling-stock-procurement); [NAO 2014, Part One](https://www.nao.org.uk/wp-content/uploads/2014/07/Procuring-new-trains.pdf) |
| Design, build, test, authorisation, delivery | Supplier executes the contract through gate reviews. | Régiolis: contract Oct 2009, first deliveries "prévues dès 2013". NSW New Intercity Fleet: first trains expected 2019, in service 3 Dec 2024. | [Alstom press release, 27 Oct 2009](https://www.alstom.com/fr/press-releases-news/2009/10/SNCF-attribue-a-Alstom-le-marche-de-la-nouvelle-generation-de-materiels-TER-a-un-niveau-20091027); [NSW Audit Office 2025](https://www.audit.nsw.gov.au/our-work/reports/rail-rolling-stock-procurement) |

- **Inference:** a fair planning figure is 3 to 6 months to prepare a bid, 1.5 to 2 years from call to contract, and 3 to 4 years from contract to first delivery for a platform-derived train. This is a synthesis of four cases from Australia, the UK and France. It is not a published benchmark.
- Alstom describes typical rolling-stock contracts as "From > €100m to € multi-billion; 3 to > 5 years" ([Equity Story Oct 2026, slide 15](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)).

### How France buys regional trains

- Historically the regions paid and SNCF bought. Quote: "les régions n'achètent pas directement les trains mais subventionnent SNCF Mobilités, qui achète les trains et en reste propriétaire" ([Cour des comptes 2019, pp.26-27](https://www.ccomptes.fr/system/files/2019-10/20191023-rapport-TER-ouverture-concurrence.pdf)).
- Two national framework contracts served the regions. Régiolis went to Alstom in 2009 with a firm first order: "La tranche ferme de ce contrat s'élève à 800 millions d'euros" for 100 trainsets ([Alstom press release, 27 Oct 2009](https://www.alstom.com/fr/press-releases-news/2009/10/SNCF-attribue-a-Alstom-le-marche-de-la-nouvelle-generation-de-materiels-TER-a-un-niveau-20091027)). Regio 2N went to Bombardier (now Alstom), with "a maximum of 860 Omneo Regio 2N trains" ([Alstom Coradia product page, vendor marketing](https://www.alstom.com/solutions/rolling-stock/coradia-regional-trains-accessible-solutions-move-regions)).
- **Inference:** for the supplier this has meant one big tender, then many smaller configured orders per region. Each order is a small "variant bid": the platform is fixed but length, traction, interior and equipment change. This matches the pilot's framing of reuse across variants.
- The picture is changing. Regions now often take ownership of their fleets, and a 2026 Senate note warns of "un risque « d'archipélisation » des modèles de rames" ([Sénat synthesis note, May 2026, p.5](https://www.senat.fr/fileadmin/cru-1778089154/Commissions/Finances/2025-2026/Controles/Controle_concurrence_ferroviaire__essentiel_post_commission.pdf)). **Inference:** more separate buyers means more variant requests for a supplier. The Senate note is about public cost, not supplier cost.

### Where money is won or lost

| Point | What the source states | Source and grade |
|---|---|---|
| The price is committed before detailed design. | Quote: "as the tender phase is not a detailed design phase, some technical assumptions and choices are made during tender about the ways to comply with customers' technical requirements. These may prove wrong at contract stage". | [Alstom URD 2025/26, 4.2.2.2, PDF p185](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf), company filing |
| Reuse of past designs is a costing assumption that can fail. | Quote: "existing references may become obsolete over time, requiring redesign or adaptation for new applications". This sentence is new in the 2025/26 edition. | Same section, company filing |
| Cost overruns and penalties follow. | Quote: "the actual costs of developing and building projects could significantly exceed the initial estimated costs at the time of bidding". If performance or schedule is missed, "the customer can, in the majority of cases, demand the payment of penalties or terminate the contract." | Same section, company filing |
| Losses hit profit at once. | Quote: "when a project review indicates a negative gross margin, the estimated loss at completion is immediately recognised." Quote: "Bid costs are recorded as selling expenses when incurred." | [Alstom URD 2025/26, PDF p79 and p83](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf), company filing |
| The margin priced at signature is not the margin booked. | Gross margin in backlog 18.0% at 31 March 2026. Booked gross margin 13.3% in FY 2025/26. Slide title: "Rolling Stock execution and industrial inefficiencies impacting margins for too long". | [Equity Story Oct 2026, slide 51](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf), company investor material |
| The trouble sits in new products. | CEO quote: "significant part of the problems are in a part of the projects where we are developing new products." And: "when we are in serial production, the product are produced efficiently". | [Alstom call transcript, 16 Apr 2026, p5](https://www.alstom.com/sites/alstom.com/files/2026/04/20/20260416_Transcript_Conference_Call_EN.pdf), company filing |
| One-off engineering makes small orders dear. | Quote: "costs per vehicle can be between 20%-60% higher for orders of less than 200 vehicles (because of non-recurring costs)". UK study, 2011. | [Arup for the Rail Value for Money study, p.47](https://www.orr.gov.uk/sites/default/files/om/rvfm-arup-rolling-stock-mar2011.pdf), government-commissioned study |
| Bidding itself is costly. | Quote: "the costs of tendering such a project are particularly large, often running to many millions of dollars". Australia only. Quote: "all tender engineering costs must be applied to the initial order". | [ARA Tendering Framework 2020, p.10](https://ara.net.au/wp-content/uploads/Tendering-Framework-2020-2.pdf), industry-association position paper |
| Most of the cost is bought in. | Quote: purchases from third parties are "a significant proportion of Alstom's cost of activities (64% in the 2025/26 fiscal year)". Group-wide, not rolling stock alone. | [Alstom URD 2025/26, 4.2.2.3, PDF p186](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf), company filing |

Key Alstom numbers, all from company filings:

| Fiscal year (to 31 March) | Sales | Adjusted EBIT margin | Backlog | Gross margin in backlog |
|---|---|---|---|---|
| 2024/25 | €18,489m | 6.4% | €94,960m | 17.8% |
| 2025/26 | €19,171m | 6.1% | €104,412m | 18.0% |

Source: [Alstom URD 2025/26, PDF p47-48](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf).

- Alstom's own margin bridge for 2025/26 attributes "(60) bps" to "projects execution" ([URD 2025/26, PDF p47](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)).
- Alstom withdrew its target: "The medium-term ambition of adjusted EBIT margin of 8-10% will no longer be met by FY 2026/27" ([preliminary results press release, 16 Apr 2026, p3](https://www.alstom.com/sites/alstom.com/files/2026/04/16/20260416_PR_Alstom_Prelim_FY202-26_Results_EN.pdf)).
- Alstom lists "Platforming & Standardisation" and "Product convergence" among its profitability levers for rolling stock, and "Accelerate procurement savings" among its priority actions ([Equity Story Oct 2026, slides 15 and 52](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)).

Inferences on size (arithmetic on Alstom's figures; Alstom does not publish these amounts):

- The slide walks from 17.8% to a "Theoretical P&L gross margin" of "16.0-16.5%", then to 13.3%. The gap of 2.7 to 3.2 points on €19,171m of sales is roughly €520m to €610m in one year.
- One point of gross margin is worth about €190m. The 60 bps for project execution is about €115m.
- Linking design reuse to this gap is this report's argument. Alstom does not say how much of the gap reuse would avoid.

### Who decides reuse, and when

- **Not found:** no source states who decides to reuse, adapt or design new, or at which review.
- What is evidenced: Alstom runs a tender review covering "contract price, margin, risks and opportunities, and related financial reserves, cash curves", including "the solution novelty", supported by a tool that "ensures the traceability of assumptions applied throughout the entire cycle" ([URD 2025/26, 4.2.2.2, PDF p185](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)).
- **Inference (likely sequence):** (1) commercial and platform managers choose which platform to offer. (2) Engineers check each requirement against that platform and class each sub-system as carry-over, adapt or new. (3) Cost estimators price each class. (4) The tender review approves price, margin and reserves. Only step 4 is directly evidenced.
- **Inference:** the URD describes no tool that compares a tender's BOM with existing sub-assemblies. A reuse view would sit inside the control framework Alstom already describes.

## 2. Problem list with evidence

Each row states what the source says, then how far it applies to Alstom's regional trains.

| # | Problem | Evidence (quote or figure) | Source, grade, sector | Applies to rail tenders? |
|---|---|---|---|---|
| P1 | Tender cost assumptions about reuse turn out wrong. | "existing references may become obsolete over time, requiring redesign or adaptation for new applications". Earlier editions said: "projects have not been undertaken over a certain period and have limited relevance for new applications". | [Alstom URD 2025/26, PDF p185](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf), company filing, rail. Earlier wording: [URD 2023/24, p.175](https://www.alstom.com/sites/alstom.com/files/2024/05/15/20240515_Alstom_Universal_Registration_Document_EN.pdf) and [URD 2024/25, PDF p175](https://www.alstom.com/sites/alstom.com/files/2025/05/28/20250528_Universal_Registration_Document_EN.pdf) (the 2024/25 text is machine-decoded from a broken PDF and needs a visual check). | Directly. Strongest single citation for the pilot. |
| P2 | Late engineering change eats the margin. | "Extended development phases and delayed homologation of new products, resulting in slower ramp-up to serial production and additional activities performed to implement engineering changes". | [Equity Story Oct 2026, slide 51](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf), company investor material, rail | Directly. The link to reuse is inference. |
| P3 | Late-stage engineering charges can be very large. | Bombardier: "an additional charge of $435 million at Transportation, largely related to incremental engineering, certification and retrofit costs associated with a number of late-stage projects mainly in the U.K. and Germany." | [Bombardier press release, 6 Aug 2020](https://bombardier.com/en/node/2010424), company filing, rail | Shows late change is costly. Sources do not say reuse would have prevented it. |
| P4 | Every customer wants its own train. | France: "en 2018, 39 différentes séries de trains TER coexistaient en France. Cette hétérogénéité nuit à l'optimisation du parc". UK: "One manufacturer stated that there are now 20 variants of its stock being maintained in the UK". | [Cour des comptes 2019, pp.64-65](https://www.ccomptes.fr/system/files/2019-10/20191023-rapport-TER-ouverture-concurrence.pdf), independent audit, France; [Arup 2011, p.48](https://www.orr.gov.uk/sites/default/files/om/rvfm-arup-rolling-stock-mar2011.pdf), government study, UK | Directly, from the buyer's side. |
| P5 | New trains on a shared platform are built by copying. | "Currently, a clone and own strategy is used in order to build a new trainset based on the existing platform. However, every new trainset developed based on the same platform requires an individual certification." | [Zeller, Ratiu, Höfig (Siemens), arXiv 2106.02273](https://arxiv.org/pdf/2106.02273), preprint by industry authors, rail (Siemens, not Alstom) | Rail, but a competitor. Whether Alstom does the same is not verified. |
| P6 | One BOM per variant breeds inconsistency. | "this approach leads to data explosion, redundancy, poor scalability, and separation of information across systems". The result is "a proliferation of BOM structures prone to inconsistencies, negatively affecting downstream processes such as production planning, costing, and change management." | [Kourtis et al., Proceedings of the Design Society 2026, pdf p.1](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader), peer-reviewed conference, ETO fibre-laser maker | By analogy (ETO, not rail). No study measures how much hardware BOMs drift. |
| P7 | Copies lose their link; reuse depends on memory. | "Reuse is done via personal knowledge, memory and networking." And: "no connection between clones is maintained." | [Cloning study, 2013, pdf pp.4-5](https://people.csail.mit.edu/mjulia/publications/An_Exploratory_Study_of_Cloning_in_Industrial_Software_Product_Lines_2013.pdf), peer-reviewed conference, **software** product lines (11 interviews) | By analogy only. Software, not hardware. |
| P8 | Engineers cannot find what exists. | "on average 20% of a designers time is spent searching for and absorbing information". "Searches to revisit past projects accounted for 61 searches (28%)." | [Design Society, "Information push", pdf p.2](https://designsociety.org/download-publication/19295/INFORMATION+PUSH%3A+STRATEGIES+FOR+IMPROVING+EFFICIENCY+OF+DESIGN+INFORMATION+MANAGEMENT) (secondary citation of a 1990s survey); [Aurisicchio et al., ICED 2003, pdf p.8](https://designsociety.org/download-publication/24024/INVESTIGATING+KNOWLEDGE+SEARCHES+IN+AEROSPACE+DESIGN), peer-reviewed conference, **aerospace**, five designers' diaries | By analogy. Aerospace, small samples, old. |
| P9 | Engineers do not try to reuse when they cannot see what is reusable. | "due to a limited support in recognising the existence of the reusable information, designers often make no attempt at reuse". | [ICED 2007, "Improving design reuse using context", pdf p.1](https://www.designsociety.org/download-publication/25416/Improving+Design+Reuse+Using+Context), peer-reviewed conference, secondary citation | By analogy. "Do not trust it" and "faster to redraw" are widely asserted but no study found quantifies them. |
| P10 | A new part number costs far more than its drawing. | "The average total cost for adding a single new part into a system is about $27,500." Engineering and design $12,600; purchasing $5,200; logistics support $5,100. The source calls its values "very conservative". | [US Defense Standardization Program Office, SD-19, Dec 2013, pdf p.11](https://everyspec.com/DoD/DoD-PUBLICATIONS/SD-19_DEC2013_49300/), government, **US defence** | By analogy only. Not a rail figure. Underlying data older than 2013. |
| P11 | Quotation takes long and errors cut both ways. | "By overestimating the cost, the risk of losing customers increases, although conversely, underestimating the cost reduces profitabilit[y]". | [Kristjansdottir PhD thesis, DTU, pdf p.23](https://backend.orbit.dtu.dk/ws/files/145893822/PhD_Katrin_Kristjansdottir.pdf), thesis, mixed manufacturing | General ETO. No rail figure for bid accuracy found. |
| P12 | PLM and ERP disagree, and errors hide. | "the errors that occur due to the inconsistent data exchange are often hidden deeply in the system and hardly recognized." Example: "the component is entered with one unit of measure in one system and in another system is the same component entered under a different unit of measure." | [Design Society case paper, Končar Instrument Transformers, pdf p.1 and p.5](https://www.designsociety.org/download-publication/32035/INTEGRATION+OF+PLM+AND+ERP+SYSTEMS+AT+KONCAR+-+INSTRUMENT+TRANSFORMERS), peer-reviewed conference, electrical equipment | By analogy. Mechanism documented; frequency never measured in any source found. |
| P13 | Dirty references block comparison. | "many of these inconsistencies that make comparison difficult are most easily discovered via comparison." Fuzzy name matching alone "flagged 743 possible matches which is difficult to sift through". | [Tate et al., arXiv 2411.10384, Sections I and VI](https://arxiv.org/pdf/2411.10384), preprint, hardware and software BOMs for supply-chain risk | Method transfers. Two worked examples only, no precision or recall. |
| P14 | Lessons sit in free text nobody reads. | Engineering change requests are "often stored but not consulted, missing important opportunities to learn from previous projects". | [Pacella, Grieco, Blaco 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5164909), peer-reviewed, **rail supplier** (MerMec, Italy), 54 documents in Italian | Rail. Shows feasibility, reports no money or time saved. |
| P15 | A searchable lessons database is not enough. | "58 percent of managers stated that current processes and systems do not allow them to retrieve the right lessons at the right time". | [US GAO-02-195, pdf p.33](https://www.govinfo.gov/content/pkg/GAOREPORTS-GAO-02-195/pdf/GAOREPORTS-GAO-02-195.pdf), government audit, **NASA**, 2002 | By analogy. Aerospace agency, 2002. |
| P16 | Each changed type needs fresh approval. | "every modification involves significant costs, as a single vehicle type can have multiple subtypes." Authorisation after an ERTMS upgrade "takes between one and four years". | [CER position paper, Feb 2026, pdf p.2 and p.7](https://www.cer.be/images/publications/positions/260203_CER_Position_Paper_Vehicle_Authorisation.pdf), industry-body position paper (operators' lobby), Europe | Rail. Advocacy document. Concerns signalling upgrades, not new regional trains. |
| P17 | Most cost is purchased, across thousands of suppliers. | "64% in the 2025/26 fiscal year"; "approximately 17,000 suppliers worldwide". | [Alstom URD 2025/26, PDF p186 and p411](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf), company filing | Directly, but Group-wide. No figure for a single train. |
| P18 | Customer requests delayed a train built at Crespin. | Regio 2N deliveries ran "huit mois en moyenne" late; the maker cited the train's complexity and the regions' requests. | [Wikipedia FR, Regio 2N](https://fr.wikipedia.org/wiki/Regio_2N), Wikipedia, read through an automated summary | Rail and local, but the source is weak. Needs a primary citation before use. |

Two cautions carried over from the notes:

- Reuse is a trade-off, not a pure good. Thevenot and Simpson warn that "Too much commonality can cause products to lack distinctiveness and perform poorly" ([abstract only](https://pure.psu.edu/en/publications/commonality-indices-for-product-family-design-a-detailed-comparis/)).
- Copies do not always drift. In software, one study found "only 12% of clones were ever changed and only 15% of all changes were unintentionally inconsistent" ([cloning study, pdf p.8](https://people.csail.mit.edu/mjulia/publications/An_Exploratory_Study_of_Cloning_in_Industrial_Software_Product_Lines_2013.pdf)). **Inference:** the pilot should measure drift in the data, not assume it.

## 3. Use cases

### What already exists, in one table

| Approach or product | What it does | Needs 3D geometry (CAD)? | Reported result | Grade |
|---|---|---|---|---|
| Structure-constrained fuzzy matching | Uses the parent-child tree to limit fuzzy name matches. | No | Hardware example: 743 candidate matches cut to 21. | [Tate et al., preprint](https://arxiv.org/pdf/2411.10384) |
| BOM tree distance and clustering | Scores how alike two BOMs are; groups them into families. | No, but needs cleaned labels | 75 electronics BOMs placed in the right families ("preliminary result"). | [Romanowski and Nagi 2005, peer-reviewed](https://www.eng.buffalo.edu/~nagi/papers/IEEESMCApaper.pdf) |
| Graph similarity of variant BOMs | Finds assemblies that are "promising standardization candidates". | No, but "'Clean' Bom data required" | 14 truck rear-axle variants at MAN, 4,250 rows. Qualitative result only. | [Schmidt et al., ICED 2017, peer-reviewed conference](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance) |
| Generic BOM by tree union | Merges variant BOMs into one structure with optional parts and quantity ranges. | No | 405 BOMs of a nurse-call device maker. No accuracy figure in passages read. | [Romanowski and Nagi, author manuscript](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf) |
| Product configurators | Build quotes from stored modules and rules. | No | 14 companies: average quotation lead time down 85.5% (abstract) or 83.7% (as relayed in a thesis). Company estimates. See section 7. | [Haug, Hvam, Mortensen 2011, peer-reviewed, abstract only](https://www.cambridge.org/core/journals/ai-edam/article/impact-of-product-configurators-on-lead-times-in-engineeringoriented-companies/107D0DB206626EE028613F59CB0DF203) |
| PTC Windchill AI Parts Rationalization | Finds duplicate parts by shape. | **Yes.** "solely based on the 3D geometry". Ignores "Metadata or part attributes". | No customer, no figure. Launched 27 Jan 2026. | [PTC help, vendor documentation](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html) |
| CADENAS PARTsolutions | Shape search, duplicate reports, costing from similar parts. | Mostly yes | Vendor claims: see UC3 and UC6. | [CADENAS and PTC deck 2015, vendor marketing](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf) |
| Dassault Part Classification as-a-Service | Classifies a whole part catalogue on one taxonomy. | Not stated | Vendor claim: "our customer business cases range from 27.5M€ to 50M€ per year." Customers unnamed, undated. | [Dassault Systèmes page, vendor marketing](https://events.3ds.com/part-classification-service-chaos-reuse) |
| Cognyx | BOM platform over PLM and ERP. | Not stated | Vendor claim: "reduce RFQ response time by up to 40%". No customer, date or method. No case study found. | [Cognyx use cases, vendor marketing](https://en.cognyx.io/use-cases) |

- **Inference:** the commercial duplicate-finding tools depend on CAD shape. The synthetic dataset has no CAD. A tool that works from BOM structure and text is not competing on the same data. No product found claims sub-assembly-level reuse detection from BOM structure without geometry.
- **Inference:** no published method outputs "reusable sub-assemblies" directly. A demo has to compose the building blocks: exact shared sub-trees, near-matching sub-trees, and optional or alternative children.

### Summary table

| # | Use case | Main user | Answers | Fit |
|---|---|---|---|---|
| UC1 | Reference reconciliation | Thomas; all others depend on it | "Are these two references the same thing?" | 4-hour build |
| UC2 | Cross-variant reuse map | Bruno, engineers | "Which sub-assemblies are reused across variants?" | 4-hour build |
| UC3 | Near-duplicate (reusable) candidates | Engineers, Bruno | "Which sub-assemblies are almost the same and could be one?" | 4-hour build (simple version) |
| UC4 | Inconsistency review queue | Engineers, Thomas | "Where are the inconsistencies?" | 4-hour build |
| UC5 | Notes attached to sub-assemblies | Engineers, bid team | "What do we already know about this sub-assembly?" | Light version in 4 hours; full version weeks 2-3 |
| UC6 | Tender carry-over estimate | Cost estimators, bid team | "For a new variant, what is carry-over, adapt or new, and what does it cost?" | Weeks 2-3 (one mock screen in the demo) |
| UC7 | Purchasing consolidation view | Procurement | "Where do we buy the same thing under different references, suppliers or prices?" | Weeks 2-3 |
| UC8 | Draft master (150%) structure | Engineering methods, Thomas | "What is the common core and what are the options?" | Weeks 2-3 |

### UC1. Reference reconciliation

| Item | Content |
|---|---|
| Who it is for | Thomas (Lead Data Engineer) first. Every other use case rests on it. |
| Problem solved | P12, P13. References with typos, different levels of detail and mixed units make variants look more different than they are. |
| What the tool shows | A table of raw reference, cleaned reference, match rule used, confidence, and the evidence for the match. Each match is tagged as one of three types found in the literature: transcription error ("IN3S00A and IN3500, where a 5 is switched for an S"), different specificity ("V17N" versus "V17N-ZB11"), or a real substitution. Units are converted to one base unit, with the original kept. |
| Data needed from the synthetic dataset | Part reference, description (French or English), parent reference, quantity, unit, variant identifier. |
| Value evidence | Using the BOM tree to constrain fuzzy matching cut candidates from 743 to "only 21 matches, identifying transcription errors and incremental component variations with high precision" ([Tate et al., Section VI, preprint](https://arxiv.org/pdf/2411.10384)). Caveats: two worked examples, no precision or recall, and the authors call their 0.85 similarity threshold "arbitrary". Text normalisation of terse maintenance notes reached precision 99.7 and recall 97.5 and cut vocabulary by more than 50%, on **English mining** work orders only ([MaintNorm, W-NUT 2024, Table 7](https://aclanthology.org/2024.wnut-1.7.pdf)). Vendor claim (Dassault): "The root cause isn't a lack of search tools. It's that your part catalog [...] was not classified on a consistent taxonomy" ([Dassault page](https://events.3ds.com/part-classification-service-chaos-reuse)). |
| Limits to state | No published accuracy exists for matching industrial part masters. No source evaluates unit reconciliation. Accuracy must be measured on a labelled sample of the pilot's own data. |
| Fit | 4-hour build. Deterministic rules first, fuzzy matching within the same parent, then a human review list. |

**Inference:** a "good enough" target is defensible. A peer-reviewed data-quality paper reports a case company holding that "it would never be possible nor expedient to obtain 100% correct prices" ([Haug, Zachariassen, van Liempd 2011, pdf p.19](https://www.jiem.org/index.php/jiem/article/view/232)). That supports a tool that flags and ranks suspect records for review over one that promises fully clean data.

### UC2. Cross-variant reuse map

| Item | Content |
|---|---|
| Who it is for | Bruno (Engineering Director) for the headline. Engineers for the detail. |
| Problem solved | P4, P5, P8, P9. Nobody can see in one place what is shared across variants. |
| What the tool shows | A grid of sub-assemblies (rows) against variants (columns). Each cell says: identical, present with differences, or absent. A headline number: the share of sub-assemblies used in all variants, in several, and in only one. |
| Data needed | Cleaned references from UC1, the parent-child tree, variant identifier, and a sub-assembly family label if the dataset has one. |
| Value evidence | The measure has peer-reviewed precedent. A study of a furniture maker found "83% of component types are used in three or fewer double bed designs" and concluded the company "does not reuse components effectively" ([Vasantha et al., ASME IDETC 2018, pdf p.4](https://strathprints.strath.ac.uk/64624/1/Vasantha_etal_IDETC_2018_A_probabilistic_design_reuse_index.pdf)). **Furniture, not ETO.** MAN and TU Munich used BOM similarity on 14 rear-axle variants to answer "Which assemblies or whole areas of the component variants are theoretically promising standardization candidates" ([Schmidt et al., ICED 2017](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance)). **Trucks, qualitative result, clean data.** Alstom itself names "Platforming & Standardisation" as a margin lever ([Equity Story, slide 15](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)). |
| Limits to state | No rolling-stock reuse rate has been published by any manufacturer, so there is no external benchmark to compare the number against. |
| Fit | 4-hour build. This is the screen that answers the first half of the case question. |

### UC3. Near-duplicate (reusable) candidates

| Item | Content |
|---|---|
| Who it is for | Engineers who decide whether two designs can become one. Bruno for the count. |
| Problem solved | P5, P6, P10. Two variants carry sub-assemblies that differ by a handful of lines. Each difference may be needed or may be an accident of copying. |
| What the tool shows | Pairs of sub-assemblies ranked by similarity, with a side-by-side list of exactly which lines differ. Each pair is a question for an engineer: "is this difference intended?" |
| Data needed | Cleaned references, tree, quantities and units. Cost per line if available, to rank by money at stake. |
| Value evidence | The US defence estimate of "about $27,500" life-cycle cost per new part ([SD-19, pdf p.11](https://everyspec.com/DoD/DoD-PUBLICATIONS/SD-19_DEC2013_49300/)). **US defence, not rail; use as an order of magnitude only.** Vendor claims: Ingersoll Rand, "Saving potential (only inventory cost) of 60.000 duplicate parts (5% of all parts) = 30 Mio. US$" (a 2010 customer conference claim relayed by a vendor, labelled a "potential") ([CADENAS and PTC deck, slide 5](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf)); MAC Trailer, parts cut "from 1.3 million distinct parts and assemblies to just 300,000" ([vendor case study](https://partsolutions.com/wp-content/uploads/2023/07/Mac-Trailer-Case-Study_FINAL.pdf)). Both are from machinery or trailers, with CAD shape search. |
| Limits to state | Two peer-reviewed sources disagree on method. Romanowski and Nagi argue tree edit distance gives wrong costs for BOMs because "we are interested primarily in content; topology is a secondary concern". Schmidt et al. use it and report valid results. **Inference:** compare content first (which children, which quantities), structure second. Cost-per-new-part figures in vendor material vary by more than ten times, so any business case needs Alstom's own number. |
| Fit | 4-hour build in a simple form: overlap of child sets between sub-assemblies of the same family, plus the difference list. Weighted similarity and tuning belong to weeks 2-3. |

### UC4. Inconsistency review queue

| Item | Content |
|---|---|
| Who it is for | Engineers and data owners. Thomas, as proof of rigour. |
| Problem solved | P6, P12, P13. The same item appears with different units, quantities, descriptions or parents across variants. |
| What the tool shows | A ranked list of findings. Each has a type (unit mismatch, quantity mismatch, description conflict, same part under a different parent, orphan reference, suspected typo), the rows involved, and a suggested fix. Nothing is auto-corrected. |
| Data needed | All BOM columns. Cost and supplier columns add price and supplier conflicts. |
| Value evidence | The 2026 Design Society paper describes the same need in ETO: inconsistencies "often remain hidden until late validation stages, requiring time-consuming manual diagnosis", and its prototype highlights "missing metadata, misaligned structures, and incomplete rule effects" ([Kourtis et al., pdf pp.1-2 and p.6](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader)). It is a proof of concept with no quantified benefit. The unit-of-measure case is documented in a PLM-ERP integration paper ([Končar case, pdf p.5](https://www.designsociety.org/download-publication/32035/INTEGRATION+OF+PLM+AND+ERP+SYSTEMS+AT+KONCAR+-+INSTRUMENT+TRANSFORMERS)). Tate et al. note that one BOM may list a component n times while another uses a quantity field, and "you have to rectify these different representations" ([Section III.G](https://arxiv.org/pdf/2411.10384)). |
| Limits to state | No source measures how often these errors occur in manufacturing. **Inference:** the pilot's own count on Alstom's extract would be stronger evidence than any published number. |
| Fit | 4-hour build. This answers the second half of the case question. |

### UC5. Notes attached to sub-assemblies

| Item | Content |
|---|---|
| Who it is for | Engineers and the bid team. |
| Problem solved | P14, P15, P16. Knowledge about a sub-assembly (obsolete component, supplier issue, approval status, "equivalent to") sits in free text and is not seen when the reuse decision is made. |
| What the tool shows | On each sub-assembly, the notes that mention it, in the original language, with a small set of extracted flags (for example: mentions obsolescence, mentions equivalence to another reference, mentions a unit or value, mentions approval). Every flag links back to its source sentence. |
| Data needed | Free-text notes in French and English, with or without an explicit part reference. Cleaned references from UC1 to link them. |
| Value evidence | A rail supplier's change requests "can contain recurring problems" yet are "often stored but not consulted" ([Pacella et al. 2016, rail, 54 Italian documents](https://pmc.ncbi.nlm.nih.gov/articles/PMC5164909)). At NASA, 58% of managers could not "retrieve the right lessons at the right time" ([GAO-02-195, pdf p.33](https://www.govinfo.gov/content/pkg/GAOREPORTS-GAO-02-195/pdf/GAOREPORTS-GAO-02-195.pdf)). **Inference:** showing the note in context, on the sub-assembly being quoted, addresses the stated failure. Alstom names component obsolescence as a risk: "Some electronic components may be discontinued long before fleet end-of-life, requiring redesign and alternative qualifications" ([URD 2025/26, PDF p186](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)). Vendor statement (Cognyx): "Use AI agents to ingest your unstructured 'Lessons Learned' into enforceable BOM Rules", with no method or accuracy published ([Cognyx use cases](https://en.cognyx.io/use-cases)). |
| Limits to state | Fine-grained extraction from short technical text is error-prone even with a purpose-built corpus: the best relation-extraction model scored micro F1 77 under loose matching and zero under strict matching ([MaintIE, LREC-COLING 2024, Tables 5-6](https://aclanthology.org/2024.lrec-main.954.pdf)). English maintenance text only. No benchmark exists for mixed French and English engineering notes. No verified accuracy exists for language-model extraction from change requests or lessons learned. |
| Fit | Light version in the 4-hour build: link notes to references and extract a small fixed set of flags, each traceable. Turning notes into enforced rules belongs to weeks 2-3 and needs a labelled sample. |

### UC6. Tender carry-over estimate

| Item | Content |
|---|---|
| Who it is for | Cost estimators and the bid team. Bruno for the value story. |
| Problem solved | P1, P2, P11. At bid time, the cost of each requirement must be assumed. The assumption "we can reuse this" is the one Alstom says can fail. |
| What the tool shows | For a requested new variant, each sub-assembly family is classed as carry-over (exists unchanged), adapt (near match from UC3) or new. Costs roll up per class, with the source variant and the open notes from UC5 shown beside each line. |
| Data needed | Everything above, plus a unit cost per line and a short description of the requested variant (for example length, voltage, interior type). |
| Value evidence | Company filing: Alstom "must be able to define the costing assumptions at the time of bidding for all customer specifications" ([URD 2025/26, PDF p185](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)). Thesis case study (a maker of standardised and engineered products): quotation lead time fell "from 9.5 days to 3.4 days" and "453,419 work-hours (75%) were saved [...] over a five-year period" after a configurator ([Kristjansdottir, pdf pp.122-123](https://backend.orbit.dtu.dk/ws/files/145893822/PhD_Katrin_Kristjansdottir.pdf)). The same analysis "assumes that no savings are gained in the case of light ETO products". Peer-reviewed, 14 companies: average quotation lead-time cut of 85.5% or 83.7% (see section 7 for the conflict). Vendor claims: Starlinger uses a parts tool "for a rough calculation with the prices of similar parts" ([vendor case study](https://www.cadenas.de/files/cadenas/Downloads/PDF/Referenzen/EN/PARTsolutions_Starlinger_Success_Story_EN.pdf)); Cognyx, "reduce RFQ response time by up to 40%" ([Cognyx use cases](https://en.cognyx.io/use-cases)). |
| Limits to state | The quotation-time figures measure a configurator in daily use, not the mining of old BOMs. **Inference:** "faster quotation through reuse" is better supported than "more accurate quotation". None of the figures is from rail. The thesis's zero-saving assumption for light ETO is a caution for train tenders. |
| Fit | Weeks 2-3. In the demo, one mock screen or one slide shows where UC2 to UC5 lead. |

### UC7. Purchasing consolidation view

| Item | Content |
|---|---|
| Who it is for | Procurement. |
| Problem solved | P10, P17. The same or an equivalent bought-in item appears under several references, suppliers or prices, so volumes are not pooled. |
| What the tool shows | Groups of equivalent purchased items across variants, with supplier, unit price and total quantity per group, and the spread between lowest and highest price. |
| Data needed | Make-or-buy flag, supplier name, unit price and currency per line, plus cleaned references. Supplier names need their own reconciliation. |
| Value evidence | Company filing: purchases are 64% of Alstom's cost of activities, and "Accelerate procurement savings" is a stated priority for 2026/27 ([URD 2025/26, PDF p186](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf); [Equity Story, slide 52](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)). In the US defence breakdown, purchasing is $5,200 of the $27,500 per new part ([SD-19, pdf p.11](https://everyspec.com/DoD/DoD-PUBLICATIONS/SD-19_DEC2013_49300/)). Vendor claim, no numbers: fewer duplicates bring "Higher purchasing volumes" ([CADENAS and PTC deck, slide 18](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf)). |
| Limits to state | No independent study of supplier master-data quality in manufacturing or rail was found. The 64% is Group-wide and includes services and signalling. No figure exists for the purchased share of one train. |
| Fit | Weeks 2-3. A thin version is possible in the build only if the synthetic dataset carries supplier and price columns. |

### UC8. Draft master (150%) structure

| Item | Content |
|---|---|
| Who it is for | Engineering methods teams. Thomas, for the target data model. |
| Problem solved | P5, P6. One BOM per variant with no shared master. |
| What the tool shows | A proposed master tree for a family: the common core, optional children, alternatives, and quantity ranges across variants. Each real variant is shown as a subset, with deviations highlighted. |
| Data needed | Cleaned, reconciled BOMs for all variants of one family. |
| Value evidence | Definition: 150% BOMs "act as master structures containing all possible components and subassemblies, avoiding duplication of variant-specific BOMs" ([Kourtis et al., pdf p.2](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader)). Precedent: tree union of 405 BOMs into generic BOMs recording optional children and ranges ([Romanowski and Nagi, Section 3.5](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf)). Cognyx lists "Manage Variants, Diversity & Configurations (150%, 100%) in one visual BOM" as a use case ([vendor marketing](https://en.cognyx.io/use-cases)). |
| Limits to state | No study isolates the benefit of a 150% BOM from that of a configurator. Alstom runs its own PLM programme, "PLM4A", to "enable ONE product lifecycle management for all the Alstom product lines" ([URD 2025/26, PDF p16](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)). **Inference:** the pilot output should be positioned as a draft for engineers to review, feeding that programme, not replacing it. |
| Fit | Weeks 2-3. |

## 4. Recommended shortlist for the 20-minute demo

**Recommendation:** show UC2, UC4 and UC3 in that order, with UC1 visible underneath and one UC5 example. Close with UC6 as the next step.

| Minutes | What to show | Use case | For whom | Why |
|---|---|---|---|---|
| 0-3 | The stakes in three company-filing facts: 18.0% priced versus 13.3% booked; "existing references may become obsolete"; 64% bought in. | Framing | Bruno | These are Alstom's own words and numbers. No jargon needed. |
| 3-8 | The reuse grid: what is shared across variants, with one headline share. | UC2 | Bruno | Answers the first half of the case question on one screen. |
| 8-12 | The inconsistency queue: three or four findings, each with its rows and a suggested fix. | UC4 | Bruno and Thomas | Answers the second half. Shows the tool flags and does not silently fix. |
| 12-15 | One near-duplicate pair, side by side, with the lines that differ and a linked French note. | UC3 + UC5 | Bruno | Turns "reusable" into a concrete decision an engineer can make. |
| 15-18 | How matches are made: rules, thresholds, the three match types, measured precision and recall on the seeded errors, what is left for human review. | UC1 | Thomas | He scrutinises quality and maintainability. Measured results on known errors are stronger than any published figure. |
| 18-20 | One slide: weeks 2-3 on real data (carry-over estimate, purchasing view, draft master structure) and what must be measured. | UC6-UC8 | Both | Shows the path to tender value without claiming it is built. |

Reasoning:

- **It answers the question asked.** The case question has two halves: reused or reusable, and inconsistencies. UC2 and UC3 cover the first, UC4 the second.
- **It fits the data.** There is no CAD in the dataset. The commercial duplicate finders rely on shape. The published methods that work on structure and text are exactly the ones UC1 to UC4 use.
- **It rests on the best-supported claims.** The problem is documented in Alstom's filings. The size of the saving is not documented for rail anywhere. A demo that shows facts found in the data avoids resting on a weak percentage.
- **It is honest about the foundation.** Tree-similarity papers assume clean data. Showing UC1 openly tells Thomas that reconciliation comes first, and that the tree helps do it.
- **It respects engineers' habits.** Copying persists because it is "perceived as a favorable and natural reuse approach" ([cloning study, abstract](https://people.csail.mit.edu/mjulia/publications/An_Exploratory_Study_of_Cloning_in_Industrial_Software_Product_Lines_2013.pdf), software). **Inference:** present the tool as making links between copies visible, not as banning copying.
- **It uses words the sponsor knows.** Alstom's public vocabulary is "platforming", "standardisation", "product convergence", "building blocks" and "modular product approach". "Reuse rate" is not a term Alstom uses publicly for design. With Bruno, say "what is common across the platform".

What to avoid in the demo:

- Do not quote a savings percentage for Alstom. None exists in any source.
- Do not present the Cognyx "up to 40%" figure as evidence. It is an unreferenced vendor claim.
- Do not use competitor margins as proof that modularity pays. Stadler markets a modular platform and had a lower margin than Alstom (see section 7 for read status).
- Do not describe the pilot as a real deployment.

## 5. Implications for the synthetic dataset

### Use the right train families

| Family | Tied to Valenciennes Petite-Forêt or Crespin? | Evidence | Use in dataset? |
|---|---|---|---|
| Regio 2N / Omneo (double-deck regional train) | Yes, Crespin. | Built by Bombardier "sur son site de Crespin" ([Wikipedia FR](https://fr.wikipedia.org/wiki/Regio_2N), automated summary). Alstom: "Omneo, a product specifically designed for France [...] more than 550 trains have been ordered" ([URD 2025/26, PDF p18](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)). | **Yes. Best fit for "regional trains".** |
| RER NG (Paris-region suburban train) | Yes, both sites. | Crespin builds the intermediate cars; Petite-Forêt builds the end cars and assembles ([IRJ](https://www.railjournal.com/analysis/new-rer-trains-lead-massive-fleet-renewal-in-greater-paris/), **snippet only**, page returned HTTP 403). New order of 96 trainsets, €1.7bn ([Equity Story, slide 12](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf)). | Possible second family. Not a regional train. |
| MF19 (Paris metro) | Yes, both sites. | Both sites do studies, design, assembly, tests and homologation; "2,300 Alstom employees, including 700 engineers" ([Alstom press release, 7 Mar 2024](https://www.alstom.com/press-releases-news/2024/3/alstom-receives-additional-order-103-mf19-new-generation-metros-modernise-paris-region-network)). | Possible, but a metro. |
| Régiolis / Coradia Polyvalent | **No.** | Designed and assembled at Reichshoffen; since 2022 "produite par CAF France" ([Wikipedia FR](https://fr.wikipedia.org/wiki/R%C3%A9giolis), automated summary). Absent from Alstom's current Coradia page. | **No.** Do not name it as a Valenciennes family. |
| Coradia Stream | Not shown. | No statement found that it is built in France. | **No.** |

- The Valenciennes site is described as "Alstom's centre of excellence for the design, manufacture and testing of metros, tram-trains, RER and double-deck regional trains" and home to the "global centre of excellence for interior design" ([Alstom recruitment page](https://www.alstom.com/join-alstom-valenciennes), vendor page from about 2020).
- Alstom's filing lists "Valenciennes, Crespin and Saint-Ouen" among development sites being merged under a new operating model ([URD 2025/26, PDF p15](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf)).
- **Inference:** which of the two sites the case's "Valenciennes" means is not established. Treat them as one engineering base.
- **Inference:** interiors are a strong domain for the dataset, since the Valenciennes interiors centre designs for all Alstom trains.
- Caveat: Regio 2N production may be near its end. Alstom reportedly said the line would stop without a new order by mid-2026 (Wikipedia). Its status after mid-2026 was not verified.

### Model realistic variant axes

Regio 2N / Omneo variant facts, **all from French Wikipedia through an automated summary; check before quoting**:

- Four lengths: about 81 m (6 cars), 95 m (7), 110 m (8), 135 m (10).
- Speeds of 160 or 200 km/h. Power supply 1.5 kV DC and 25 kV 50 Hz.
- Interiors: suburban high-capacity, regional, and intercity "Omneo Premium".
- Ten French regional customers.

**Inference:** a credible synthetic dataset has 4 to 6 variants of one double-deck regional family, differing by length, speed class, interior type and customer region. Sub-assembly families that follow from the public variant axes: car-body modules, traction chain, bogies, doors, interiors (seats, lighting, toilets), driver's cab, climate unit, and signalling equipment. This mapping is this report's own. Alstom does not publish a product structure.

### Seed the dirt the literature documents

| Defect to inject | Why (source) | Tests which use case |
|---|---|---|
| Character-swap typos in references (5 for S, 0 for O) | Tate et al.: "IN3S00A and IN3500" | UC1 |
| Same part at different levels of detail (base reference versus reference with suffix) | Tate et al.: "V17N" versus "V17N-ZB11" | UC1 |
| A real, intended substitution by an equivalent part | Tate et al., third category | UC1, UC3 (must **not** be "corrected") |
| Mixed units for the same item (mm and m, kg and g, pieces and metres) | Končar case paper | UC4 |
| One variant lists a part on n rows; another uses a quantity field | Tate et al., Section III.G | UC4 |
| Same part under a different parent in one variant ("level jump") | Romanowski and Nagi: "in 10 out of 25 BOMs the plug is a child of the cable assembly" | UC3, UC8 |
| Near-identical sub-assemblies differing by one to three lines | Schmidt et al. standardisation candidates | UC3 |
| French and English descriptions of the same item | Case brief; no benchmark exists | UC1, UC5 |
| Notes that mention obsolescence, equivalence or approval, some without a clean reference | Pacella et al.; Alstom URD on obsolescence | UC5 |
| Optional columns: supplier name with spelling variants, unit price, make-or-buy flag | Alstom 64% purchased share | UC7 |

### Rules for building it

- **Keep a ground-truth file.** Record every injected defect and every true match. No published benchmark gives precision or recall for part matching or for mixed French and English notes, so the demo's own measured scores are the only defensible accuracy claim.
- **Include true negatives.** Add pairs that look alike but are truly different (for example the same seat frame in two lengths). This tests for false merges. Shape tools show the same risk: PTC notes that two bolts of "1 cm vs. 2 cm" are "considered identical" ([PTC help](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html)).
- **Do not assume a drift rate.** No study quantifies drift between copied hardware BOMs. Say the injected rate is a design choice.
- **Label everything as synthetic.** The case statement itself says candidates may "invent any plausible figure" for "this fictional exercise" ([case statement repository](https://github.com/leopoldlacroix/Cognyx_case)). Invented reuse rates or savings must be marked as invented and never mixed with sourced figures.
- **Do not use real Alstom part numbers or internal codes.**
- **A classification column is useful but unverified.** EN 15380 is the European standard for breaking a rail vehicle into product groups; Part 2 is "the basis for establishing productoriented structures" ([EVS catalogue summary](https://www.evs.ee/en/evs-en-15380-2-2006)). **Inference:** it is a natural shared key across variants. Whether Alstom Valenciennes structures its BOMs this way was not verified, and the standard's code list was not read (paid text). Do not present invented codes as EN 15380 codes.

## 6. Full source list

Read-status labels: **Full** = read in full. **Partial** = named sections or keyword-targeted passages read. **Partial (summary tool)** = read through a summarising fetch, so wording is not verified verbatim. **Abstract** = abstract only. **Snippet** = search-engine summary only; unverified. **Inaccessible** = could not be opened.

### Company filings and investor material

| Source | Date | Read status | Notes |
|---|---|---|---|
| [Alstom URD 2025/26](https://www.alstom.com/sites/alstom.com/files/2026/05/28/20260528_URD_Alstom_EN.pdf) (554 pages) | 28 May 2026 | Partial | Read in full: CEO message, sections 1.1.1 to 1.2.2, risk factors 4.2.2.1 to 4.2.2.4. Rest by extract and keyword search. PDF page = printed page + 2. |
| [Alstom URD 2024/25](https://www.alstom.com/sites/alstom.com/files/2025/05/28/20250528_Universal_Registration_Document_EN.pdf) (512 pages) | 28 May 2025 | Partial, with caveat | **Broken text layer.** Body text recovered with a hand-built substitution table. Every quote needs a visual check against the PDF page. |
| [Alstom URD 2023/24](https://www.alstom.com/sites/alstom.com/files/2024/05/15/20240515_Alstom_Universal_Registration_Document_EN.pdf) (432 pages) | May 2024 | Partial | Sections 4.2.2.1 and 4.2.2.2 (pp.174-175) and passages at pp.15, 191-192, 233, 361. |
| [Alstom Equity Story](https://www.alstom.com/sites/alstom.com/files/2026/10/06/Alstom_Equity_Story_October_2026_EN.pdf) (79 slides) | 6 Oct 2026 | Partial | Slides 11-16 and 46-53 read as text. Charts are flattened; chart labels need a visual check. |
| [Alstom conference call transcript](https://www.alstom.com/sites/alstom.com/files/2026/04/20/20260416_Transcript_Conference_Call_EN.pdf) | 16 Apr 2026 | Full | 9 pages. |
| [Alstom preliminary FY 2025/26 press release](https://www.alstom.com/sites/alstom.com/files/2026/04/16/20260416_PR_Alstom_Prelim_FY202-26_Results_EN.pdf) | 16 Apr 2026 | Full | 7 pages. |
| [Alstom FY 2025/26 results press release](https://www.alstom.com/sites/alstom.com/files/2026/05/12/20260513_PR_FY202526_Annual_Results_EN.pdf) | 13 May 2026 | Partial | Keyword extracts. |
| [Alstom FY 2025/26 results presentation](https://www.alstom.com/sites/alstom.com/files/2026/05/12/20260513_FY202526_Annual_Results_Presentation_EN.pdf) | 13 May 2026 | Partial | A few slides. |
| [Alstom FY 2024/25 results page](https://www.alstom.com/press-releases-news/2025/5/fy-202425-alstom-delivers-solid-profit-and-cash-medium-term-ambitions-confirmed) | 14 May 2025 | Partial | Read up to the net debt section. |
| [Alstom H1 2024/25 management report](https://alstom.com/sites/alstom.com/files/2024/11/13/20241113_H1_Financial_Results_Management_Report_EN.pdf) | 13 Nov 2024 | Partial | Page 6 in full. |
| [Alstom Q1 2026/27 press release](https://www.alstom.com/sites/alstom.com/files/2026/07/22/20210722_PR_Q1_2026_27_results_EN.pdf) | 22 Jul 2026 | Partial | Pages 1-2 of 8. |
| [Alstom aide-memoire H1 2026/27](https://www.alstom.com/sites/alstom.com/files/2026/10/05/20261006_Aide_Memoire_H1_2026_27_EN.pdf) | 6 Oct 2026 | Partial | Pages 1-2 of 3. |
| [Bombardier Q2 2020 press release](https://bombardier.com/en/node/2010424) | 6 Aug 2020 | Partial | Transportation passages. |
| [Siemens Earnings Release Q4 FY 2025](https://assets.new.siemens.com/siemens/assets/api/uuid:3948cdd4-35e0-4c1d-8412-9aed4097b3d0/HQCOPR202511117277EN.pdf) | Nov 2025 | Partial | Mobility table only. |
| [Stadler Annual Report 2025](https://www.stadlerrail.com/api/docs/x/518f589306/annual-report_2025_en.pdf) | 2026 | Partial | Keyword extracts. Headline financials were **not** located in the text by the researcher. |

### Independent audits and government studies

| Source | Date | Read status | Notes |
|---|---|---|---|
| [NSW Audit Office, Rail rolling stock procurement](https://www.audit.nsw.gov.au/our-work/reports/rail-rolling-stock-procurement) | 21 Oct 2025 | Partial | Sections 2, 4.1, 4.2, 4.4, 5.3-5.5 read. Australia. |
| [NSW Audit Office report snapshot](https://www.audit.nsw.gov.au/media-release/report-snapshot-rail-rolling-stock-procurement) | 21 Oct 2025 | Full | |
| [UK National Audit Office, Procuring new trains](https://www.nao.org.uk/wp-content/uploads/2014/07/Procuring-new-trains.pdf) | 9 Jul 2014 | Partial | Summary, Part One, parts of Part Two. UK. |
| [Arup, Rolling stock whole life costs (Rail Value for Money study)](https://www.orr.gov.uk/sites/default/files/om/rvfm-arup-rolling-stock-mar2011.pdf) | Mar 2011 | Partial | Read from an Internet Archive copy. UK. Government-commissioned. |
| [Cour des comptes, TER report](https://www.ccomptes.fr/system/files/2019-10/20191023-rapport-TER-ouverture-concurrence.pdf) | Oct 2019 | Partial | pp.20-21, 26-27, 64-65, 86. France. |
| [Sénat, synthesis note on rail competition](https://www.senat.fr/fileadmin/cru-1778089154/Commissions/Finances/2025-2026/Controles/Controle_concurrence_ferroviaire__essentiel_post_commission.pdf) | May 2026 | Partial | 8-page synthesis only. Full report not located. |
| [US DoD SD-19 Parts Management Guide](https://everyspec.com/DoD/DoD-PUBLICATIONS/SD-19_DEC2013_49300/) | Dec 2013 | Partial | Targeted passages. US defence. |
| [US GAO-02-195, NASA lessons learned](https://www.govinfo.gov/content/pkg/GAOREPORTS-GAO-02-195/pdf/GAOREPORTS-GAO-02-195.pdf) | Jan 2002 | Partial | Targeted passages. |
| [NIST GCR 04-867, interoperability cost](https://nvlpubs.nist.gov/nistpubs/gcr/2004/NIST.GCR.04-867.pdf) | 2004 | Partial | Summary passages. US construction, not manufacturing. Not used for a claim above. |
| [World Bank working paper 3781 (Flyvbjerg)](https://openknowledge.worldbank.org/server/api/core/bitstreams/824924ad-5b05-5980-a173-a8c184434df6/content) | 2005 | Partial | Rail **infrastructure** cost overrun (44.7%). Not rolling-stock bids. Not used above. |
| [European Commission slides (K. Fitch), 4th Railway Package](https://era.europa.eu/system/files/2022-11/ec_technical_pillar_of_the_4th_railway_package-h_en.pdf) | 10 May 2017 | Full | Conference slides, no method. |
| [EU Agency for Railways FAQ](https://www.era.europa.eu/can-we-help-you/faq/292_en) | Undated | Partial (summary tool) | |
| [European Parliament report summary 2019/2191(INI)](https://oeil.europarl.europa.eu/oeil/en/document-summary?id=1664211) | 2021 | Partial (summary tool) | |
| [Géorisques inspection report, Petite-Forêt](https://www.georisques.gouv.fr/webappReport/ws/installations/inspection/SMUHpR8AdZMPwcEKdqadZ8TLhfys1jFC) | Jan 2026 | Snippet | Headcount of about 2,400 unverified. |
| [DLA parts management business case](https://www.dsp.dla.mil/Portals/26/Documents/Programs/PartsManagement/070524-Report-ReduceCostThroughPSCMBusinessCasePartsManagement.pdf) | 2007 | Snippet | HTTP 403. |
| [European Commission / Ecorys rail supply industry study](https://ec.europa.eu/docsroom/documents/38025?locale=en) | Sep 2019 | Inaccessible (located, not read) | |
| [GOV.UK note on Splink](https://www.gov.uk/government/publications/joined-up-data-in-government-the-future-of-data-linking-methods/splink-mojs-open-source-library-for-probabilistic-record-linkage-at-scale) | Undated | Snippet | |

### Standards

| Source | Read status | Notes |
|---|---|---|
| EN 15380 Parts 1 to 5, catalogue pages: [Part 1](https://www.evs.ee/en/evs-en-15380-1-2006), [Part 2](https://www.evs.ee/en/evs-en-15380-2-2006), [Part 5](https://www.evs.ee/en/evs-en-15380-5-2014) | Snippet (Part 1); Partial (summary tool) for Parts 2 and 5 | Catalogue summaries only. The standards themselves are paid and were not read. |

### Peer-reviewed (journals and conferences)

| Source | Read status | Notes |
|---|---|---|
| [Romanowski and Nagi 2005, On comparing bills of materials](https://www.eng.buffalo.edu/~nagi/papers/IEEESMCApaper.pdf) | Partial | Author manuscript. Sections I to III.C in full. |
| [Schmidt et al., ICED 2017 (MAN, TU Munich)](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance) | Partial | |
| [Kourtis et al., Design Society 2026](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader) | Partial | Proof of concept. |
| [Haug, Hvam, Mortensen 2011, AI EDAM](https://www.cambridge.org/core/journals/ai-edam/article/impact-of-product-configurators-on-lead-times-in-engineeringoriented-companies/107D0DB206626EE028613F59CB0DF203) | Abstract | Conflicting average: see section 7. |
| [Haug, Zachariassen, van Liempd 2011, costs of poor data quality](https://www.jiem.org/index.php/jiem/article/view/232) | Partial | |
| [Pacella, Grieco, Blaco 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5164909) | Partial (summary tool) | Rail supplier case. |
| [Cloning in industrial software product lines, 2013](https://people.csail.mit.edu/mjulia/publications/An_Exploratory_Study_of_Cloning_in_Industrial_Software_Product_Lines_2013.pdf) | Partial | Software. |
| [Vasantha et al., ASME IDETC 2018](https://strathprints.strath.ac.uk/64624/1/Vasantha_etal_IDETC_2018_A_probabilistic_design_reuse_index.pdf) | Partial | Furniture. |
| [Aurisicchio et al., ICED 2003](https://designsociety.org/download-publication/24024/INVESTIGATING+KNOWLEDGE+SEARCHES+IN+AEROSPACE+DESIGN) | Partial | Aerospace. |
| [Design Society, "Information push"](https://designsociety.org/download-publication/19295/INFORMATION+PUSH%3A+STRATEGIES+FOR+IMPROVING+EFFICIENCY+OF+DESIGN+INFORMATION+MANAGEMENT) | Partial | Authors and year not captured. Secondary citations. |
| [ICED 2007, "Improving design reuse using context"](https://www.designsociety.org/download-publication/25416/Improving+Design+Reuse+Using+Context) | Partial | Authors not captured. Secondary citations. |
| [Design Society case paper, Končar](https://www.designsociety.org/download-publication/32035/INTEGRATION+OF+PLM+AND+ERP+SYSTEMS+AT+KONCAR+-+INSTRUMENT+TRANSFORMERS) | Partial | Year not captured. |
| [Duffy and Ferns, design reuse benefits](https://strathprints.strath.ac.uk/18794/6/strathprints018794.pdf) | Partial | Perceptions in one company. Not used above. |
| [Ishii and Muraki 2011](https://www.scitepress.org/Papers/2011/36204/36204.pdf) | Partial | A model, no measurements. Not used above. |
| [MaintNorm, W-NUT 2024](https://aclanthology.org/2024.wnut-1.7.pdf) | Partial | English mining text. |
| [MaintIE, LREC-COLING 2024](https://aclanthology.org/2024.lrec-main.954.pdf) | Partial | The paper gives both 1,076 and 1,067 expert-annotated texts. |
| [Kaewunruen and Lee 2017](https://www.frontiersin.org/articles/10.3389/fbuil.2017.00010/pdf) | Full | Opinion article. Not used above. |
| [Kashkoush and ElMaraghy 2013](https://www.sciencedirect.com/science/article/pii/S2212827113002369) | Abstract | |
| [Thevenot and Simpson 2006](https://pure.psu.edu/en/publications/commonality-indices-for-product-family-design-a-detailed-comparis/) | Abstract | |
| [Brundage et al. 2020, technical language processing](https://www.nist.gov/node/1647801) | Abstract | |
| [Løkkegaard and Mortensen, ICED 2017](https://www.designsociety.org/publication/39607/assessing_the_financial_potential_for_modularization_a_case_study_in_a_global_oem) | Abstract | Industrial equipment. Not used above. |
| [Brunoe and Nielsen 2012](https://www.inderscience.com/offers.php?id=47400) | Snippet | HTTP 403. |
| [Jiao, Simpson, Siddique 2007](https://pure.psu.edu/en/publications/product-family-design-and-platform-based-product-development-a-st/); [Hicks et al. 2000](https://eprints.ncl.ac.uk/13830); [Gosling and Naim 2009](https://orca.cardiff.ac.uk/id/eprint/18183/); [Cannas and Gosling 2021](https://orca.cardiff.ac.uk/143586) | Snippet | Scope only. No numbers taken. |
| [Journal of Manufacturing Systems 2021, complexity cost](https://www.sciencedirect.com/science/article/abs/pii/S0278612521000972); [Production Engineering 2026](https://link.springer.com/article/10.1007/s11740-026-01458-y); [Chalmers 2020](https://research.chalmers.se/en/publication/515875); [Cash et al.](https://researchgate.net/profile/Philip-Cash/publication/256132203_An_Analysis_Of_Engineers_Information_Seeking_Activity/links/594223c40f7e9b1d452df5fd/An-Analysis-Of-Engineers-Information-Seeking-Activity.pdf) | Snippet | Percentages not seen. |
| [Busby 1999](https://eprints.lancs.ac.uk/id/eprint/43797/); [Jarratt et al. 2011](https://oro.open.ac.uk/28816) | Inaccessible | Known only through other papers. |

### Preprints and theses (not peer-reviewed)

| Source | Read status | Notes |
|---|---|---|
| [Tate et al., Comparing Bills of Materials, arXiv 2411.10384](https://arxiv.org/pdf/2411.10384) | Full | 8 pages. Preprint. |
| [Zeller, Ratiu, Höfig (Siemens), arXiv 2106.02273](https://arxiv.org/pdf/2106.02273) | Partial | Abstract and rail passage. |
| [Peeters, Steiner, Bizer, arXiv 2310.11244](https://arxiv.org/pdf/2310.11244) | Partial | E-commerce product matching. Not used for a claim above. |
| [French building specifications NLP, arXiv 2508.13833](https://arxiv.org/pdf/2508.13833) | Abstract | Not used above. |
| [Romanowski and Nagi, generic BOM manuscript](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf) | Partial | Publication venue not verified. |
| [Kristjansdottir PhD thesis, DTU](https://backend.orbit.dtu.dk/ws/files/145893822/PhD_Katrin_Kristjansdottir.pdf) | Partial | Date about 2017-2018, not verified. |
| [FIU dissertation on ETO cost estimation](https://digitalcommons.fiu.edu/dissertations/AAI3471601) | Snippet | HTTP 403 on every attempt. |
| [Gothenburg master's thesis](https://gupea.ub.gu.se/items/2264948b-fddb-4e15-9630-d22ae7d6356b); [TU Delft yacht thesis](https://repository.tudelft.nl/file/File_43c059cd-ecb5-409a-8df8-ae468714c922) | Snippet | |
| [University of Twente thesis on Bombardier platforms](https://essay.utwente.nl/66384/) | Inaccessible | Page shell only. |

### Trade press and industry bodies

| Source | Grade | Read status | Notes |
|---|---|---|---|
| [ARA Tendering Framework 2020](https://ara.net.au/wp-content/uploads/Tendering-Framework-2020-2.pdf) | Industry-association position paper (not independent) | Full | 14 pages. Australia. |
| [CER position paper on vehicle authorisation](https://www.cer.be/images/publications/positions/260203_CER_Position_Paper_Vehicle_Authorisation.pdf) | Industry-body position paper | Partial | Operators' lobby. |
| [AERRL, CER, UIP paper on conformity to type](https://cer.be/images/publications/positions/220728_AERRL-CER-UIP_PositionPaper_CTT.pdf) | Industry-body position paper | Partial | |
| [EuroSpec presentation 2014](https://www.schienenfahrzeugtagung.at/download/PDF2014/DiV05-Michielsen.pdf) | Industry-body presentation | Full | No figures. |
| [Railway Gazette on ARA framework](https://railwaygazette.com/business/industry-calls-for-improvements-to-australian-rail-tendering-processes/56508.article) | Trade press | Full (to paywall) | |
| [Railway Gazette, Coradia Stream](https://railwaygazette.com/passenger/alstom-unveils-coradia-stream-modular-emu-designs-for-ns-and-trenitalia/45257.article) | Trade press | Full | Year (2017) inferred. |
| [Railway Gazette, Mireo Smart](https://www.railwaygazette.com/traction-and-rolling-stock/mireo-smart-to-speed-emu-deliveries/57752.article); [Railway Gazette, Adtranz 1999](https://railwaygazette.com/news/adtranz-gets-two-years-to-move-into-profit/29499.article) | Trade press | Partial (summary tool) | |
| [Railway Gazette, Régiolis framework 2009](https://railwaygazette.com/news/regions-confirm-7bn-framework-ter-contract/34484.article) | Trade press | Partial (summary tool) | Not verbatim. |
| [Rail Magazine, Taking stock of how we procure trains](https://railmagazine.com/features/taking-stock-of-how-we-procure-trains) | Trade press, signed opinion | Full | From an Internet Archive snapshot. 2014. |
| [Banque des Territoires / Localtis](https://www.banquedesterritoires.fr/materiel-ferroviaire-les-regions-veulent-reprendre-les-commandes) | Public-sector news service | Partial (summary tool) | 2014. |
| [Railway News, 500th Omneo](https://railwaynews.net/alstom-delivers-500th-omneo-regio2n-train-in-france.html) | Trade press, **low reliability** | Partial (summary tool) | Article contained unrelated filler figures. |
| [ARC Advisory on Windchill AI Parts Rationalization](https://www.arcweb.com/blog/ptc-introduces-windchill-ai-parts-rationalization-capability) | Trade press | Full | Read through a text proxy. Restates the vendor release. |
| [CFNews on Cognyx](https://www.cfnews.net/L-actualite/Capital-innovation/Operations/Amorcage/Cognyx-se-developpe-aupres-de-business-angels-491005) | Trade press | Partial | Paywall. |
| IRJ articles: [RER NG](https://www.railjournal.com/analysis/new-rer-trains-lead-massive-fleet-renewal-in-greater-paris/), [Bombardier results](https://www.railjournal.com/financial/alstom-to-consider-weak-bombardier-transportation-results-in-takeover-talks/), [Deloitte/ARA savings](https://www.railjournal.com/regions/australia-nz/australians-seek-to-reduce-train-procurement-costs/) | Trade press | Snippet | HTTP 403. |
| Press on Alstom's 2021 provisions and October 2023 cash warning ([Boursorama](https://www.boursorama.com/bourse/actualites/alstom-annonce-une-provision-de-632-millions-d-euros-sur-bombardier-transport-86435ac36afd0d456d77df3c789d686d), [Sharecast](https://sharecast.com/amp/news/news-and-announcements/alstom-slides-after-free-cash-flow-warning--14879596.html), others) | Press | Snippet | Not checked against Alstom filings. |
| [UNIFE World Rail Market Study page](https://www.unife.org/news-resources/wrms/); [UNIFE on authorisation](https://www.unife.org/news/positive-risc-vote-for-the-implementing-regulation-on-vehicle-authorisation/) | Industry body | Snippet | |
| [Purdue press release 2004](https://www.purdue.edu/uns/html4ever/2004/040420.Ramani.CAD.html) | University press office | Snippet | Source of the "60% of time searching" estimate. |

### Consulting reports

| Source | Read status | Notes |
|---|---|---|
| McKinsey: [smart platforms](https://www.mckinsey.com/br/our-insights/how-smart-platforms-can-crack-the-complexity-challenge-in-project-industries), [platforming and modularity](https://www.mckinsey.com/capabilities/operations/our-insights/platforming-and-modularity-smart-answers-to-ever-increasing-complexity), [calculating complexity](https://www.mckinsey.com/capabilities/operations/our-insights/calculating-complexity-maximizing-the-value-of-customization) | Inaccessible (timeouts); snippet only | Not used for any claim above. |
| [Deloitte on parts proliferation](https://www2.deloitte.com/us/en/pages/operations/articles/rpa-for-manufacturing-parts-proliferation.html) | Snippet, unverified | Figure not found in the page text retrieved. |

### Vendor marketing and vendor documentation

| Source | Read status | Notes |
|---|---|---|
| Cognyx: [home](https://cognyx.io/), [use cases](https://en.cognyx.io/use-cases), [technology](https://en.cognyx.io/technology), [about](https://en.cognyx.io/about) | Full | One quantified claim ("up to 40%"), no basis given. |
| [Cognyx 2023 landing page](https://cognyx-landing.pages.dev/) | Full | |
| [PTC press release, 27 Jan 2026](https://www.ptc.com/en/news/2026/ptc-launches-windchill-ai-parts-rationalization); [PTC blog on duplicate parts](https://www.ptc.com/en/blogs/plm/challenges-managing-duplicate-parts) | Full | |
| PTC help: [introduction](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginIntroduction.html), [known limitations](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html) | Full | Vendor documentation. |
| [CADENAS and PTC deck 2015](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf) | Full | 19 slides. |
| CADENAS customer stories: [Starlinger](https://www.cadenas.de/files/cadenas/Downloads/PDF/Referenzen/EN/PARTsolutions_Starlinger_Success_Story_EN.pdf), [MAC Trailer](https://partsolutions.com/wp-content/uploads/2023/07/Mac-Trailer-Case-Study_FINAL.pdf), [BOMAG](https://partsolutions.com/bomag-utilize-partsolutions-parts-management-software-to-search-and-control-standard-parts) | Partial | |
| [Dassault Part Classification as-a-Service page](https://events.3ds.com/part-classification-service-chaos-reuse) | Full (page text) | Webinar video not watched. |
| [Siemens Geolus blog](https://blogs.sw.siemens.com/designcenter/geolus-shape-search-i-need-a-part-that-looks-like-this/); [3DPartFinder](https://www.3dpartfinder.com/) | Partial | |
| [Siemens Mireo presentation, June 2016](https://assets.new.siemens.com/siemens/assets/api/uuid:33dda3d5-a6d5-4f6b-88dd-cfd914de1c6a/presentation-mireo-e.pdf) | Partial | Slides 1-12 of 40. |
| [Zuken case study on Alstom](https://www.zuken.com/en/resource/alstom/) | Partial | Undated. |
| [OpenBOM blog on product knowledge graphs](https://openbom.com/blog/digital-thread-product-knowledge-graph-bill-of-materials-and-change-events) | Full | Not used above. |
| Alstom press releases: [Régiolis 2009](https://www.alstom.com/fr/press-releases-news/2009/10/SNCF-attribue-a-Alstom-le-marche-de-la-nouvelle-generation-de-materiels-TER-a-un-niveau-20091027) (Full), [MF19 2024](https://www.alstom.com/press-releases-news/2024/3/alstom-receives-additional-order-103-mf19-new-generation-metros-modernise-paris-region-network) and [French investment plan 2025](https://www.alstom.com/press-releases-news/2025/4/alstom-announces-investment-plan-over-150-million-euro-increase-production-capacity-its-sites-france) (Partial, summary tool) | See left | |
| Alstom pages: [Coradia product page](https://www.alstom.com/solutions/rolling-stock/coradia-regional-trains-accessible-solutions-move-regions), [Join Alstom Valenciennes](https://www.alstom.com/join-alstom-valenciennes), [Alstom in France](https://www.alstom.com/alstom-france) | Partial | Undated. Product pages contain internal inconsistencies. |
| Vendor blogs with cost or duplicate figures: [Siemens Teamcenter](https://blogs.sw.siemens.com/teamcenter/reuse-classification-teamcenter), [Autodesk](https://blogs.autodesk.com/vault/?p=3535), [Infor](https://www.infor.com/blog/why-manufacturing-quotes-are-wrong) | Snippet | See section 7. Do not quote. |
| [Dassault press release on Alstom PLM, 2021](https://www.3ds.com/newsroom/press-releases/alstom-chooses-accenture-and-dassault-systemes-develop-new-cloud-platform-plm-increase-competitiveness-and-support-growth); [Alstom bid manager job posting](https://jobsearch.alstom.com/job/Saint-Ouen-Senior-Bid-Technical-Manager-J/1291263901/); [Siemens job posting](https://jobs.siemens.com/en_US/externaljobs/JobDetail/490064) | Snippet | |

### Wikipedia and other

| Source | Grade | Read status | Notes |
|---|---|---|---|
| [Regio 2N (FR)](https://fr.wikipedia.org/wiki/Regio_2N), [Régiolis (FR)](https://fr.wikipedia.org/wiki/R%C3%A9giolis), [Alstom Crespin (EN)](https://en.wikipedia.org/wiki/Alstom_Crespin) | Wikipedia | Partial (summary tool) | First 100,000 characters only for the French pages. |
| [GitHub repository reproducing the case statement](https://github.com/leopoldlacroix/Cognyx_case) | Third-party repository | Partial | First 9 KB of the README. |
| [Signalbase](https://www.trysignalbase.com/news/funding/funding-alert-cognyx-secures-1.7-million-for-revolutionizing-manufacturing-with-ai-and-graph-technology!) (Partial); [CB Insights](https://www.cbinsights.com/company/cognyx/financials) (Snippet) | Funding aggregators | See left | Funding figures differ slightly from the company's own. |

## 7. Not found or unverified

### Statistics that circulate widely but could not be traced. Do not quote them.

| Claim | Why not to quote it |
|---|---|
| "30-40% of parts are duplicates or have acceptable substitutes" | Vendor blog (Siemens), attributed to an unnamed study. Snippet only. No primary study found. |
| "40% of new parts already exist, 40% are modifications, 20% are new" | Group-technology rule of thumb. No original source found. |
| "A new part number costs $4,500 to $23,000 a year" (Aberdeen Group) | Seen only in vendor blogs. The Aberdeen original was not located. Not found in the Siemens page that was opened. |
| "$25k per new part number", "$50,000 lifetime cost per automotive part number", "$1,300-$12,000 per part", a "1980s Scania study" | Vendor blog, practitioner blog or unsourced lecture deck. |
| "Engineers spend 60% of their time searching for information" | A professor's estimate in a 2004 press release. Not a measurement. Observed figures are about 20-25%, in aerospace. |
| "80% of enterprise information is unstructured text" | "It has been estimated", no traceable origin. |
| "90% of organisational memory exists in the form of text-based documents" | Appears in a conference paper with no reference. |
| "Engineering change consumes 30-50% (up to 70%) of development capacity" | Second-hand citation of a 1998 German book. Not traced. |
| "More than 35% of manufacturing resources are devoted to managing changes" (Boeing, 2002) | Second-hand. Original not retrieved. |
| "ETO estimates are off by 30-50%" and "17.3% error for a statistical model" | From a dissertation abstract seen only as a snippet. |
| "ETO rough estimates diverge from final costs by 15-30%" | Vendor blog (Infor). No source named. |
| "Poor data costs 8-12% of revenue"; "field error rates of 0.5-30%" | Redman (1998), relayed. The relaying paper notes he "does not provide references". |
| "Tendering costs 1-2% of project cost against a 0.5% world benchmark" | ARA (industry lobby) citing a 2012 trade article that was not located. Australia. Unclear whether it covers one bidder or all parties. Quote only as an industry-association claim. |
| "Up to 70% reuse of identical parts in modular designs" (Siemens) | Snippet of German vendor material. |
| "A$6bn savings over 30 years from coordinated ordering" (Deloitte for ARA) | Snippet only. Report not obtained. |
| Deloitte: "$30M savings, 30% of parts identified as duplicates" | Not found in the page text retrieved. |
| Cognyx: "reduce RFQ response time by up to 40%" and "10x improvement" | Vendor claims with no customer, date or method. The second is an aspiration. |
| Dassault: "27.5M€ to 50M€ per year" business cases | Vendor claim. Customers unnamed, undated. |

### Conflicting figures. State the conflict if you use them.

| Topic | Conflict | Status |
|---|---|---|
| Average cut in quotation lead time, Haug, Hvam and Mortensen (14 companies) | **85.5%** in the paper's abstract. **83.7%** (with 78.4% work-hours saved) as relayed by the DTU thesis. | The full paper was not opened. It is not known which average applies to which measure. Both are company estimates. |
| Regio 2N trains ordered | "more than 550" (Alstom URD), 558 (Wikipedia), 567 (low-reliability trade outlet). | Use Alstom's "more than 550". |
| Régiolis trains ordered | 483 (Wikipedia); about 400 (low-reliability outlet). | Unverified. |
| NSW New Intercity Fleet contract award | "August 2016" in one section, "September 2016" in another. | Inconsistency is in the source. |
| Cognyx funding | €1.7m pre-seed plus €0.8m debt (company); $1.83M over two rounds (CB Insights, snippet). | Minor. |
| Cognyx founders | Different names on the 2023 landing page and on the current site. | Not resolved. |
| MaintIE corpus size | 1,076 in the abstract, 1,067 in Section 6.1. | Inconsistency is in the source. |
| Legacy Bombardier contracts, 30 bps | URD 2023/24 ties 30 bps to FY 2023/24 gross margin. The FY 2024/25 results page gives "(30)bps" for legacy portfolio in FY 2024/25. | Both stated by Alstom for different years. Cite the year with the figure. |

### Figures that need a check before being quoted

- **All quotes from Alstom URD 2024/25.** The PDF text layer is broken and the text was machine-decoded. Check each against the page image. One bracketed phrase ("customer's requirements") was reconstructed from a garbled fragment.
- **Chart labels in the Equity Story** (for example Alstom at 25% of a €38bn addressable market on slide 12, and the customer-date pairing on slide 47). Charts are flattened.
- **Everything from French Wikipedia** on Regio 2N and Régiolis: variant counts, customers, the eight-month delay and its causes, the Crespin and Reichshoffen site attributions, the possible line stop.
- **RER NG work split between Crespin and Petite-Forêt** (snippet only).
- **Stadler's 4.4% EBIT margin for 2025** (search summary; not located in the report by the researcher).
- **Alstom's €632m provision on Bombardier contracts and the October 2023 cash warning details** (press snippets; not checked against Alstom's filings).
- **Bombardier's US$350m charge for Q4 2019** (trade press snippet).
- **Régiolis and Banque des Territoires details**, including "330 versions différentes" on order in 2014 (read through a summarising tool).
- **EUR 0.9m to 2m and "up to 2 years" for a vehicle authorisation**: these come from 2017 European Commission slides, concern an *additional* authorisation of a *locomotive* type, and describe the regime before 2019. They are not the cost of authorising a new regional train.
- **Siemens "clone and own" statement**: from a preprint by Siemens authors, about Siemens. It says nothing about Alstom.

### Not found

- A design reuse rate, parts commonality rate, carry-over target or variant count for any Alstom platform, or for Siemens, Stadler or Bombardier.
- Engineering hours per tender, bid cost in euros for a European train tender, tender win rate, or number of tenders per year.
- A statement of who decides reuse versus new design in a train bid, at which review, with what data.
- Contingency percentages, late-delivery penalty rates or caps in European rolling-stock contracts. The term "fixed-price" does not appear in Alstom's risk factors.
- The split of a train bid price between recurring and non-recurring cost.
- Purchased share of the cost of a single train. Only the Group-wide 64% exists.
- Margin by product line, site or contract at Alstom.
- Any Alstom or Bombardier statement tying a specific contract loss to customisation or to a failure to reuse a design.
- Any rail-specific study by a consultancy or industry body that quantifies complexity cost or savings from modularisation.
- Any study quantifying drift between copied hardware BOMs, or rates of EBOM/MBOM mismatch, duplicate items or unit errors.
- Any measured accuracy (precision or recall) for matching industrial part or supplier records, for BOM comparison against ground truth, or for language-model extraction from change requests, non-conformance reports or lessons learned.
- Any benchmark for mixed French and English engineering text.
- Any independent evaluation of a commercial part-rationalisation product.
- Any Cognyx case study, named customer or measured result. Any public evidence of a real Cognyx pilot at Alstom. The only public trace is the recruitment case, which calls itself fictional.
- Current official headcount and product list for Petite-Forêt and Crespin.
- Whether Alstom Valenciennes structures its BOMs to EN 15380.
- A French regional train tender run directly by a region after 2020, with its timeline.

## Conclusion

The research changes the shape of the pitch. The natural instinct is to lead with a savings percentage. The evidence does not support one for rail, and a careful listener like Thomas would find that out. What the evidence does support is narrower and more useful: Alstom has told its own shareholders that reuse assumptions made at tender time can fail and that engineering changes during ramp-up cost margin, and no commercial tool found answers the reuse question from BOM structure and text alone. A demo that finds real shared sub-assemblies, real near-duplicates and real inconsistencies in the data, and shows how each finding was reached, makes that case without borrowing numbers from defence or software.

The second implication is about sequence. Every published method for comparing BOMs assumes clean references, and the one worked example that starts from dirty data shows that the tree structure itself is the best cleaning aid. Reconciliation is therefore the first deliverable, not a chore before the real work. Weeks 2 and 3 of a pilot should be spent measuring what the literature has not: how much variant BOMs really drift, how accurate matching is on a labelled sample, and how many hours a carry-over estimate saves a cost estimator on one real tender.
