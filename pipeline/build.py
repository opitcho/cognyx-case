"""build(): replays the claims in force over the raw files and writes the resolved model to a SQLite file.

Nothing here is kept between runs. Every build starts from the raw files and the claim log, so the database can
be deleted at any time, and a claim appended to the log changes the model at the next build. No model is involved.

The five steps:
1. load the raw files, every value as text
2. load the claim log and work out which claims are in force
3. group the written values: spellings linked by same_as become one part (or one supplier)
4. rewrite the BOM and the prices through those groups, with units converted and repeated rows left out
5. compare sub-assemblies by content and give each design a verdict

Run: uv run python -m pipeline.build
"""

import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.claims import FIELDS, RANK, RELATIONS, load, select, split, statuses
from pipeline.compare import Design, Occurrence, Pair, Relations, build_designs, find_pairs
from pipeline.ingest import BOM_FILE, ERP_FILE, NOTE_FILE, Raw, ingest, read_raw
from pipeline.rules import BASE_UNITS
from pipeline.verdict import Verdict, decide

KINDS = {2: "system", 3: "sub-assembly", 4: "component"}
VIEWS = Path(__file__).with_name("views.sql")


@dataclass
class Model:
    """The resolved model in memory, before it is written."""

    raw: Raw
    claims: list[dict]                       # the claims this replay looks at
    status: dict                             # claim id -> Status
    part_of: dict[str, str] = field(default_factory=dict)       # written reference -> part id
    parts: dict[str, dict] = field(default_factory=dict)
    supplier_of: dict[str, str] = field(default_factory=dict)   # written supplier name -> supplier id
    suppliers: dict[str, dict] = field(default_factory=dict)
    variants: dict[str, dict] = field(default_factory=dict)
    units: dict[str, tuple[str, Decimal]] = field(default_factory=dict)
    lines: list[dict] = field(default_factory=list)
    prices: list[dict] = field(default_factory=list)
    cost: dict[str, Decimal | None] = field(default_factory=dict)  # part id -> unit cost, None if unknown or disputed
    cost_status: dict[str, str] = field(default_factory=dict)      # part id -> agreed, disputed or missing
    relations: list[dict] = field(default_factory=list)
    occurrences: list[Occurrence] = field(default_factory=list)
    designs: list[Design] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    verdicts: dict[str, Verdict] = field(default_factory=dict)   # design id -> verdict
    issues: list[dict] = field(default_factory=list)

    def name(self, part_id: str | None) -> str:
        return self.parts[part_id]["canonical_ref"] if part_id in self.parts else ""

    def issue(self, type: str, detail: str, source_file: str = "", rows=()) -> None:
        self.issues.append({"type": type, "detail": detail, "source_file": source_file,
                            "source_rows": ", ".join(str(r) for r in rows)})

    @property
    def force(self) -> list[dict]:
        return [c for c in self.claims if self.status[c["id"]].in_force]


def group(values: set[str], links: list[tuple[str, str, dict]], vetoes: set[frozenset[str]]):
    """Put linked values in one group, strongest link first, never joining a vetoed pair.

    Returns each value's group (named by one of its members) and the links that were skipped because they would
    have put a vetoed pair in one group.
    """
    root = {value: value for value in values}
    members = {value: {value} for value in values}

    def find(value):
        while root[value] != value:
            value = root[value]
        return value

    skipped = []
    for a, b, claim in links:
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        if any(len(veto & members[ra]) == 1 and len(veto & members[rb]) == 1 for veto in vetoes):
            skipped.append(claim)
            continue
        root[rb] = ra
        members[ra] |= members.pop(rb)
    return {value: find(value) for value in values}, skipped


def number(text: str | None) -> Decimal | None:
    """A written number, with a decimal point or a decimal comma. None if it is not one."""
    if text is None or not text.strip():
        return None
    try:
        return Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        return None


