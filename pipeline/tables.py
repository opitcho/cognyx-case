"""The database: every table defined once, and the write.

`TABLES` lists the tables in the order they are created. Each entry holds the table's name, what one row of it is,
its columns, and the function that takes the rows from the model. The raw tables are written by `ingest()` and the
views are in `views.sql`; their descriptions are in `RAW_ABOUT` and `VIEW_ABOUT`. The `about` table of the database
is made from all three.
"""

import json
import os
import sqlite3
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable

from pipeline.claims import FIELDS
from pipeline.ingest import ingest
from pipeline.model import Model
from pipeline.reports import claim_effect, evidence, readiness, reuse_between

VIEWS = Path(__file__).with_name("views.sql")


@dataclass
class Table:
    name: str
    one_row_is: str  # empty: the table is read through its view, which has the description
    columns: str
    rows: Callable[[Model], list[tuple]]


def fl(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def joined(values, separator: str = ", ") -> str:
    return separator.join(map(str, values))


def part_costs(m: Model) -> list[tuple]:
    n_prices = Counter(p["part"] for p in m.prices if p["cost"] is not None)
    return [(part, fl(cost), n_prices[part], m.cost_status[part]) for part, cost in m.cost.items()]


TABLES = [
    Table("claim", "one claim of the log", ", ".join(FIELDS),
          lambda m: [tuple(json.dumps(c[f], ensure_ascii=False) if f == "evidence" else c[f] for f in FIELDS)
                     for c in m.claims]),
    Table("claim_status", "one claim, and whether it is in force", "claim_id INTEGER, status, in_force INTEGER",
          lambda m: [(i, str(m.status[i]), int(m.status[i].in_force)) for i in dict.fromkeys(c["id"] for c in m.claims)]),
    Table("part", "one real part: a system, a sub-assembly or a component",
          "part_id, kind, canonical_ref, description, known INTEGER, spellings",
          lambda m: [(i, p["kind"], p["canonical_ref"], p["description"], int(p["known"]), joined(p["spellings"]))
                     for i, p in m.parts.items()]),
    Table("supplier", "one real supplier", "supplier_id, name, spellings",
          lambda m: [(i, s["name"], joined(s["spellings"], "; ")) for i, s in m.suppliers.items()]),
    Table("resolution", "one written value (a reference or a supplier name) and the part or supplier it stands for",
          "written_value, kind, entity_id",
          lambda m: [(ref, "ref", part) for ref, part in sorted(m.part_of.items())]
                    + [(name, "supplier", supplier) for name, supplier in sorted(m.supplier_of.items())]),
    Table("variant", "one train variant", "variant_id, cars INTEGER, speed_class_kmh INTEGER, interior",
          lambda m: [(v, int(a["cars"]), int(a["speed_class_kmh"]), a["interior"]) for v, a in sorted(m.variants.items())]),
    Table("unit", "one written unit and its base unit", "written_unit, base_unit, factor REAL",
          lambda m: [(u, base, float(f)) for u, (base, f) in sorted(m.units.items())]),
    Table("bom_line", "one parent-child link in one variant, quantity in the base unit",
          "variant_id, level INTEGER, parent_part_id, child_part_id, quantity REAL, unit, raw_rows",
          lambda m: [(l["variant"], l["level"], l["parent"], l["child"], fl(l["quantity"]), l["unit"], joined(l["rows"]))
                     for l in m.lines]),
    Table("price", "one ERP row, cost per base unit",
          "part_id, supplier_id, supplier_written, cost_per_base_unit_eur REAL, raw_row INTEGER",
          lambda m: [(p["part"], p["supplier"], p["supplier_written"], fl(p["cost"]), p["row"]) for p in m.prices]),
    Table("part_cost", "one part and its unit cost: agreed, disputed (two prices, cost empty) or missing (cost empty)",
          "part_id, unit_cost_eur REAL, n_prices INTEGER, status", part_costs),
    Table("relation", "one relation between parts stated by a claim",
          "claim_id INTEGER, type, part_a, part_b, ref_a, ref_b, option, as_of, note_id, quote",
          lambda m: [(r["claim_id"], r["type"], r["part_a"], r["part_b"], r["ref_a"], r["ref_b"], r["option"], r["as_of"],
                      r["note_id"], r["quote"]) for r in m.relations]),
    Table("design", "one distinct content of a sub-assembly",
          "design_id, content_hash, system_part_id, n_lines INTEGER, comparable INTEGER, refs, variants",
          lambda m: [(d.id, d.hash, d.system, len(d.lines), int(d.comparable), joined(m.name(p) for p in d.parts),
                      " ".join(d.variants)) for d in m.designs]),
    Table("occurrence", "one sub-assembly in one variant",
          "variant_id, part_id, system_part_id, design_id, per_train REAL, raw_rows, verdict, reason, verdict_bom_only",
          lambda m: [(o.variant, o.part, o.system, o.design.id, fl(o.per_train), joined(o.raw_rows), o.verdict.verdict,
                      o.verdict.reason, o.verdict_bom_only) for o in m.occurrences]),
    Table("pair", "two designs that are near or functionally equivalent",
          "pair_id INTEGER, design_a, design_b, kind, n_shared INTEGER, n_differing INTEGER, separating_options, "
          "cost_gap_eur REAL, claim_id INTEGER",
          lambda m: [(p.id, p.a.id, p.b.id, p.kind, p.n_shared, p.n_differing, joined(p.separating_options),
                      fl(p.cost_gap), p.claim_id) for p in m.pairs]),
    Table("pair_diff", "one differing line of a pair",
          "pair_id INTEGER, part_a, part_b, qty_a REAL, qty_b REAL, explanation, claim_id INTEGER, cost_gap_eur REAL",
          lambda m: [(p.id, l.part_a, l.part_b, fl(l.qty_a), fl(l.qty_b), l.explanation, l.claim_id, fl(l.cost_gap))
                     for p in m.pairs for l in p.lines]),
    Table("verdict", "the verdict a design gets from its content (v_verdict has the final one per sub-assembly)",
          "design_id, verdict, reason, counterpart_design_id, claim_ids",
          lambda m: [(i, v.verdict, v.reason, v.counterpart.id if v.counterpart else None, joined(v.claim_ids))
                     for i, v in m.verdicts.items()]),
    Table("issue", "one inconsistency, or one thing left undecided", "type, detail, source_file, source_rows",
          lambda m: [(i["type"], i["detail"], i["source_file"], i["source_rows"]) for i in m.issues]),
    Table("queue", "", "kind, detail, claim_id INTEGER, source_rows",
          lambda m: [(i["kind"], i["detail"], i["claim_id"], i["source_rows"]) for i in m.open_items]),
    Table("readiness", "", "what, n INTEGER, of INTEGER",
          lambda m: [(r["what"], r["n"], r["of"]) for r in readiness(m, m.open_items)]),
    Table("claim_effect", "",
          "claim_id INTEGER, type, made_by, spellings_merged INTEGER, lines_affected INTEGER, verdicts_involved INTEGER",
          lambda m: [tuple(r.values()) for r in claim_effect(m)]),
    Table("reuse_between", "",
          "variant_from, variant_to, subassembly_ref, status, counterpart_ref, differing_lines INTEGER, "
          "cost_gap_eur REAL, blocked_by",
          lambda m: [tuple(r.values()) for r in reuse_between(m)]),
    Table("evidence", "", "design_id, kind, detail, claim_id INTEGER, source_file, source_row",
          lambda m: [tuple(r.values()) for r in evidence(m)]),
]

RAW_ABOUT = {
    "raw_bom": "one line of plm_bom_export.csv, as written",
    "raw_erp": "one line of erp_items.csv, as written",
    "raw_note": "one note of technical_notes.jsonl, as written",
}

VIEW_ABOUT = {
    "v_verdict": "one sub-assembly in one variant, with its verdict and the reason",
    "v_evidence": "one fact behind a verdict",
    "v_pair_diff": "one differing line between two sub-assemblies",
    "v_reuse_map": "one design, with the reference each variant uses for it",
    "v_tender_start": "one sub-assembly of V1: reuse, adapt, replace or keep, with its cost",
    "v_purchasing": "one bought part: its references, suppliers and prices",
    "v_issue": "one inconsistency, or one thing left undecided",
    "v_queue": "one open item waiting for a decision",
    "v_readiness": "one count of how much of the data can be relied on",
    "v_claim_effect": "one claim in force and what it touches",
    "v_content": "one line of one sub-assembly in one variant, with the component's unit cost",
    "v_subassembly_cost": "one sub-assembly in one variant: its unit cost, empty while any line has no agreed price, and the components that block it",
    "v_reuse_between": "one sub-assembly of one variant, seen from another variant",
}

ABOUT = RAW_ABOUT | {table.name: table.one_row_is for table in TABLES if table.one_row_is} | VIEW_ABOUT


def write(m: Model, db_path: Path) -> None:
    """Write the model to a new SQLite file, then put it in place of the old one in a single step."""
    tmp = db_path.with_suffix(f".{os.getpid()}.tmp")  # per process: two builds at once never share a file
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)

    def create(name: str, columns: str, rows: list[tuple]) -> None:
        conn.execute(f"CREATE TABLE {name} ({columns})")
        if rows:
            conn.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(rows[0]))})", rows)

    ingest(conn, m.raw)
    for table in TABLES:
        create(table.name, table.columns, table.rows(m))
    conn.executescript(VIEWS.read_text())
    create("about", "name, one_row_is", sorted(ABOUT.items()))
    conn.commit()
    conn.close()
    os.replace(tmp, db_path)
