# Approaches, products and reported results: sub-assembly reuse, dirty BOM reconciliation, and knowledge extraction from engineering text

Research date: 2026-10-12.

**How to read these notes**

- Every finding carries a tag: `[grade | read status]`.
  - Grades: peer-reviewed, preprint, independent study, trade press, vendor marketing, vendor documentation, other.
  - Read status: **full** (whole document read), **partial** (named sections or targeted passages read), **abstract** (abstract only), **snippet** (search-engine summary only, not opened or not extractable; treat as unverified), **no access**.
- Quotes are verbatim and short. Locations are section, page or slide numbers where the source has them.
- "Vendor claim" means the number comes from the vendor or its customer in vendor-published material and was not independently checked.
- CAD dependence is flagged as **needs geometry** or **works on BOM structure and text**.
- A consolidated source log and a "not found" list are at the end.

---

## 1. BOM comparison and similarity: methods, inputs, outputs, limits, named use cases

### Takeaway
The literature offers four families that work without CAD: list and set comparison with fuzzy string matching, graph or tree matching that uses the parent-child structure to constrain fuzzy matches, tree-distance measures (weighted symmetric difference, tree edit distance) that feed clustering into product families, and tree union into a generic BOM. The most directly transferable result is from Tate et al. (2024): constraining fuzzy name matching by BOM structure cut candidate matches on a hardware BOM from 743 to 21 and isolated typos, real substitutions and naming-specificity differences. Evidence is thin: every evaluation found is a small case study (2 to 405 BOMs), and all tree-distance methods assume part labels were already cleaned or generalised.

### Cited Findings

