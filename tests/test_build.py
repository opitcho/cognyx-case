"""build(): claims in force change the resolved model; nothing else does."""

import sqlite3
from decimal import Decimal

import pytest

from conftest import bom_row
from pipeline.build import build, compute
from pipeline.claims import ClaimLog
from pipeline.ingest import Raw
from pipeline.reports import queue
from pipeline.resolve import group
from pipeline.tables import write

RULE = {"made_by": "rule", "maker": "test"}
AGENT = {"made_by": "agent", "maker": "test-model"}
NOTE = {"evidence": ["note:TN-0001"], "as_of": "2025-01-10"}


def model(tiny, tmp_path, *claims, **filters):
    log = ClaimLog(tmp_path / "claims.jsonl", tiny)
    for claim in claims:
        log.append(claim)
    return compute(tiny, log.claims, **filters)


SEAL = {"type": "same_as", "subject": "ref:JT 218", "object": "ref:JT-218", **RULE}
SEAL_ERP = {"type": "same_as", "subject": "ref:JT218", "object": "ref:JT-218", **RULE}
ACTUATOR_ERP = {"type": "same_as", "subject": "ref:AC501", "object": "ref:AC-501", **RULE}
MM = {"type": "converts_to", "subject": "unit:mm", "object": "unit:m", "value": "0.001", **RULE}
RENUMBERED = {"type": "same_as", "subject": "ref:PT-7731", "object": "ref:DR-1042", **AGENT, **NOTE,
              "quote": "PT-7731 = ex DR-1042, renumbered"}
OBSOLETE_REF = {"type": "obsolete", "subject": "ref:PT-7731", **AGENT, **NOTE, "quote": "PT-7731 = ex DR-1042"}
SUPERSEDED = {"type": "superseded_by", "subject": "ref:AC-501", "object": "ref:AC-560", **AGENT, **NOTE,
              "quote": "AC-501 superseded by AC-560"}


def verdicts(m):
    return {(o.variant, m.name(o.part)): m.verdicts[o.design.id].verdict for o in m.occurrences}


def obsolete(m):
    return {(o.variant, m.name(o.part)): o.obsolete_parts for o in m.occurrences}


def test_with_no_claims_every_spelling_is_its_own_part_and_nothing_is_shared(tiny, tmp_path):
    m = model(tiny, tmp_path)
    assert len(m.designs) == 2
    assert set(verdicts(m).values()) == {"specific"}
    assert [i["type"] for i in m.issues].count("unknown_unit") == 1  # 2400 mm: no claim says what mm is


def test_spelling_and_unit_claims_make_the_two_door_leaves_one_design(tiny, tmp_path):
    # The worked example of the plan: 2.4 m and 2400 mm of the same seal under two spellings.
    m = model(tiny, tmp_path, SEAL, MM)
    assert len(m.designs) == 1
    assert verdicts(m) == {("V1", "DR-1042"): "reused", ("V2", "PT-7731"): "reused"}
    assert m.designs[0].lines[m.part_of["JT-218"]] == Decimal("2.4")
    assert m.part_of["JT 218"] == m.part_of["JT-218"]


def test_a_same_as_claim_on_the_sub_assemblies_makes_them_one_part(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, RENUMBERED)
    assert m.part_of["PT-7731"] == m.part_of["DR-1042"]
    assert m.parts[m.part_of["PT-7731"]]["spellings"] == ["DR-1042", "PT-7731"]


def test_a_superseded_component_is_named_apart_from_the_verdict_and_not_at_all_without_the_notes(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, SUPERSEDED)
    assert set(verdicts(m).values()) == {"reused"}
    assert next(iter(m.verdicts.values())).reason == "same content in V1, V2 under references DR-1042, PT-7731"
    assert set(obsolete(m).values()) == {"AC-501, superseded by AC-560"}
    plain = model(tiny, tmp_path, without_notes=True)  # same log, replayed without the claims that cite a note
    assert set(verdicts(plain).values()) == {"reused"} and set(obsolete(plain).values()) == {""}
    assert [i["type"] for i in m.issues].count("unresolved_reference") == 1  # AC-560 is in no BOM or ERP row


