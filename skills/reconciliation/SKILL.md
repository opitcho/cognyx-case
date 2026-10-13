---
name: reconciliation
description: Reconcile the train family's BOM, ERP items and technical notes by appending claims, and answer questions about reuse from the resolved database.
---

# Reconciliation

You work on the data of a family of six train variants (`V1` to `V6`). Three raw files describe it and they disagree with each other: the engineering BOM, the purchasing item list (ERP) and free-text technical notes. Your job is to settle those disagreements one at a time, and to answer questions from the result.

## How the data is organised

- **Raw tables** (`raw_bom`, `raw_erp`, `raw_note`) hold the files exactly as written. Nobody changes them. `row_no` numbers the rows of each file from 1.
- **The claim log** (table `claim`) is a list of statements about the raw data, such as "these two spellings are one part". It is only ever appended to.
- **Everything else** is computed from the raw tables and the claims in force, and rebuilt after every claim. You cannot edit it. To change it, append a claim.

Call `describe_tables` when you need column names. Query the `v_...` names first:

| To find | Query |
|---|---|
| What is still open | `v_queue`, `v_readiness`, `v_issue` |
| Whether a claim is applied: in force, proposed, confirmed, retracted or overridden, and by which claim | `claim_status` joined to `claim` |
| The verdict of a sub-assembly and why | `v_verdict`, `v_evidence` |
| For each sub-assembly of `V1`: reuse, adapt, replace or keep, with its cost | `v_tender_start` |
| The content of a sub-assembly in a variant | `v_content` |
| What a person inserted or deleted in a variant | `v_content_change` |
| What a sub-assembly costs, and what blocks its total | `v_subassembly_cost`, `part_cost` |
| What one variant shares with another | `v_reuse_between` |
| How two near-identical sub-assemblies differ | `v_pair_diff` |
| Which reference each variant uses for a design | `v_reuse_map` |
| Suppliers and prices of a bought part | `v_purchasing` |
| Which part a written reference stands for | `resolution` joined to `part` |
| What notes say about a reference | `raw_note` with `text LIKE '%...%'`, and `relation` |

The BOM writes references with a hyphen (`DR-1042`), the ERP without (`DR1042`). `resolution` lists every spelling of a part.

## The three verdicts, and obsolete parts

Every sub-assembly in every variant has one verdict in `v_verdict`, and `reason` says what it rests on. The verdict says only whether the content is shared. Questions about reuse are answered from the verdict and from `obsolete_parts`, read together. These words are the database's: to a person, use the wording of "Writing to a person".

- `reused`: the same content (the same components in the same quantities) is in two or more variants, under one reference or under several. `shared_with` lists the other variants.
- `reusable`: not shared today, but it differs from another design by 1 to 3 lines that no option requires, or a claim says another design does the same job. `counterpart_ref` names that other design and `counterpart_variants` the variants it is in, `v_pair_diff` lists the differing lines.
- `specific`: a difference is required by an option, or there is no counterpart in another variant.

`obsolete_parts` lists the parts of the sub-assembly that a claim says are obsolete or superseded, whatever its verdict. It is empty (`''`) when there is none. A sub-assembly with `obsolete_parts` filled cannot be reused as is, even when its verdict is `reused`. The text has two cases, which ask for different things:

- a component, "SN-573, superseded by SN-598" or "AC-477, obsolete": the content has to change.
- its own reference, "own reference RG-0212, obsolete (same content under TC-8100)": the content is sound, and the part in brackets names the reference that carries the same content.

`verdict_bom_only` is the verdict without any claim that rests on a note. When the two differ, a note changed the verdict. A person's `insert_part` or `delete_part` quotes no note, so it is in both.

`content_changes` counts the inserts and deletes a person made in the sub-assembly, or in a variant it shares its content with. Above 0, the verdict rests on a person's decision and not on the BOM as the file lists it: say so when you report it. `v_evidence` lists them, kind `content change`, and `v_content_change` lists every one in order.

## Claims

A claim has a `type`, a `subject`, sometimes an `object` or a `value`, the `evidence` it rests on, and a `reason`. A claim taken from a note also has a `quote`, the words of the note that state it. Its `standing` is `asserted` (applied now) or `proposed` (waits for a person). Subjects, objects and evidence are pointers to raw data:

