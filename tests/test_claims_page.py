"""The Claims page of the jean-code UI, on this project's log: it lists the claims and filters them."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APPS = Path(__file__).parent / "apps"  # one-page apps the tests start
APP = str(APPS / "claims_page_app.py")


def test_no_log_yet_says_how_to_make_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page = AppTest.from_file(APP).run()
    assert not page.exception
    assert "No claim log yet" in page.info[0].value


def test_the_page_lists_every_claim_of_the_log_newest_first(monkeypatch):
    monkeypatch.chdir(ROOT)
    page = AppTest.from_file(APP).run()
    assert not page.exception
    lines = sum(1 for line in open(ROOT / "data" / "claims.jsonl") if line.strip())
    assert f"{lines:,} claims" in page.caption[0].value
    table = page.dataframe[0].value
    assert len(table) == lines and table.iloc[0]["id"] == lines


def test_search_narrows_the_table_to_claims_naming_a_reference(monkeypatch):
    monkeypatch.chdir(ROOT)
    page = AppTest.from_file(APP).run()
    page.text_input(key="claims-search").set_value("DR-1043").run()
    table = page.dataframe[0].value
    assert 0 < len(table) < 20
    assert all("DR-1043" in " ".join(map(str, row)) for row in table.itertuples())


def test_the_detail_of_a_claim_shows_its_evidence_as_the_raw_rows_and_the_quoted_note(tmp_path, monkeypatch, rules_log):
    # A log with one claim of the kinds the detail view treats differently: rows, a cell, a note with a quote,
    # and a confirm that points at another claim.
    from pipeline.claims import ClaimLog
    from pipeline.ingest import read_raw

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "raw").symlink_to(ROOT / "data" / "raw")
    (tmp_path / "pipeline").symlink_to(ROOT / "pipeline")
    log = ClaimLog(tmp_path / "data" / "claims.jsonl", read_raw(ROOT / "data" / "raw"))
    agent = {"made_by": "agent", "maker": "test-model"}
    quote = "DR-1043 (door leaf assy, RIGHT) is NOT the same as DR-1042 (door leaf assy, LEFT)."
    log.append({"type": "same_as", "subject": "ref:AL-6056", "object": "ref:AL-6065", "standing": "proposed",
                "evidence": ["bom:1091", "erp:9"], "made_by": "rule", "maker": "near_key"})
    log.append({"type": "confirm", "subject": "claim:1", "reason": "same parent", **agent})
    log.append({"type": "not_same_as", "subject": "ref:DR-1043", "object": "ref:DR-1042", "evidence": ["note:TN-0116"],
                "quote": quote, **agent})
    log.append({"type": "value_is", "subject": "cell:bom:53:quantity", "value": "4.3", "evidence": ["bom:52"], **agent})
    # A person's insert of a sub-assembly: its subject and its object are both BOM rows.
    log.append({"type": "insert_part", "subject": "bom:1286", "object": "bom:39", "value": "20 pcs",
                "made_by": "person", "maker": "Oscar"})
    monkeypatch.chdir(tmp_path)
    page = AppTest.from_file(str(APPS / "claim_detail_app.py")).run()
    assert not page.exception
    text = " ".join(str(element.value) for element in [*page.markdown, *page.caption])
    assert "`insert_part(bom:1286, bom:39) = 20 pcs`" in text
    assert "`bom:1286`" in text and "`bom:39`" in text and "child_ref: PW-4700" in text  # both rows printed
    assert "confirmed by claim 2" in text                       # the proposal's status, and the claim that confirmed it
    assert "`bom:1091`" in text and "child_ref: AL-6056" in text  # a row pointer shown as the row's values
    assert "written value: '6.4'" in text                       # a cell pointer shown with what the file says
    assert f"<mark>{quote}</mark>" in page.get("html")[0].proto.body  # the note, with the quote highlighted