def test_a_not_same_as_claim_keeps_two_references_apart_even_through_a_chain(tiny, tmp_path):
    # JT-218 = JT218 and JT218 = JT 218 would join JT-218 and JT 218; the veto stops the second link.
    veto = {"type": "not_same_as", "subject": "ref:JT-218", "object": "ref:JT 218", **AGENT}
    chain = {"type": "same_as", "subject": "ref:JT218", "object": "ref:JT 218", "made_by": "rule", "maker": "other"}
    m = model(tiny, tmp_path, SEAL_ERP, chain, veto)
    assert m.part_of["JT-218"] != m.part_of["JT 218"]
    assert [i["type"] for i in m.issues].count("merge_skipped") == 1


def test_group_skips_only_the_link_that_would_join_a_vetoed_pair():
    groups, skipped = group({"a", "b", "c", "d"}, [("a", "b", 1), ("b", "c", 2), ("c", "d", 3)], {frozenset("ac")})
    assert groups["a"] == groups["b"] != groups["c"] == groups["d"]
    assert skipped == [2]


def test_prices_join_through_the_claims_and_a_missing_price_is_never_zero(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, SEAL_ERP, MM)
    assert m.cost[m.part_of["JT-218"]] == Decimal("38.5")
    assert m.cost[m.part_of["AC-501"]] is None  # AC501 is not linked to AC-501 yet
    assert any(i["type"] == "missing_price" and "AC-501" in i["detail"] for i in m.issues)
    assert model(tiny, tmp_path, ACTUATOR_ERP).cost[m.part_of["AC-501"]] == Decimal("412")


def test_two_quantities_for_one_line_are_not_folded_until_a_claim_settles_them(tiny, tmp_path):
    tiny.bom.append({**tiny.bom[3], "row_no": 9, "quantity": "2"})  # AC-501 in DR-1042 again, with 2 instead of 1
    tiny._refs = None
    m = model(tiny, tmp_path, SEAL, MM)
    assert any(i["type"] == "two_quantities" for i in m.issues)
    assert verdicts(m)[("V1", "DR-1042")] == "specific" and "not comparable" in m.verdicts[m.designs[0].id].reason
    settled = model(tiny, tmp_path, {"type": "value_is", "subject": "cell:bom:9:quantity", "value": "1", **AGENT})
    assert not any(i["type"] == "two_quantities" for i in settled.issues)
    assert set(verdicts(settled).values()) == {"reused"}