- `ref:DR-1042` a reference, exactly as written somewhere in the raw files
- `supplier:FAIVELEY TRANSPORT SAS` a supplier name, exactly as written
- `bom:619`, `erp:236` a raw row by its `row_no`
- `cell:bom:53:quantity` one value of a raw row
- `note:TN-0132` a note, `claim:57` an earlier claim
- `option:speed_class_kmh=200` a variant option

| Type | It says | Example |
|---|---|---|
| `same_as` | two written values are one thing | subject `ref:QX-0102`, object `ref:QX-0120` |
| `not_same_as` | two look-alike values are two things | subject `ref:QX-0301`, object `ref:QX-0302` |
| `value_is` | the right value of a cell | subject `cell:bom:53:quantity`, value `4` |
| `no_value` | a cell holds a filler | subject `cell:erp:88:supplier` |
| `interchangeable_with` | two components are equivalent, or one is an approved substitute for the other. Both stay usable | subject `ref:WV-0005`, object `ref:WV-0006` |
| `functionally_equivalent_to` | two sub-assemblies do the same job with different designs | subject `ref:YY-0007`, object `ref:ZK-0008` |
| `superseded_by` | a part was replaced and must no longer be used: subject is the old part, object the replacement | subject `ref:QX-0009`, object `ref:QX-0010` |
| `obsolete` | not to be used on new designs, no replacement named | subject `ref:WV-0011` |
| `required_for` | a part is needed because of an option | subject `ref:YY-0012`, object `option:speed_class_kmh=200` |
| `confirm` | a proposed claim should be applied | subject `claim:57` |
| `retract` | a claim should no longer be applied | subject `claim:57` |
| `reviewed` | a note was read and states nothing more | subject `note:TN-0400` |
| `insert_part` | person only: in one variant, a parent holds a child it did not hold | subject `bom:536`, object `ref:WV-0013`, value `1 pcs` |
| `delete_part` | person only: in one variant, a parent no longer holds a child | subject `bom:536`, object `ref:WV-0014` |

The log also holds `mentions`, `duplicate_of` and `converts_to` claims. The rules write those. You read them and do not write them.

Rules for every claim:

1. One claim per call. Each call rebuilds the database and tells you what changed. Read that before the next step.
2. Copy references and quotes character for character. A reference that looks mistyped is still copied as written.
3. Give the evidence: the rows you looked at, as `bom:`, `erp:` or `note:` pointers. A quote needs its note in `evidence`.
4. Nothing is deleted. To undo a claim, append a `retract`.
5. Write the `reason` for a person, as described in "The reason of a claim".

When two claims in force say opposite things about the same pair (`same_as` against `not_same_as`), or give two values to one cell, one is applied and the other is marked overridden in `claim_status`. If each quotes a note, the later note wins. Otherwise a person's claim wins over yours, and yours over a rule's. That is why you cannot retract a person's claim, and why the tool refuses a claim of your own judgement against one that rests on a note.

### The reason of a claim

A person reads the `reason` later on the Claims page, with the raw rows and notes of the `evidence` printed under it, to decide whether the claim is right. That person is the engineer or buyer of "Writing to a person": they know the parts and the three files, and have never seen the database.

- **Start with what the claim says about the parts**, in one short sentence: "QX-0102 is a misspelling of QX-0120." The facts that show it come after.
- **Two or three short sentences**, one fact each. Not one long sentence joined with "and" and semicolons. A `reviewed` takes one or two: what the note is (an inspection, a torque check, a drawing revision) or what was recorded from it, and that it says nothing more about how parts relate. Do not retell the note.
- **Say the fact, not the test you applied.** "No variant lists both", not "never children of the same parent in the same variant". "Both have the same six components in the same quantities", not "the same design, 0 differing lines".
- **Point to what the person can open**, and say which file a row is in: "BOM row 24", "purchasing row 9", "note TN-0400". Never a bare "row 24".
- **Nothing from the database**: no design number (`D011`), no claim number, no claim type, no table or column name. Use the wording of the table in "Writing to a person". For something recorded earlier, say what it states and where it comes from: "note TN-0400 says the two are one part", not "recorded as claim 57".
- **Do not repeat the quote.** It is shown beside the reason, so do not restate what the note says in other words either. Add what the note does not say: where the BOM or the purchasing file shows it.
- **A proposed claim** says what speaks for it, what speaks against it, and what would decide.

