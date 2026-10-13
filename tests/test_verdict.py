"""decide(): one test per branch of the verdict, on hand-made designs and pairs. Then the obsolete parts."""

from pipeline.compare import Pair, Relations, diff_lines
from pipeline.verdict import VERDICTS, decide, describe_obsolete, obsolete_components

from test_compare import SHARED, design, relation, with_extras


def pair(id, a, b, relations, kind="near", claim_id=None):
    lines = diff_lines(a, b, relations, {})
    return Pair(id, a, b, kind, len(set(a.lines) & set(b.lines)), len(lines), lines, [], claim_id)


def verdict_of(d, pairs=()):
    verdict = decide(d, list(pairs), lambda part: part)
    assert verdict.verdict in VERDICTS
    return verdict


def test_the_same_content_in_two_variants_is_reused():
    verdict = verdict_of(design("A", SHARED, ("V2", "V1")))
    assert (verdict.verdict, verdict.reason) == ("reused", "same content in V1, V2")
    assert (verdict.counterpart, verdict.claim_ids, verdict.pair) == (None, [], None)


def test_a_reused_design_under_two_references_names_them():
    d = design("A", SHARED, ("V1", "V2"))
    d.occurrences[1].part = "PT-7731"
    assert verdict_of(d).reason == "same content in V1, V2 under references PT-7731, SA-A"


def test_a_design_in_one_variant_with_a_quantity_not_agreed_is_specific_whatever_its_pairs():
    d, other = design("A", {**SHARED, "E1": None}, comparable=False), design("B", SHARED, ("V2",))
    relations = Relations([relation("functionally_equivalent_to", "SA-A", "SA-B", 3)])
    verdict = verdict_of(d, [pair(1, d, other, relations, "functional", 3)])
    assert (verdict.verdict, verdict.reason) == ("specific", "not comparable: a line has no agreed quantity")


def test_a_design_with_no_pair_is_specific():
    verdict = verdict_of(design("A", SHARED))
    assert (verdict.verdict, verdict.reason, verdict.counterpart) == ("specific", "no counterpart in another variant", None)


def test_a_near_pair_that_no_option_requires_makes_both_designs_reusable():
    relations = Relations([relation("interchangeable_with", "E1", "F1", 5)])
    a, b = design("A", {**SHARED, "E1": "1", "E2": "1"}), design("B", {**SHARED, "F1": "1"}, ("V2",))
    near = pair(1, a, b, relations)
    verdict = verdict_of(a, [near])
    assert (verdict.verdict, verdict.reason) == ("reusable", "differs from SA-B by 2 line(s): interchangeable, unexplained")
    assert (verdict.counterpart, verdict.claim_ids, verdict.pair) == (b, [5], near)
    assert verdict_of(b, [near]).counterpart is a


def test_a_near_pair_whose_difference_an_option_requires_leaves_the_design_specific():
    relations = Relations([relation("required_for", "E1", None, 9, "200 km/h")])
    a, b = design("A", with_extras(2)), design("B", SHARED, ("V2",))
    near = pair(1, a, b, relations)
    verdict = verdict_of(a, [near])
    assert (verdict.verdict, verdict.reason) == ("specific", "its difference from SA-B is required by an option")
    assert (verdict.counterpart, verdict.claim_ids, verdict.pair) == (b, [9], near)


def test_a_claim_that_another_design_does_the_same_job_makes_it_reusable_and_comes_before_a_required_difference():
    relations = Relations([relation("required_for", "E1", None, 9, "200 km/h"),
                           relation("functionally_equivalent_to", "SA-A", "SA-C", 12)])
    a, b, c = design("A", with_extras(1)), design("B", SHARED, ("V2",)), design("C", {"Q1": "1"}, ("V3",))
    functional = pair(2, a, c, relations, "functional", 12)
    verdict = verdict_of(a, [pair(1, a, b, relations), functional])
    assert (verdict.verdict, verdict.reason) == ("reusable", "a note says it does the same job as SA-C")
    assert (verdict.counterpart, verdict.claim_ids, verdict.pair) == (c, [12], functional)