def test_build_writes_every_table_and_view_and_each_view_can_be_read(tmp_path, rules_log):
    db = tmp_path / "pilot.db"
    summary = build("data/raw", rules_log, db)
    conn = sqlite3.connect(db)
    names = [name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")]
    described = {name for (name,) in conn.execute("SELECT name FROM about")}
    for name in names:
        conn.execute(f"SELECT * FROM {name} LIMIT 1").fetchall()
    assert {n for n in names if n.startswith("v_")} <= described
    assert conn.execute("SELECT COUNT(*) FROM raw_bom").fetchone()[0] == 1538
    assert conn.execute("SELECT COUNT(*) FROM v_verdict").fetchone()[0] == 240 == len(summary.verdicts)
    assert conn.execute("SELECT COUNT(*) FROM v_reuse_between").fetchone()[0] == 6 * 5 * 40


def test_the_evidence_of_a_verdict_lists_the_corrections_its_bom_rows_were_read_with(tmp_path, rules_log):
    db = tmp_path / "pilot.db"
    build("data/raw", rules_log, db)
    conn = sqlite3.connect(db)
    fixes = conn.execute("SELECT detail, claim_id, source_row FROM evidence WHERE kind = 'correction'").fetchall()
    assert all(claim_id for _, claim_id, _ in fixes)
    details = {(detail, source_row) for detail, _, source_row in fixes}
    assert ("V1: row 138 repeats row 137 and is left out", "138") in details  # a repeated row
    assert ("V5: BE-6281: 11000 mm read as 11 m", "1087") in details           # a unit converted
    counted = conn.execute("SELECT SUM(corrections > 0), SUM(corrections) FROM v_verdict").fetchone()
    assert counted[0] > 0 and counted[1] >= len(fixes)


def test_build_replays_without_the_claims_that_rest_on_a_note(tmp_path, rules_log):
    assert build("data/raw", rules_log, tmp_path / "pilot.db", without_notes=True).designs > 0


def test_a_part_with_two_prices_has_no_cost_and_waits_for_a_person(tiny, tmp_path):
    tiny.erp.append({"row_no": 3, "item_ref": "JT 218", "description": "JOINT DE PORTE", "supplier": "Wabtec",
                     "unit_cost_eur": "41,20", "price_unit": "m"})
    tiny._refs = None
    m = model(tiny, tmp_path, SEAL, SEAL_ERP, MM)
    seal = m.part_of["JT-218"]
    assert m.cost[seal] is None and m.cost_status[seal] == "disputed"
    assert any(i["kind"] == "two prices" and "38.5 EUR (row 1), 41.2 EUR (row 3)" in i["detail"] for i in queue(m))
    settled = model(tiny, tmp_path, {"type": "value_is", "subject": "cell:erp:3:unit_cost_eur", "value": "38,50",
                                     "made_by": "person", "maker": "Oscar"})
    assert settled.cost[seal] == Decimal("38.5") and settled.cost_status[seal] == "agreed"


def test_a_cost_total_is_empty_while_a_line_has_no_agreed_price(tmp_path, rules_log):
    # With the rules alone some components have two prices or none. Their sub-assemblies must show no total,
    # name what blocks it, and keep the partial sum apart.
    db = tmp_path / "pilot.db"
    build("data/raw", rules_log, db)
    conn = sqlite3.connect(db)
    blocked = conn.execute("SELECT unit_cost_eur, known_cost_eur, priced_lines, total_lines, blocked_by "
                           "FROM v_subassembly_cost WHERE priced_lines < total_lines").fetchall()
    assert blocked and all(total is None and known is not None and names for total, known, _, _, names in blocked)
    whole = conn.execute("SELECT COUNT(*) FROM v_subassembly_cost WHERE priced_lines = total_lines AND unit_cost_eur IS NULL")
    assert whole.fetchone()[0] == 0
    kinds = dict(conn.execute("SELECT kind, COUNT(*) FROM v_queue GROUP BY 1"))
    assert kinds["two prices"] == 2 and kinds["missing price"] == 7


def test_an_obsolete_own_reference_is_named_for_that_sub_assembly_only_and_both_stay_reused(tiny, tmp_path):
    # PT-7731 and DR-1042 carry the same content. A note retires the reference PT-7731, not the content.
    log = ClaimLog(tmp_path / "claims.jsonl", tiny)
    for claim in (SEAL, MM, OBSOLETE_REF):
        log.append(claim)
    m = compute(tiny, log.claims)
    assert verdicts(m) == {("V1", "DR-1042"): "reused", ("V2", "PT-7731"): "reused"}
    assert obsolete(m) == {("V1", "DR-1042"): "", ("V2", "PT-7731"): "own reference PT-7731, obsolete (same content under DR-1042)"}
    db = tmp_path / "pilot.db"
    write(m, db)
    shown = sqlite3.connect(db).execute(
        "SELECT subassembly_ref, detail, source_row FROM v_evidence WHERE kind = 'claim' AND detail LIKE 'obsolete(%'").fetchall()
    assert shown == [("PT-7731", "obsolete(PT-7731): PT-7731 = ex DR-1042", "TN-0001")]


# A person's inserts and deletes. In the tiny set, row 1 is the door system in V1 and row 2 lists DR-1042 under it
# (JT-218, 2.4 m, and AC-501); row 5 is the door system in V2 and row 6 lists PT-7731 (JT 218, 2400 mm, and AC-501).
PERSON = {"made_by": "person", "maker": "Oscar"}


def delete(row, ref):
    return {"type": "delete_part", "subject": f"bom:{row}", "object": f"ref:{ref}", **PERSON}


def insert(row, child, value):
    return {"type": "insert_part", "subject": f"bom:{row}", "object": child, "value": value, **PERSON}


def content(m, variant):
    """The components of the sub-assembly of `variant`, with their quantities."""
    return {m.name(l["child"]): l["quantity"] for l in m.lines if l["variant"] == variant and l["level"] == 4}


def test_replacing_a_component_makes_two_designs_one_and_the_cost_follows(tiny, tmp_path):
    # With no spelling or unit claim the two door leaves differ by their seal. A person puts the V1 seal in V2.
    m = model(tiny, tmp_path, SEAL_ERP, ACTUATOR_ERP, delete(6, "JT 218"), insert(6, "ref:JT-218", "2.4 m"))
    assert len(m.designs) == 1
    assert verdicts(m) == {("V1", "DR-1042"): "reused", ("V2", "PT-7731"): "reused"}
    assert [c["detail"] for c in m.content_changes] == ["V2: JT 218 deleted from PT-7731 (was no agreed quantity)",
                                                        "V2: JT-218 inserted in PT-7731, 2.4 m"]
    db = tmp_path / "pilot.db"
    write(m, db)
    cost = dict(sqlite3.connect(db).execute("SELECT variant_id, unit_cost_eur FROM v_subassembly_cost"))
    assert cost == {"V1": 504.4, "V2": 504.4}  # 2.4 m of seal at 38.50 and one actuator at 412.00


def test_a_quantity_a_person_chooses_is_a_delete_and_an_insert(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, delete(2, "AC-501"), insert(2, "ref:AC-501", "2 pcs"))
    assert content(m, "V1")["AC-501"] == 2 and len(m.designs) == 2
    m = model(tiny, tmp_path, delete(6, "AC-501"), insert(6, "ref:AC-501", "2 pcs"))  # then the same in V2
    assert len(m.designs) == 1 and set(verdicts(m).values()) == {"reused"}


def test_replacing_a_sub_assembly_copies_the_other_variants_and_the_database_shows_the_claims(tiny, tmp_path):
    # V2 takes the door leaf of V1 in place of its own. The inserted one has no BOM row: the claim stands for it.
    m = model(tiny, tmp_path, delete(5, "PT-7731"), insert(5, "bom:2", "3 pcs"))
    assert verdicts(m) == {("V1", "DR-1042"): "reused", ("V2", "DR-1042"): "reused"}
    assert content(m, "V2") == content(m, "V1") == {"JT-218": Decimal("2.4"), "AC-501": Decimal(1)}
    db = tmp_path / "pilot.db"
    write(m, db)
    conn = sqlite3.connect(db)

    def rows(query):
        return conn.execute(query).fetchall()

    inserted = "V2: DR-1042 inserted in DOOR-SYS-01, 3 per train, 2 components copied from V1 (BOM row 2)"
    assert rows("SELECT * FROM v_content_change") == [
        (1, "V2", 3, "DOOR-SYS-01", "PT-7731", "deleted", 2.0, "pcs", "6", 2, None,
         "V2: PT-7731 deleted from DOOR-SYS-01 (was 2 per train, 2 components)"),
        (2, "V2", 3, "DOOR-SYS-01", "DR-1042", "inserted", 3.0, "pcs", "", 2, 2, inserted)]
    assert rows("SELECT variant_id, component_ref, changed_by_claim FROM v_content ORDER BY 1, 2") == [
        ("V1", "AC-501", None), ("V1", "JT-218", None), ("V2", "AC-501", 2), ("V2", "JT-218", 2)]
    assert rows("SELECT variant_id, subassembly_ref, verdict, content_changes FROM v_verdict ORDER BY 1") == [
        ("V1", "DR-1042", "reused", 1), ("V2", "DR-1042", "reused", 1)]
    assert rows("SELECT kind, detail, claim_id, source_row FROM v_evidence WHERE variant_id = 'V2' ORDER BY 1, 2") == [
        ("bom row", "V1: DR-1042, 2 lines", None, "2"), ("bom row", "V2: DR-1042, 2 lines", None, ""),
        ("content change", inserted, 2, "")]
    assert rows("SELECT variant_id, per_train, raw_rows FROM occurrence ORDER BY 1") == [("V1", 2.0, "2"), ("V2", 3.0, "")]
    described = {name for (name,) in conn.execute("SELECT name FROM about")}
    assert {"content_change", "v_content_change"} <= described


def test_a_component_change_shows_in_the_content_the_evidence_and_the_count(tiny, tmp_path):
    m = model(tiny, tmp_path, delete(6, "JT 218"), insert(6, "ref:JT-218", "2.4 m"))
    db = tmp_path / "pilot.db"
    write(m, db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT variant_id, component_ref, changed_by_claim FROM v_content ORDER BY 1, 2").fetchall() == [
        ("V1", "AC-501", None), ("V1", "JT-218", None), ("V2", "AC-501", None), ("V2", "JT-218", 2)]
    shown = conn.execute("SELECT detail, claim_id, source_row FROM v_evidence WHERE variant_id = 'V1' "
                         "AND kind = 'content change' ORDER BY claim_id").fetchall()  # V1 shares the content of V2
    assert shown == [("V2: JT 218 deleted from PT-7731 (was no agreed quantity)", 1, "7"),
                     ("V2: JT-218 inserted in PT-7731, 2.4 m", 2, "")]
    assert conn.execute("SELECT DISTINCT content_changes FROM v_verdict").fetchall() == [(2,)]


def test_an_inserted_sub_assembly_takes_its_source_as_the_claims_before_it_left_it(tiny, tmp_path):
    m = model(tiny, tmp_path, insert(2, "ref:AC501", "1 pcs"), delete(5, "PT-7731"), insert(5, "bom:2", "2 pcs"))
    assert set(content(m, "V2")) == {"JT-218", "AC-501", "AC501"} and len(m.designs) == 1


def test_deleting_the_superseded_component_empties_obsolete_parts(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, SUPERSEDED, delete(2, "AC-501"))
    assert obsolete(m) == {("V1", "DR-1042"): "", ("V2", "PT-7731"): "AC-501, superseded by AC-560"}


def test_a_delete_finds_the_line_under_another_spelling_of_the_component(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, delete(2, "JT 218"))  # the BOM of V1 writes JT-218
    assert list(content(m, "V1")) == ["AC-501"] and not m.not_applied


@pytest.mark.parametrize("claims, why", [
    ([insert(2, "ref:AC-501", "2 pcs")], "AC-501 is already in DR-1042 in V1; delete it first to change its quantity"),
    ([insert(1, "bom:2", "2 pcs")], "DR-1042 is already in DOOR-SYS-01 in V1"),
    ([delete(1, "DR-1042"), insert(5, "bom:2", "2 pcs")], "row 2 to copy from is no longer in the BOM of V1"),
    ([insert(6, "ref:DR-1042", "1 pcs")], "DR-1042 is not a component"),
    ([insert(2, "ref:AC501", "3 furlongs")], "the unit of '3 furlongs' cannot be converted"),
    ([insert(6, "ref:JT-218", "3 pcs")], "JT-218 is counted in m on its other lines, not in pcs"),
    ([delete(6, "JT-218")], "JT-218 is not in PT-7731 in V2"),
    ([delete(2, "AC-501"), delete(2, "JT-218")], "JT-218 is the only component left in DR-1042"),
    ([delete(1, "DR-1042"), delete(2, "AC-501")], "DR-1042 is no longer in V1"),
])
def test_an_insert_or_delete_that_cannot_be_applied_changes_nothing_and_is_reported(tiny, tmp_path, claims, why):
    before = model(tiny, tmp_path, *claims[:-1])
    m = model(tiny, tmp_path, *claims)
    last = len(claims)
    assert m.lines == before.lines and len(m.content_changes) == last - 1
    assert list(m.not_applied) == [last] and why in m.not_applied[last]
    assert [i["detail"] for i in m.issues if i["type"] == "content_change_not_applied"] == [
        f"claim {last} ({claims[-1]['type']}) was not applied: {m.not_applied[last]}"]


def test_a_sub_assembly_is_not_inserted_in_a_variant_that_lists_it_under_another_system(tiny, tmp_path):
    # A sub-assembly is identified by variant and part, so a variant holds it once.
    two_systems = Raw(tiny.bom + [bom_row(9, "V1", 2, "V1", "HVAC-SYS-01", "HVAC")], tiny.erp, tiny.notes)
    m = model(two_systems, tmp_path, insert(9, "bom:2", "1 pcs"))
    assert m.not_applied == {1: "V1 already lists DR-1042"} and not m.content_changes
