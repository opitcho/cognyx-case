"""The rules: each rule's count on the generated files, that a second run adds nothing, and each rule on a few
hand-made rows."""

from decimal import Decimal

from conftest import bom_row
from pipeline.claims import load
from pipeline.ingest import Raw
from pipeline.refs import normalise, one_apart, swapped
from pipeline import rules
from pipeline.rules import RULES, list_rules, run_rules, show
from pipeline.units import to_base_by_list as to_base

# Measured by .experiments/40_reconciliation_workload.py, except near_key: the probe's pattern needed three
# digits and missed FB-76, a two-digit reference mistyped in a note, which the rule's pattern finds.
EXPECTED = {"same_key": 313, "near_key": 29, "sibling": 2, "unit_list": 5, "same_row": 20, "filler": 19,
            "supplier_key": 3, "note_field": 41}


def test_each_rule_makes_the_number_of_claims_the_probe_measured(raw):
    assert {rule.__name__: len(rule(raw)) for rule in RULES} == EXPECTED


def test_rules_only_assert_what_is_mechanical(raw):
    proposed = {(c["maker"], c["type"]) for rule in RULES for c in rule(raw) if c["standing"] == "proposed"}
    assert proposed == {("near_key", "same_as"), ("supplier_key", "same_as")}


def test_running_the_rules_twice_writes_each_claim_once(tmp_path):
    log = tmp_path / "claims.jsonl"
    first = run_rules(log, "data/raw")
    second = run_rules(log, "data/raw")
    assert {name: new for name, (_, new) in first.items()} == EXPECTED
    assert all(new == 0 for _, new in second.values())
    assert len(load(log)) == sum(EXPECTED.values())


def test_the_list_has_each_rule_with_its_description_and_what_it_makes(raw):
    lines = list_rules(raw)
    assert [line.split()[0] for line in lines[::2]] == [rule.__name__ for rule in RULES]
    assert lines[2].endswith("may be one part: a proposal only.") and lines[3].endswith("makes 29 same_as proposed")
    assert lines[-1].endswith("makes 41 mentions asserted")


def test_show_marks_a_changed_rule_against_the_log_and_writes_nothing(raw, rules_log, monkeypatch):
    before = rules_log.read_bytes()
    assert [line[0] for line in show(rules.unit_list, raw, rules_log)[:-1]] == [" "] * 5

    monkeypatch.setitem(rules.UNIT_LIST, "mm", ("m", "0.01"))  # one factor changed: one claim gone, one new
    monkeypatch.delitem(rules.UNIT_LIST, "u")
    lines = show(rules.unit_list, raw, rules_log)
    assert sorted(line.split(" [")[0] for line in lines if line[0] in "+-") == [
        "+ converts_to unit:mm -> unit:m = 0.01", "- converts_to unit:U -> unit:pcs = 1",
        "- converts_to unit:mm -> unit:m = 0.001"]
    assert "1 not in the log (+)" in lines[-2] and "2 in the log and no longer made (-)" in lines[-2]

    def all_asserted(raw):
        return [{**c, "standing": "asserted"} for c in rules.near_key(raw)]
    all_asserted.__name__ = "near_key"
    assert {line[0] for line in show(all_asserted, raw, rules_log)[:-2]} == {"~"}
    assert rules_log.read_bytes() == before


def test_normalise_reads_o_as_zero_only_after_a_two_letter_prefix():
    assert normalise("DR-1O42") == normalise("dr 1042") == "DR1042"
    assert normalise("DOOR-SYS-01") == "DOORSYS01"  # the letters of a system reference are left alone


def test_closeness_tests():
    assert one_apart("DR1042", "DR1043") and one_apart("PF253", "PF2533") and not one_apart("RL205", "RL025")
    assert swapped("RL205", "RL025") and not swapped("DR1042", "DR1043")
    assert not one_apart("DR1042", "DR1042")


def test_quantities_convert_by_the_fixed_list():
    assert to_base("2400", "mm") == to_base("2.4", "m")
    assert to_base("1", "PCE") == to_base("1", "U") == to_base("1", "pcs")
    assert to_base("3", "furlong") is None


