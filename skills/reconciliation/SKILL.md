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

Call `describe_tables` when you need column names. Query the views (`v_...`) first:

| To find | Query |
|---|---|
| What is still open | `v_queue`, `v_readiness`, `v_issue` |
| Whether a claim is applied: in force, proposed, confirmed, retracted or overridden, and by which claim | `claim_status` joined to `claim` |
| What one claim touches | `v_claim_effect` |
| The verdict of a sub-assembly and why | `v_verdict`, `v_evidence` |
| For each sub-assembly of `V1`: reuse, adapt, replace or keep, with its cost | `v_tender_start` |
| The content of a sub-assembly in a variant | `v_content` |
| What a sub-assembly costs, and what blocks its total | `v_subassembly_cost`, `part_cost` |
| What one variant shares with another | `v_reuse_between` |
| How two near-identical sub-assemblies differ | `v_pair_diff` |
| Which reference each variant uses for a design | `v_reuse_map` |
| Suppliers and prices of a bought part | `v_purchasing` |
| Which part a written reference stands for | `resolution` joined to `part` |
| What notes say about a reference | `raw_note` with `text LIKE '%...%'`, and `relation` |

The BOM writes references with a hyphen (`DR-1042`), the ERP without (`DR1042`). `resolution` lists every spelling of a part.

## The four verdicts

Every sub-assembly in every variant has one verdict in `v_verdict`, and `reason` says what it rests on. Questions about reuse are answered from them. These four words are the database's: to a person, use the wording of "Writing to a person".

- `reused`: the same content (the same components in the same quantities) is in two or more variants, under one reference or under several.
- `reusable`: not shared today, but it differs from another design by 1 to 3 lines that no option requires, or a claim says another design does the same job. `counterpart_ref` names that other design, `v_pair_diff` lists the differing lines.
- `blocked`: it would be reused or reusable, but it holds a part that a claim says is obsolete or superseded. The reason names the part.
- `specific`: a difference is required by an option, or there is no counterpart in another variant.

`verdict_bom_only` is the verdict the BOM alone gives, before any claim that rests on a note. When the two differ, a note changed the verdict.

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

The log also holds `mentions`, `duplicate_of` and `converts_to` claims. The rules write those. You read them and do not write them.

Rules for every claim:

1. One claim per call. Each call rebuilds the database and tells you what changed. Read that before the next step.
2. Copy references and quotes character for character. A reference that looks mistyped is still copied as written.
3. Give the evidence: the rows you looked at, as `bom:`, `erp:` or `note:` pointers. A quote needs its note in `evidence`.
4. Nothing is deleted. To undo a claim, append a `retract`.

When two claims in force say opposite things about the same pair (`same_as` against `not_same_as`), or give two values to one cell, one is applied and the other is marked overridden in `claim_status`. If each quotes a note, the later note wins. Otherwise a person's claim wins over yours, and yours over a rule's. That is why you cannot retract a person's claim, and why the tool refuses a claim of your own judgement against one that rests on a note.

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
| `functionally_equivalent_to`, functional pair | "a different design that does the same job" |
| `required_for`, `required_by_option` | "required for" the option, named: "required for 200 km/h" |
| `reused` | "shared today", with the variants |
| `reusable` | "could be shared", with what differs |
| `blocked` | "cannot be reused as is", with the part that prevents it |
| `specific` | "particular to this variant", with the reason |
| near pair, `near` | "almost identical: N lines differ", with the lines |
| a design, `D011` | "the same content", with the references that carry it |
| `unexplained` | "no note explains this difference" |
| `no counterpart` | "nothing equivalent in the other variant" |
| proposed, in force or confirmed, retracted, overridden | "waiting for your decision", "applied", "withdrawn", "replaced by a later decision" |
| `disputed`, `missing` | "two different prices", "no price" |
| any table, view or column (`v_pair_diff`, `blocked_by`, `known_cost_eur`) | not named: say what it holds |

The reasons the database gives are written for you too. "differs from PW-4700 by 1 line(s): unexplained" becomes "it differs from PW-4700 by one line, and no note explains the difference", followed by the line itself.

When you ask a person to decide, ask about the parts: "RL-205 has two prices, 87,53 in purchasing row 235 and 82,30 in row 236. Which one holds?" After recording, say what now holds and what it changed: "Recorded: 87,53 holds for RL-205. The door leaf DR-1043 now has a total."

This section is about what a person reads. In a turn that settles an open item with nobody there, the claim's `reason` is read later by a person on the Claims page: write it in plain words too, with the references and the rows.
