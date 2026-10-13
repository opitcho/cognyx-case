"""Comparison by content, on hand-made designs: the hash, the grouping into designs, the differing lines and
the pairs."""

from decimal import Decimal

from pipeline.compare import (MAX_DIFF, MIN_SHARED, Design, DiffLine, Occurrence, Pair, Relations, build_designs,
                              content_hash, diff_lines, find_pairs)

SHARED = {f"S{n}": "1" for n in range(1, MIN_SHARED + 1)}  # enough shared components for a near pair
VARIANTS = {"V1": {"cars": "4", "speed_class_kmh": "160", "interior": "suburban"},
            "V2": {"cars": "6", "speed_class_kmh": "160", "interior": "suburban"},
            "V3": {"cars": "6", "speed_class_kmh": "200", "interior": "regional"}}


def quantities(lines):
    return {part: None if qty is None else Decimal(qty) for part, qty in lines.items()}


def design(id, lines, variants=("V1",), system="DOOR", comparable=True):
    """A design with one occurrence per variant, under the reference SA-<id>."""
    d = Design(id, "", system, quantities(lines), comparable)
    d.occurrences = [Occurrence(variant, f"SA-{id}", system, Decimal(1), []) for variant in variants]
    return d


def relation(type, a, b=None, claim_id=1, option=None):
    return {"type": type, "part_a": a, "part_b": b, "claim_id": claim_id, "option": option}


def line_tuples(lines):
    return [(line.part_a, line.part_b, line.explanation, line.claim_id) for line in lines]


# ---------------------------------------------------------------- content_hash


def test_the_hash_ignores_how_a_quantity_is_written_and_the_order_of_the_lines():
    assert content_hash({"A": Decimal("2.4"), "B": Decimal("1")}) == content_hash({"B": Decimal("1.0"), "A": Decimal("2.400")})
    assert content_hash({"A": Decimal("100")}) == content_hash({"A": Decimal("1E+2")})


def test_the_hash_ignores_a_difference_past_six_decimal_places():
    assert content_hash({"A": Decimal("2.4")}) == content_hash({"A": Decimal("2.4000001")})
    assert content_hash({"A": Decimal("2.4")}) != content_hash({"A": Decimal("2.400001")})


def test_the_hash_tells_apart_a_part_a_quantity_and_a_quantity_that_is_not_agreed():
    base = content_hash({"A": Decimal("1")})
    assert base != content_hash({"B": Decimal("1")})
    assert base != content_hash({"A": Decimal("2")})
    assert content_hash({"A": None}) != content_hash({"A": Decimal("0")})


# ---------------------------------------------------------------- build_designs


def occurrence(variant, part, system="DOOR"):
    return Occurrence(variant, part, system, Decimal(1), [])


def test_the_same_content_in_two_variants_is_one_design_whatever_the_reference():
    occurrences = [occurrence("V2", "PT-7731"), occurrence("V1", "DR-1042")]
    content = {("V1", "DR-1042"): quantities({"JT": "2.4", "AC": "1"}),
               ("V2", "PT-7731"): quantities({"AC": "1.0", "JT": "2.400"})}
    designs = build_designs(occurrences, content)
    assert [(d.id, d.variants, d.parts, d.comparable) for d in designs] == [("D001", ["V1", "V2"], ["DR-1042", "PT-7731"], True)]
    assert all(o.design is designs[0] for o in occurrences)


def test_a_different_quantity_or_another_system_makes_another_design():
    occurrences = [occurrence("V1", "DR-1"), occurrence("V2", "DR-1"), occurrence("V3", "DR-1", system="HVAC")]
    content = {("V1", "DR-1"): quantities({"JT": "2"}), ("V2", "DR-1"): quantities({"JT": "3"}),
               ("V3", "DR-1"): quantities({"JT": "2"})}
    designs = build_designs(occurrences, content)
    assert [(d.id, d.system, d.variants) for d in designs] == [("D001", "DOOR", ["V1"]), ("D002", "DOOR", ["V2"]),
                                                                ("D003", "HVAC", ["V3"])]