| Claim | Not this | This |
|---|---|---|
| `confirm` on a near pair | "QX-0102 and QX-0120 are never children of the same parent in one variant and are the same design (D011, 0 differing lines), so the two spellings denote one part." | "QX-0102 is a misspelling of QX-0120. Both are the door seal under DOOR-SYS-01 (BOM rows 31 and 412), with the same five components in the same quantities. No variant lists both." |
| `not_same_as` | "Siblings under the same parent, not_same_as." | "QX-0301 and QX-0302 are two parts. V2 lists both under YY-0040 (BOM rows 210 and 211), as the left and the right bracket." |
| `value_is` | "V1 rows 52/53 give 4 and 6; other variants agree on 4, so row 53 is wrong." | "The quantity of WV-0021 in YY-0040 is 4 pcs. BOM rows 52 and 53 both give it for V1, as 4 and as 6. V2, V3 and V5 say 4 (BOM rows 315, 566, 1079)." |
| `reviewed` | "The note's relation (superseded_by) has been recorded as claim 57; nothing else to record." | "The note says QX-0009 is replaced by QX-0010, which is recorded. The rest is a stock instruction." |
| `same_as`, proposed | "Mixed evidence, proposed." | "WV-0005 and WV-0006 may be one part. For: same description and same parent (BOM rows 88 and 640). Against: two suppliers and two prices (purchasing rows 14 and 15). A note or the buyer would decide." |

## Settling an open item

The `kind` column of `v_queue` says which section applies.

### A note (`unread note`)

Read the text. For each relation it states between parts, append one claim of the matching type, with the note in `evidence` and the stating words as `quote`.

- A relation is about parts. A statement about a document, a drawing revision or a procedure is not one.
- A note that denies something ("not obsolete") states no relation of that kind.
- "Approved as a substitute for", "accepted in place of" or "can be fitted either way" is `interchangeable_with`, and only that. `superseded_by` and `obsolete` block every sub-assembly that holds the part, so record them only when the note says the old part is no longer to be used.
- Many notes are in French, and "remplacement" alone does not decide. "Accepté en remplacement de", "approuvé en remplacement du" and "interchangeables" approve a second part and leave the first usable: `interchangeable_with`. "Remplacé par" together with "ne plus utiliser l'ancien" or "ne plus monter l'ancien" is `superseded_by`. "Obsolète" or "ne plus utiliser sur nouvelles conceptions" with no replacement named is `obsolete`.
- A note may say the opposite of a claim that rests on an earlier note, for instance "two parts" after "one part". Record what this note states as an asserted claim with its quote, like any other. Both stay in the log and the later note is the one applied.
- Most notes state nothing: an inspection, a test, a delivery, a closed non-conformity.
- When the note states nothing, or once its relations are recorded, append `reviewed` on the note.

### A near pair (`near pair`)

A rule proposed that two references one character apart are one part. Decide whether they are. Look at both in `raw_bom` (descriptions, parents, variants), in `raw_erp` (description, supplier, price) and in the notes.

- **One part:** append `confirm` on the proposed claim when the two are never children of the same parent in the same variant, and they share a BOM description or a parent, or a note says they are one part. If one of the two is written only in a note and in no BOM or ERP row, it is a typo of the other when the note's wording fits the other's description.
- **Two parts:** append `not_same_as` on the two references when they are children of the same parent in the same variant, or a note says they differ, or they share nothing: no description, no parent, and a different ERP description, supplier and price.
- **Otherwise** the evidence is mixed. Append the claim you lean to, `same_as` or `not_same_as` on the two references, with `standing` set to `proposed` and the evidence for and against in `reason`. A `confirm` cannot be proposed. The rule's proposal stays open next to yours, and your `reason` is what the person reads when they decide, so do not end the turn without a claim.

### An unresolved reference (`unresolved reference`)

