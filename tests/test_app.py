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


def test_the_agent_page_puts_answers_in_the_chat_and_the_work_behind_them_in_the_trace(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("JEAN_AGENT", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    app = AppTest.from_file(str(ROOT / "jean-code" / "src" / "app.py"), default_timeout=30).run()

    def call(id, query):
        return {"id": id, "type": "function", "function": {"name": "run_sql", "arguments": '{"query": "%s"}' % query}}

    app.session_state.agent.messages += [
        {"role": "user", "content": "Is the bogie frame reused?"},
        {"role": "assistant", "content": None, "reasoning": "I need the BOM rows.",
         "tool_calls": [call("c1", "SELECT 1"), call("c2", "SELECT * FROM nope")]},
        {"role": "tool", "tool_call_id": "c1", "content": "[[1]]"},
        {"role": "tool", "tool_call_id": "c2", "content": "Error: no such table: nope"},
        {"role": "assistant", "content": "Yes, in V1 to V4.", "reasoning": "The rows agree."},
    ]
    app.run()
    assert not app.exception
    assert not app.tabs
    chat, trace = app.columns
    assert [m.value for m in chat.markdown] == ["Is the bogie frame reused?", "The rows agree.", "Yes, in V1 to V4."]
    assert [e.label for e in chat.expander] == ["Reasoning"] and not chat.expander[0].proto.expanded
    # the trace: the question, the step's reasoning in full, then one folded row per call holding its result
    assert any("Is the bogie frame reused?" in h.proto.body for h in trace.get("html"))
    assert [m.value for m in trace.markdown] == ["I need the BOM rows."]
    ok, failed = trace.expander
    assert (ok.label, failed.label) == ("`run_sql · SELECT 1`", "`run_sql · SELECT * FROM nope` :red[failed]")
    assert not ok.proto.expanded and not failed.proto.expanded
    assert [c.value for c in ok.code] == ["[\n  [\n    1\n  ]\n]"]
    assert [c.value for c in failed.code] == ["Error: no such table: nope"]
    assert "SELECT * FROM nope" in failed.get("html")[0].proto.body  # a short argument, in the arguments table