def test_a_content_with_a_quantity_not_agreed_is_never_merged_even_with_an_identical_one():
    occurrences = [occurrence("V1", "DR-1"), occurrence("V2", "DR-1")]
    content = {("V1", "DR-1"): quantities({"JT": None, "AC": "1"}), ("V2", "DR-1"): quantities({"JT": None, "AC": "1"})}
    designs = build_designs(occurrences, content)
    assert [(d.variants, d.comparable) for d in designs] == [(["V1"], False), (["V2"], False)]
    assert designs[0].hash == designs[1].hash


def test_a_sub_assembly_with_no_lines_is_not_comparable_and_stays_alone():
    designs = build_designs([occurrence("V1", "DR-1"), occurrence("V2", "DR-1")], {})
    assert [(d.variants, d.lines, d.comparable) for d in designs] == [(["V1"], {}, False), (["V2"], {}, False)]


# ---------------------------------------------------------------- Relations


def test_relations_answer_in_either_order_and_skip_a_relation_whose_part_is_unknown():
    relations = Relations([relation("interchangeable_with", "A", "B", 7), relation("obsolete", None, None, 8),
                           relation("required_for", "R", None, 9, "200 km/h")])
    assert relations.swap("A", "B") == relations.swap("B", "A") == ("interchangeable", 7)
    assert relations.swap("A", "R") is None
    assert relations.required("R") == (9, "200 km/h") and relations.required("A") is None
    assert relations.dead("A") is None


def test_interchangeable_wins_over_superseded_for_one_pair_in_either_order_of_the_claims():
    both = [relation("superseded_by", "A", "B", 1), relation("interchangeable_with", "B", "A", 2)]
    for relations in (Relations(both), Relations(both[::-1])):
        assert relations.swap("A", "B") == ("interchangeable", 2)
        assert relations.dead("A") == (1, "B") and relations.dead("B") is None


def test_a_superseded_part_keeps_its_replacement_when_it_is_also_called_obsolete():
    both = [relation("obsolete", "A", None, 1), relation("superseded_by", "A", "B", 2)]
    for relations in (Relations(both), Relations(both[::-1])):
        assert relations.dead("A") == (2, "B")
    assert Relations([relation("obsolete", "A", None, 1)]).dead("A") == (1, None)


# ---------------------------------------------------------------- diff_lines


def test_identical_contents_have_no_differing_line():
    assert diff_lines(design("A", SHARED), design("B", SHARED), Relations([]), {}) == []


def test_a_changed_quantity_is_one_line_with_the_part_on_both_sides():
    a, b = design("A", {"JT": "2", "AC": "1"}), design("B", {"JT": "3", "AC": "1"})
    assert diff_lines(a, b, Relations([]), {}) == [DiffLine("JT", "JT", Decimal(2), Decimal(3))]


def test_parts_on_one_side_only_are_paired_in_order_and_a_leftover_has_one_side_empty():
    a, b = design("A", {"P1": "1", "P2": "1", "P3": "1"}), design("B", {"Q1": "1", "Q2": "1"})
    assert line_tuples(diff_lines(a, b, Relations([]), {})) == [
        ("P1", "Q1", "unexplained", None), ("P2", "Q2", "unexplained", None), ("P3", None, "unexplained", None)]
    assert line_tuples(diff_lines(b, a, Relations([]), {}))[-1] == (None, "P3", "unexplained", None)


def test_a_relation_pairs_two_parts_before_the_rest_are_paired_in_order():
    a, b = design("A", {"P1": "1", "P2": "1"}), design("B", {"Q1": "1", "Q2": "1"})
    relations = Relations([relation("interchangeable_with", "Q2", "P1", 5)])
    assert line_tuples(diff_lines(a, b, relations, {})) == [("P1", "Q2", "interchangeable", 5),
                                                             ("P2", "Q1", "unexplained", None)]