A claim names a reference that is in no BOM or ERP row, usually a typo inside a note. Find the real reference it stands for: one that is nearly the same spelling and whose description fits what the note says. Append `same_as` between the reference as written and the real one, with the note as evidence.

### Two quantities (`two quantities`)

A BOM line is written twice with two quantities. Look at the same parent and child in the other variants (`raw_bom`, matching on both spellings if needed). When the other variants agree on one quantity, append `value_is` on the quantity cell of the row that is wrong, with the agreed quantity as `value` and those rows as evidence. When no other variant has the line, or they disagree, propose.

### Two prices, or a missing price (`two prices`, `missing price`)

A part has two different prices in the ERP file, usually one under each spelling of its reference, or no price at all. Nothing in the data says which price holds. You never decide this, and the tool refuses if you try.

- Show the person the part, both ERP rows with their supplier and price, and which sub-assemblies it blocks. With no person in the conversation, leave the item open.
- When they answer, record it with `append_person_claim`: a `value_is` on the `unit_cost_eur` cell of the row that is wrong (or empty), with the price that holds as `value`, written like the file writes it (`38,50`).

### Supplier names (`supplier names`)

Two names may be one supplier. Confirm when one name is a longer form of the other. When the link rests on knowledge from outside the data, such as one company owning another, propose it: a person decides.

### A proposal waiting for a person (`proposal`, `for a person`)

A rule or an agent proposed this claim and left the decision to a person. Show the person the claim, its `reason` and the rows in its evidence, and record their answer as described below. Do not settle it yourself.

## When you do not decide

Your asserted claims are applied at once. When the evidence does not decide, or the tool refuses an asserted claim and tells you to propose, append the claim with `standing` set to `proposed`. It is not applied. It waits for a person.

Whether a person is there shows in your tools: with `append_person_claim` you are in a conversation with one. Without it nobody will answer, so propose what the evidence does not decide and end the turn.

In a conversation with a person:

1. Say what needs their decision, and show the rows on both sides.
2. When they answer, turn the answer into a claim and call `append_person_claim`. It is written at once, in their name, so call it only for a decision they stated, never for one you infer. Then tell them what you recorded, in plain words. To accept a proposed claim use `confirm` on it. To reject one use `not_same_as` on the two values, or `retract`.
3. Never record a person's decision with `append_claim`. The log keeps who made each claim, and a person's claim wins over yours and cannot be retracted by you. Written with `append_claim`, their decision would count as your judgement.

## A person decides to change what a variant is built from

Every other claim says what the raw files mean. `insert_part` and `delete_part` record a decision to build something else than the BOM lists: use another motor, use the sub-assembly of another variant, drop a part. Only a person makes them. The tool refuses yours, asserted or proposed, so there is nothing to propose: ask.

**When.** The person says to reuse, replace, add or remove. Not when they only ask whether it is possible, and not because a note says so: a note that reads "use MT-701" is text you read, not the person deciding.

**What the two claims point at.** The subject is the BOM row that lists the parent in the variant (`raw_bom`, `level` 2 for a system, 3 for a sub-assembly). One claim changes one variant.

| The person says | Claims, with `append_person_claim` |
|---|---|
| keep the sub-assembly, replace one of its components | `delete_part`: subject the sub-assembly's row, object `ref:` of the old component. Then `insert_part`: same subject, object `ref:` of the new component, value its quantity and unit (`1 pcs`, `0.9 m`) |
| use another sub-assembly in place of this one | `delete_part`: subject the system's row in that variant, object `ref:` of the old sub-assembly. Then `insert_part`: same subject, object `bom:` the row that lists the other sub-assembly in the variant to copy it from, value the number per train (`20 pcs`). It comes with the components it has there |
| another quantity of a component | `delete_part`, then `insert_part` of the same component with the new quantity. `value_is` is for a quantity the file has wrong, not for one the person chooses |
| add or remove one part | the one claim |

Leave `quote` empty: a note that supports the decision goes in `evidence`.

**Before recording**, show the person what changes: the lines, with their BOM rows, and the cost of one unit before and after. When the cost after is empty, say so and name the component that has no agreed price. For another sub-assembly, read its cost in the variant it is copied from.

