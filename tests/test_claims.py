"""Tests for the claim log: the checks before a claim is written, and which claims are in force."""

import json

import pytest

from pipeline.claims import ClaimLog, ClaimRefused, in_force, load, statuses

RULE = {"made_by": "rule", "maker": "test_rule"}
AGENT = {"made_by": "agent", "maker": "test-model"}
PERSON = {"made_by": "person", "maker": "Oscar"}


@pytest.fixture
def log(tmp_path, tiny):
    return ClaimLog(tmp_path / "claims.jsonl", tiny)


def test_append_writes_one_line_and_numbers_from_one(log):
    first = log.append({"type": "same_as", "subject": "ref:JT-218", "object": "ref:JT 218", **RULE})
    second = log.append({"type": "obsolete", "subject": "ref:AC-501", **AGENT})
    assert (first, second) == (1, 2)
    lines = log.path.read_text().splitlines()
    assert [json.loads(line)["id"] for line in lines] == [1, 2]
    assert load(log.path) == log.claims


def test_the_same_claim_is_not_written_twice_whatever_the_order_of_a_symmetric_pair(log):
    # Catches rerunning the rules doubling the log.
    first = log.append({"type": "same_as", "subject": "ref:JT-218", "object": "ref:JT 218", **RULE})
    again = log.append({"type": "same_as", "subject": "ref:JT 218", "object": "ref:JT-218", **RULE})
    assert again == first and log.added is False
    assert len(log.path.read_text().splitlines()) == 1
    # Another maker saying the same thing is a new claim.
    assert log.append({"type": "same_as", "subject": "ref:JT 218", "object": "ref:JT-218", **AGENT}) == 2


@pytest.mark.parametrize("claim, why", [
    ({"type": "merged_with", "subject": "ref:JT-218"}, "unknown claim type"),
    ({"type": "same_as", "subject": "ref:JT-218", "object": "ref:JT-999"}, "not written anywhere"),
    ({"type": "same_as", "subject": "ref:JT-218", "object": "supplier:Faiveley"}, "same kind"),
    ({"type": "same_as", "subject": "ref:JT-218", "object": "ref:JT-218"}, "are the same"),
    ({"type": "obsolete", "subject": "ref:AC-501", "object": "ref:JT-218"}, "takes no object"),
    ({"type": "converts_to", "subject": "unit:mm", "object": "unit:m", "value": "tiny"}, "not a positive number"),
    ({"type": "converts_to", "subject": "unit:furlong", "object": "unit:m", "value": "201"}, "is not written"),
    ({"type": "duplicate_of", "subject": "bom:99", "object": "bom:1"}, "no row"),
    ({"type": "value_is", "subject": "cell:erp:1:price", "value": "3"}, "not a column"),
    ({"type": "retract", "subject": "claim:5"}, "no claim"),
    ({"type": "obsolete", "subject": "ref:AC-501", "quote": "AC-501 is dead", "evidence": ["note:TN-0001"]},
     "word for word"),
    ({"type": "obsolete", "subject": "ref:AC-501", "quote": "superseded by AC-560"}, "needs the note"),
    ({"type": "confirm", "subject": "claim:1", "standing": "proposed"}, "always asserted"),
])
def test_a_claim_that_fails_a_check_is_refused_and_nothing_is_written(log, claim, why):
    log.append({"type": "mentions", "subject": "note:TN-0001", "object": "ref:PT-7731", **RULE})
    with pytest.raises(ClaimRefused, match=why):
        log.append({**AGENT, **claim})
    assert len(log.path.read_text().splitlines()) == 1


def test_made_by_must_be_a_known_maker(log):
    with pytest.raises(ClaimRefused, match="made_by"):
        log.append({"type": "obsolete", "subject": "ref:AC-501", "made_by": "model", "maker": "x"})


