"""build(): claims in force change the resolved model; nothing else does."""

import sqlite3
from decimal import Decimal

import pytest

from pipeline.build import build, compute
from pipeline.claims import ClaimLog
from pipeline.reports import queue
from pipeline.resolve import group

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
    return {(o.variant, m.name(o.part)): o.verdict.verdict for o in m.occurrences}


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


def test_a_superseded_component_blocks_what_would_be_reused_and_bom_only_shows_the_difference(tiny, tmp_path):
    m = model(tiny, tmp_path, SEAL, MM, SUPERSEDED)
    assert set(verdicts(m).values()) == {"blocked"}
    assert "contains AC-501, superseded by AC-560" in next(iter(m.verdicts.values())).reason
    plain = model(tiny, tmp_path, without_notes=True)  # same log, replayed without the claims that cite a note
    assert set(verdicts(plain).values()) == {"reused"}
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


@pytest.mark.parametrize("filters", [{"without_notes": True}, {"made_by": {"rule"}}, {"up_to": 5}])
def test_build_replays_with_claims_left_out(tmp_path, rules_log, filters):
    assert build("data/raw", rules_log, tmp_path / "pilot.db", **filters).designs > 0


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


def test_a_sub_assembly_whose_own_reference_is_obsolete_is_blocked_while_its_twin_design_stays_reused(tiny, tmp_path):
    # PT-7731 and DR-1042 carry the same content. A note retires the reference PT-7731, not the content.
    m = model(tiny, tmp_path, SEAL, MM, OBSOLETE_REF)
    assert verdicts(m) == {("V1", "DR-1042"): "reused", ("V2", "PT-7731"): "blocked"}
    blocked = next(o for o in m.occurrences if m.name(o.part) == "PT-7731")
    assert "the reference PT-7731 is obsolete; the same content is carried by DR-1042" in blocked.verdict.reason