def test_a_superseded_part_swapped_for_its_replacement_is_explained_by_that_claim():
    a, b = design("A", {"AC-501": "1"}), design("B", {"AC-560": "1"})
    relations = Relations([relation("superseded_by", "AC-501", "AC-560", 4)])
    assert line_tuples(diff_lines(a, b, relations, {})) == [("AC-501", "AC-560", "superseded", 4)]


def test_a_part_required_for_an_option_explains_its_line_on_either_side_but_not_a_line_already_explained():
    relations = Relations([relation("required_for", "Q1", None, 9, "200 km/h"),
                           relation("required_for", "P2", None, 8, "200 km/h"),
                           relation("interchangeable_with", "P2", "Q2", 5)])
    a, b = design("A", {"P1": "1", "P2": "1"}), design("B", {"Q1": "1", "Q2": "1"})
    assert line_tuples(diff_lines(a, b, relations, {})) == [("P2", "Q2", "interchangeable", 5),
                                                             ("P1", "Q1", "required_by_option", 9)]
    assert line_tuples(diff_lines(b, a, relations, {}))[-1] == ("Q1", "P1", "required_by_option", 9)


def test_the_cost_gap_is_side_b_minus_side_a_and_is_empty_when_a_price_or_a_quantity_is_missing():
    cost = {"P": Decimal(10), "Q": Decimal(15), "X": None}
    gap = lambda a, b: [line.cost_gap for line in diff_lines(design("A", a), design("B", b), Relations([]), cost)]
    assert gap({"P": "2"}, {"Q": "2"}) == [Decimal(10)]   # a swap: 2 x 15 - 2 x 10
    assert gap({"P": "2"}, {"P": "3"}) == [Decimal(10)]   # one more of the same part
    assert gap({"P": "2"}, {}) == [Decimal(-20)]          # a part side b does not have
    assert gap({"P": "2"}, {"X": "2"}) == [None]          # X has no agreed price
    assert gap({"P": "2"}, {"Z": "2"}) == [None]          # Z has no price at all
    assert gap({"P": None}, {"P": "2"}) == [None]         # no agreed quantity


def test_a_pairs_cost_gap_is_the_sum_of_its_lines_and_is_empty_when_one_line_has_none():
    a, b = design("A", {}), design("B", {})
    lines = [DiffLine("P", "Q", Decimal(1), Decimal(1), cost_gap=Decimal(5)),
             DiffLine("R", None, Decimal(1), None, cost_gap=Decimal(-2))]
    assert Pair(1, a, b, "near", 4, 2, lines, []).cost_gap == Decimal(3)
    lines.append(DiffLine("X", "Y", Decimal(1), Decimal(1)))
    assert Pair(1, a, b, "near", 4, 3, lines, []).cost_gap is None
    assert Pair(1, a, b, "functional", 0, 0, [], []).cost_gap == Decimal(0)


# ---------------------------------------------------------------- find_pairs


def with_extras(count, shared=SHARED):
    return {**shared, **{f"E{n}": "1" for n in range(1, count + 1)}}


def pairs_of(*designs, relations=()):
    return find_pairs(list(designs), Relations(list(relations)), {}, VARIANTS)


def test_a_near_pair_has_one_to_max_diff_differing_lines():
    base = design("D001", SHARED)
    assert pairs_of(base, design("D002", SHARED, ("V2",))) == []  # nothing differs: build_designs would merge them
    assert [p.n_differing for p in pairs_of(base, design("D002", with_extras(1), ("V2",)))] == [1]
    assert [p.n_differing for p in pairs_of(base, design("D002", with_extras(MAX_DIFF), ("V2",)))] == [MAX_DIFF]
    assert pairs_of(base, design("D002", with_extras(MAX_DIFF + 1), ("V2",))) == []


