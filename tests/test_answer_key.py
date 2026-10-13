"""The build's verdicts on the generated data are those of the answer key, data/truth/verdicts.csv.

The build uses data/claims.demo_start.jsonl: the rules' and the agent's claims. If that file is regenerated from
another agent run, a failure here means that run reached different verdicts.
"""

import csv
import shutil
import sqlite3

from pipeline.build import Summary, build
from pipeline.claims import ClaimLog
from pipeline.ingest import read_raw

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


# A person's inserts and deletes on the generated data, each on a copy of the demo log. The answer key holds
# none, so the test above is not concerned.

def decided(tmp_path, *claims) -> tuple[sqlite3.Connection, Summary]:
    """The database built from the demo log with a person's claims added, and the build's summary."""
    log = tmp_path / "claims.jsonl"
    shutil.copy(ROOT / "data" / "claims.demo_start.jsonl", log)
    writer = ClaimLog(log, read_raw(ROOT / "data" / "raw"))
    for type, subject, object, value in claims:
        writer.append({"type": type, "subject": subject, "object": object, "value": value,
                       "made_by": "person", "maker": "Oscar"})
    summary = build(ROOT / "data" / "raw", log, tmp_path / "decided.db")
    return sqlite3.connect(tmp_path / "decided.db"), summary


def counts(summary: Summary) -> tuple[int, int, int]:
    return tuple(list(summary.verdicts.values()).count(verdict) for verdict in ("reused", "reusable", "specific"))


def test_replacing_the_motor_of_the_v3_door_drive_makes_it_the_door_drive_of_v1_and_v2(tmp_path):
    # Row 536 lists DD-2037 in V3. It differs from DD-2010 of V1 and V2 by its motor, MT-745 where they have MT-701.
    conn, summary = decided(tmp_path, ("delete_part", "bom:536", "ref:MT-745", ""),
                            ("insert_part", "bom:536", "ref:MT-701", "1 pcs"))
    assert counts(summary) == (223, 14, 3)  # from 222, 15, 3
    reason = "same content in V1, V2, V3 under references DD-2010, DD-2037"
    assert conn.execute("SELECT variant_id, subassembly_ref, verdict, verdict_bom_only, reason, shared_with, content_changes "
                        "FROM v_verdict WHERE subassembly_ref IN ('DD-2010', 'DD-2037') ORDER BY 1").fetchall() == [
        ("V1", "DD-2010", "reused", "reused", reason, "V2 V3", 2), ("V2", "DD-2010", "reused", "reused", reason, "V1 V3", 2),
        ("V3", "DD-2037", "reused", "reused", reason, "V1 V2", 2)]
    assert conn.execute("SELECT unit_cost_eur, train_cost_eur FROM v_subassembly_cost WHERE variant_id = 'V3' "
                        "AND subassembly_ref = 'DD-2037'").fetchone() == (836.30, 26761.60)  # from 1295.74, 41463.68
    assert conn.execute("SELECT component_ref, changed_by_claim FROM v_content WHERE variant_id = 'V3' "
                        "AND subassembly_ref = 'DD-2037' AND changed_by_claim IS NOT NULL").fetchall() == [("MT-701", 580)]
    assert summary.content_changes == {579: "V3: MT-745 deleted from DD-2037 (was 1 pcs)",
                                       580: "V3: MT-701 inserted in DD-2037, 1 pcs"}


def test_replacing_a_sub_assembly_of_v6_by_the_one_the_other_variants_use(tmp_path):
    # Row 1286 is the interior system of V6, which lists GP-8805 where V1, V2, V3 and V5 list PW-4700 (row 39 in V1).
    # A note says the two do the same job; they share no component.
    conn, summary = decided(tmp_path, ("delete_part", "bom:1286", "ref:GP-8805", ""),
                            ("insert_part", "bom:1286", "bom:39", "20 pcs"))
    assert counts(summary) == (223, 14, 3) and summary.designs == 73  # from 222, 15, 3 and 74
    assert conn.execute("SELECT variant_id, subassembly_ref, verdict, verdict_bom_only, reason, shared_with, content_changes "
                        "FROM v_verdict WHERE variant_id = 'V6' AND subassembly_ref IN ('GP-8805', 'PW-4700')").fetchall() == [
        ("V6", "PW-4700", "reused", "reused", "same content in V1, V2, V3, V5, V6", "V1 V2 V3 V5", 1)]
    # PW-4700 has no total cost in any variant: one of its components has no agreed price.
    assert conn.execute("SELECT per_train, unit_cost_eur, total_lines, blocked_by FROM v_subassembly_cost "
                        "WHERE variant_id = 'V6' AND subassembly_ref = 'PW-4700'").fetchone() == (20.0, None, 5, "PF-253")
    assert conn.execute("SELECT COUNT(*), MIN(changed_by_claim), MAX(changed_by_claim) FROM v_content "
                        "WHERE variant_id = 'V6' AND subassembly_ref = 'PW-4700'").fetchone() == (5, 580, 580)
    assert summary.content_changes == {
        579: "V6: GP-8805 deleted from INTR-SYS-01 (was 20 per train, 5 components)",
        580: "V6: PW-4700 inserted in INTR-SYS-01, 20 per train, 5 components copied from V1 (BOM row 39)"}
    assert not summary.not_applied and "content_change_not_applied" not in summary.issues


def test_replacing_a_superseded_component_empties_obsolete_parts(tmp_path):
    # SN-573 is superseded by SN-598. Rows 23, 286, 537 and 787 list the four sub-assemblies that hold it.
    claims = [claim for row in (23, 286, 537, 787) for claim in (("delete_part", f"bom:{row}", "ref:SN-573", ""),
                                                                 ("insert_part", f"bom:{row}", "ref:SN-598", "2 pcs"))]
    conn, summary = decided(tmp_path, *claims)
    assert len(summary.content_changes) == 8
    assert conn.execute("SELECT variant_id, subassembly_ref, obsolete_parts, shared_with FROM v_verdict "
                        "WHERE subassembly_ref IN ('DC-3001', 'KP-0457') ORDER BY 1").fetchall() == [
        ("V1", "KP-0457", "own reference KP-0457, superseded by DC-3001 (same content under DC-3001, DC-3020)", "V2 V3 V4 V5 V6"),
        ("V2", "DC-3001", "", "V1 V3 V4 V5 V6"), ("V3", "DC-3001", "", "V1 V2 V4 V5 V6"), ("V4", "DC-3001", "", "V1 V2 V3 V5 V6")]
