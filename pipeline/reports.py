"""Tables worked out from the finished model, for the agent and the app: nothing in the build depends on them.

- queue: the open items waiting for a decision (table v_queue)
- readiness: counts of how much of the data can be relied on (table v_readiness)
- reuse_between: every sub-assembly of every variant, seen from each other variant (table v_reuse_between)
- evidence: the facts behind each verdict (table evidence, read through v_evidence)
"""

from collections import defaultdict

from pipeline.claims import split
from pipeline.ingest import BOM_FILE, NOTE_FILE
from pipeline.model import Model
from pipeline.units import number
from pipeline.verdict import obsolete_components


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
    components = m.used_components()
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
                row = {"variant_from": source, "variant_to": target, "subassembly_ref": m.name(occurrence.part),
                       "status": "no counterpart", "counterpart_ref": "", "differing_lines": None, "cost_gap_eur": None,
                       "obsolete_parts": occurrence.obsolete_parts}
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
                                   differing_lines=pair.n_differing, cost_gap_eur=None if gap is None else round(float(gap), 2))
                rows.append(row)
    return rows


def corrections(m: Model) -> dict[int, list[tuple[str, int | None]]]:
    """BOM row number -> what the claims in force changed in how that row is read, each with its claim.

    Four things are corrections: a reference written in another spelling than the part's own, a row left out as
    a repeat, a cell replaced or emptied, and a quantity converted from another unit.
    """
    linked = defaultdict(list)  # written reference -> (the reference a same_as claim links it to, the claim)
    for claim in sorted(m.by_type["same_as"], key=lambda c: c["id"]):
        a, b = split(claim["subject"])[1], split(claim["object"])[1]
        linked[a].append((b, claim["id"]))
        linked[b].append((a, claim["id"]))

    def path(written: str, target: str) -> list[int]:
        """The same_as claims that lead from one spelling to another, by the shortest way."""
        reached, todo = {written: []}, [written]
        for ref in todo:
            for other, claim_id in linked[ref]:
                if other not in reached:
                    reached[other] = reached[ref] + [claim_id]
                    todo.append(other)
        return reached.get(target, [])

    repeats = {int(split(c["subject"])[1]): c for c in m.by_type["duplicate_of"]}
    cells = {tuple(split(c["subject"])[1].split(":", 2)): c for c in m.by_type["no_value"] + m.by_type["value_is"]}
    units = {split(c["subject"])[1]: c for c in m.by_type["converts_to"]}
    found = defaultdict(list)
    for row in m.raw.bom:
        row_no = row["row_no"]
        for column in ("parent_ref", "child_ref") if int(row["level"]) > 2 else ("child_ref",):  # a system's parent is the variant
            written = row[column]
            own = m.name(m.part_of[written])
            if written != own:
                claim_ids = path(written, own)
                via = f" (claims {', '.join(map(str, claim_ids))})" if len(claim_ids) > 1 else ""
                found[row_no].append((f"{written} read as {own}{via}", claim_ids[0] if claim_ids else None))
        if row_no in repeats:
            claim = repeats[row_no]
            found[row_no].append((f"row {row_no} repeats row {split(claim['object'])[1]} and is left out", claim["id"]))
            continue
        for column in ("quantity", "unit"):
            claim = cells.get(("bom", str(row_no), column))
            if claim:
                now = f"replaced by {claim['value']}" if claim["type"] == "value_is" else "holds no value"
                found[row_no].append((f"{row['child_ref']}: {column} {row[column]!r} {now}", claim["id"]))
        unit = m.cell("bom", row, "unit")
        value = m.to_base(number(m.cell("bom", row, "quantity")), unit)
        if value and unit != value[1]:
            found[row_no].append((f"{row['child_ref']}: {m.cell('bom', row, 'quantity')} {unit} read as {value[0]:f} {value[1]}",
                                  units[unit]["id"] if unit in units else None))
    return found


def evidence(m: Model) -> list[dict]:
    """The facts behind each design's verdict: where it occurs, the corrections its BOM rows were read with, the
    pair it was compared with, the claims used, and the claims that call one of its parts obsolete or superseded.

    `variant_id` and `part_id` are filled only on a claim about a sub-assembly's own reference: it concerns that
    sub-assembly, not the others that carry the same design.
    """
    relations = m.relation_index
    claims = {c["id"]: c for c in m.claims}

    def row(design, kind, detail, claim_id=None, source_file="", source_row="", occurrence=None):
        return {"design_id": design.id, "variant_id": occurrence.variant if occurrence else "",
                "part_id": occurrence.part if occurrence else "", "kind": kind, "detail": detail,
                "claim_id": claim_id, "source_file": source_file, "source_row": source_row}

    def claim_row(design, claim_id, occurrence=None):
        claim = claims[claim_id]
        about = split(claim["subject"])[1] + (f", {split(claim['object'])[1]}" if claim["object"] else "")
        note_id = next((split(item)[1] for item in claim["evidence"] if split(item)[0] == "note"), "")
        return row(design, "claim", f"{claim['type']}({about})" + (f": {claim['quote']}" if claim["quote"] else ""),
                   claim_id, NOTE_FILE if note_id else "", note_id, occurrence)

    content_rows = defaultdict(list)  # (variant, sub-assembly) -> the raw rows of its lines
    for line in m.lines:
        if line["level"] == 4:
            content_rows[(line["variant"], line["parent"])] += line["rows"]
    changed = defaultdict(list)  # (variant, sub-assembly) -> the inserts and deletes of its components, and its own insert
    for change in m.content_changes:
        changed[(change["variant"], change["parent"] if change["level"] == 4 else change["child"])].append(change)
    fixes = corrections(m)
    rows = []
    for design in m.designs:
        verdict = m.verdicts[design.id]
        for occurrence in design.occurrences:
            own = relations.dead(occurrence.part)
            if own:
                rows.append(claim_row(design, own[0], occurrence))
            listed = occurrence.raw_rows  # empty for a sub-assembly a person inserted: no BOM row lists it
            rows.append(row(design, "bom row", f"{occurrence.variant}: {m.name(occurrence.part)}, {len(design.lines)} lines",
                            source_file=BOM_FILE if listed else "", source_row=str(min(listed)) if listed else ""))
        for occurrence in design.occurrences:
            rows += [row(design, "content change", change["detail"], change["claim_id"], BOM_FILE if change["rows"] else "",
                         str(min(change["rows"])) if change["rows"] else "")
                     for change in changed[(occurrence.variant, occurrence.part)]]
            raw_rows = sorted(set(occurrence.raw_rows + content_rows[(occurrence.variant, occurrence.part)]))
            rows += [row(design, "correction", f"{occurrence.variant}: {detail}", claim_id, BOM_FILE, str(row_no))
                     for row_no in raw_rows for detail, claim_id in fixes[row_no]]
        if verdict.pair:
            pair = verdict.pair
            rows.append(row(design, "pair", f"{pair.kind} pair with {', '.join(m.name(p) for p in pair.other(design).parts)}: "
                                            f"{pair.n_differing} differing lines, {pair.n_shared} shared"))
        obsolete = [claim_id for _, claim_id, _ in obsolete_components(design, relations)]
        rows += [claim_row(design, claim_id) for claim_id in dict.fromkeys(obsolete + verdict.claim_ids)]
    return rows