def test_a_free_near_pair_comes_before_a_functional_pair():
    relations = Relations([relation("functionally_equivalent_to", "SA-A", "SA-C", 12)])
    a, b, c = design("A", with_extras(1)), design("B", SHARED, ("V2",)), design("C", {"Q1": "1"}, ("V3",))
    verdict = verdict_of(a, [pair(1, a, c, relations, "functional", 12), pair(2, a, b, relations)])
    assert (verdict.verdict, verdict.counterpart) == ("reusable", b)


def test_the_counterpart_is_the_design_in_the_most_variants_then_the_fewest_differing_lines_then_the_first_pair():
    a = design("A", with_extras(1))
    close, wide = design("B", SHARED, ("V2",)), design("C", with_extras(3), ("V2", "V3"))
    pairs = [pair(1, a, close, Relations([])), pair(2, a, wide, Relations([]))]
    assert verdict_of(a, pairs).counterpart is wide          # 2 lines away but in two variants
    far = design("D", with_extras(2), ("V3",))
    pairs = [pair(1, a, far, Relations([])), pair(2, a, close, Relations([]))]
    assert verdict_of(a, pairs).counterpart is far           # both 1 line away, in one variant: the first pair
    farther = design("E", with_extras(3), ("V3",))
    pairs = [pair(1, a, farther, Relations([])), pair(2, a, close, Relations([]))]
    assert verdict_of(a, pairs).counterpart is close         # 1 line away against 2


def obsolete_of(d, relations, variant="V1"):
    for occurrence in d.occurrences:
        occurrence.design = d
    return describe_obsolete(next(o for o in d.occurrences if o.variant == variant), relations, lambda part: part)


def test_a_design_holding_a_superseded_or_obsolete_component_keeps_its_verdict_and_names_the_parts():
    relations = Relations([relation("superseded_by", "S1", "S9", 4), relation("obsolete", "S2", None, 6)])
    d = design("A", SHARED, ("V1", "V2"))
    assert verdict_of(d).verdict == "reused"
    assert obsolete_components(d, relations) == [("S1", 4, "S9"), ("S2", 6, None)]
    assert obsolete_of(d, relations) == obsolete_of(d, relations, "V2") == "S1, superseded by S9; S2, obsolete"


def test_a_design_with_no_obsolete_part_has_an_empty_text():
    d = design("A", SHARED, ("V1", "V2"))
    assert obsolete_components(d, Relations([])) == [] and obsolete_of(d, Relations([])) == ""


def test_an_obsolete_own_reference_is_named_with_the_reference_that_carries_the_same_content():
    relations = Relations([relation("obsolete", "PT-7731", None, 6)])
    d = design("A", SHARED, ("V1", "V2"))
    d.occurrences[1].part = "PT-7731"
    assert obsolete_of(d, relations, "V2") == "own reference PT-7731, obsolete (same content under SA-A)"
    assert obsolete_of(d, relations, "V1") == ""  # the other reference carries the same content and is sound
    assert obsolete_components(d, relations) == []


def test_an_obsolete_own_reference_that_no_other_reference_carries_is_named_alone():
    relations = Relations([relation("superseded_by", "SA-A", "SA-Z", 6)])
    assert obsolete_of(design("A", SHARED, ("V1", "V2")), relations) == "own reference SA-A, superseded by SA-Z"


def test_the_own_reference_comes_before_the_components():
    relations = Relations([relation("obsolete", "S1", None, 6), relation("superseded_by", "PT-7731", "SA-A", 7)])
    d = design("A", SHARED, ("V1", "V2"))
    d.occurrences[1].part = "PT-7731"
    assert obsolete_of(d, relations, "V2") == ("own reference PT-7731, superseded by SA-A (same content under SA-A); "
                                               "S1, obsolete")
    assert obsolete_of(d, relations, "V1") == "S1, obsolete"


def test_a_specific_design_holding_an_obsolete_part_stays_specific_and_names_it():
    relations = Relations([relation("obsolete", "S1", None, 6)])
    d = design("A", SHARED)
    assert verdict_of(d).verdict == "specific"
    assert obsolete_of(d, relations) == "S1, obsolete"
