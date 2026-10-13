"""The agent's tools: reading is read-only and capped, appending is checked, guarded and reports what changed."""

import shutil

import pytest

from pipeline.claims import load
from reconcile.tools import Workbench, verdict_counts


@pytest.fixture
def bench(tmp_path, rules_log):
    shutil.copy(rules_log, tmp_path / "claims.jsonl")
    return Workbench(tmp_path / "pilot.db", tmp_path / "claims.jsonl", "data/raw", "test-model", "Oscar")


def test_describe_tables_lists_the_views_with_their_columns(bench):
    text = bench.describe_tables()
    assert "v_reuse_between" in text and "variant_from, variant_to, subassembly_ref" in text
    assert "about" not in text.split()  # the table of descriptions is not itself listed
    assert text.index("v_queue (") < text.index("bom_line (")  # the v_ names first, stored tables among them


def test_run_sql_returns_rows_and_cannot_write(bench):
    assert bench.run_sql("SELECT COUNT(*) AS n FROM raw_bom").splitlines()[:2] == ["n", "1538"]
    assert bench.run_sql("DELETE FROM raw_bom").startswith("refused: only SELECT")
    assert bench.run_sql("SELECT nope FROM raw_bom").startswith("error:")


def test_run_sql_cannot_create_a_file(bench, tmp_path):
    """ATTACH and VACUUM INTO create a file even on a read-only connection, so they are refused."""
    before = sorted(tmp_path.iterdir())
    assert bench.run_sql(f"VACUUM INTO '{tmp_path / 'copy.db'}'").startswith("refused: only SELECT")
    assert bench.run_sql(f"ATTACH DATABASE 'file:{tmp_path / 'new.db'}?mode=rwc' AS x").startswith("refused: only SELECT")
    assert bench.run_sql("PRAGMA user_version = 7").startswith("refused: only SELECT")
    assert sorted(tmp_path.iterdir()) == before


def test_run_sql_caps_the_rows_it_returns(bench):
    text = bench.run_sql("SELECT row_no FROM raw_bom")
    assert "more than 200 rows" in text and len(text.splitlines()) == 202


def test_append_claim_is_written_as_the_agent_and_reports_what_changed(bench):
    before = len(load(bench.log_path))
    reply = bench.append_claim("not_same_as", "ref:BL-330", "ref:BL-338", evidence=["bom:108", "bom:115"],
                               reason="M8x25 and M8x35 are two bolt lengths")
    claim = load(bench.log_path)[-1]
    open_before = sum(bench.summary.open_items.values()) + 1  # the summary is already the one after the claim
    assert reply.startswith(f"claim {before + 1} recorded and in force.")
    assert f"Open items: {open_before} to {open_before - 1}." in reply
    assert (claim["made_by"], claim["maker"], claim["standing"]) == ("agent", "test-model", "asserted")


def test_a_claim_that_makes_a_part_obsolete_is_reported_though_no_verdict_moves(bench):
    before = bench.summary
    reply = bench.append_claim("obsolete", "ref:AC-477", evidence=["note:TN-0471"],
                               quote="AC-477 door actuator now obsolete, do not use on new designs.")
    assert before.verdicts == bench.summary.verdicts and not before.obsolete
    assert "Obsolete parts changed (6): DR-1043 in V1, none to AC-477, obsolete; " in reply
    assert verdict_counts(bench.summary).endswith("; 6 sub-assemblies with an obsolete or superseded part")
    assert verdict_counts(before).endswith(" specific; 0 sub-assemblies with an obsolete or superseded part")


def test_a_refused_claim_says_why_and_writes_nothing(bench):
    before = len(load(bench.log_path))
    assert "not written anywhere" in bench.append_claim("obsolete", "ref:ZZ-0000")
    assert "word for word" in bench.append_claim("obsolete", "ref:AC-477", evidence=["note:TN-0471"], quote="AC-477 is dead")
    assert len(load(bench.log_path)) == before


def test_the_agent_may_not_assert_that_two_siblings_are_one_part_but_may_propose_it(bench):
    # DR-1042 and DR-1043 are the left and right door leaves, children of the same parent in the same variant.
    reply = bench.append_claim("same_as", "ref:DR-1042", "ref:DR-1043")
    assert reply.startswith("refused:") and "proposed" in reply
    assert "recorded as proposed" in bench.append_claim("same_as", "ref:DR-1043", "ref:DR-1042", standing="proposed")


def test_a_claim_resting_on_a_note_takes_the_notes_date_and_the_agent_may_not_contradict_it(bench):
    quote = "DR-1043 (door leaf assy, RIGHT) is NOT the same as DR-1042 (door leaf assy, LEFT)."
    bench.append_claim("not_same_as", "ref:DR-1043", "ref:DR-1042", evidence=["note:TN-0116"], quote=quote)
    assert load(bench.log_path)[-1]["as_of"] == "2019-01-29"
    bench.siblings = set()  # so that only the note-based claim stands in the way
    reply = bench.append_claim("same_as", "ref:DR-1042", "ref:DR-1043")
    assert reply.startswith("refused:") and "rests on a note" in reply