**Tate, Jones, Dennis, Benko, Askren (PNNL), "Comparing Bills of Materials", arXiv 2411.10384v1, 15 Nov 2024** `[preprint | full]` — [arXiv](https://arxiv.org/pdf/2411.10384)

- Scope is supply-chain risk (software and hardware BOMs), not design reuse. Named use cases (Section I): version or patch change, "evaluating a received BOM against an authoritative reference BOM", "variation across a family of products", and "identifying inconsistencies in the creation of BOMs themselves".
- On the dirty-data paradox (Section I): "many of these inconsistencies that make comparison difficult are most easily discovered via comparison."
- Barriers to comparison listed in Section III: standards and versions, naming conventions, hashing, structure, scoping, quantities, order. On naming (III.C): "'MSFT', 'Microsoft Corporation', and 'Microsoft' are all defensible values but the inconsistent recording makes systematically disambiguating them difficult." Hardware identifiers "have a tendency to describe a family of components", e.g. `AD7579` versus `AD7579JN`.
- On quantities (III.G): one BOM may list a component n times while another uses a quantity field, and "you have to rectify these different representations when conducting a comparison."
- Method claim (Section IV): "Unfortunately there is no single method that can be used to compare BOMs." Fuzzy matching "allows for some threshold of leniency in matching values that are 'close enough' at the expense of possibly making errant matches."
- List and set comparison (IV.A): input is flattened component lists; output is counts of common and unique names. Limit: ignores relationships. It may be necessary to compare "the manufacturer and name at the same time".
- Graph comparison (IV.B): components become nodes, relationships become edges, attributes are attached, then a node mapping is built. Merge uses "a depth-first search matching algorithm" with exact matching, from the authors' earlier VizSec 2023 paper.
- Software BOM example (Section V, Thingsboard 3.6.4 versus 3.7.0, 230 and 234 components): Jaro-Winkler above 0.85 on names alone "resulted in a total of 887 matches"; with the graph constraint "there are 7 similar packages". The authors call the 0.85 threshold "arbitrary".
- Hardware BOM example (Section VI, two instances of the same product, 156 and 169 components): 35 names only in HBOM 1 and 46 only in HBOM 2. Fuzzy matching alone "flagged 743 possible matches which is difficult to sift through". With the graph constraint "there are only 21 matches, identifying transcription errors and incremental component variations with high precision."
- The differences fell into three categories (Section VI): (1) transcription error, "IN3S00A and IN3500, where a 5 is switched for an S"; (2) a real substitution "with a different but equivalent component"; (3) different specificity, "V17N" versus "V17N-ZB11".
- The comparison also surfaced an unexpected extra circuit board in one unit (Section VI).
- Limits stated or visible: two worked examples only, no precision or recall figures, obfuscated hardware data, threshold not tuned. Conclusion (Section VII): "List, set, and graphical comparisons are complimentary".
- Literature review claim (Section II): after listing Romanowski and Nagi, Shih, Kashkoush and ElMaraghy, and Schmidt et al., "This is all of the literature we could find on applying graph comparisons to BOMs."
- **Works on BOM structure and text.**

**Romanowski and Nagi, "On comparing bills of materials: a similarity/distance measure for unordered trees", IEEE Trans. SMC Part A 35(2), 2005, pp. 249-260** `[peer-reviewed, read as author-hosted manuscript SMCA03-05-0120 | partial: Sections I to III.C read in full, III.D to V and appendix via targeted passages]` — [author PDF](https://www.eng.buffalo.edu/~nagi/papers/IEEESMCApaper.pdf). The listed SUTD repository page is a JavaScript application and returned no content `[no access]` — [SUTD record](https://repository.sutd.edu.sg/esploro/outputs/journalArticle/On-comparing-bills-of-materials-a/9911026209846)

- Purpose (abstract): a similarity metric between existing products "based on bills of materials (BOMs), a class of unordered trees", used as the distance for clustering BOMs into product families.
- Named use cases (abstract and Section I): "marketing, variant design, group technology and cellular manufacturing". Motivation (I.B): "identifying similar end items whose designs can be re-used in new products."
- Why BOMs are hard (I.A): "Different engineers may build completely identical end items with very different BOM structures". BOMs differ in structure, in component labels, or both.
- Why not tree edit distance (II.A to II.B): unit-cost edit operations give wrong distances for BOMs. Example (Case 2): moving a subtree to a new parent costs 6 by delete and insert, where the intuitive cost is 2. "In BOMs, we are interested primarily in content; topology is a secondary concern". Edit distance between unordered labelled trees is NP-complete (II.A).
- Method (Section III): each BOM becomes an adjacency matrix where an entry is the quantity of child per parent. The symmetric difference "is the set of edges that appear in one graph but not the other". A normalised "sparsity value" is the similarity score; smaller means more similar.
- Partial matching (III.D): weights w between 0 (perfect match) and 1 (no match) "represent the design, functional, or manufacturing similarities between two parts".
- Input requirement (II.D): exact part numbers are replaced by generalised class labels (washers `XYZ-10` and `XYZ-20` become `XYZ`). "this part label generalization requires domain knowledge to accomplish effectively, and is currently a primarily manual operation." The paper assumes "the distances between purchased items (leaf nodes) are available in an offline lookup table".
- Algorithm (Section IV and complexity discussion): the "DeRe" algorithm removes exactly matching subtrees, pairs remaining subtrees by bipartite matching, then sums. "Therefore, the algorithm takes O(n2) time."
- Evidence (Section V): "75 bills of materials with known product family classifications were collected from an electronics manufacturer"; the k-medoid clustering "correctly placed the BOMs in the appropriate families." The authors call this a "preliminary result".
- Stated limit (Section V): the algorithm "could 'double count'" nodes with different parents and so gives "a higher weighted symmetric difference than some designers might prefer."
- Output: one pairwise distance per BOM pair and a clustering. It does not directly output a list of shared sub-assemblies.
- **Works on BOM structure**, but only after labels are cleaned and generalised.

**Romanowski and Nagi, "A data mining approach to forming generic bills of materials in support of variant design activities"** `[author-hosted manuscript; publication venue not verified | partial: abstract, Sections 1 to 3.5 by targeted passages]` — [author PDF](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf)

- This is the companion paper I could open. The paper with the exact title "Data mining in an engineering design environment: OR applications from graph matching" (Computers and Operations Research, 2006) was `[snippet]` only — [SUTD record](https://repository.sutd.edu.sg/esploro/outputs/journalArticle/Data-mining-in-an-engineering-design/9911032309846); the search summary says it defines "tree bundle matching" and shows it is NP-hard.
- Motivation (Section 1): "Variant design, which accounts for approximately 80% of design tasks (Prebil et al. 1995), seeks to solve new design problems by reusing or adapting existing work."
- Two named uses of a generic BOM (Section 1): it acts as "a tool for configuring new variants (colloquially referred to as a 'product configurator')" and it supports "a designer's search for similar parts – and thus the reuse of existing designs."
- Pipeline (Sections 3.3 to 3.4): text-mine part descriptions, build a company thesaurus, compute part similarity, cluster parts into groups, replace part numbers by group labels, cluster single-level subtrees, cluster BOMs, then unify each cluster by tree union.
- No-CAD case (Section 3.4.2): for purchased buttons, "No CAD drawings are available" and "the part description must be used to form part families."
- The tree union records optional and alternative children, quantity ranges and "level jumps" (same part under different parents). Example (Section 3.5): raw cable multiplicity "from 21 to 366 inches"; "in 10 out of 25 BOMs the plug is a child of the cable assembly."
- Design rules by association mining within each cluster (Section 3.4): "If the car type is compact, the engine type is 4 cylinder."
- Evidence (Section 3.5): "a sample of 405 BOMs from one of the major product families" of a nurse call device maker; "156 single level trees were clustered using CLARANS". No accuracy figure is given in the passages read.
- **Works on BOM structure and part description text.**

**Schmidt, Gehring, Gerber, Stocker, Kreimeyer, Lienkamp (TU Munich and MAN Truck & Bus), "Graph-based similarity analysis of BOM data to identify unnecessary inner product variance", ICED17, 2017, pp. 489-498** `[peer-reviewed conference | partial: abstract, Sections 1, 2 and 4 passages, Table 1 and comparison table, conclusion]` — [Design Society](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance)

- Aim (abstract): reduce "unnecessary inner variety", which "adds no value to the customer, yet it induces complexity costs within the whole company."
- Method: BOMs as hierarchical graphs; similarity by APTED tree edit distance (Pawlik and Augsten 2016) converted to an index, compared with a simpler content-only algorithm labelled CPA (expansion not captured in my extraction) and with classical commonality indices (DCI, CIC, TCCI; Table 1).
- Case study (Section 4): "BOM data sets of 14 different rear axle component variants", "an Excel table with 4250 rows", average "304" nodes per variant; implemented in Soley Studio.
- Questions it answers (conclusion): "Which assemblies or whole areas of the component variants are theoretically promising standardization candidates due to high similarity and high savings potential? How similar are these variants? Where are the similar assemblies and areas located in the product structure".
- Limits (comparison table before the conclusion): for both algorithms, "'Clean' Bom data required". The content-only algorithm has "no consideration of structural similarity"; APTED has "Higher run time" and needs "Determination of optimal setting parameters".
- Result is qualitative: the case study "showed that the approach provides valid and practicable search results". No savings figure.
- **Works on BOM structure.** Requires clean data.

**Kashkoush and ElMaraghy, "Matching Bills of Materials Using Tree Reconciliation", Procedia CIRP 7, 2013, pp. 169-174** `[peer-reviewed conference | abstract]` — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2212827113002369)

- Borrows "tree reconciliation" from phylogenetics "to match pairs of BOM trees and retrieve the most similar design". Named use: design retrieval to speed up downstream planning.
- Their later paper (CIRP JMST 2016, product family formation) states the earlier method had "some limitations" and proposes a new measure `[snippet from ScienceDirect related-articles panel]`.

**Other methods named in the literature but not opened**

- Shih (2011), orthogonal Procrustes product-structure similarity; Cinelli et al. (2020), network analysis of a single BOM; both listed in Tate et al. Section II `[cited via Tate et al., not read]` — [arXiv](https://arxiv.org/pdf/2411.10384)
- Chowdhury and Nayak, matrix-based data mining for product families, reported to beat the Procrustes baseline `[snippet]` — [CRPIT abstract](https://crpit.scem.westernsydney.edu.au/abstracts/CRPITV158Chowdhury.html)
- Commonality indices DCI (Collier 1981), CIC (Jiao and Tseng 2000), TCCI (Wacker and Treleven 1986): computed from BOM data alone; DCI is "Difficult to interpret due to varying upper limit" (Schmidt et al., Table 1) `[peer-reviewed conference | partial]` — [Design Society](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance)

**Method summary table (compiled from the sources above)**

| Method | Input | Output | Limits stated in source | Needs CAD? | Source |
|---|---|---|---|---|---|
| Set or list overlap, exact | Flattened part lists | Common and unique parts, counts | Ignores structure and near-duplicates | No | Tate et al. IV.A |
| Fuzzy string match (Jaro-Winkler) | Part names | Candidate pairs | Too many candidates alone: 743 and 887 in the examples | No | Tate et al. V, VI |
| Structure-constrained fuzzy match | Parent-child BOM plus names | Merged graph, matched and unmatched nodes | Assumes comparable structure; arbitrary threshold | No | Tate et al. V, VI |
| Weighted symmetric difference (DeRe) | Trees with generalised labels, leaf distance table | Pairwise distance, product families | Manual label generalisation; may double count moved nodes | No | Romanowski and Nagi 2005 |
| Tree edit distance (APTED) | Clean hierarchical BOM | Similarity index per assembly pair | Clean data, run time, cost tuning; criticised as wrong for BOMs by Romanowski and Nagi | No | Schmidt et al. 2017 |
| Commonality indices | BOM, sometimes volumes and cost | One index per family | Hard to interpret or hard to collect data | No | Schmidt et al. Table 1 |
| Tree union into generic BOM, plus association rules | Clustered BOMs, part descriptions | Generic BOM with optional parts, ranges, level jumps; design rules | Global rules not addressed | No | Romanowski and Nagi GBOM |
| Tree reconciliation | Pairs of BOM trees | Most similar past design | Not read in full | No | Kashkoush and ElMaraghy 2013 |

### Inferences
- (Inference) The structure-constrained fuzzy match in Tate et al. is the closest published analogue to the pilot question "where are the inconsistencies?". Its three difference categories map onto typo, legitimate variant difference, and reference written at different specificity.
- (Inference) Two peer-reviewed sources disagree on tree edit distance for BOMs: Romanowski and Nagi argue it gives wrong costs, while Schmidt et al. use APTED and report valid results at MAN. Both can hold, since Schmidt compares variants of one component with similar structure. For BOMs written by different engineers, content-first measures are safer.
- (Inference) No method found outputs "reusable sub-assemblies" directly. The published building blocks are: exact shared subtrees (step 1 of DeRe), near-matching subtrees (step 2), and optional or alternative children in a generic BOM. A demo would compose these.
- (Inference) All tree-distance papers assume the cleaning step is done. For dirty data, reconciliation has to come first, and Tate et al. show that structure can help that reconciliation rather than only consume its output.

### Gaps
- No source found applies graph kernels, frequent-subtree mining or learned embeddings to BOM similarity. A targeted search for 2022 to 2024 work returned only general subtree-mining papers (Welke et al., HOPS) with no BOM application `[snippet]` — [Fraunhofer record](https://publica.fraunhofer.de/handle/publica/253388)
- No BOM-comparison paper reports precision, recall or F1 against a labelled ground truth.
- No paper evaluates on rail or rolling-stock BOMs.
- Kashkoush and ElMaraghy 2014 and 2016, and the Windsor dissertation, were not read in full.

---

## 2. Part and sub-assembly rationalisation products

### Takeaway
Commercial part-rationalisation tools are dominated by 3D shape search (PTC Windchill AI Parts Rationalization, CADENAS GEOsearch, Siemens Geolus, 3DPartFinder), which needs CAD geometry and so does not fit the pilot data. Classification-based offers (PTC Windchill classification, Dassault Part Classification as-a-Service) work from attributes and a taxonomy. All savings figures found are vendor claims; the only ones with a named customer and date are Ingersoll Rand (2010), Starlinger (2011 to 2013) and MAC Trailer (2020 to 2022), and several are estimates rather than measurements.

### Cited Findings

**PTC Windchill AI Parts Rationalization**

- Launch: 27 January 2026. It "detects similar parts to prevent duplicates, identifies redundant parts already in enterprise systems, and drives consolidation through change workflows." Delivered as a plugin. No customer and no savings figure in the release `[vendor marketing | full]` — [PTC press release](https://www.ptc.com/en/news/2026/ptc-launches-windchill-ai-parts-rationalization)
- Roadmap in the release: "smart-assisted classification, part reuse in design environments, schema guidance, and tools for monitoring duplicates and comparing material and cost properties." `[vendor marketing | full]` — [PTC press release](https://www.ptc.com/en/news/2026/ptc-launches-windchill-ai-parts-rationalization)
- ARC Advisory Group note by Craig Resnick, 28 January 2026: restates the release. Listed aims include "Identifying duplicate and similar parts across enterprise systems" and "Supporting consolidation workflows". No customer, no number, no independent test `[trade press | full, read through a text proxy because the site returned HTTP 403 to direct requests]` — [ARC](https://www.arcweb.com/blog/ptc-introduces-windchill-ai-parts-rationalization-capability)
- **Needs geometry.** PTC help: the plugin finds "duplicates or similar parts based on shape similarity with minor variations" in the engineering BOM `[vendor documentation | full]` — [PTC help, introduction](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginIntroduction.html)
- Known limitations page: "The AI model generates part representations solely based on the 3D geometry provided in the PVZ file." Ignored: colours, materials, decals, inner structure, and "Metadata or part attributes". Scale-insensitive: two bolts "1 cm vs. 2 cm" are "considered identical". "Mirrored parts ... are not treated as duplicates." `[vendor documentation | full]` — [PTC help, limitations](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html)
- Same page: "Duplicate search is not idempotent"; it "may take several hours"; groups hold 2 to 1024 parts `[vendor documentation | full]` — [PTC help, limitations](https://support.ptc.com/help/windchill/ai_plugin/en/Windchill_Help_Center/parts_rationalization/AIPluginLimitation.html)

**PTC blog, "Challenges Managing Duplicate Parts", Claire Cavanaugh, 8 June 2023** `[vendor marketing | full]` — [PTC](https://www.ptc.com/en/blogs/plm/challenges-managing-duplicate-parts)

- Use case: classification to avoid duplicates. Problem example: "screws with the same thread size, but different length or coating".
- Vendor claim, no customer named: "Reducing duplicate parts to maximize reuse can save manufacturers millions of dollars per year."
- Consequence of no classification: "poor part reuse, increased scrap and rework, and high inventory."
- Data needed: classification schemes and attributes. Windchill "automatically assigns names to parts and documents based on their classification" and supports "localized text and measurements" for search across regions.
- **Works on attributes and classification, no geometry required.**

**CADENAS and PTC deck, "Find, Search & Reuse: Repetitive parts management with PTC Windchill & PARTsolutions", Thorsten Müller and Jürgen Leiprecht, Augsburg, February 2015, 19 slides** `[vendor marketing | full]` — [CADENAS PDF](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf)

- Note: the file sits under a `/de/` path but the slide text is in English, so no translation was needed.
- Key figure (slide 5), with its original source as printed: "Ingersoll Rand (David Owens, PTC-User 2010)". "Saving potential (only inventory cost) of 60.000 duplicate parts (5% of all parts) = 30 Mio. US$" and "Every new part costs 2.775 US$". This is a vendor-relayed customer conference claim from 2010, labelled a "potential".
- Four use cases (slide 8): A, catalogue content in Windchill ("600 catalogues available"); B, "Suggestion for best class during check-in process"; C, "Geometrical Search" combined with full-text search; D, "automated reports with duplicate candidates" and reports that "check, if company part is available as purchasing part".
- Duplicate report triggers (slide 17): daily, on every check-in, or on user command, sent to the standards department.
- Claimed benefits (slide 18), no numbers: "Less duplicate parts", "Less materials in stock", "Higher purchasing volumes", "Less (costly) changes, late in the product development cycle".
- Search modes (slide 6): "Geo-Search", "Topol. Search", "Full Text Search", "Classif. Search". Class suggestions are "based on geometry and/or attributes" (slide 13).
- **Mostly needs geometry**; full-text and classification search do not.

**CADENAS PARTsolutions customer stories** (all vendor claims)

- Starlinger (Austria, machinery), operational use 2011 to 2013. Infographic figures: purchased parts 15% and company parts 8% under "Reducing the parts", against product-range growth of 18% in machine types and 30% in versions. New creation of "A and Z parts was reduced by approx. 1100 parts"; savings of "about one million Euros compared to the forecast curve". Caveat in the source: "The complete savings ... can only be estimated roughly". Search takes "between three and ten seconds". Each engineer "saves 0.25 hours per day" `[vendor marketing | partial]` — [CADENAS Starlinger PDF](https://www.cadenas.de/files/cadenas/Downloads/PDF/Referenzen/EN/PARTsolutions_Starlinger_Success_Story_EN.pdf)
- Starlinger quotation use case, same source: before costing a new machine, PARTsolutions "is used for a rough calculation with the prices of similar parts" `[vendor marketing | partial]` — [CADENAS Starlinger PDF](https://www.cadenas.de/files/cadenas/Downloads/PDF/Referenzen/EN/PARTsolutions_Starlinger_Success_Story_EN.pdf)
- MAC Trailer (US, trailers), project from fall 2020, in Teamcenter by 2022: parts cut "from 1.3 million distinct parts and assemblies to just 300,000. That is a decrease of 77% of redundant 3D models." Money claim is rhetorical: "Even if we only saved one dollar per part, this project has saved MAC Trailer over a million dollars" (Zach Kennedy, Director of IT) `[vendor marketing | partial]` — [PARTsolutions MAC Trailer PDF](https://partsolutions.com/wp-content/uploads/2023/07/Mac-Trailer-Case-Study_FINAL.pdf)
- BOMAG (Germany, construction machinery), user since 2009: internal cost per new part "1,200 Euros ($1600 US)", "more than 85,000 parts". The "$2.72 million" figure is a hypothetical: "Estimating a reduction ... by a conservative 2%". Also a costing use: procurement uses the new part "to look for a similar component" to estimate its cost `[vendor marketing | partial]` — [PARTsolutions BOMAG page](https://partsolutions.com/bomag-utilize-partsolutions-parts-management-software-to-search-and-control-standard-parts)
- EIRICH and RÖHM stories report slower growth of new parts and about 50 EUR saved per new part at EIRICH, no percentage `[snippet]` — [CADENAS EIRICH news](https://cadenas.de/de/news/partsolutions-reduces-design-times-and-costs-for-creating-new-parts-at-eirich)
- **Needs geometry** for the headline capability.

**Dassault Systèmes, "Part Classification as-a-Service: From Chaos to Reuse" (on-demand webinar page, 33 minutes, speaker Olivier Astier, Portfolio Director, Virtual Twin as-a-Service)** `[vendor marketing | full page text; webinar video not watched]` — [3DS](https://events.3ds.com/part-classification-service-chaos-reuse)

- Vendor claim, customers unnamed, no date on the page: "our customer business cases range from 27.5M€ to 50M€ per year."
- Cost logic: "the annual carrying cost of a single new part number is in the thousands."
- Diagnosis: "The root cause isn't a lack of search tools. It's that your part catalog — scattered across PLM, PDM and ERP systems — was not classified on a consistent taxonomy."
- Delivery model: Dassault "classifies your catalog for you — on your own taxonomy, on our infrastructure", with experts validating. Steps named: "From taxonomy and training data to batch classification of the full catalog".
- Data needed: a taxonomy and training data. The page does not say whether 3D geometry is required.

**Siemens Teamcenter Geolus shape search**

- "Geolus Shape Search quickly finds parts with similar geometry, regardless of how they are classified." Claimed savings areas, unquantified: "design time, cost estimating, procurement, manufacturing, and inventory" (Siemens blog, 18 April 2017) `[vendor marketing | partial]` — [Siemens blog](https://blogs.sw.siemens.com/designcenter/geolus-shape-search-i-need-a-part-that-looks-like-this/)
- BCT Technology (Siemens partner) case: keyword search "fails to return similarly shaped parts if there are naming issues"; shape plus metadata lets shops "quickly respond to RFQs with less risk" (Juergen Hillemann). No numbers `[vendor marketing | partial]` — [Siemens case study](https://resources.sw.siemens.com/en-US/case-study-bct-technology/)
- A Siemens page is reported to cite Aberdeen research putting the annual carrying cost of a new part number at $4,500 to $23,000. I did not find this figure in the page I opened `[snippet, unverified]` — [Siemens blog index](https://blogs.sw.siemens.com/news/?p=2166)
- **Needs geometry.**

**3DPartFinder** `[vendor marketing | partial: home page]` — [3DPartFinder](https://www.3dpartfinder.com/)

- Use cases named: "Stop Part Proliferation!", "Create quotations in a snap!" by reusing "previous quotations and your manufacturing data of similar parts", and reuse of CNC programs and tooling.
- Premise: "two similar parts with the same material will most likely have the same function, similar cost, similar manufacturing processes".
- No customer and no number on the page read. **Needs geometry.**

**Other**

- Deloitte article reported to describe an industrial manufacturer achieving more than $30M savings across 18 commodities, with 30% of parts identified as duplicates by clustering. Not found in the page text I retrieved `[snippet, unverified]` — [Deloitte](https://www2.deloitte.com/us/en/pages/operations/articles/rpa-for-manufacturing-parts-proliferation.html)

**Product summary**

| Product | Use cases offered | Data needed | Savings claim (all vendor claims) | Customer, date |
|---|---|---|---|---|
| PTC Windchill AI Parts Rationalization | Duplicate detection, consolidation by change workflow | 3D geometry only (PVZ); attributes ignored | None quantified | None named; launched 27 Jan 2026 |
| PTC Windchill classification | Classify, auto-name, attribute search | Classification scheme, attributes | "millions of dollars per year" | None named; blog 8 Jun 2023 |
| CADENAS PARTsolutions | Geometric search, class suggestion at check-in, duplicate and make-or-buy reports, costing by similar part | Geometry, catalogues, attributes | $30M inventory potential for 60,000 duplicates; 77% fewer models; about 1 M€ versus forecast | Ingersoll Rand 2010; MAC Trailer 2020 to 2022; Starlinger 2011 to 2013 |
| Dassault Part Classification as-a-Service | Batch classification of whole catalogue on customer taxonomy | Taxonomy, training data; geometry not stated | 27.5 M€ to 50 M€ per year business cases | Unnamed; undated |
| Siemens Geolus | Shape search, reuse, RFQ response | Geometry, optional attributes | None quantified in pages read | BCT (partner), JCB listed but not read |
| 3DPartFinder | Reuse, quotation from similar parts, CNC reuse | Geometry | None found | None found |

### Inferences
- (Inference) The Ingersoll Rand slide mixes two cost bases: $30M over 60,000 duplicates is $500 per part in inventory cost, while $2,775 is the cost of creating a new part. They should not be multiplied together.
- (Inference) Cost-per-new-part figures vary by more than an order of magnitude across vendor material: about 700 EUR process cost plus 100 EUR a year at Starlinger, 1,200 EUR at BOMAG, $2,775 at Ingersoll Rand, "thousands" per year at Dassault. Any business case built on one of them needs the customer's own number.
- (Inference) A text-and-structure tool is not competing with shape search on the same data. Its niche is the cases shape search cannot see: PTC's own documentation says attributes, materials and scale are ignored, and none of these tools reasons at sub-assembly level from BOM structure.
- (Inference) Two vendor stories (Starlinger, BOMAG) and one product page (3DPartFinder) name "cost a new item from similar existing items at quotation time" as a use case. This is the nearest product precedent for the tender-reuse framing.
- (Inference) Dassault's framing that classification on one taxonomy is the precondition for any reuse or AI supports presenting reconciliation as the first deliverable.

### Gaps
- aPriori: no relevant page found; one guessed URL returned 404.
- Aras: nothing found on similar-part search or rationalisation results.
- Siemens Teamcenter classification AI and product configurator: no page with use cases or figures was opened.
- No independent or peer-reviewed evaluation of any commercial rationalisation product was found.
- No product found claims sub-assembly-level reuse detection from BOM structure without geometry.

---

## 3. Product master data cleansing and entity resolution for parts and suppliers

### Takeaway
I found no published accuracy figure for entity resolution on industrial part or supplier master data. The nearest evidence is from e-commerce product matching, where Peeters, Steiner and Bizer report that GPT-4 with no task-specific training beats fine-tuned language models on 3 of 4 datasets, and from BOM papers that use simple string similarity with structural constraints.

### Cited Findings
- Peeters, Steiner, Bizer, "Entity Matching using Large Language Models", arXiv 2310.11244v4 (18 Oct 2024): pre-trained-model matchers "require significant amounts of task-specific training data" and "are not robust concerning out-of-distribution entities" (abstract) `[preprint; the search record indicates a later conference version, not verified | partial: abstract, Sections 1 and 2]` — [arXiv](https://arxiv.org/pdf/2310.11244)
- Same paper, contribution 4 (Section 1): "GPT4 without any task-specific training data outperforms fine-tuned PLMs on 3 out of 4 e-commerce datasets". Here PLM means pre-trained language model, not product lifecycle management.
- Same paper, abstract: "there is no single best prompt but that the prompt needs to be tuned for each model/dataset combination." It also reports that GPT-4 "can generate structured explanations for matching decisions".
- Same paper, contribution 5: open-source models "can reach a similar F1 performance as hosted LLMs given that a small amount of task-specific training data or matching knowledge in the form of rules is available."
- Datasets used are WDC Products, Abt-Buy, Walmart-Amazon and others (Section 2). These are consumer product offers, not industrial part masters.
- WDC Products benchmark: built from product offers on thousands of e-shops; all tested systems struggled with unseen entities `[snippet]` — [arXiv abstract](https://arxiv.org/abs/2301.09521v1)
- An arXiv paper on OpenSanctions entity pairs is reported to show LLMs reaching up to 98.95% F1 against a rule-based production baseline at 91.33% F1. Domain is persons and organisations, not parts `[snippet, unverified]` — [arXiv](https://arxiv.org/pdf/2603.11051)
- Splink (UK Ministry of Justice) is a probabilistic Fellegi-Sunter library that needs no training labels; the UK government review is reported to say direct, generalisable accuracy comparisons between approaches "are rare in the literature" `[snippet]` — [GOV.UK](https://www.gov.uk/government/publications/joined-up-data-in-government-the-future-of-data-linking-methods/splink-mojs-open-source-library-for-probabilistic-record-linkage-at-scale)
- In BOM comparison, Jaro-Winkler at 0.85 on names alone gave 743 candidates on a 156 versus 169 component hardware BOM; adding the structural constraint left 21 (Tate et al., Section VI) `[preprint | full]` — [arXiv](https://arxiv.org/pdf/2411.10384)
- Text mining of the item-master description field can build part families when no CAD exists (Romanowski and Nagi GBOM paper, Section 3.4) `[author manuscript | partial]` — [author PDF](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf)
- Lexical normalisation of noisy technical short text reached precision 99.7, recall 97.5 and error-reduction rate 95.8 on the combined test set, and cut vocabulary size by more than 50% (MaintNorm, Table 7 and Results) `[peer-reviewed workshop | partial]` — [ACL Anthology](https://aclanthology.org/2024.wnut-1.7.pdf)

### Inferences
- (Inference) For part references with typos, the published pattern that fits is blocking by structure (same parent or same position), then string similarity, then human review. Tate et al. give the only worked numbers.
- (Inference) LLM-based matching is plausible for the residual hard pairs and can give an explanation per decision, which matters to a sceptical data engineer. Its accuracy on part masters is unmeasured in the literature found, so a pilot would need its own labelled sample.
- (Inference) MaintNorm's vocabulary reduction suggests that normalising free text before matching is high-leverage, though it was shown on English mining work orders only.

### Gaps
- No precision or recall on part-master or supplier-master deduplication was found for Splink, dedupe, Zingg or any commercial MDM tool. Dedupe and Zingg were not researched beyond one combined search.
- No commercial MDM vendor material was read.
- No source addresses unit reconciliation (mixed units) as an evaluated task; Tate et al. only discuss quantity representation.

---

## 4. Variant and configuration management: 150% BOM, modular BOM, configurators, reuse at quotation time

### Takeaway
The 150% (overcomplete) BOM and the generic BOM are the standard structures for holding all variants once, and configurators that sit on them have the strongest quantified evidence in this whole review: a peer-reviewed study of 14 companies estimates an average 85.5% cut in quotation lead time. Those figures are company estimates, and they measure a configurator in use, not the mining of legacy BOMs to build one.

### Cited Findings
- Haug, Hvam, Mortensen, "The impact of product configurators on lead times in engineering-oriented companies", AI EDAM, 2011: a literature study found "Only six cases" with lead-time estimates; the authors' study of 14 companies found configurators "estimated to have implied up to a 99.9% reduction of the quotation lead time with an average estimated reduction of 85.5%" (abstract) `[peer-reviewed | abstract]` — [Cambridge](https://www.cambridge.org/core/journals/ai-edam/article/impact-of-product-configurators-on-lead-times-in-engineeringoriented-companies/107D0DB206626EE028613F59CB0DF203)
- Same abstract: studies of configurator effects "are mostly vague when reporting the effects of configurator projects."
- F.L. Smidth (cement plants) case: budget quotation lead time reported to fall from 2 to 5 weeks to 1 to 3 days `[snippet, unverified]` — [DTU Orbit](https://orbit.dtu.dk/en/publications/improving-the-quotation-process-with-product-configuration/)
- Kourtis, Hvam, Fernandez Correa, Johnsen, Proceedings of the Design Society, 2026 (DOI 10.1017/pds.2026.10424): 150% BOMs "act as master structures containing all possible components and subassemblies, avoiding duplication of variant-specific BOMs"; modular BOMs enable "reuse and reducing engineering effort" (introduction, citing earlier work) `[peer-reviewed conference | partial: abstract, introduction, method and case passages]` — [Cambridge](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader)
- Same paper, the problem it targets: "inconsistencies between configuration intent and released BOM structures often remain hidden until late validation stages, requiring time-consuming manual diagnosis."
- Same paper, evidence: a proof-of-concept at "a European fibre-laser manufacturer" that "demonstrates support for variant validation, error detection, and alignment" (abstract). The prototype shows the generic 150% BOM beside a released variant "with non-included nodes filtered out and detected inconsistencies highlighted" (Figure 7 text). No quantified benefit in the passages read.
- Generic BOM as configurator and as reuse aid (Romanowski and Nagi GBOM paper, Section 1): see section 1 above `[author manuscript | partial]` — [author PDF](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf)
- Alstom electrical design configurator (Zuken E3.series case study, undated): "they feed the configurator with only the main parameters taken from the customer's requirements. A set of rules stored in the configurator automatically computes most of the follow-up parameters." Result claimed: "faster work processes with improved quality", unquantified `[vendor marketing | partial]` — [Zuken](https://www.zuken.com/en/resource/alstom/)
- Cognyx positions on the same ground: "Manage Variants, Diversity & Configurations (150%, 100%) in one visual BOM" `[vendor marketing | full]` — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Vendor statements, not opened: Dassault ENOVIA on one configured structure generating each 100% BOM; Siemens German-language material citing up to 70% reuse of identical parts in modular designs `[snippet, unverified]` — [3DS ENOVIA](https://www.3ds.com/products/enovia/configuration-management.md), [Siemens PDF](https://www.plm.automation.siemens.com/media/global/de/vereinfachung-des-variantenmanagements_tcm53-88740.pdf)

### Inferences
- (Inference) The quotation-time evidence supports the value story "answer tenders faster by reusing configured modules", but the causal chain for a pilot is longer: reconcile data, find shared sub-assemblies, propose a generic structure, then configure. The 85.5% figure belongs to the last step only.
- (Inference) Deriving a draft 150% view from several variant BOMs (shared core, optional and alternative children, quantity ranges, parts that jump level) is a concrete, demonstrable output with a peer-reviewed precedent in the generic BOM work.
- (Inference) Kourtis et al. treat "inconsistency between variant BOM and generic structure" as a diagnostic view in its own right, which matches the second half of the pilot question.

### Gaps
- No study found quantifies the benefit of a 150% BOM separately from a configurator.
- Haug et al. was read as abstract only; the per-company figures and how the estimates were collected were not checked.
- No rail-specific configurator results with numbers were found.

---

## 5. Knowledge graphs in manufacturing and PLM

### Takeaway
Public material on product knowledge graphs is mostly architectural argument and vendor positioning. I found no source that reports a measured business result from a product or BOM knowledge graph at ASML, Bosch, Siemens or Airbus.

### Cited Findings
- OpenBOM blog, Oleg Shilovitsky, 22 November 2023: comments on an article by "Martijn Dullaart, a PLM and change management architect from ASML" about a product knowledge graph that "can track changes and semantic relationships" `[vendor marketing | full]` — [OpenBOM](https://openbom.com/blog/digital-thread-product-knowledge-graph-bill-of-materials-and-change-events)
- Dullaart passage as quoted by OpenBOM: "By bringing product data and process data together, interesting patterns emerge that could help us further improve the way we develop our products, prevent corrective actions and delays". This is a forward-looking statement ("could"), not a result.
- Same quoted passage on LLMs: modelling change events in a graph means LLMs "can use these to be trained and find patterns", to "improve the quality of your impact analysis and implementation planning of changes".
- OpenBOM's own claims: it uses "Graph Database (Neo4j)"; the graph is updated "from both user changes (eg. price change) and system changes (eg. CAD BOM update)". No customer and no number.
- Tate et al. (Section II) name the general advantage: "pairing the knowledge of what's inside something with information about how those components relate to each other", and note that "multiple BOMs can easily be combined to gain new information on a larger system". They cite Neo4j and OpenBOM as companies taking the graph approach `[preprint | full]` — [arXiv](https://arxiv.org/pdf/2411.10384)
- Cognyx's 2023 landing site lists three examples under "Join the innovators": Tesla "custom developed an end-to-end Product structure platform" for the Model 3 ramp-up; "Michelin created the knowledge graph to allow unification of R&D (material) and Engineering data"; the US Army "built a data layer on top of its system". These are presented as precedents, not as Cognyx customers, and carry no source or figures `[vendor marketing | full]` — [Cognyx 2023 landing page](https://cognyx-landing.pages.dev/)
- Bosch: published work is on knowledge graphs and ontologies for machine-learning pipelines in resistance spot welding quality monitoring (SemML; "Scaling Data Science Solutions with Semantics and Machine Learning: Bosch Case", ISWC 2023), not on product structure `[snippet]` — [KIT repository](https://publikationen.bibliothek.kit.edu/1000127042/97525942)
- Airbus: reported uses include ontology-driven requirements engineering (OntoREM, wing design requirements, with claimed cost and time savings and higher requirements reusability) and linking operator reports to maintenance tasks (ESWC 2017) `[snippet, unverified]` — [REF impact case study](https://impact.ref.ac.uk/casestudies/Results.aspx?Id=16104), [ESWC 2017 talk](https://videolectures.net/eswc2017_atemezing_semantic_web_technologies)

### Inferences
- (Inference) The questions these graphs are said to answer are impact analysis of a change, where-used across products, and joining product data with process or event data. Reuse across variants is a where-used question and fits the pattern.
- (Inference) Since no quantified knowledge-graph result was found, a use-case document should claim value from the task outcome (faster quotation, fewer duplicates) and treat the graph as the means.

### Gaps
- Dullaart's original article was not found; two searches and one guessed URL failed. Only OpenBOM's quotation of it was read.
- No Siemens product-knowledge-graph case with results was found; search returned digital-thread marketing only.
- The Bosch and Airbus items were not opened.

---

## 6. LLM and NLP extraction from engineering text

### Takeaway
The best-documented benchmarks are on English maintenance work orders: normalisation is near-solved (precision 99.7, recall 97.5 on MaintNorm), while fine-grained relation extraction is not (MaintIE's best model reaches about 77 micro F1 only under loose matching, and its strict score in one setting is zero). I found no verified precision or recall for LLM extraction from engineering change requests, non-conformance reports or lessons learned.

### Cited Findings

**Brundage, Sexton, Hodkiewicz, Dima, Lukens, "Technical Language Processing: Unlocking Maintenance Knowledge", Manufacturing Letters, published 11 December 2020 (NIST record)** `[peer-reviewed | abstract]` — [NIST](https://www.nist.gov/node/1647801)

- "Out-of-the-box natural-language processing (NLP) pipelines need re-imagining to understand and meet the requirements of the engineering sector."
- Industrial implementations built on general tools suffer "from a lack of verification, validation, and ultimately, personnel trust."
- Proposes "a holistic, domain-driven approach" named Technical Language Processing. This is a position paper; the abstract reports no accuracy figures.

**Bikaun, Hodkiewicz, Liu, "MaintNorm: A corpus and benchmark model for lexical normalisation and masking of industrial maintenance short text", W-NUT 2024** `[peer-reviewed workshop | partial: abstract, Sections 3 to 5, Tables 2 to 7, conclusion]` — [ACL Anthology](https://aclanthology.org/2024.wnut-1.7.pdf)

- Data: "12,000 MSTs sourced from three major Australian mining companies", heavy mobile equipment (Section 3).
- Task: correct spelling, expand abbreviations ("'eng' are converted to their full form 'engine'"), split joined tokens ("'250hr' to '250 hour'"), and mask identifiers, numbers, dates and sensitive spans.
- Model: ByT5-small encoder-decoder, byte-level (Section 4.3).
- Results, combined test set (Table 7): MaintNorm precision 99.7, recall 97.5, error-reduction rate 95.8. Baselines: most-frequent-replacement 99.8, 93.0, 89.4; ÚFAL 99.5, 90.2, 85.0.
- Effect on text: "a substantial reduction (>50%) in vocabulary size across all three companies" (Results).
- Noise is similar across independent companies: characteristics "are consistent across companies despite their independent creation" (Results).
- Limit: "Annotation is performed by the first author due to resource constraints" (Section 3.3). English only.

**Bikaun, French, Stewart, Liu, Hodkiewicz, "MaintIE: A Fine-Grained Annotation Schema and Benchmark for Information Extraction from Maintenance Short Texts", LREC-COLING 2024** `[peer-reviewed | partial: abstract, Sections 5 to 8, conclusion, appendix Tables 5 to 8]` — [ACL Anthology](https://aclanthology.org/2024.lrec-main.954.pdf)

- Scheme (abstract): "5 top-level classes: PhysicalObject, State, Process, Activity and Property and 224 leaf entities, along with 6 relations".
- Corpora: 1,076 expert-annotated texts (abstract; Section 6.1 says 1,067) and 7,000 coarse-grained texts. Texts average 5.4 tokens (Section 6).
- Headline (conclusion): "The best models achieved over 70% micro and macro F1-scores."
- Relation extraction detail, evaluated across 224 entity classes: REBEL with loose matching, micro precision 76, recall 81, F1 77 (Table 6). REBEL with strict matching, all zeros (Table 5). SpERT strict, micro F1 35 (Table 7); SpERT loose, micro F1 61 (Table 8).
- Earlier entity-only result cited (Section 2): Stewart et al. 2022 "achieved an impressive 82.8% micro F1 on a dataset comprising 4,000 annotated entities".
- Named purpose: answer "who is doing what to what, and why?" from work orders.
- Limit (Section 8.1): short texts "often lack the context to disambiguate and situate named entities (e.g. 'cable' in 'replace cable' ...)".
- Cost data point: coarse annotation of 7,000 pre-annotated texts took "approximately 40 hours", "averaging 25 seconds per text" (Section 5).

**LLM-based knowledge graph construction, 2023 to 2026**

- A management-of-change study on 12 cases from Shell across 6 process units is reported with document-level recall 0.904, precision 0.706, F1 0.776 against 467 ground-truth change locations, beating a dense-embedding baseline at F1 0.612; region-level recall 0.625. I could not identify the paper: the arXiv ID returned by the first search (2412.08593) is a different paper on software requirements `[snippet, unverified; source not located]` — [TU Delft repository author page](https://repository.tudelft.nl/person/other/Person_59d80119-42e0-4827-aa8d-27f61a1a5473?page=1)
- A Politecnico di Milano paper on requirements knowledge graphs is reported with slot-level macro accuracy 94.50% and quantitative-constraint precision 97.64%, recall 96.88% `[snippet, unverified]` — [Polimi repository](https://re.public.polimi.it/handle/11311/1320488)
- An IIT Madras project converts paper non-conformance records into a knowledge graph with an LLM query layer; no precision or recall reported in the summary `[snippet]` — [IIT Madras](https://wcte.iitm.ac.in/?p=1427)
- ChatP&ID (TU Delft), graph-based retrieval over piping diagrams: reported 18% better answer accuracy than raw images and 85% lower token cost, on a single one-page diagram `[snippet]` — [arXiv](https://arxiv.org/pdf/2603.22528)

**Vendor use of the idea**

- Cognyx: "Use AI agents to ingest your unstructured 'Lessons Learned' into enforceable BOM Rules." No method or accuracy published `[vendor marketing | full]` — [Cognyx use cases](https://en.cognyx.io/use-cases)

### Inferences
- (Inference) Normalisation (typos, abbreviations, joined tokens, masking) is the safest text capability to promise; it has the strongest numbers and directly reduces vocabulary before matching.
- (Inference) Fine-grained relation extraction from terse technical notes is error-prone even with a purpose-built corpus. A pilot should extract a small fixed schema (for example part reference, equivalence, constraint, unit and value) and keep every extraction traceable to its source sentence for review.
- (Inference) The technical-language-processing argument about validation and trust supports a design where the LLM proposes and a deterministic or human step confirms.

### Gaps
- No verified precision or recall for LLM extraction from engineering change requests, non-conformance reports or lessons learned. The two numeric results found are search-summary only.
- No paper found on turning lessons-learned text into BOM rules.
- The NIST technical-language-processing project page returned 404; Nestor and related tools were not reviewed.

---

## 7. Multilingual technical text (French and English)

### Takeaway
I found no benchmark or published pipeline for mixed French and English industrial short text. The closest evidence is a 2025 preprint on French building specifications, where CamemBERT and spaCy's French model reach entity F1 above 90%.

### Cited Findings
- "This study explores the integration of Building Information Modeling (BIM) with Natural Language Processing (NLP) to automate the extraction of requirements from unstructured French Building Technical Specification (BTS) documents" (arXiv 2508.13833, 20 August 2025; Arts et Métiers, G-SCOP, CSTB) `[preprint | abstract]` — [arXiv](https://arxiv.org/pdf/2508.13833)
- Same abstract: CamemBERT and `fr_core_news_lg` "exhibited superior performance in NER, achieving F1-scores over 90%, while Random Forest proved most effective in RE, with an F1 score above 80%." Evaluated on "A hand-crafted annotated dataset"; a knowledge graph is "future work".
- MaintNorm builds on the Multilingual Lexical Normalization shared task (van der Goot et al. 2021) and on ByT5, a byte-level model, but evaluates on English only (Sections 2 and 4.3) `[peer-reviewed workshop | partial]` — [ACL Anthology](https://aclanthology.org/2024.wnut-1.7.pdf)
- CamemBERT is a French-only model whose authors report it matches or beats multilingual models on tagging, parsing, entity recognition and inference `[snippet]` — [HAL](https://hal.archives-ouvertes.fr/hal-02445946)
- PTC Windchill states it "enables localized text and measurements for highly specific search functionality across multiple business regions", the only product statement found on multilingual part data `[vendor marketing | full]` — [PTC](https://www.ptc.com/en/blogs/plm/challenges-managing-duplicate-parts)
- MaintIE and MaintNorm are English. No French version of either was found `[snippet]` — [ACL Anthology](https://aclanthology.org/2024.lrec-main.954.pdf)

### Inferences
- (Inference) Handling French and English notes in one field is unmeasured ground. Any accuracy claim for the pilot has to come from a labelled sample of the pilot's own notes.
- (Inference) A byte-level or multilingual model, or a general LLM, is the natural choice for code-switched short text, but this is a design judgement and not a cited result.

### Gaps
- No corpus, benchmark or product claim for French-English code-switched engineering text.
- No evidence on French technical abbreviations or unit notation in normalisation tasks.

---

## 8. Cognyx: published use cases, features, results, customers, press

### Takeaway
Cognyx's public material is a five-page marketing site with one quantified claim, "reduce RFQ response time by up to 40%", stated without customer, date or method. It publishes no case study, no named customer and no measured result. Its stated positioning (fast concept BOM for tenders, reuse, 150% BOM, lessons learned into rules) matches the pilot's scope closely.

### Cited Findings

**Site pages** (all `[vendor marketing | full]`)

- Tagline: "Building hardware at software speed." Product description: "Ingest your PLM-ERP data and map it out in a smart R&D Ontology, securely stored in our Knowledge Graph." — [Cognyx home](https://cognyx.io/)
- Value claims on the home page: "Answer RFQ's in Days, rather than Months"; "Enhance modular design, maximize Re-Use"; "Minimize Non-Recurring Engineering costs"; "Enforce BOM Rules inferred from company's Knowledge"; "Control BOM against RFQ requirements" — [Cognyx home](https://cognyx.io/)
- Positioning in the stack: "Cognyx deploys as a Data Layer and System of Engagement on top of your existing IT stack." It "accelerates early Product Development phases ... before handing over seamlessly to PLM for Serial Life." — [Cognyx home](https://cognyx.io/)
- Use case 1, RFQ and concept BOM: "reduce RFQ response time by up to 40%, while maintaining quote's technical and financial accuracy." Also: "Re-use standard components, processes and configurations to respond to customer while reducing Non-Recurring Engineering (NRE) costs." — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Use case 2, multi-BOM: "Manage Variants, Diversity & Configurations (150%, 100%) in one visual BOM"; eBOM to mBOM or pBOM "without breaking continuity". — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Use case 3, rules and integrity: "built-in MBSE module"; "Use AI agents to ingest your unstructured 'Lessons Learned' into enforceable BOM Rules." — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Use case 4, optimisation under constraints: "Define your BOM constraints (AMDEC)"; "real-time AI recommendations for components, processes, or materials substitutions". — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Use case 5, sourcing BOM: "Associate BOM components, processes or materials with costing scenarios"; "Minimize Lead Time and Cost base for each BOM". — [Cognyx use cases](https://en.cognyx.io/use-cases)
- Technology page features: "Assemble BOMs in minutes using existing objects or groups of objects. Start from scratch, from a template or from a past project"; "Prompt Cognyx's AI to generate, compare, or optimize BOMs"; "Perform FMEA or Compliance checks"; "Full Changelog & Version History"; "Define your very own data model: custom objects, attributes and relationships"; "Connect to your CAD, PLM, and ERP tools." — [Cognyx technology](https://en.cognyx.io/technology)
- `https://www.cognyx.io/sbom` redirects to the technology page; the text is identical apart from whitespace. There is no separate sBOM page. — [Cognyx sbom URL](https://www.cognyx.io/sbom)
- About page: "Founded in Paris in September 2023"; mission "to build the 'GitHub for Hardware'"; aims at "a 10x improvement in speed and reliability of their engineering operations" (an aspiration, not a result). — [Cognyx about](https://en.cognyx.io/about)
- Funding, about page: "In summer 2024, Cognyx raised a 1.7m€ pre-seed round led by BPI Digital Venture ... supplemented by 0.8m€ of Venture Debt, taking initial funding to 2.5m€." — [Cognyx about](https://en.cognyx.io/about)
- Team listed: Matthias Berahya-Lazarus (CEO), Deon van der Vyver (CTO), Marie Petit (Product), François Roland (Software Engineer), Anna Larnicol (UX/UI), Anmol Bhoj (AI & Data), Antoine Gribaudo (Customer Success & Operations). — [Cognyx about](https://en.cognyx.io/about)
- Vision statement: by 2035 about 25% of software spend at engineering-heavy companies will go to "Engineering Knowledge", a category "between" ERP and PLM. This is a forecast by the company. — [Cognyx about](https://en.cognyx.io/about)

**Earlier Cognyx site and blog**

- A 2023 landing site carries the tagline "Enter the era of AI-powered product data management" and lists co-founders Deon van der Vyver, Michaël Valentin and Renan Devillières, with Luc Leroy ("ex director of automation at Tesla") as advisor `[vendor marketing | full]` — [Cognyx 2023 landing page](https://cognyx-landing.pages.dev/)
- Blog post, 20 September 2023, on graph databases in automotive: expected outcomes include "Significant cost savings, namely by reducing NRE" and "Increased portfolio profitability through standardization, automation of dataflows and generative design". It names relational legacy systems as the obstacle to "draw links between objects across the value chain". Outcomes are "expected", with no data `[vendor marketing | partial: body read to the cut-off of my extraction]` — [Cognyx blog](https://cognyx-landing.pages.dev/accelerating-time-to-market-in-the-age-of-electrification-how-graph-databases-pave-the-road-to-the-transformation-of-automotive-manufacturing/)

**Press and third-party**

- CFNews, Mickaël Deneux, dated 1 July 2024: Cognyx was "co-fondée par Matthias Berahya-Lazarus et Deon van der Vyver, au sein du startup studio spécialisé OSS Ventures" and publishes SaaS that lets manufacturers accelerate R&D. The rest is paywalled ("92% reste à lire"). Named angels in the page sidebar include Christophe Raynaud and Roxanne Varza `[trade press | partial: paywall]` — [CFNews](https://www.cfnews.net/L-actualite/Capital-innovation/Operations/Amorcage/Cognyx-se-developpe-aupres-de-business-angels-491005)
- Signalbase funding note: "$1,700,000 in funding"; Cognyx consolidates "product data throughout the value chain, including eBOM, mBOM, and sBOM" `[other: funding aggregator | partial]` — [Signalbase](https://www.trysignalbase.com/news/funding/funding-alert-cognyx-secures-1.7-million-for-revolutionizing-manufacturing-with-ai-and-graph-technology!)
- CB Insights lists $1.83M over two rounds, latest 3 July 2024, a slightly different figure from the company's own `[snippet]` — [CB Insights](https://www.cbinsights.com/company/cognyx/financials)
- A podcast episode (SaaS Connection no. 168, with the CEO) is described as saying the early months were built around paid design partners; none named `[snippet; page returned 403]` — [Podscan](https://www.podscan.fm/podcasts/saas-connection/episodes/168-matthias-berahya-lazarus-ceo-et-cofondateur-de-cognyx-reinventer-lingenierie-industrielle-avec-un-saas-enterprise)

**On the Alstom pilot itself**

- A public GitHub repository titled "Case Statement — Alstom x Cognyx — FDE" reproduces a recruitment case whose wording matches this brief (3-week pilot, Valenciennes, regional trains, multi-variant BOM CSV, free-text notes, the same client question). Its foreword says: "This case (inspired by real events…) was designed to simulate a work situation" and "For the purposes of this fictional exercise, feel free to invent any plausible figure, metric or detail about Cognyx or the client." It instructs candidates to "generate your own plausible synthetic dataset" `[other: third-party repository reproducing a Cognyx document | partial: README first 9 KB]` — [GitHub](https://github.com/leopoldlacroix/Cognyx_case)

### Inferences
- (Inference) The "up to 40%" RFQ figure should be quoted only as an unreferenced vendor claim. It is far below the 85.5% average in Haug et al., so it is at least not implausible relative to the configurator literature, but the two are not the same measurement.
- (Inference) The Alstom pilot described in the brief appears to be a role-play scenario from a Cognyx hiring case, and I found no public evidence of a real Cognyx deployment at Alstom. A use-case document should not present it as a customer reference or cite pilot results as real.
- (Inference) Cognyx's published use cases contain no explicit "find reused or duplicate sub-assemblies in legacy data" or "data reconciliation" feature. The nearest are "compare" BOMs by AI prompt, reuse of standard components at RFQ, and rules from lessons learned. The pilot question sits in a gap that the public feature list does not yet describe.
- (Inference) The founding-team lists differ between the 2023 landing page and the current site and CFNews. This may reflect studio founders versus operating founders; I did not resolve it.

### Gaps
- No Cognyx case study, named customer, customer quote or measured result was found anywhere.
- The "Supported by" logos on the home page are images and were not identifiable from the text.
- Careers page is a Notion embed (no text retrieved); the Trust Center URL I tried returned 404.
- Maddyness returned a page with no mention of Cognyx; Techleap returned 403.
- The basis for "up to 40%" and "10x" is not published.

---

## 9. Documented use in rail and comparable sectors

### Takeaway
Rail evidence is sparse and unquantified. Alstom is documented using a rules-based configurator for electrical design and standardising on Dassault's platform; a Siemens paper says trains on a shared platform are still built by "clone and own". Comparable-sector evidence with numbers comes from trucks (MAN), trailers (MAC Trailer), construction machinery (BOMAG) and industrial machinery (Starlinger, Ingersoll Rand), mostly through vendors.

### Cited Findings
- Alstom, electrical design (Zuken case study, undated): Alstom's Power and Transport electrical departments chose E3.series; with a configurator, a seven-carriage 120 km/h vehicle is specified by feeding "only the main parameters taken from the customer's requirements", after which rules compute "most of the follow-up parameters". Cable lengths are computed automatically through a CATIA V5 interface. Benefits unquantified `[vendor marketing | partial]` — [Zuken](https://www.zuken.com/en/resource/alstom/)
- Alstom, PLM: in 2021 Alstom chose Accenture and Dassault Systèmes for a cloud PLM platform on 3DEXPERIENCE, to "better integrate and standardize the company's engineering, manufacturing and maintenance processes", with rollout to all sites planned for 2022 `[vendor marketing | snippet: page downloaded but my text extraction returned nothing]` — [3DS press release](https://www.3ds.com/newsroom/press-releases/alstom-chooses-accenture-and-dassault-systemes-develop-new-cloud-platform-plm-increase-competitiveness-and-support-growth)
- Alstom, bids: 2026 job postings for bid technical managers are reported to describe checking tender requirements against Alstom's standard solutions and promoting those solutions `[snippet, unverified]` — [Alstom careers](https://jobsearch.alstom.com/job/Saint-Ouen-Senior-Bid-Technical-Manager-J/1291263901/)
- Alstom, earlier: an ENOVIA selection release is reported to cite the ability to "reuse standard parts easily" `[snippet; undated]` — [3DS press release](https://www.3ds.com/newsroom/press-releases/alstom-transport-selects-enovia-plm-solution)
- Siemens, rail (Zeller, Ratiu, Höfig, Siemens Corporate Technology, arXiv 2106.02273, 4 June 2021): "Modern trains are built using a modular platform concept." "Currently, a clone and own strategy is used in order to build a new trainset based on the existing platform. However, every new trainset developed based on the same platform requires an individual certification." `[preprint by industry authors | partial: abstract and the rail passage]` — [arXiv](https://arxiv.org/pdf/2106.02273)
- Trucks: MAN Truck & Bus with TU Munich, 14 rear-axle variants, 4,250 BOM rows, standardisation candidates identified; qualitative result (see section 1) `[peer-reviewed conference | partial]` — [Design Society](https://www.designsociety.org/publication/39548/Graph-based+similarity+analysis+of+BOM+data+to+identify+unnecessary+inner+product+variance)
- Electronics: 75 BOMs clustered correctly into known families (Romanowski and Nagi 2005, Section V); 405 nurse-call-device BOMs unified into generic BOMs (GBOM paper, Section 3.5) `[peer-reviewed and author manuscript | partial]` — [author PDF](https://www.eng.buffalo.edu/~nagi/papers/IEEESMCApaper.pdf), [author PDF](https://www.eng.buffalo.edu/~nagi/papers/ASMEpaper.pdf)
- Heavy and industrial machinery, vendor claims: Ingersoll Rand 2010, MAC Trailer 2020 to 2022, BOMAG, Starlinger 2011 to 2013 (see section 2) `[vendor marketing]` — [CADENAS deck](https://www.cadenas.de/files/iforum/PDF/presentations/2015/de/Industry-Forum_2015_Psol_PTC_Mueller_DE.pdf)
- Engineer-to-order laser systems: 150% BOM diagnostic prototype (Kourtis et al. 2026; see section 4) `[peer-reviewed conference | partial]` — [Cambridge](https://www.cambridge.org/core/product/355ED65C175FDCBF747B29F2A9B121DA/core-reader)
- Aerospace: only search-summary items (Airbus OntoREM, Airbus operational interruptions, a GE Aviation non-conformity ontology) `[snippet, unverified]` — [REF impact case study](https://impact.ref.ac.uk/casestudies/Results.aspx?Id=16104)

### Inferences
- (Inference) "Clone and own" at a major rolling-stock maker is the practice the pilot's premise describes: copies of a platform BOM diverge per contract. That is the condition in which cross-variant comparison finds both reuse and accidental divergence.
- (Inference) The certification point in the Siemens paper implies that in rail a "reusable" sub-assembly also has a qualification dimension. Free-text notes about homologation or qualification are therefore relevant inputs to a reusability judgement, beyond structural similarity.
- (Inference) Alstom already uses rule-based configuration in one discipline, so the configurator concept is familiar there; the open ground is cross-variant analysis of legacy BOM data.

### Gaps
- Nothing found for Stadler, CAF, Hitachi Rail or SNCF.
- No quantified reuse rate, engineering-hours saving or tender-time figure for any rolling-stock manufacturer.
- No shipbuilding source found.
- A Zuken blog on platform design and reuse in railway electrical design was downloaded but the article body was not extractable `[no access]` — [Zuken blog](https://www.zuken.com/us/blog/platform-design-design-reuse-strategy-for-electrical-system-design-within-the-railway-industry/)

---

## Source log and "not found" list

### Sources the brief asked to be read in full

| Source | Grade | Read status | Note |
|---|---|---|---|
| Tate et al., Comparing Bills of Materials, arXiv 2411.10384 | Preprint | Full | 8 pages |
| Romanowski and Nagi, On comparing bills of materials (SUTD link) | Peer-reviewed | No access at SUTD; partial via author manuscript | SUTD page is a JavaScript app. Manuscript: Sections I to III.C in full, the rest by targeted passages |
| Romanowski and Nagi, "Data mining in an engineering design environment" (Computers and OR 2006) | Peer-reviewed | Snippet only | Read the companion GBOM manuscript instead (partial) |
| PTC blog, Challenges Managing Duplicate Parts | Vendor marketing | Full | 8 June 2023 |
| ARC on Windchill AI Parts Rationalization | Trade press | Full | Direct fetch returned 403; read via a text proxy |
| CADENAS and PTC deck 2015 | Vendor marketing | Full | 19 slides, in English |
| 3DS Part Classification page | Vendor marketing | Full page | Webinar video not watched |
| OpenBOM on product knowledge graphs | Vendor marketing | Full | 22 November 2023 |
| en.cognyx.io/use-cases, /technology, /about, cognyx.io | Vendor marketing | Full | |
| cognyx.io/sbom | Vendor marketing | Full | Redirects to the technology page |

### Additional sources

| Source | Grade | Read status |
|---|---|---|
| PTC press release, 27 Jan 2026 | Vendor marketing | Full |
| PTC help: plugin introduction and known limitations | Vendor documentation | Full |
| Schmidt et al., ICED17 | Peer-reviewed conference | Partial |
| Kashkoush and ElMaraghy 2013 | Peer-reviewed conference | Abstract |
| Haug, Hvam, Mortensen 2011 | Peer-reviewed | Abstract |
| Kourtis et al. 2026 | Peer-reviewed conference | Partial |
| MaintIE (LREC-COLING 2024) | Peer-reviewed | Partial |
| MaintNorm (W-NUT 2024) | Peer-reviewed workshop | Partial |
| Brundage et al. 2020, technical language processing | Peer-reviewed | Abstract |
| Peeters, Steiner, Bizer, arXiv 2310.11244 | Preprint | Partial |
| French building specifications, arXiv 2508.13833 | Preprint | Abstract |
| Zeller et al. (Siemens), arXiv 2106.02273 | Preprint | Partial |
| CADENAS Starlinger, MAC Trailer, BOMAG | Vendor marketing | Partial |
| Siemens Geolus blog 2017, BCT case study | Vendor marketing | Partial |
| 3DPartFinder home page | Vendor marketing | Partial |
| Zuken Alstom case study | Vendor marketing | Partial |
| Cognyx 2023 landing page and blog post | Vendor marketing | Full and partial |
| CFNews on Cognyx | Trade press | Partial (paywall) |
| Signalbase on Cognyx | Funding aggregator | Partial |
| GitHub repository reproducing the Alstom x Cognyx case statement | Third-party repository | Partial |
| Everything tagged `[snippet]` above | Mixed | Search summary only; unverified |

### Not found

- Any Cognyx case study, named customer, customer testimonial or measured result.
- The basis, customer or date for Cognyx's "up to 40%" RFQ claim.
- Public evidence of a real Cognyx pilot at Alstom. The only public trace is a recruitment case that calls itself a fictional exercise.
- Named customers or dates behind Dassault's "27.5M€ to 50M€ per year" business cases.
- Any customer or savings figure for PTC Windchill AI Parts Rationalization.
- Any use case or figure for aPriori or Aras in part rationalisation.
- Any figures for Siemens Teamcenter classification or product configurator; the Aberdeen carrying-cost figure attributed to Siemens was not found in the page read.
- Any independent or peer-reviewed evaluation of a commercial part-rationalisation product.
- Precision or recall for entity resolution on part or supplier master data, with any tool (Splink, dedupe, Zingg, commercial MDM).
- Any BOM-similarity paper using graph kernels, frequent-pattern mining or embeddings.
- Any BOM-comparison paper reporting precision and recall against ground truth.
- Martijn Dullaart's original ASML product-knowledge-graph article.
- Quantified value from a product knowledge graph at ASML, Bosch, Siemens or Airbus.
- Verified precision and recall for LLM extraction from engineering change requests, non-conformance reports or lessons learned; the Shell management-of-change paper could not be located.
- Any corpus, benchmark or product claim for mixed French and English engineering text.
- Any documented use or figures for Stadler, CAF, Hitachi Rail or SNCF; any shipbuilding source.
- Quantified reuse rates or tender-time savings at any rolling-stock manufacturer.
- A study isolating the benefit of a 150% BOM from that of a configurator.
