"""Reading the raw files: values are kept as written, rows are numbered from one, and a line that cannot be
parsed stops the run with the file and the line in the message."""

import json
import sqlite3

import pytest

from pipeline.ingest import BOM_COLUMNS, BOM_FILE, ERP_COLUMNS, ERP_FILE, NOTE_FILE, Raw, ingest, read_raw

BOM = [",".join(BOM_COLUMNS),
       "V1,6,160,suburban,2,V1,DOOR-SYS-01,Door system,1,pcs",
       'V1,6,160,suburban,3,DOOR-SYS-01, dr-1042 ,"Door leaf, left",2,PCE']
ERP = [";".join(ERP_COLUMNS),
       "JT218;JOINT DE PORTE;Faiveley; 38,50 ;m",
       "AC501;ACTIONNEUR;N/A;;pcs"]
NOTES = [json.dumps({"note_id": "TN-0001", "date": "2025-01-10", "reference": "", "text": "See AC-560, not XAC-561."}),
         "",
         json.dumps({"note_id": "TN-0002", "date": "2025-02-01", "reference": "PT-7731", "text": "Révisé."})]


def write_raw(folder, bom=BOM, erp=ERP, notes=NOTES):
    for name, lines in ((BOM_FILE, bom), (ERP_FILE, erp), (NOTE_FILE, notes)):
        (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def test_rows_are_numbered_from_one_and_every_value_is_kept_as_written(tmp_path):
    raw = read_raw(write_raw(tmp_path))
    assert [row["row_no"] for row in raw.bom] == [1, 2] and [row["row_no"] for row in raw.erp] == [1, 2]
    assert (raw.bom[1]["child_ref"], raw.bom[1]["description"], raw.bom[1]["unit"]) == (" dr-1042 ", "Door leaf, left", "PCE")
    assert (raw.erp[0]["unit_cost_eur"], raw.erp[1]["supplier"], raw.erp[1]["unit_cost_eur"]) == (" 38,50 ", "N/A", "")
    assert all(isinstance(value, str) for row in raw.bom + raw.erp for key, value in row.items() if key != "row_no")


def test_a_blank_line_between_notes_is_skipped_and_does_not_take_a_row_number(tmp_path):
    raw = read_raw(write_raw(tmp_path))
    assert [(note["row_no"], note["note_id"]) for note in raw.notes] == [(1, "TN-0001"), (2, "TN-0002")]
    assert raw.note("TN-0002")["text"] == "Révisé." and raw.note("TN-9999") is None


def test_a_note_value_that_is_not_text_is_stored_as_text(tmp_path):
    notes = [json.dumps({"note_id": 7, "date": "2025-01-10", "reference": "", "text": "x"})]
    assert read_raw(write_raw(tmp_path, notes=notes)).note("7")["note_id"] == "7"


@pytest.mark.parametrize("files, message", [
    ({"bom": [BOM[0].replace("child_ref", "child"), *BOM[1:]]}, r"plm_bom_export\.csv has columns .*'child'.* expected"),
    ({"bom": [",".join(BOM_COLUMNS[::-1]), *BOM[1:]]}, r"plm_bom_export\.csv has columns"),
    ({"erp": [ERP[0].replace(";", ","), *ERP[1:]]}, r"erp_items\.csv has columns"),
    ({"bom": [*BOM, "V1,6,160,suburban,3,DOOR-SYS-01,DR-1043,Door leaf,2"]}, r"plm_bom_export\.csv line 4 has 9 values, expected 10"),
    ({"erp": [ERP[0], ERP[1], ERP[2] + ";extra"]}, r"erp_items\.csv line 3 has 6 values, expected 5"),
    ({"notes": [NOTES[0], "{not json"]}, r"technical_notes\.jsonl line 2 is not valid JSON"),
    ({"notes": [NOTES[0], "", json.dumps({"note_id": "TN-2", "date": "", "text": ""})]}, r"technical_notes\.jsonl line 3 has fields \['date', 'note_id', 'text'\], expected"),
    ({"notes": [json.dumps({"note_id": "TN-1", "date": "", "reference": "", "text": "", "author": "x"})]}, r"technical_notes\.jsonl line 1 has fields"),
])
def test_a_file_that_cannot_be_read_as_expected_stops_the_run_and_says_where(tmp_path, files, message):
    with pytest.raises(ValueError, match=message):
        read_raw(write_raw(tmp_path, **files))


def test_written_refs_takes_the_reference_columns_and_the_shapes_in_a_notes_text(tmp_path):
    refs = read_raw(write_raw(tmp_path)).written_refs()
    assert refs["bom"] == {"DOOR-SYS-01", " dr-1042 "}  # V1, the parent of a system row, is a variant, not a part
    assert refs["erp"] == {"JT218", "AC501"}
    assert refs["note"] == {"PT-7731", "AC-560"}         # XAC-561 is not shaped like a reference


def test_has_ref_wants_the_reference_character_for_character(tmp_path):
    raw = read_raw(write_raw(tmp_path))
    assert raw.has_ref("JT218") and raw.has_ref("PT-7731") and raw.has_ref(" dr-1042 ")
    assert raw.has_ref("AC-561")  # written inside a note's text, though not as a reference of its own
    assert not raw.has_ref("JT-218") and not raw.has_ref("dr-1042") and not raw.has_ref("V1")
    assert not raw.has_ref("") and not raw.has_ref(" ")


def test_ingest_writes_the_three_raw_tables_as_text_and_returns_their_row_counts(tmp_path):
    raw = read_raw(write_raw(tmp_path))
    conn = sqlite3.connect(":memory:")
    assert ingest(conn, raw) == {"raw_bom": 2, "raw_erp": 2, "raw_note": 2}
    assert conn.execute("SELECT row_no, cars, typeof(cars), child_ref FROM raw_bom WHERE row_no = 2").fetchone() == (2, "6", "text", " dr-1042 ")
    assert conn.execute("SELECT unit_cost_eur FROM raw_erp ORDER BY row_no").fetchall() == [(" 38,50 ",), ("",)]
    assert conn.execute("SELECT note_id, text FROM raw_note WHERE row_no = 2").fetchone() == ("TN-0002", "Révisé.")


def test_an_empty_set_of_files_is_read_as_no_rows(tmp_path):
    raw = read_raw(write_raw(tmp_path, bom=BOM[:1], erp=ERP[:1], notes=[]))
    assert (raw.bom, raw.erp, raw.notes) == ([], [], [])
    assert Raw([], [], []).written_refs() == {"bom": set(), "erp": set(), "note": set()}