def test_a_near_pair_shares_at_least_min_shared_components():
    few = {part: "1" for part in list(SHARED)[:MIN_SHARED - 1]}
    assert pairs_of(design("D001", few), design("D002", with_extras(1, few), ("V2",))) == []
    pair, = pairs_of(design("D001", SHARED), design("D002", with_extras(1), ("V2",)))
    assert (pair.kind, pair.n_shared, pair.claim_id) == ("near", MIN_SHARED, None)


def test_a_component_shared_with_another_quantity_counts_as_shared_and_as_a_differing_line():
    pair, = pairs_of(design("D001", SHARED), design("D002", {**SHARED, "S1": "2"}, ("V2",)))
    assert (pair.n_shared, pair.n_differing) == (MIN_SHARED, 1)


def test_no_near_pair_across_systems_or_with_a_design_that_is_not_comparable():
    base = design("D001", SHARED)
    assert pairs_of(base, design("D002", with_extras(1), ("V2",), system="HVAC")) == []
    assert pairs_of(base, design("D002", with_extras(1), ("V2",), comparable=False)) == []


def test_side_a_is_the_design_used_in_more_variants_then_the_lower_id():
    one, two = design("D001", with_extras(1), ("V1",)), design("D002", SHARED, ("V2", "V3"))
    pair, = pairs_of(one, two)
    assert (pair.a, pair.b) == (two, one)
    assert line_tuples(pair.lines) == [(None, "E1", "unexplained", None)]
    pair, = pairs_of(design("D002", SHARED, ("V2",)), design("D001", with_extras(1), ("V1",)))
    assert (pair.a.id, pair.b.id) == ("D001", "D002")


def test_a_pair_lists_the_options_that_split_its_variants_cleanly():
    pair, = pairs_of(design("D001", SHARED, ("V1", "V2")), design("D002", with_extras(1), ("V3",)))
    assert pair.separating_options == ["speed_class_kmh", "interior"]  # cars is 6 in both V2 and V3
    pair, = pairs_of(design("D001", SHARED, ("V1",)), design("D002", with_extras(1), ("V2",)))
    assert pair.separating_options == ["cars"]


def test_a_claim_that_two_sub_assemblies_do_the_same_job_makes_a_functional_pair():
    a, b = design("D001", {"P1": "1"}), design("D002", {"Q1": "1", "Q2": "1"}, ("V2",), comparable=False)
    pair, = pairs_of(a, b, relations=[relation("functionally_equivalent_to", "SA-D001", "SA-D002", 12)])
    assert (pair.kind, pair.claim_id, pair.n_shared, pair.n_differing) == ("functional", 12, 0, 2)
    assert pairs_of(a, b, relations=[relation("functionally_equivalent_to", "P1", "Q1", 12)]) == []  # components, not sub-assemblies


def test_a_functional_claim_adds_nothing_to_a_pair_that_is_already_near_or_to_one_design():
    a, b = design("D001", SHARED), design("D002", with_extras(1), ("V2",))
    equivalent = relation("functionally_equivalent_to", "SA-D001", "SA-D002", 12)
    assert [p.kind for p in pairs_of(a, b, relations=[equivalent])] == ["near"]
    assert [p.kind for p in pairs_of(a, b, relations=[equivalent, {**equivalent, "claim_id": 13}])] == ["near"]
    assert pairs_of(a, relations=[relation("functionally_equivalent_to", "SA-D001", "SA-D001", 12)]) == []


def test_pairs_are_numbered_from_one_in_the_order_found():
    designs = [design("D001", SHARED), design("D002", with_extras(1), ("V2",)), design("D003", with_extras(2), ("V3",))]
    assert [(p.id, p.a.id, p.b.id) for p in pairs_of(*designs)] == [(1, "D001", "D002"), (2, "D001", "D003"), (3, "D002", "D003")]
