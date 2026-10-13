"""The build's verdicts on the generated data are those of the answer key, data/truth/verdicts.csv.

The build uses data/claims.demo_start.jsonl: the rules' and the agent's claims. If that file is regenerated from
another agent run, a failure here means that run reached different verdicts.
"""

import csv
import sqlite3

from pipeline.build import build

from conftest import ROOT


def built(tmp_path) -> dict[tuple[str, str], tuple]:
    """(variant, part id) -> (verdict_bom_only, verdict, holds an obsolete part), for every sub-assembly of the build."""
    db = tmp_path / "pilot.db"
    build(ROOT / "data" / "raw", ROOT / "data" / "claims.demo_start.jsonl", db)
    conn = sqlite3.connect(db)
    return {(variant, part): (bom_only, verdict, bool(holds)) for variant, part, bom_only, verdict, holds in conn.execute(
        "SELECT v.variant_id, r.entity_id, v.verdict_bom_only, v.verdict, v.obsolete_parts <> '' FROM v_verdict v "
        "JOIN resolution r ON r.kind = 'ref' AND r.written_value = v.subassembly_ref")}


def key(db) -> dict[tuple[str, str], tuple]:
    """The same, read from the answer key: one entry per variant listed in a row."""
    part_of = dict(sqlite3.connect(db).execute("SELECT written_value, entity_id FROM resolution WHERE kind = 'ref'"))
    with open(ROOT / "data" / "truth" / "verdicts.csv", encoding="utf-8") as f:
        return {(variant, part_of[row["subassembly"]]): (row["verdict_bom_only"], row["verdict_with_notes"], row["holds_obsolete_part"] == "yes")
                for row in csv.DictReader(f) for variant in row["variants"].split()}


def test_every_sub_assembly_has_the_verdict_of_the_answer_key(tmp_path):
    assert built(tmp_path) == key(tmp_path / "pilot.db")