def test_a_persons_claim_is_written_in_the_persons_name(bench):
    proposal = next(c for c in load(bench.log_path) if c["standing"] == "proposed" and c["subject"].startswith("supplier:"))
    reply = bench.append_person_claim("confirm", f"claim:{proposal['id']}", reason="same company")
    claim = load(bench.log_path)[-1]
    assert "recorded and in force" in reply and (claim["made_by"], claim["maker"]) == ("person", "Oscar")


def test_the_agent_may_not_settle_a_price_but_a_person_may(bench):
    # Which of two prices holds is not in the data. The agent is refused; the person's claim unblocks the total.
    conn = bench.connect()
    part, rows = conn.execute("SELECT detail, source_rows FROM v_queue WHERE kind = 'two prices'").fetchone()
    row = rows.split(", ")[0].split(":")[1]
    other = conn.execute("SELECT unit_cost_eur FROM raw_erp WHERE row_no = ?", (rows.split(", ")[1].split(":")[1],)).fetchone()[0]
    conn.close()
    cell = f"cell:erp:{row}:unit_cost_eur"
    refused = bench.append_claim("value_is", cell, value=other)
    assert refused.startswith("refused:") and "purchasing decides" in refused
    reply = bench.append_person_claim("value_is", cell, value=other, reason="the price on the current contract")
    assert "Issues of type two_prices: 2 to 1." in reply


def test_two_notes_that_disagree_are_both_recorded_and_the_later_one_is_applied(bench):
    # TN-0216 (2021) says PB-2281 and LR-1500 are not the same part. TN-0418 (2024) says they are.
    bench.append_claim("not_same_as", "ref:PB-2281", "ref:LR-1500", evidence=["note:TN-0216"],
                       quote="PB-2281 and LR-1500 are NOT the same part")
    reply = bench.append_claim("same_as", "ref:PB-2281", "ref:LR-1500", evidence=["note:TN-0418"],
                               quote="PB-2281 = LR-1500, same luggage rack")
    assert "recorded and in force" in reply
    conn = bench.connect()
    assert conn.execute("SELECT COUNT(DISTINCT entity_id) FROM resolution WHERE written_value IN ('PB-2281', 'LR-1500')").fetchone()[0] == 1
    statuses = [row[0] for row in conn.execute("SELECT status FROM claim_status ORDER BY claim_id DESC LIMIT 2")]
    assert statuses[0] == "in force" and statuses[1].startswith("overridden by claim")


def test_the_agent_cannot_insert_or_delete_a_part_asserted_or_proposed(bench):
    # Row 536 lists the door drive DD-2037 in V3; MT-745 is its motor. What a variant is built from is a person's decision.
    before = len(load(bench.log_path))
    asserted = bench.append_claim("delete_part", "bom:536", "ref:MT-745")
    proposed = bench.append_claim("insert_part", "bom:536", "ref:MT-701", value="1 pcs", standing="proposed")
    assert asserted.startswith("refused:") and "only a person can record it" in asserted
    assert proposed.startswith("refused:")
    assert len(load(bench.log_path)) == before


def test_a_persons_delete_and_insert_are_each_reported_in_words_and_can_be_undone(bench):
    # Catches "No change to parts, designs, verdicts, ..." after a delete that moves no count and no verdict.
    deleted = bench.append_person_claim("delete_part", "bom:536", "ref:MT-745", evidence=["bom:628"])
    assert "Content changed: V3: MT-745 deleted from DD-2037 (was 1 pcs)." in deleted
    inserted = bench.append_person_claim("insert_part", "bom:536", "ref:MT-701", value="1 pcs")
    assert "Content changed: V3: MT-701 inserted in DD-2037, 1 pcs." in inserted
    assert "DD-2037 in V3, reusable to reused" in inserted
    claim_id = len(load(bench.log_path))
    # One that cannot be applied now is not written: in the log, it would start to act when another claim allows it.
    again = bench.append_person_claim("insert_part", "bom:536", "ref:MT-701", value="2 pcs")
    absent = bench.append_person_claim("delete_part", "bom:536", "ref:MT-745")
    assert again == ("refused: MT-701 is already in DD-2037 in V3; delete it first to change its quantity. "
                     "Nothing was written.")
    assert absent == "refused: MT-745 is not in DD-2037 in V3. Nothing was written."
    assert len(load(bench.log_path)) == claim_id
    undone = bench.append_person_claim("retract", f"claim:{claim_id}")
    assert "No longer applied: V3: MT-701 inserted in DD-2037, 1 pcs." in undone
    assert "DD-2037 in V3, reused to reusable" in undone
