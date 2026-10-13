"""The jean-code app starts in this project with the reconciliation agent and shows the Reconciled data and Claims pages."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


def test_the_app_builds_the_reconciliation_agent_and_draws_the_claims_page(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("JEAN_AGENT", raising=False)  # the reconciliation agent is the app's default
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # the client is built, never called
    app = AppTest.from_file(str(ROOT / "jean-code" / "src" / "app.py"), default_timeout=30).run()
    assert not app.exception
    agent = app.session_state.agent
    assert set(agent.tool_map) == {"describe_tables", "run_sql", "append_claim", "append_person_claim"}
    assert agent.needs_approval == set() and set(agent.skills) == {"reconciliation"}
    assert not app.sidebar.toggle  # no shell, so no choice of where one runs
    pages = app.sidebar.button_group(key="page")
    assert pages.options == ["Agent", "Raw data", "Reconciled data", "Claims"]
    pages.set_value("Reconciled data").run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Parts", "Suppliers", "Bill of materials", "Relations from notes",
                                               "Reuse verdicts", "Open items"]
    parts, verdicts = app.tabs[0], app.tabs[4]
    assert " parts: " in parts.markdown[0].value and len(parts.dataframe[0].value) > 300
    assert len(verdicts.dataframe[0].value) == 240  # 40 sub-assemblies in each of the 6 variants
    assert not any(name in tab.label for tab in app.tabs for name in ("raw", "claim"))  # those have their own pages
    pages.set_value("Claims").run()
    assert not app.exception
    assert any("claims" in caption.value and "by rule" in caption.value for caption in app.caption)
    assert len(app.dataframe[0].value) > 400  # the rules alone write more than 400 claims