def compute(raw: Raw, all_claims: list[dict], without_notes: bool = False, made_by: set[str] | None = None,
            up_to: int | None = None) -> Model:
    """Steps 2 to 5, in memory."""
    chosen = select(all_claims, without_notes, made_by, up_to)
    m = Model(raw, chosen, statuses(chosen))
    force = m.force
    by_type = defaultdict(list)
    for claim in force:
        by_type[claim["type"]].append(claim)

    def linked(kind: str):
        """The same_as links of one kind, strongest first, and the not_same_as pairs of that kind."""
        links = [(split(c["subject"])[1], split(c["object"])[1], c)
                 for c in sorted(by_type["same_as"], key=lambda c: (-RANK[c["made_by"]], c["id"]))
                 if split(c["subject"])[0] == kind]
        vetoes = {frozenset((split(c["subject"])[1], split(c["object"])[1]))
                  for c in by_type["not_same_as"] if split(c["subject"])[0] == kind}
        return links, vetoes

    # --- Step 3: parts. Every reference written in a reference column or named in a claim stands for a part.
    written = raw.written_refs()
    universe = set(written["bom"]) | set(written["erp"]) | {n["reference"] for n in raw.notes if n["reference"]}
    for claim in chosen:
        for target in (claim["subject"], claim["object"]):
            if split(target)[0] == "ref":
                universe.add(split(target)[1])
    links, vetoes = linked("ref")
    roots, skipped = group(universe, links, vetoes)
    for claim in skipped:
        m.issue("merge_skipped", f"claim {claim['id']} ({claim['subject']} same as {claim['object']}) was not applied: "
                                 "it would join two references that a not_same_as claim keeps apart")
    bom_uses, levels, bom_text, erp_text = Counter(), defaultdict(list), defaultdict(Counter), defaultdict(Counter)
    for row in raw.bom:
        bom_uses[row["child_ref"]] += 1
        levels[row["child_ref"]].append(int(row["level"]))
        bom_text[row["child_ref"]][row["description"]] += 1
        if row["level"] != "2":
            bom_uses[row["parent_ref"]] += 1
    for row in raw.erp:
        erp_text[row["item_ref"]][row["description"]] += 1
    spellings = defaultdict(set)
    for ref, root in roots.items():
        spellings[root].add(ref)
    canonical = {root: min(refs, key=lambda r: (-bom_uses[r], r not in written["erp"], r)) for root, refs in spellings.items()}
    for number_, root in enumerate(sorted(spellings, key=lambda r: canonical[r]), 1):
        refs = spellings[root]
        part_id = f"P{number_:04d}"
        seen_levels = [level for ref in refs for level in levels[ref]]
        in_erp = any(ref in written["erp"] for ref in refs)
        texts = sum((bom_text[ref] for ref in refs), Counter()) or sum((erp_text[ref] for ref in refs), Counter())
        m.parts[part_id] = {
            "kind": KINDS[min(seen_levels)] if seen_levels else ("component" if in_erp else "unknown"),
            "canonical_ref": canonical[root],
            "description": texts.most_common(1)[0][0] if texts else "",
            "known": bool(seen_levels) or in_erp,  # False: named only in notes or claims, in no BOM or ERP row
            "spellings": sorted(refs),
        }
        for ref in refs:
            m.part_of[ref] = part_id

    # --- Cells: a value_is claim replaces a written value, a no_value claim empties it.
    overrides = {tuple(split(c["subject"])[1].split(":", 2)): c["value"] for c in by_type["value_is"]}
    emptied = {tuple(split(c["subject"])[1].split(":", 2)) for c in by_type["no_value"]}

    def cell(file: str, row: dict, column: str) -> str | None:
        key = (file, str(row["row_no"]), column)
        if key in overrides:  # a value someone supplied also fills a cell a rule marked as holding no value
            return overrides[key]
        return None if key in emptied else row[column]

    # --- Suppliers: the same grouping, on the names written in the ERP file.
    names = Counter(cell("erp", row, "supplier") for row in raw.erp)
    names = Counter({name: n for name, n in names.items() if name and name.strip()})
    links, vetoes = linked("supplier")
    roots, skipped = group(set(names), [(a, b, c) for a, b, c in links if a in names and b in names], vetoes)
    for claim in skipped:
        m.issue("merge_skipped", f"claim {claim['id']} ({claim['subject']} same as {claim['object']}) was not applied")
    grouped = defaultdict(list)
    for name, root in roots.items():
        grouped[root].append(name)
    for number_, names_ in enumerate(sorted(grouped.values(), key=lambda g: max(g, key=lambda n: (names[n], n))), 1):
        supplier_id = f"S{number_:02d}"
        m.suppliers[supplier_id] = {"name": max(names_, key=lambda n: (names[n], n)), "spellings": sorted(names_)}
        for name in names_:
            m.supplier_of[name] = supplier_id

    # --- Variants, from the four columns every BOM row repeats.
    for row in raw.bom:
        attributes = {"cars": row["cars"], "speed_class_kmh": row["speed_class_kmh"], "interior": row["interior"]}
        if m.variants.setdefault(row["variant_id"], attributes) != attributes:
            m.issue("variant_attributes", f"{row['variant_id']} is described two ways", BOM_FILE, [row["row_no"]])

    # --- Units.
    m.units = {unit: (unit, Decimal(1)) for unit in BASE_UNITS}
    for claim in by_type["converts_to"]:
        m.units[split(claim["subject"])[1]] = (split(claim["object"])[1], Decimal(claim["value"]))

    def to_base(quantity: Decimal | None, unit: str | None) -> tuple[Decimal, str] | None:
        """A quantity in its base unit. None when the number is missing or the unit has no converts_to claim."""
        for _ in range(5):  # follows mm -> m; a chain longer than this is a mistake in the claims
            if quantity is None or unit not in m.units:
                return None
            base, factor = m.units[unit]
            quantity = quantity * factor
            if base == unit or base in BASE_UNITS:
                return round(quantity, 6).normalize(), base
            unit = base
        return None

    # --- Step 4: the BOM. Rows of one parent-child link in one variant are folded into one line.
    repeats = {int(split(c["subject"])[1]) for c in by_type["duplicate_of"]}
    folded: dict[tuple, dict] = {}
    for row in raw.bom:
        level = int(row["level"])
        parent = m.part_of[row["parent_ref"]] if level > 2 else None
        line = folded.setdefault((row["variant_id"], level, parent, m.part_of[row["child_ref"]]),
                                 {"rows": [], "values": [], "unknown": []})
        line["rows"].append(row["row_no"])
        if row["row_no"] in repeats:
            continue
        unit = cell("bom", row, "unit")
        value = to_base(number(cell("bom", row, "quantity")), unit)
        (line["values"] if value else line["unknown"]).append((row["row_no"], value or (cell("bom", row, "quantity"), unit)))
    for (variant, level, parent, child), line in folded.items():
        where = f"{variant} {m.name(parent) or variant} / {m.name(child)}"
        distinct = {value for _, value in line["values"]}
        quantity = unit = None
        if line["unknown"]:
            written_as = ", ".join(f"{q} {u} (row {r})" for r, (q, u) in line["unknown"])
            m.issue("unknown_unit", f"{where}: {written_as} cannot be converted to a base unit", BOM_FILE,
                    [r for r, _ in line["unknown"]])
        elif len(distinct) == 1:
            quantity, unit = next(iter(distinct))
        elif len(distinct) > 1:
            written_as = ", ".join(f"{q:f} {u} (row {r})" for r, (q, u) in line["values"])
            m.issue("two_quantities", f"{where}: written as {written_as}", BOM_FILE, [r for r, _ in line["values"]])
        m.lines.append({"variant": variant, "level": level, "parent": parent, "child": child, "quantity": quantity,
                        "unit": unit, "rows": line["rows"]})

    # --- Prices: one per ERP row, per base unit. A part's cost is known only when its rows agree.
    by_part = defaultdict(list)
    for row in raw.erp:
        part_id = m.part_of[row["item_ref"]]
        supplier = cell("erp", row, "supplier")
        amount = number(cell("erp", row, "unit_cost_eur"))
        per_unit = to_base(Decimal(1), cell("erp", row, "price_unit"))  # how many base units the price covers
        cost = None
        if amount is not None and per_unit is not None:
            cost = round(amount / per_unit[0], 6).normalize()
        elif amount is not None:
            m.issue("unknown_unit", f"{row['item_ref']}: price unit {row['price_unit']!r} cannot be converted",
                    ERP_FILE, [row["row_no"]])
        m.prices.append({"part": part_id, "supplier": m.supplier_of.get(supplier) if supplier else None,
                         "supplier_written": supplier or "", "cost": cost, "row": row["row_no"]})
        by_part[part_id].append((row["row_no"], cost))
    used = {line["child"] for line in m.lines if line["level"] == 4}
    for part_id in sorted(set(by_part) | used):
        costs = {round(cost, 4) for _, cost in by_part.get(part_id, []) if cost is not None}
        m.cost[part_id] = next(iter(costs)) if len(costs) == 1 else None
        m.cost_status[part_id] = "agreed" if len(costs) == 1 else "disputed" if costs else "missing"
        rows = [row for row, _ in by_part.get(part_id, [])]
        if len(costs) > 1:
            written_as = ", ".join(f"{cost:f} EUR (row {row})" for row, cost in by_part[part_id] if cost is not None)
            m.issue("two_prices", f"{m.name(part_id)}: {written_as}", ERP_FILE, rows)
        elif not costs and part_id in used:
            m.issue("missing_price", f"{m.name(part_id)} is used in the BOM and has no price", ERP_FILE, rows)

    # --- Relations between parts, from the five relation types.
    for claim in force:
        if claim["type"] not in RELATIONS:
            continue
        object_kind, object_rest = split(claim["object"])
        ref_a, ref_b = split(claim["subject"])[1], object_rest if object_kind == "ref" else ""
        note_id = next((split(item)[1] for item in claim["evidence"] if split(item)[0] == "note"), "")
        m.relations.append({"claim_id": claim["id"], "type": claim["type"], "part_a": m.part_of.get(ref_a),
                            "part_b": m.part_of.get(ref_b) if ref_b else None, "ref_a": ref_a, "ref_b": ref_b,
                            "option": object_rest if object_kind == "option" else "", "as_of": claim["as_of"],
                            "note_id": note_id, "quote": claim["quote"]})
        for ref in (ref_a, ref_b):
            if ref and not m.parts[m.part_of[ref]]["known"]:
                m.issue("unresolved_reference", f"{ref} in claim {claim['id']} ({claim['type']}) is in no BOM or ERP "
                        "row: it may be a mistyped reference", NOTE_FILE if note_id else "", [note_id] if note_id else [])
    relations = Relations(m.relations)
    for part_id, (claim_id, _) in sorted(relations._dead.items()):
        if part_id in used:
            m.issue("note_contradicts_bom", f"{m.name(part_id)} is obsolete or superseded (claim {claim_id}) and is "
                    "still in the BOM", BOM_FILE)

    # --- Step 5: designs, pairs, verdicts.
    content: dict[tuple[str, str], dict] = defaultdict(dict)
    for line in m.lines:
        if line["level"] == 3:
            m.occurrences.append(Occurrence(line["variant"], line["child"], line["parent"], line["quantity"], line["rows"]))
        elif line["level"] == 4:
            content[(line["variant"], line["parent"])][line["child"]] = line["quantity"]
    known = {(o.variant, o.part) for o in m.occurrences}
    for (variant, parent), lines in content.items():
        if (variant, parent) not in known:
            m.issue("orphan_lines", f"{variant}: {len(lines)} lines under {m.name(parent)}, which is not listed as a "
                    "sub-assembly of that variant", BOM_FILE)
    m.designs = build_designs(m.occurrences, content)
    m.pairs = find_pairs(m.designs, relations, m.cost, m.variants)
    for design in m.designs:
        mine = [pair for pair in m.pairs if design is pair.a or design is pair.b]
        m.verdicts[design.id] = decide(design, mine, relations, m.name)
    # The verdict of a design holds for each sub-assembly that carries it, with one exception: a sub-assembly
    # whose own reference is obsolete or superseded is blocked, even when its content is shared and sound.
    for occurrence in m.occurrences:
        verdict = m.verdicts[occurrence.design.id]
        dead = relations.dead(occurrence.part)
        if dead and verdict.verdict in ("reused", "reusable"):
            claim_id, new = dead
            others = [m.name(p) for p in occurrence.design.parts if p != occurrence.part]
            why = (f"the reference {m.name(occurrence.part)} is " + (f"superseded by {m.name(new)}" if new else "obsolete")
                   + (f"; the same content is carried by {', '.join(others)}" if others else ""))
            verdict = Verdict("blocked", f"{why} (otherwise {verdict.verdict}: {verdict.reason})", verdict.counterpart,
                              [claim_id, *verdict.claim_ids], verdict.pair)
        occurrence.verdict = verdict
    return m