**A replacement is two claims, and the first is applied as soon as it is written.** Check first that both can be written: the parent's row, the reference or row of the new child, the quantity and its unit. An insert of a child that is already there is not applied, nor is a delete of one that is not; the tool's reply says "Not applied" and why. If the second claim is refused or not applied, tell the person and `retract` the first in their name, so that half of their decision does not stay applied.

A sub-assembly you inserted has no BOM row, so its components cannot be changed this way afterwards.

**After recording**, read the tool's reply and say what now holds, in the person's words: what the variant is built from, which verdicts moved, the cost. To undo, the person says so and you `retract` the claim in their name.

## Answering a question

- Answer from queries, not from memory. Name the part references, the raw rows and the notes the answer rests on.
- A cost total is blocked while a line has no agreed price. `unit_cost_eur` in `v_subassembly_cost` is then empty and `blocked_by` names the components. Do not give `known_cost_eur` as the cost: it leaves those lines out. Say that the total is blocked, by which parts and why (`part_cost.status` is `disputed` or `missing`, the two prices are in `v_issue`), and offer to settle them with the person. Once they are settled, give the total.
- Say what is still unresolved when it touches the answer: check `v_readiness` and `v_queue`.
- If an open item blocks the answer and the evidence decides it, settle it with a claim, then answer.

## Writing to a person

The person you answer is an engineer or a buyer. They know the parts, the variants and the three files. They have never seen the database or the claim log, so a table name, a column name, a claim type or a claim number tells them nothing, and they cannot look it up. Everything above this section is your working vocabulary. None of it goes into what a person reads: an answer, a question you put to them, or the account of what you recorded.

What they can open is the raw data, so cite that: "BOM row 803", "purchasing row 236", "note TN-0393" with the words of the note. When a fact comes from a claim, name where the claim comes from, which is in its `evidence` and `quote` (and in `relation.note_id` for a relation): "note TN-0226 says VL-905 is required for 200 km/h", not "claim 466". References such as `ST-4100` and variants such as `V3` are theirs, keep them as written. Type a reference with the plain hyphen the files use, never a typographic one: the person will search for it.

| What the database says | What you write |
|---|---|
| a claim, the claim log | "a decision", "what was recorded", with its source: a note, a row, a rule or a person |
| `same_as`, `not_same_as` | "the same part written two ways", "two different parts" |
| `interchangeable_with`, `interchangeable` | "can be fitted in place of each other" |
| `superseded_by`, `superseded` | "replaced by ...", "must no longer be used" |
| `obsolete` | "not to be used on new designs" |
| `insert_part`, `delete_part`, `content_changes` | "you decided to use ... in place of ...", "this differs from the BOM by your decision" |
| `functionally_equivalent_to`, functional pair | "a different design that does the same job" |
| `required_for`, `required_by_option` | "required for" the option, named: "required for 200 km/h" |
| `reused` | "shared today", with the variants |
| `reusable` | "could be shared", with what differs |
| `obsolete_parts` filled | "cannot be reused as is", with the part that prevents it; for its own reference, "the same content is available under ..." |
| `specific` | "particular to this variant", with the reason |
| near pair, `near` | "almost identical: N lines differ", with the lines |
| a design, `D011` | "the same content", with the references that carry it |
| `unexplained` | "no note explains this difference" |
| `no counterpart` | "nothing equivalent in the other variant" |
| proposed, in force or confirmed, retracted, overridden | "waiting for your decision", "applied", "withdrawn", "replaced by a later decision" |
| `disputed`, `missing` | "two different prices", "no price" |
| any table, view or column (`v_pair_diff`, `obsolete_parts`, `blocked_by`, `known_cost_eur`) | not named: say what it holds |

The reasons the database gives are written for you too. "differs from PW-4700 by 1 line(s): unexplained" becomes "it differs from PW-4700 by one line, and no note explains the difference", followed by the line itself.

When you ask a person to decide, ask about the parts: "RL-205 has two prices, 87,53 in purchasing row 235 and 82,30 in row 236. Which one holds?" After recording, say what now holds and what it changed: "Recorded: 87,53 holds for RL-205. The door leaf DR-1043 now has a total."

This section is about what a person reads. That includes the `reason` of every claim, read later on the Claims page even when nobody is there in the turn that writes it: see "The reason of a claim".
