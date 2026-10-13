"""The reset puts the log back to a starting point without a person's claim, and keeps the log it replaces."""

import json
import shutil

import pytest

from pipeline.claims import load
from pipeline.reset import START, reset


def test_the_demo_starts_from_the_rules_and_the_agents_claims_only():
    makers = {claim["made_by"] for claim in load(START)}
    assert makers == {"rule", "agent"}


def test_a_reset_restores_the_start_and_keeps_the_log_as_it_was(tmp_path, rules_log):
    log = tmp_path / "claims.jsonl"
    shutil.copy(rules_log, log)
    person = {**load(rules_log)[0], "id": len(load(rules_log)) + 1, "made_by": "person", "maker": "Oscar"}
    log.write_text(log.read_text() + json.dumps(person) + "\n")
    kept, summary = reset(rules_log, log, "data/raw", tmp_path / "out" / "pilot.db")
    assert log.read_text() == rules_log.read_text() and summary.parts > 0
    assert load(kept)[-1]["made_by"] == "person"  # the replaced log, with the person's claim, is still on disk
    with pytest.raises(ValueError):  # a starting point must not hold a person's claim
        reset(kept, log, "data/raw", tmp_path / "out" / "pilot.db")
    assert log.read_text() == rules_log.read_text()  # and a refused reset changes nothing