# ---------------------------------------------------------------- derived tables


def queue(m: Model) -> list[dict]:
    """The open items: what is proposed and not settled, notes nobody read, and issues a claim could settle."""
    items = []
    apart = defaultdict(set)  # entity -> entities a not_same_as claim keeps it apart from
    for claim in m.force:
        if claim["type"] == "not_same_as":
            kind = split(claim["subject"])[0]
            lookup = m.part_of if kind == "ref" else m.supplier_of
            a, b = lookup.get(split(claim["subject"])[1]), lookup.get(split(claim["object"])[1])
            apart[a].add(b)
            apart[b].add(a)
    for claim in m.claims:
        if str(m.status[claim["id"]]) != "proposed":
            continue
        subject, target = split(claim["subject"])[1], split(claim["object"])[1]
        about = f"{subject} / {target}" if claim["object"] else subject
        if claim["type"] == "same_as":
            kind = split(claim["subject"])[0]
            lookup = m.part_of if kind == "ref" else m.supplier_of
            a, b = lookup.get(subject), lookup.get(target)
            if a == b or b in apart[a]:
                continue  # settled since: the two are now one, or a claim keeps them apart
            label = "near pair" if kind == "ref" else "supplier names"
        else:
            label = "proposal"
        if claim["made_by"] == "agent":
            label = "for a person"
        items.append({"kind": label, "detail": f"{claim['type']}: {about} ({claim['reason']})", "claim_id": claim["id"],
                      "source_rows": ", ".join(claim["evidence"])})
    read = {split(c["subject"])[1] for c in m.force if c["type"] == "reviewed"}
    read |= {split(item)[1] for c in m.force if c["made_by"] != "rule" for item in c["evidence"] if split(item)[0] == "note"}
    for note in sorted(m.raw.notes, key=lambda n: (n["date"], n["note_id"])):
        if note["note_id"] not in read:
            items.append({"kind": "unread note", "detail": f"{note['note_id']} ({note['date']})", "claim_id": None,
                          "source_rows": f"note:{note['note_id']}"})
    for issue in m.issues:
        # Which of two prices holds, or what a missing price is, is not in the data: those wait for a person.
        if issue["type"] in ("two_quantities", "unresolved_reference", "two_prices", "missing_price"):
            rows = issue["source_rows"]
            if issue["type"] in ("two_prices", "missing_price"):
                rows = ", ".join(f"erp:{row}" for row in rows.split(", ") if row)
            items.append({"kind": issue["type"].replace("_", " "), "detail": issue["detail"], "claim_id": None,
                          "source_rows": rows})
    return items


