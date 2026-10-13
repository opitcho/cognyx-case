"""Tables worked out from the finished model, for the agent and the app: nothing in the build depends on them.

- queue: the open items waiting for a decision
- readiness: counts of how much of the data can be relied on
- reuse_between: every sub-assembly of every variant, seen from each other variant
- evidence: the facts behind each verdict
- claim_effect: what each claim in force touches
"""

from collections import Counter, defaultdict

from pipeline.claims import split
from pipeline.ingest import BOM_FILE, NOTE_FILE
from pipeline.model import Model


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
    relations = m.relation_index
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
