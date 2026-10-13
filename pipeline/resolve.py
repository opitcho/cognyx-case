"""Steps 3 and 4 of the build: from the raw rows and the claims in force to parts, suppliers, variants, units,
BOM lines, prices and relations.

Each function fills its own fields of the model and reads the ones filled before it, so `resolve()` calls them
in a fixed order. Issues are added to the model as they are found.
"""

from collections import Counter, defaultdict
from decimal import Decimal

from pipeline.claims import RANK, RELATIONS, split
from pipeline.compare import Relations
from pipeline.ingest import BOM_FILE, ERP_FILE, NOTE_FILE
from pipeline.model import Model
from pipeline.units import number, units_from_claims

KINDS = {2: "system", 3: "sub-assembly", 4: "component"}


def resolve(m: Model) -> None:
    resolve_parts(m)
    resolve_suppliers(m)
    read_variants(m)
    m.units = units_from_claims(m.by_type["converts_to"])
    fold_bom(m)
    price_parts(m)
    read_relations(m)


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


def links_of(m: Model, kind: str):
    """The same_as links of one kind, strongest first, and the not_same_as pairs of that kind."""
    links = [(split(c["subject"])[1], split(c["object"])[1], c)
             for c in sorted(m.by_type["same_as"], key=lambda c: (-RANK[c["made_by"]], c["id"]))
             if split(c["subject"])[0] == kind]
    vetoes = {frozenset((split(c["subject"])[1], split(c["object"])[1]))
              for c in m.by_type["not_same_as"] if split(c["subject"])[0] == kind}
    return links, vetoes


def resolve_parts(m: Model) -> None:
    """Step 3. Every reference written in a reference column or named in a claim stands for a part."""
    raw = m.raw
    written = raw.written_refs()
    universe = set(written["bom"]) | set(written["erp"]) | {n["reference"] for n in raw.notes if n["reference"]}
    for claim in m.claims:
        for target in (claim["subject"], claim["object"]):
            if split(target)[0] == "ref":
                universe.add(split(target)[1])
    links, vetoes = links_of(m, "ref")
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


def resolve_suppliers(m: Model) -> None:
    """The same grouping, on the names written in the ERP file."""
    names = Counter(m.cell("erp", row, "supplier") for row in m.raw.erp)
    names = Counter({name: n for name, n in names.items() if name and name.strip()})
    links, vetoes = links_of(m, "supplier")
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


def read_variants(m: Model) -> None:
    """The variants, from the four columns every BOM row repeats."""
    for row in m.raw.bom:
        attributes = {"cars": row["cars"], "speed_class_kmh": row["speed_class_kmh"], "interior": row["interior"]}
        if m.variants.setdefault(row["variant_id"], attributes) != attributes:
            m.issue("variant_attributes", f"{row['variant_id']} is described two ways", BOM_FILE, [row["row_no"]])


def fold_bom(m: Model) -> None:
    """Step 4. Rows of one parent-child link in one variant are folded into one line."""
    repeats = {int(split(c["subject"])[1]) for c in m.by_type["duplicate_of"]}
    folded: dict[tuple, dict] = {}
    for row in m.raw.bom:
        level = int(row["level"])
        parent = m.part_of[row["parent_ref"]] if level > 2 else None
        line = folded.setdefault((row["variant_id"], level, parent, m.part_of[row["child_ref"]]),
                                 {"rows": [], "values": [], "unknown": []})
        line["rows"].append(row["row_no"])
        if row["row_no"] in repeats:
            continue
        unit = m.cell("bom", row, "unit")
        value = m.to_base(number(m.cell("bom", row, "quantity")), unit)
        (line["values"] if value else line["unknown"]).append((row["row_no"], value or (m.cell("bom", row, "quantity"), unit)))
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


def price_parts(m: Model) -> None:
    """One price per ERP row, per base unit. A part's cost is known only when its rows agree."""
    by_part = defaultdict(list)
    for row in m.raw.erp:
        part_id = m.part_of[row["item_ref"]]
        supplier = m.cell("erp", row, "supplier")
        amount = number(m.cell("erp", row, "unit_cost_eur"))
        per_unit = m.to_base(Decimal(1), m.cell("erp", row, "price_unit"))  # how many base units the price covers
        cost = None
        if amount is not None and per_unit is not None:
            cost = round(amount / per_unit[0], 6).normalize()
        elif amount is not None:
            m.issue("unknown_unit", f"{row['item_ref']}: price unit {row['price_unit']!r} cannot be converted",
                    ERP_FILE, [row["row_no"]])
        m.prices.append({"part": part_id, "supplier": m.supplier_of.get(supplier) if supplier else None,
                         "supplier_written": supplier or "", "cost": cost, "row": row["row_no"]})
        by_part[part_id].append((row["row_no"], cost))
    used = m.used_components()
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


def read_relations(m: Model) -> None:
    """The relations between parts, from the five relation types."""
    for claim in m.force:
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
    m.relation_index = Relations(m.relations)
    used = m.used_components()
    for part_id, claim_id in m.relation_index.dead_parts():
        if part_id in used:
            m.issue("note_contradicts_bom", f"{m.name(part_id)} is obsolete or superseded (claim {claim_id}) and is "
                    "still in the BOM", BOM_FILE)