def readiness(m: Model, open_items: list[dict]) -> list[dict]:
    """Counts that say how much of the data can be relied on, each with its total."""
    components = {line["child"] for line in m.lines if line["level"] == 4}
    content_lines = [line for line in m.lines if line["level"] >= 3]
    proposed = [c for c in m.claims if c["standing"] == "proposed" and m.status[c["id"]].state != "retracted"]
    still_open = {item["claim_id"] for item in open_items if item["claim_id"]}
    unread = sum(1 for item in open_items if item["kind"] == "unread note")
    rows = [
        ("written references standing for a part of the BOM or ERP", sum(1 for ref in m.part_of if m.parts[m.part_of[ref]]["known"]), len(m.part_of)),
        ("BOM components with one agreed price", sum(1 for p in components if m.cost.get(p) is not None), len(components)),
        ("BOM lines with an agreed quantity in a base unit", sum(1 for line in content_lines if line["quantity"] is not None), len(content_lines)),
        ("sub-assembly designs that can be compared", sum(1 for d in m.designs if d.comparable), len(m.designs)),
        ("notes read", len(m.raw.notes) - unread, len(m.raw.notes)),
        ("proposals settled", sum(1 for c in proposed if c["id"] not in still_open), len(proposed)),
        ("relations whose parts are all in the BOM or ERP", sum(1 for r in m.relations if all(
            m.parts[p]["known"] for p in (r["part_a"], r["part_b"]) if p)), len(m.relations)),
    ]
    return [{"what": what, "n": n, "of": of} for what, n, of in rows]