def test_a_quantity_or_a_unit_that_is_not_understood_converts_to_nothing():
    assert to_base("2,4", "m") == to_base("2.40", "m") == (Decimal("2.4"), "m")
    assert to_base("1", "MM") == (Decimal("0.001"), "m") and to_base("500", "g") == (Decimal("0.5"), "kg")
    assert to_base("", "m") is None and to_base("two", "m") is None and to_base("1.2.3", "m") is None
    assert to_base("1", "") is None and to_base("1", "unit") is None


# ---------------------------------------------------------------- each rule on a few hand-made rows


def erp_row(row_no, item_ref, supplier="Faiveley", cost="10,00", price_unit="pcs"):
    return {"row_no": row_no, "item_ref": item_ref, "description": "PART", "supplier": supplier,
            "unit_cost_eur": cost, "price_unit": price_unit}


def note(row_no, note_id, reference="", text=""):
    return {"row_no": row_no, "note_id": note_id, "date": "2025-01-10", "reference": reference, "text": text}


def triples(claims):
    return [(c["subject"], c["object"], c["standing"]) for c in claims]


def test_same_key_points_each_other_spelling_at_the_one_the_bom_uses_most():
    raw = Raw([bom_row(1, "V1", 3, "DOOR-SYS-01", "JT-218"), bom_row(2, "V2", 3, "DOOR-SYS-01", "JT-218"),
               bom_row(3, "V3", 3, "DOOR-SYS-01", "JT 218"), bom_row(4, "V1", 3, "DOOR-SYS-01", "AC-501")],
              [erp_row(1, "jt218"), erp_row(2, "AC-501")], [note(1, "TN-1", text="Seal JT-2I8 checked.")])
    claims = rules.same_key(raw)
    assert triples(claims) == [("ref:JT 218", "ref:JT-218", "asserted"), ("ref:jt218", "ref:JT-218", "asserted")]
    assert [c["evidence"] for c in claims] == [["bom:3", "bom:1"], ["erp:1", "bom:1"]]  # JT-2I8 has another key


def test_same_key_takes_the_first_spelling_in_alphabetical_order_when_the_bom_uses_none_more():
    raw = Raw([bom_row(1, "V1", 3, "DOOR-SYS-01", "JT-218"), bom_row(2, "V2", 3, "DOOR-SYS-01", "JT 218")], [], [])
    assert triples(rules.same_key(raw)) == [("ref:JT-218", "ref:JT 218", "asserted")]


def test_near_key_proposes_two_references_one_character_apart_or_swapped_and_no_others():
    raw = Raw([bom_row(1, "V1", 3, "DOOR-SYS-01", "DR-1042"), bom_row(2, "V2", 3, "DOOR-SYS-01", "DR-1043"),
               bom_row(3, "V1", 3, "DOOR-SYS-01", "RL-205"), bom_row(4, "V1", 3, "DOOR-SYS-01", "AC-501")],
              [erp_row(1, "RL025")], [])
    claims = rules.near_key(raw)
    assert triples(claims) == [("ref:DR-1042", "ref:DR-1043", "proposed"), ("ref:RL025", "ref:RL-205", "proposed")]
    assert [c["reason"] for c in claims] == ["one character apart", "two neighbouring characters swapped"]
    assert [c["evidence"] for c in claims] == [["bom:1", "bom:2"], ["erp:1", "bom:3"]]


def test_near_key_compares_keys_so_two_spellings_of_one_reference_are_not_a_near_pair():
    raw = Raw([bom_row(1, "V1", 3, "DOOR-SYS-01", "DR-1042"), bom_row(2, "V2", 3, "DOOR-SYS-01", "DR 1042")], [], [])
    assert rules.near_key(raw) == []


def test_sibling_keeps_apart_two_near_references_under_one_parent_in_one_variant_only():
    together = [bom_row(1, "V1", 3, "DOOR-SYS-01", "DR-1042"), bom_row(2, "V1", 3, "DOOR SYS 01", "dr 1043")]
    claims = rules.sibling(Raw(together, [], []))
    assert triples(claims) == [("ref:DR-1042", "ref:dr 1043", "asserted")]
    assert (claims[0]["type"], claims[0]["evidence"]) == ("not_same_as", ["bom:1", "bom:2"])
    other_variant = [together[0], bom_row(2, "V2", 3, "DOOR-SYS-01", "DR-1043")]
    other_parent = [together[0], bom_row(2, "V1", 3, "HVAC-SYS-01", "DR-1043")]
    assert rules.sibling(Raw(other_variant, [], [])) == [] and rules.sibling(Raw(other_parent, [], [])) == []


