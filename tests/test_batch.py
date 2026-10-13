"""The batch run's task text: what the agent is asked for one open item."""

import json
from types import SimpleNamespace

from reconcile.batch import task


def test_an_unread_note_is_given_whole_without_its_row_number(tiny):
    item = {"kind": "unread note", "detail": "TN-0001", "claim_id": None, "source_rows": "note:TN-0001"}
    first, note = task(item, SimpleNamespace(raw=tiny)).split("\n")
    assert first == "Settle this open item: an unread note. Record what it states, then mark it reviewed."
    assert json.loads(note) == {"note_id": "TN-0001", "date": "2025-01-10", "reference": "PT-7731",
                                "text": "PT-7731 = ex DR-1042, renumbered. Actuator AC-501 superseded by AC-560."}


def test_a_notes_text_is_not_escaped(tiny):
    tiny.note("TN-0001")["text"] = "Joint révisé"
    item = {"kind": "unread note", "detail": "TN-0001", "claim_id": None, "source_rows": "note:TN-0001"}
    assert "Joint révisé" in task(item, SimpleNamespace(raw=tiny))


def test_another_item_is_given_by_kind_detail_and_raw_rows_with_its_claim_when_it_has_one(tiny):
    item = {"kind": "near pair", "detail": "DR-1042 and DR-1043", "claim_id": 17, "source_rows": "bom:2, bom:9"}
    assert task(item, SimpleNamespace(raw=tiny)) == ('Settle this open item of kind "near pair" (claim 17): '
                                                     "DR-1042 and DR-1043\nRaw rows: bom:2, bom:9")
    item = {"kind": "two quantities", "detail": "JT-218 in DR-1042", "claim_id": None, "source_rows": "bom:3, bom:4"}
    assert task(item, SimpleNamespace(raw=tiny)) == ('Settle this open item of kind "two quantities": '
                                                     "JT-218 in DR-1042\nRaw rows: bom:3, bom:4")