def reuse_between(m: Model) -> list[dict]:
    """Every sub-assembly of every variant, seen from each other variant: is the same thing there?"""
    relations = Relations(m.relations)
    in_variant = defaultdict(list)
    for occurrence in m.occurrences:
        in_variant[occurrence.variant].append(occurrence)
    rows = []
    for source in sorted(in_variant):
        for target in sorted(in_variant):
            if target == source:
                continue
            there = {o.design.id: o for o in in_variant[target]}
            for occurrence in sorted(in_variant[source], key=lambda o: m.name(o.part)):
                design = occurrence.design
                dead = [p for p in (occurrence.part, *sorted(design.lines)) if relations.dead(p)]
                row = {"variant_from": source, "variant_to": target, "subassembly_ref": m.name(occurrence.part),
                       "status": "no counterpart", "counterpart_ref": "", "differing_lines": None, "cost_gap_eur": None,
                       "blocked_by": ", ".join(m.name(p) for p in dead)}
                if design.id in there:
                    other = there[design.id]
                    same = other.part == occurrence.part
                    row.update(status="same reference" if same else "same content under another reference",
                               counterpart_ref=m.name(other.part), differing_lines=0)
                else:
                    pairs = [p for p in m.pairs if (design is p.a or design is p.b) and p.other(design).id in there]
                    pairs.sort(key=lambda p: (p.kind != "near", p.n_differing))
                    if pairs:
                        pair = pairs[0]
                        gap = pair.cost_gap
                        if gap is not None and pair.b is design:
                            gap = -gap  # the gap is counted from this sub-assembly to its counterpart
                        row.update(status="near" if pair.kind == "near" else "functionally equivalent",
                                   counterpart_ref=m.name(there[pair.other(design).id].part),
                                   differing_lines=pair.n_differing, cost_gap_eur=None if gap is None else float(gap))
                rows.append(row)
    return rows