def test_a_reference_written_only_inside_a_note_is_accepted_with_its_quote(log):
    # AC-560 is in no BOM or ERP row: it exists only in the note's text.
    claim_id = log.append({"type": "superseded_by", "subject": "ref:AC-501", "object": "ref:AC-560",
                           "evidence": ["note:TN-0001"], "quote": "AC-501 superseded by AC-560", **AGENT})
    assert log.claims[claim_id - 1]["quote"] == "AC-501 superseded by AC-560"


def claim(id, type, subject, object="", standing="asserted", made_by="rule", as_of="", value="", evidence=(), quote=""):
    return {"id": id, "type": type, "subject": subject, "object": object, "value": value, "standing": standing,
            "made_by": made_by, "maker": made_by, "evidence": list(evidence), "quote": quote, "reason": "",
            "as_of": as_of}


def test_proposed_is_not_in_force_until_confirmed_and_a_retract_takes_it_out_again():
    claims = [claim(1, "same_as", "ref:A", "ref:B", standing="proposed")]
    assert in_force(claims) == []
    claims.append(claim(2, "confirm", "claim:1", made_by="agent"))
    assert [c["id"] for c in in_force(claims)] == [1, 2]
    assert str(statuses(claims)[1]) == "confirmed by claim 2"
    claims.append(claim(3, "retract", "claim:1", made_by="person"))
    assert [c["id"] for c in in_force(claims)] == [2, 3]
    assert str(statuses(claims)[1]) == "retracted by claim 3"


def test_a_retracted_retract_no_longer_counts():
    claims = [claim(1, "obsolete", "ref:A"), claim(2, "retract", "claim:1"), claim(3, "retract", "claim:2")]
    assert [c["id"] for c in in_force(claims)] == [1, 3]


def test_opposite_claims_with_dates_the_later_date_wins_whoever_made_them():
    # The generated notes do this: TN-0191 says same, TN-0331 two years later says not the same.
    claims = [claim(1, "same_as", "ref:BK-121", "ref:BK-120", made_by="person", as_of="2020-11-23"),
              claim(2, "not_same_as", "ref:BK-120", "ref:BK-121", made_by="agent", as_of="2023-02-14")]
    status = statuses(claims)
    assert str(status[1]) == "overridden by claim 2" and status[2].in_force


def test_opposite_claims_without_dates_a_person_beats_an_agent_beats_a_rule():
    claims = [claim(1, "not_same_as", "ref:A", "ref:B", made_by="person"),
              claim(2, "same_as", "ref:A", "ref:B", made_by="agent", as_of="2024-01-01"),
              claim(3, "same_as", "ref:B", "ref:A", made_by="rule")]
    status = statuses(claims)
    assert status[1].in_force
    assert str(status[2]) == str(status[3]) == "overridden by claim 1"


def test_two_values_for_one_cell_the_stronger_claim_is_applied():
    claims = [claim(1, "value_is", "cell:bom:5:quantity", value="6", made_by="agent"),
              claim(2, "value_is", "cell:bom:5:quantity", value="4", made_by="person")]
    assert [c["id"] for c in in_force(claims)] == [2]


def test_replay_filters_leave_out_note_claims_makers_and_later_claims():
    claims = [claim(1, "same_as", "ref:A", "ref:B", evidence=["bom:1", "note:TN-1"]),  # a note listed, not quoted
              claim(2, "obsolete", "ref:C", made_by="agent", evidence=["note:TN-1"], quote="C is obsolete"),
              claim(3, "retract", "claim:1", made_by="person")]
    assert [c["id"] for c in in_force(claims, without_notes=True)] == [3]  # 1 stays in the replay, and is retracted
    assert [c["id"] for c in in_force(claims[:2], without_notes=True)] == [1]
    assert [c["id"] for c in in_force(claims, made_by={"rule"})] == [1]  # the person's retract is left out too
    assert [c["id"] for c in in_force(claims, up_to=2)] == [1, 2]