def test_unit_list_converts_the_listed_units_as_written_and_leaves_base_and_unknown_units():
    raw = Raw([bom_row(1, "V1", 3, "DOOR-SYS-01", "A-1", unit="mm"), bom_row(2, "V1", 3, "DOOR-SYS-01", "A-2", unit="PCE"),
               bom_row(3, "V1", 3, "DOOR-SYS-01", "A-3", unit="m"), bom_row(4, "V1", 3, "DOOR-SYS-01", "A-4", unit="unit")],
              [erp_row(1, "A-1", price_unit="mm"), erp_row(2, "A-2", price_unit="g")], [])
    assert [(c["type"], c["subject"], c["object"], c["value"]) for c in rules.unit_list(raw)] == [
        ("converts_to", "unit:PCE", "unit:pcs", "1"), ("converts_to", "unit:g", "unit:kg", "0.001"),
        ("converts_to", "unit:mm", "unit:m", "0.001")]


def test_same_row_folds_a_repeated_line_only_when_the_quantity_is_the_same_once_converted():
    line = lambda row_no, quantity, unit, variant="V1", child="JT-218": bom_row(row_no, variant, 4, "DR-1042", child, quantity=quantity, unit=unit)
    raw = Raw([line(1, "2.4", "m"), line(2, "2400", "mm", child="jt 218"), line(3, "2,40", "m"), line(4, "3", "m"),
               line(5, "2.4", "m", variant="V2"), line(6, "?", "m", child="AC-501"), line(7, "?", "m", child="AC-501")], [], [])
    claims = rules.same_row(raw)
    assert [(c["type"], c["subject"], c["object"]) for c in claims] == [("duplicate_of", "bom:2", "bom:1"),
                                                                       ("duplicate_of", "bom:3", "bom:1")]


def test_filler_marks_an_empty_or_filler_supplier_or_cost_and_no_other_cell():
    raw = Raw([], [erp_row(1, "A-1", supplier="N/A", cost=""), erp_row(2, "A-2", supplier=" tbd ", cost="0"),
                   erp_row(3, "A-3", supplier="Unknown Parts Ltd", cost="-")], [])
    raw.erp[1]["description"] = ""
    claims = rules.filler(raw)
    assert [(c["type"], c["subject"]) for c in claims] == [
        ("no_value", "cell:erp:1:supplier"), ("no_value", "cell:erp:1:unit_cost_eur"),
        ("no_value", "cell:erp:2:supplier"), ("no_value", "cell:erp:3:unit_cost_eur")]
    assert [c["reason"] for c in claims] == ["'N/A' is a filler", "the cell is empty", "' tbd ' is a filler", "'-' is a filler"]


def test_supplier_key_asserts_names_equal_without_case_and_punctuation_and_proposes_a_longer_name():
    suppliers = ["Sofra-Tec", "Sofra-Tec", "SOFRATEC", "sofra tec", "Sofratec Rail SAS", "Knorr", "N/A", ""]
    raw = Raw([], [erp_row(n, f"A-{n}", supplier=name) for n, name in enumerate(suppliers, 1)], [])
    claims = rules.supplier_key(raw)
    assert triples(claims) == [("supplier:SOFRATEC", "supplier:Sofra-Tec", "asserted"),
                               ("supplier:sofra tec", "supplier:Sofra-Tec", "asserted"),
                               ("supplier:Sofra-Tec", "supplier:Sofratec Rail SAS", "proposed")]
    assert [c["evidence"] for c in claims] == [["erp:3", "erp:1"], ["erp:4", "erp:1"], ["erp:1", "erp:5"]]


def test_note_field_links_a_note_to_its_reference_field_and_not_to_references_in_its_text():
    raw = Raw([], [], [note(1, "TN-1", "PT-7731", "PT-7731 = ex DR-1042."), note(2, "TN-2", "", "See DR-1042.")])
    assert [(c["type"], c["subject"], c["object"], c["evidence"]) for c in rules.note_field(raw)] == [
        ("mentions", "note:TN-1", "ref:PT-7731", ["note:TN-1"])]


def test_every_rule_makes_nothing_from_empty_files_and_signs_its_claims_with_its_name(tiny):
    assert all(rule(Raw([], [], [])) == [] for rule in RULES)
    assert all(c["made_by"] == "rule" and c["maker"] == rule.__name__ for rule in RULES for c in rule(tiny))