def evidence(m: Model) -> list[dict]:
    """The facts behind each design's verdict: where it occurs, the pair it was compared with, the claims used."""
    claims = {c["id"]: c for c in m.claims}
    rows = []
    for design in m.designs:
        verdict = m.verdicts[design.id]
        for occurrence in design.occurrences:
            for claim_id in occurrence.verdict.claim_ids:
                if claim_id not in verdict.claim_ids:  # the claim that blocks this reference alone
                    claim = claims[claim_id]
                    rows.append({"design_id": design.id, "kind": "claim",
                                 "detail": f"{claim['type']}({split(claim['subject'])[1]}): {claim['quote']}",
                                 "claim_id": claim_id, "source_file": NOTE_FILE, "source_row": ""})
            rows.append({"design_id": design.id, "kind": "bom row",
                         "detail": f"{occurrence.variant}: {m.name(occurrence.part)}, {len(design.lines)} lines",
                         "claim_id": None, "source_file": BOM_FILE, "source_row": str(min(occurrence.raw_rows))})
        if verdict.pair:
            pair = verdict.pair
            rows.append({"design_id": design.id, "kind": "pair",
                         "detail": f"{pair.kind} pair with {', '.join(m.name(p) for p in pair.other(design).parts)}: "
                                   f"{pair.n_differing} differing lines, {pair.n_shared} shared",
                         "claim_id": None, "source_file": "", "source_row": ""})
        for claim_id in dict.fromkeys(verdict.claim_ids):
            claim = claims[claim_id]
            about = split(claim["subject"])[1] + (f", {split(claim['object'])[1]}" if claim["object"] else "")
            note_id = next((split(item)[1] for item in claim["evidence"] if split(item)[0] == "note"), "")
            rows.append({"design_id": design.id, "kind": "claim",
                         "detail": f"{claim['type']}({about})" + (f": {claim['quote']}" if claim["quote"] else ""),
                         "claim_id": claim_id, "source_file": NOTE_FILE if note_id else "", "source_row": note_id})
    return rows


def claim_effect(m: Model) -> list[dict]:
    """For each claim in force, a rough measure of what it touches."""
    lines_of = Counter()
    for line in m.lines:
        lines_of[line["child"]] += 1
        if line["parent"]:
            lines_of[line["parent"]] += 1
    in_verdicts = Counter()
    for design in m.designs:
        for claim_id in set(m.verdicts[design.id].claim_ids):
            in_verdicts[claim_id] += len(design.occurrences)
    rows = []
    for claim in m.force:
        kind, rest = split(claim["subject"])
        part = m.part_of.get(rest) if kind == "ref" else None
        merged = len(m.parts[part]["spellings"]) if part and claim["type"] == "same_as" else 0
        touched = lines_of[part] if part else (1 if kind in ("bom", "cell") else 0)
        rows.append({"claim_id": claim["id"], "type": claim["type"], "made_by": claim["made_by"],
                     "spellings_merged": merged, "lines_affected": touched, "verdicts_involved": in_verdicts[claim["id"]]})
    return rows


# ---------------------------------------------------------------- writing

ABOUT = {
    "raw_bom": "one line of plm_bom_export.csv, as written", "raw_erp": "one line of erp_items.csv, as written",
    "raw_note": "one note of technical_notes.jsonl, as written",
    "claim": "one claim of the log", "claim_status": "one claim, and whether it is in force",
    "resolution": "one written value (a reference or a supplier name) and the part or supplier it stands for",
    "part": "one real part: a system, a sub-assembly or a component",
    "supplier": "one real supplier", "variant": "one train variant", "unit": "one written unit and its base unit",
    "bom_line": "one parent-child link in one variant, quantity in the base unit",
    "price": "one ERP row, cost per base unit", "part_cost": "one part and its unit cost: agreed, disputed (two prices, cost empty) or missing (cost empty)",
    "relation": "one relation between parts stated by a claim",
    "design": "one distinct content of a sub-assembly", "occurrence": "one sub-assembly in one variant",
    "pair": "two designs that are near or functionally equivalent", "pair_diff": "one differing line of a pair",
    "verdict": "the verdict a design gets from its content (v_verdict has the final one per sub-assembly)", "issue": "one inconsistency, or one thing left undecided",
    "v_verdict": "one sub-assembly in one variant, with its verdict and the reason",
    "v_evidence": "one fact behind a verdict", "v_pair_diff": "one differing line between two sub-assemblies",
    "v_reuse_map": "one design, with the reference each variant uses for it",
    "v_tender_start": "one sub-assembly of V1: reuse, adapt, replace or keep, with its cost",
    "v_purchasing": "one bought part: its references, suppliers and prices",
    "v_issue": "one inconsistency, or one thing left undecided", "v_queue": "one open item waiting for a decision",
    "v_readiness": "one count of how much of the data can be relied on",
    "v_claim_effect": "one claim in force and what it touches",
    "v_content": "one line of one sub-assembly in one variant, with the component's unit cost",
    "v_subassembly_cost": "one sub-assembly in one variant: its unit cost, empty while any line has no agreed price, and the components that block it",
    "v_reuse_between": "one sub-assembly of one variant, seen from another variant",
}


def fl(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def write(m: Model, bom_only: dict[tuple[str, int], str], db_path: Path) -> None:
    """Write the model to a new SQLite file, then put it in place of the old one in a single step."""
    tmp = db_path.with_suffix(f".{os.getpid()}.tmp")  # per process: two builds at once never share a file
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    ingest(conn, m.raw)

    def table(name: str, columns: str, rows: list[tuple]) -> None:
        conn.execute(f"CREATE TABLE {name} ({columns})")
        if rows:
            conn.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(rows[0]))})", rows)

    all_claims = {c["id"]: c for c in m.claims}
    table("claim", ", ".join(FIELDS),
          [tuple(json.dumps(c[f], ensure_ascii=False) if f == "evidence" else c[f] for f in FIELDS) for c in m.claims])
    table("claim_status", "claim_id INTEGER, status, in_force INTEGER",
          [(i, str(m.status[i]), int(m.status[i].in_force)) for i in all_claims])
    table("part", "part_id, kind, canonical_ref, description, known INTEGER, spellings",
          [(i, p["kind"], p["canonical_ref"], p["description"], int(p["known"]), ", ".join(p["spellings"]))
           for i, p in m.parts.items()])
    table("supplier", "supplier_id, name, spellings", [(i, s["name"], "; ".join(s["spellings"])) for i, s in m.suppliers.items()])
    table("resolution", "written_value, kind, entity_id",
          [(ref, "ref", part) for ref, part in sorted(m.part_of.items())]
          + [(name, "supplier", supplier) for name, supplier in sorted(m.supplier_of.items())])
    table("variant", "variant_id, cars INTEGER, speed_class_kmh INTEGER, interior",
          [(v, int(a["cars"]), int(a["speed_class_kmh"]), a["interior"]) for v, a in sorted(m.variants.items())])
    table("unit", "written_unit, base_unit, factor REAL", [(u, base, float(f)) for u, (base, f) in sorted(m.units.items())])
    table("bom_line", "variant_id, level INTEGER, parent_part_id, child_part_id, quantity REAL, unit, raw_rows",
          [(l["variant"], l["level"], l["parent"], l["child"], fl(l["quantity"]), l["unit"], ", ".join(map(str, l["rows"])))
           for l in m.lines])
    table("price", "part_id, supplier_id, supplier_written, cost_per_base_unit_eur REAL, raw_row INTEGER",
          [(p["part"], p["supplier"], p["supplier_written"], fl(p["cost"]), p["row"]) for p in m.prices])
    n_prices = Counter(p["part"] for p in m.prices if p["cost"] is not None)
    table("part_cost", "part_id, unit_cost_eur REAL, n_prices INTEGER, status",
          [(part, fl(cost), n_prices[part], m.cost_status[part]) for part, cost in m.cost.items()])
    table("relation", "claim_id INTEGER, type, part_a, part_b, ref_a, ref_b, option, as_of, note_id, quote",
          [(r["claim_id"], r["type"], r["part_a"], r["part_b"], r["ref_a"], r["ref_b"], r["option"], r["as_of"],
            r["note_id"], r["quote"]) for r in m.relations])
    table("design", "design_id, content_hash, system_part_id, n_lines INTEGER, comparable INTEGER, refs, variants",
          [(d.id, d.hash, d.system, len(d.lines), int(d.comparable), ", ".join(m.name(p) for p in d.parts),
            " ".join(d.variants)) for d in m.designs])
    table("occurrence", "variant_id, part_id, system_part_id, design_id, per_train REAL, raw_rows, verdict, reason, verdict_bom_only",
          [(o.variant, o.part, o.system, o.design.id, fl(o.per_train), ", ".join(map(str, o.raw_rows)),
            o.verdict.verdict, o.verdict.reason, bom_only.get((o.variant, min(o.raw_rows)), "")) for o in m.occurrences])
    table("pair", "pair_id INTEGER, design_a, design_b, kind, n_shared INTEGER, n_differing INTEGER, "
                  "separating_options, cost_gap_eur REAL, claim_id INTEGER",
          [(p.id, p.a.id, p.b.id, p.kind, p.n_shared, p.n_differing, ", ".join(p.separating_options), fl(p.cost_gap),
            p.claim_id) for p in m.pairs])
    table("pair_diff", "pair_id INTEGER, part_a, part_b, qty_a REAL, qty_b REAL, explanation, claim_id INTEGER, cost_gap_eur REAL",
          [(p.id, l.part_a, l.part_b, fl(l.qty_a), fl(l.qty_b), l.explanation, l.claim_id, fl(l.cost_gap))
           for p in m.pairs for l in p.lines])
    table("verdict", "design_id, verdict, reason, counterpart_design_id, claim_ids",
          [(i, v.verdict, v.reason, v.counterpart.id if v.counterpart else None, ", ".join(map(str, v.claim_ids)))
           for i, v in m.verdicts.items()])
    table("issue", "type, detail, source_file, source_rows",
          [(i["type"], i["detail"], i["source_file"], i["source_rows"]) for i in m.issues])
    open_items = queue(m)
    table("queue", "kind, detail, claim_id INTEGER, source_rows",
          [(i["kind"], i["detail"], i["claim_id"], i["source_rows"]) for i in open_items])
    table("readiness", "what, n INTEGER, of INTEGER", [(r["what"], r["n"], r["of"]) for r in readiness(m, open_items)])
    table("claim_effect", "claim_id INTEGER, type, made_by, spellings_merged INTEGER, lines_affected INTEGER, verdicts_involved INTEGER",
          [tuple(r.values()) for r in claim_effect(m)])
    table("reuse_between", "variant_from, variant_to, subassembly_ref, status, counterpart_ref, differing_lines INTEGER, "
                           "cost_gap_eur REAL, blocked_by", [tuple(r.values()) for r in reuse_between(m)])
    table("evidence", "design_id, kind, detail, claim_id INTEGER, source_file, source_row", [tuple(r.values()) for r in evidence(m)])
    conn.executescript(VIEWS.read_text())
    table("about", "name, one_row_is", sorted(ABOUT.items()))
    conn.commit()
    conn.close()
    os.replace(tmp, db_path)


@dataclass
class Summary:
    """What a build produced, small enough to compare with the build before it."""

    parts: int
    designs: int
    verdicts: dict[tuple[str, str], str]  # (variant, sub-assembly reference) -> verdict
    issues: dict[str, int]
    open_items: dict[str, int]
    seconds: float

    def line(self) -> str:
        counts = Counter(self.verdicts.values())
        return (f"{self.parts} parts, {self.designs} designs; verdicts: "
                + ", ".join(f"{counts[v]} {v}" for v in ("reused", "reusable", "blocked", "specific"))
                + f"; {sum(self.open_items.values())} open items; {sum(self.issues.values())} issues")


def build(raw_dir: str | Path = "data/raw", log_path: str | Path = "data/claims.jsonl",
          out_db: str | Path = "out/pilot.db", without_notes: bool = False, made_by: set[str] | None = None,
          up_to: int | None = None) -> Summary:
    """Rebuild the database from the raw files and the claim log.

    The three filters replay the log with claims left out: `without_notes` drops every claim that rests on a note
    (it quotes one), `made_by` keeps only some makers' claims, `up_to` keeps the first N claims.
    """
    started = time.perf_counter()
    raw, claims = read_raw(raw_dir), load(log_path)
    model = compute(raw, claims, without_notes, made_by, up_to)
    # The verdict from the BOM alone: the same replay without any claim that rests on a note.
    plain = model if without_notes else compute(raw, claims, True, made_by, up_to)
    bom_only = {(o.variant, min(o.raw_rows)): o.verdict.verdict for o in plain.occurrences}
    out_db = Path(out_db)
    out_db.parent.mkdir(parents=True, exist_ok=True)
    write(model, bom_only, out_db)
    return Summary(
        parts=sum(1 for p in model.parts.values() if p["known"]), designs=len(model.designs),
        verdicts={(o.variant, model.name(o.part)): o.verdict.verdict for o in model.occurrences},
        issues=dict(Counter(i["type"] for i in model.issues)),
        open_items=dict(Counter(i["kind"] for i in queue(model))), seconds=time.perf_counter() - started)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--log", default="data/claims.jsonl")
    parser.add_argument("--out", default="out/pilot.db")
    parser.add_argument("--without-notes", action="store_true", help="leave out every claim that rests on a note")
    parser.add_argument("--made-by", nargs="+", choices=("rule", "agent", "person"), help="keep only these makers' claims")
    parser.add_argument("--up-to", type=int, help="keep only the first N claims")
    args = parser.parse_args()
    summary = build(args.raw, args.log, args.out, args.without_notes, set(args.made_by) if args.made_by else None, args.up_to)
    print(f"{args.out} built in {summary.seconds:.2f} s: {summary.line()}")
    print("issues:", summary.issues)
    print("open items:", summary.open_items)
