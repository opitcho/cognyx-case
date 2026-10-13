"""Streamlit UI for the agent: the chat, and beside it a live trace of the agent's work.

Run from the project that holds the data: uv run --env-file .env streamlit run jean-code/src/app.py

The agent stays UI-agnostic: `run_turn` runs in a background thread and this UI polls
`agent.messages`. The chat shows the user's messages and the agent's answers; the trace shows, under
each question, the reasoning and tool calls that led to its answer, each call unfolding to its
arguments and result. Both read the UI's own history of every message it has seen, matched by object
identity, so it survives the context window being rewritten (e.g. compaction): turns that leave
`agent.messages` stay on the page.

The sidebar picks which agent the chat and trace show: the main agent, or any subagent run in its tree.
Every agent's history is kept, whichever one is shown, so switching back loses nothing.
"""

import base64
import html
import importlib
import json
import os
import re
import sys
import threading
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from agent import DEFAULT_MODEL, Agent
from claims_page import CLAIMS_LOG, claim_count, render_claims_page
from config import USAGE_LOG
from data_page import DATA_DIR, data_files, render_data_page
from db_page import DB_PATH, claims_in_force, render_db_page
from prompts import HEAD_MARKER_TAG, SUMMARY_TAG
from repl import compaction_line
from subagents import Run
from usage import COST_UNKNOWN, human, usage_line

MODEL = DEFAULT_MODEL
REASONING_LEVELS = ("off", "low", "medium", "high")  # "off" sends no reasoning setting (agent.reasoning = None)
POLL_SECONDS = 0.5
CSS_PATH = Path(__file__).with_name("app.css")
APP_NAME = "Reuse Advisor"
# The function that builds the agent, as `module:function`, called with the model and `reasoning`. The default
# is the reconciliation agent of the project the app is started in, which has no shell. JEAN_AGENT names another.
AGENT_FACTORY = os.environ.get("JEAN_AGENT") or "reconcile.agent:reconciliation_agent"
PAGES = ("Agent", "Raw data", "Reconciled data", "Claims")
LOGO_PATH = Path(__file__).parent.parent / "assets" / "alstom-logo.svg"  # gitignored: absent on a fresh clone

# kind -> (label, icon, accent color)
# the two cards the page draws: kind -> (label, icon, accent color)
KINDS = {
    "thinking": ("THINKING", "✦", "#9647DE"),
    "approval": ("APPROVAL", "⚠", "#B54708"),
}
CHAT_KINDS = {"user": "YOU", "agent": "AGENT"}  # kind -> label in the chat
STEP_KINDS = {"tool_call", "thinking"}  # what the trace draws under each question: the agent's work towards its answer
# status -> (color in the agent picker, dot and pill classes in the header)
STATUSES = {
    "running": ("green", "run", "status-run"),
    "awaiting approval": ("orange", "wait", "status-wait"),
    "idle": ("gray", "", ""),
    "done": ("blue", "done", ""),
    "stopped": ("orange", "stop", "status-stop"),
    "failed": ("red", "fail", "status-fail"),
}
ERROR_PREFIXES = ("Error", "Denied by user", "Not run")  # results the agent writes when a call didn't succeed
EXIT_CODE = re.compile(r"exit code: (\d+)[^\n]*\n?")  # first line of a bash result, see shell.format_result
LONG_ARG = 80  # string arguments longer than this get their own code block


@dataclass
class Entry:
    """A message the UI has seen. `uid` is stable even if the message leaves the context."""

    uid: int
    msg: dict
    in_context: bool = True


@dataclass
class View:
    """An agent the UI can show: the main agent (no `run`), or a subagent run somewhere in its tree."""

    path: str  # its budget path: "main", "main/1", "main/1/2"
    agent: Agent
    run: Run | None = None
    profile: str = ""
    id: int | None = None  # the run id its parent's model knows it by


def agent_views(agent) -> dict[str, View]:
    """The main agent, then every subagent run below it depth-first, keyed by budget path."""
    views = {agent.budget.path: View(agent.budget.path, agent)}

    def walk(parent) -> None:
        for id, profile, run in parent.subagents.snapshot() if parent.subagents else []:
            views[run.path] = View(run.path, run.agent, run, profile, id)
            walk(run.agent)

    walk(agent)
    return views


def mget(msg, key, default=None):
    """Read `key` from a message whether it's a plain dict or an attribute-style object."""
    if isinstance(msg, dict):
        return msg.get(key, default)
    return getattr(msg, key, default)


def turn_kind(msg) -> str:
    """Classify a transcript message by its most important part: calls, then thinking, then role."""
    role = mget(msg, "role")
    if mget(msg, "tool_calls"):
        return "tool_call"
    if mget(msg, "reasoning") and not mget(msg, "content"):
        return "thinking"
    content = mget(msg, "content")
    if role == "user" and isinstance(content, str) and content.startswith(HEAD_MARKER_TAG):
        return "marker"
    if role == "user" and isinstance(content, str) and content.startswith(SUMMARY_TAG):
        return "summary"
    if role in ("tool", "user", "system"):
        return {"tool": "tool_result"}.get(role, role)
    return "agent"


def parse_args(call) -> dict:
    """A tool call's arguments: the agent stores them as the model sent them, a JSON string."""
    try:
        value = json.loads(call["function"].get("arguments") or "{}")
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def is_error(msg) -> bool:
    """A tool result that reports a failure: a tool error, a denial, a skipped call or a non-zero exit code."""
    content = str(mget(msg, "content") or "")
    exit_code = EXIT_CODE.match(content)
    return content.startswith(ERROR_PREFIXES) or (exit_code is not None and exit_code.group(1) != "0")


def one_line(text) -> str:
    return " ".join(str(text).split())


def clip(text, limit: int) -> str:
    text = one_line(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def call_summary(call) -> str:
    """`name · first argument`, e.g. `bash · ls -la`."""
    args = parse_args(call)
    first = next(iter(args.values()), None)
    if first is None:
        return call["function"]["name"]
    return f"{call['function']['name']} · {first if isinstance(first, str) else json.dumps(first)}"


def sync_history(entries: list[Entry], ctx: list) -> None:
    """Mark which seen messages are still in the context, and add unseen ones after the message before them.

    A compaction's summary thus lands where it sits in the context, after the messages it replaced.
    Entries hold references to their messages, so `id()` can't be reused while they exist.
    Uids count up within each agent's history: entries are never removed, so the largest is the latest.
    """
    uid = max((e.uid for e in entries), default=0)
    ctx_ids = {id(m) for m in ctx}
    position = {}
    for i, e in enumerate(entries):
        e.in_context = id(e.msg) in ctx_ids
        position[id(e.msg)] = i
    start = 0  # where the next unseen message may go: after the previous context message
    for m in ctx:
        if id(m) in position:
            start = position[id(m)] + 1
            continue
        # before the next entry still in context, so it follows the compacted entries it replaced
        at = next((j for j in range(start, len(entries)) if entries[j].in_context), len(entries))
        uid += 1
        entries.insert(at, Entry(uid, m))
        position = {id(e.msg): i for i, e in enumerate(entries)}
        start = at + 1


def results_of(entries: list[Entry], pos: int) -> list[Entry]:
    """The tool results following the call at `pos`, in call order (results match calls by position)."""
    results = []
    for e in entries[pos + 1 :]:
        if turn_kind(e.msg) != "tool_result":
            break
        results.append(e)
    return results


def compaction_of(agent, msg) -> dict | None:
    """The compaction record whose summary is `msg`, if any."""
    return next((c for c in agent.compactions if c.get("summary") is msg), None)


# ---------------------------------------------------------------- background run


def is_running() -> bool:
    thread = st.session_state.run["thread"]
    return thread is not None and thread.is_alive()


def status_of(view: View) -> tuple[str, str | None]:
    """(status, reason): the main agent's "running", "awaiting approval" or "idle"; a run's "running", or how it
    ended ("done", "stopped" with why, "failed")."""
    if view.run is not None:
        outcome = view.run.outcome(0)  # None while it runs
        return (outcome.status, outcome.reason) if outcome else ("running", None)
    if is_running():
        return "running", None
    return ("awaiting approval" if view.agent.pending_calls else "idle"), None


def tree_state(agent) -> tuple[tuple[tuple[str, bool], ...], int]:
    """((path, done) of every run in the tree, results pending for the main agent). While a run is unfinished,
    the view keeps polling; when this changes (a run starts or ends, a result is delivered), it reruns in full,
    so the sidebar catches up."""
    runs = tuple((path, view.run.done()) for path, view in agent_views(agent).items() if view.run)
    return runs, agent.subagents.pending if agent.subagents else 0


def start_run(fn, *args) -> None:
    """Run an agent method (`run_turn`, `approve`, `deny`) off the script thread; the UI polls the agent's state.

    The model calls it makes are logged as they're charged, through `agent.budget.log_path` (set in `new_chat`).
    """
    run = st.session_state.run

    def target():
        try:
            fn(*args)
        except Exception as e:  # surfaced in the header; never call st.* from here
            run["error"] = f"{type(e).__name__}: {e}"

    run["error"] = run["notice"] = None
    run["thread"] = threading.Thread(target=target, daemon=True)
    run["thread"].start()
    st.session_state.was_running = True


def compact_now(agent, run: dict) -> None:
    """`/compact`: compact regardless of the threshold. An outcome that leaves no record in `agent.compactions`
    (refused, nothing to compact) is kept as the run's notice; recorded ones are toasted from the records.

    Runs on the background thread, so it gets the agent and run as arguments: no `st.session_state` there."""
    before = len(agent.compactions)
    status = agent.compact(force=True)
    if len(agent.compactions) == before:
        run["notice"] = f"[compaction {status}]"


def load_named(spec: str):
    """The function named as `module:function`. The module may be one of the project the app was started in."""
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def new_chat() -> None:
    """A fresh agent, built by AGENT_FACTORY. The old agent is closed."""
    if old := st.session_state.get("agent"):
        old.close()
    st.session_state.agent = load_named(AGENT_FACTORY)(MODEL, reasoning=reasoning_effort())
    st.session_state.agent.budget.log_path = USAGE_LOG  # every call in its tree, subagents' between turns included
    st.session_state.histories = {}  # budget path -> that agent's list[Entry]
    st.session_state.view = st.session_state.agent.budget.path  # the agent picker's value
    st.session_state.run = {"thread": None, "error": None, "notice": None}
    st.session_state.compactions_seen = 0


def reasoning_effort() -> str | None:
    """The sidebar's reasoning level as `Agent.reasoning` takes it: None for "off"."""
    level = st.session_state.get("reasoning", "medium")
    return None if level == "off" else level


def set_reasoning() -> None:
    """Apply the picked level to the live agent: each request reads `agent.reasoning`, so no new chat is needed."""
    st.session_state.agent.reasoning = reasoning_effort()


def show(path: str) -> None:
    """Show another agent. A button callback: the picker's value can only change before the picker is drawn."""
    st.session_state.view = path


# ---------------------------------------------------------------- html snippets (styles in app.css)


def kind_css() -> str:
    """Each card kind's accent as `--c`, on its block and on anything tagged `k-<kind>`."""
    rules = "".join(f'[class*="st-key-blk-{k}-"], .k-{k} {{ --c:{c}; }}\n' for k, (_, _, c) in KINDS.items())
    return f"<style>{rules}</style>"


def pill(text, *, bold=None, cls: str = "", dot: str | None = None) -> str:
    """A rounded label: an optional status dot, an optional bold value, then the text."""
    dot_html = f'<span class="dot {dot}"></span>' if dot is not None else ""
    bold_html = f"<b>{html.escape(str(bold))}</b> " if bold is not None else ""
    return f'<span class="pill {cls}">{dot_html}{bold_html}{html.escape(str(text))}</span>'


def chips(items, *, on=(), empty_text: str = "none") -> str:
    """A wrapping row of pills; items in `on` are highlighted."""
    if not items:
        return f'<div class="row">{pill(empty_text)}</div>'
    return '<div class="row">' + "".join(pill(i, cls="mono on" if i in on else "mono") for i in items) + "</div>"


def card(kind: str, text: str, *, classes: str = "", mono: bool = False) -> str:
    """A card: kind label and icon over one line of text."""
    label, icon, _ = KINDS[kind]
    return (
        f'<div class="tl-card k-{kind} {classes}"><div class="tl-head"><span>{icon}</span><span>{label}</span>'
        f'</div><div class="tl-prev{" mono" if mono else ""}">{html.escape(text)}</div></div>'
    )


def kv_grid(rows: dict, fmt=json.dumps) -> str:
    """A two-column key/value table; values go through `fmt` (JSON by default, so strings show quoted)."""
    cells = "".join(
        f'<div class="k">{html.escape(str(k))}</div><div>{html.escape(fmt(v))}</div>' for k, v in rows.items()
    ) or '<div class="k">—</div><div>none</div>'
    return f'<div class="kv">{cells}</div>'


def logo() -> str:
    """The client logo as an inline image; nothing if the file isn't there."""
    if not LOGO_PATH.exists():
        return ""
    data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f'<img class="logo" src="data:image/svg+xml;base64,{data}" alt="Alstom">'


def brand() -> str:
    """Logo and name, at the start of a page's header."""
    return f'<span class="hdr-brand">{logo()}<span class="hdr-title">{APP_NAME}</span></span>'


def eyebrow(text: str) -> str:
    """Small uppercase section label."""
    return f'<div class="eyebrow">{html.escape(text)}</div>'


def empty(icon: str, text: str) -> None:
    st.html(f'<div class="empty"><div class="big">{icon}</div>{text}</div>')


def show_reasoning(text: str, key: str) -> None:
    """An answer's reasoning, folded away so the answer comes first. `key` tells apart the reasoning blocks."""
    with st.expander("Reasoning", icon=":material/psychology:"), st.container(key=f"thought-{key}"):
        st.markdown(text)


# ---------------------------------------------------------------- rendering


def render_sidebar_top() -> None:
    """Brand and the page picker."""
    with st.sidebar:
        st.html(
            f'<div class="brand">{logo()}<div class="brand-name">{APP_NAME}</div>'
            '<div class="brand-sub">Rolling stock BOM analysis</div></div>'
        )
        st.segmented_control("Page", PAGES, key="page", default=PAGES[0], label_visibility="collapsed")


def render_sidebar(agent) -> None:
    tools = sorted(agent._all_tools())
    if agent.needs_approval:
        note = f"<b>Asks before</b> {html.escape(', '.join(sorted(agent.needs_approval)))}"
    else:
        note = "<b>Nothing else</b> — these are all it can do, and they run without asking"
    with st.sidebar:
        st.html(eyebrow(f"TOOLS · {len(tools)}"))
        st.html(chips(tools))
        st.html(f'<div class="shell-note">{note}</div>')
        st.html(eyebrow(f"SKILLS · {len(agent.skills)}"))
        st.html(chips(sorted(agent.skills), on=agent.loaded_skills, empty_text="no skills found"))
        st.html(eyebrow("SESSION"))
        st.html('<div class="row">' + pill(agent.model, cls="model") + "</div>")
        st.segmented_control("Reasoning effort", REASONING_LEVELS, default="medium", required=True,
                             key="reasoning", on_change=set_reasoning,
                             help="Sent with each of the main agent's requests, from the next one on, "
                                  "so it can change mid-chat. Subagents keep their own (medium).")
        budget = agent.budget  # the agent and any subagents
        if budget.limit:
            st.progress(min(budget.spent / budget.limit, 1.0),
                        text=f"${budget.spent:.4f} of ${budget.limit:.2f} budget")
        render_agents(agent)


def agent_label(view: View) -> str:
    """The picker's line for an agent: its name, runs indented by depth. It must never change, status included:
    the browser sends the picked label back, and a label that no longer matches an option loses the pick."""
    if view.run is None:
        return f"**{view.path}**"
    indent = "\u2003" * (view.path.count("/") - 1)  # em spaces: markdown collapses plain ones
    return f"{indent}↳ **#{view.id}** {view.profile}"


def agent_caption(view: View) -> str:
    """The picker's second line: a status dot and status, the agent's own calls and spend, and a run's task."""
    status, reason = status_of(view)
    parts = [f":{STATUSES[status][0]}[●] " + (f"{status} ({reason})" if reason else status),
             f"{len(view.agent.usage)} calls · ${view.agent.total_cost:.4f}"]
    if view.run is not None:
        parts.append(clip(re.sub(r"[*_`#>\[\]]+", "", view.run.task), 48))  # plain text: captions are markdown
    return " · ".join(parts)


def render_agents(agent) -> None:
    """The agent picker: the main agent and every subagent run, and a notice for results waiting to be delivered.
    Refreshed by full reruns, which `tree_state` triggers whenever a run starts or ends."""
    views = agent_views(agent)
    st.html(eyebrow(f"AGENTS · {len(views)}"))
    st.radio("Agent to inspect", list(views), key="view", format_func=lambda path: agent_label(views[path]),
             captions=[agent_caption(v) for v in views.values()], label_visibility="collapsed")
    if agent.subagents and not agent.subagents.snapshot():
        st.caption("No subagents started yet.")
    if pending := agent.subagents.pending if agent.subagents else 0:
        st.info(f"{pending} subagent result{'s' if pending > 1 else ''} waiting; your next message delivers "
                f"{'them' if pending > 1 else 'it'}.", icon=":material/inbox:")


def render_header(view: View, running: bool) -> None:
    agent = view.agent
    status, _ = status_of(view)
    _, dot, cls = STATUSES[status]
    pills = [pill(view.path, bold=f"#{view.id} {view.profile}", cls="on")] if view.run else []
    pills += [pill(agent.model, cls="model"), pill(status, dot=dot, cls=cls)]
    if agent.usage:
        pills.append(pill(usage_line(agent.usage), cls="mono"))

    with st.container(horizontal=True, vertical_alignment="center", wrap=False):
        st.html(f'<div class="hdr">{brand()}{"".join(pills)}</div>')
        if view.run is None:
            if running:
                st.button("Stop", icon=":material/stop_circle:", on_click=agent.interrupt, type="primary")
            else:
                st.button("New chat", icon=":material/refresh:", on_click=new_chat)
        elif running:
            st.button("Cancel run", icon=":material/cancel:", on_click=view.run.cancel, type="primary",
                      help="Stops this subagent, and any it started, after the model call it is making.")
        else:
            st.button("Back to main", icon=":material/arrow_back:", on_click=show,
                      args=(st.session_state.agent.budget.path,))

    if view.run is not None:  # a run's warnings are in how it ended
        outcome = view.run.outcome(0)
        if outcome and outcome.status == "failed":
            st.error(outcome.text, icon=":material/error:")
        elif outcome and outcome.status == "stopped":
            st.warning(f"Stopped before answering: {outcome.reason}", icon=":material/warning:")
        return
    if error := st.session_state.run["error"]:
        st.error(error, icon=":material/error:")
    if not running and agent.interrupted and agent.last_cost_unknown and not agent.over_budget:
        st.warning(COST_UNKNOWN, icon=":material/warning:")
    if not running and agent.interrupted and agent.stop_reason:
        st.warning(agent.stop_reason, icon=":material/warning:")


def render_chat(entries: list[Entry], running: bool, pending: bool, agent) -> None:
    """The conversation: the user's messages and the agent's answers, each answer's reasoning folded above it."""
    shown = [(e, kind) for e in entries if (kind := turn_kind(e.msg)) in CHAT_KINDS]
    with st.container(height=640, autoscroll=True, border=False, key="chat"):
        if not shown and not running:
            empty("✦", "Ask something below.")
        for e, kind in shown:
            with st.container(key=f"msg-{kind}-{e.uid}"):
                st.html(eyebrow(CHAT_KINDS[kind]))
                if mget(e.msg, "reasoning"):
                    show_reasoning(mget(e.msg, "reasoning"), f"chat-{e.uid}")
                st.markdown(mget(e.msg, "content"))
        if running:
            with st.container(key="blk-thinking-chat-live"):
                st.html(card("thinking", "working…", classes="ghost"))
        elif pending:
            render_approval(agent)


def render_trace(entries: list[Entry], running: bool, pending: bool, agent) -> None:
    """The agent's work in order: under each question, the reasoning and tool calls that led to its answer."""
    with st.container(height=640, autoscroll=True, border=False, key="trace"):
        if not running and not any(turn_kind(e.msg) in STEP_KINDS for e in entries):
            empty("⚒", "The agent's reasoning and tool calls show up here.")
            return
        compacted_run = 0
        for pos, e in enumerate(entries):
            if e.in_context and compacted_run:
                text = f"⟲ {compacted_run} messages compacted"
                if rec := compaction_of(agent, e.msg):
                    text += f" · ~{human(rec['tokens_before'])} → ~{human(rec['tokens_after'])} tokens"
                st.html(f'<div class="divider">{text}</div>')
            compacted_run = 0 if e.in_context else compacted_run + 1

            kind = turn_kind(e.msg)
            if kind == "user":
                st.html(f'<div class="question">{html.escape(clip(mget(e.msg, "content"), 120))}</div>')
            elif kind in STEP_KINDS:
                render_step(entries, pos, running, pending)
        if running:
            with st.container(key="blk-thinking-live"):
                st.html(card("thinking", "waiting for model…", classes="ghost"))


def render_step(entries: list[Entry], pos: int, running: bool, pending: bool) -> None:
    """One step of the agent: its reasoning, any text it wrote, then each tool call, unfolding to its arguments
    and result."""
    step = entries[pos]
    if mget(step.msg, "reasoning"):
        with st.container(key=f"thought-step-{step.uid}"):
            st.markdown(mget(step.msg, "reasoning"))
    if mget(step.msg, "content"):
        st.markdown(mget(step.msg, "content"))
    results = {mget(e.msg, "tool_call_id"): e for e in results_of(entries, pos)}
    is_last = pos + len(results) == len(entries) - 1
    for i, call in enumerate(mget(step.msg, "tool_calls") or []):
        result = results.get(call.get("id"))
        failed = result is not None and is_error(result.msg)
        label = "`" + clip(call_summary(call), 90).replace("`", "'") + "`" + (" :red[failed]" if failed else "")
        # keyed, so it stays unfolded while the page polls and its result arrives
        with st.expander(label, key=f"call-{step.uid}-{i}", icon=":material/error:" if failed else ":material/build:"):
            render_args(parse_args(call))
            st.html(eyebrow("↳ RESULT"))
            if result is not None:
                render_output(result)
            elif running and is_last:
                st.caption("running…")
            elif pending and is_last:
                st.caption("waiting for approval")
            else:
                st.caption("no result")


def render_approval(agent) -> None:
    """The first call waiting for approval, with Approve / Deny. Sending a message instead also answers it."""
    name, arguments = agent.pending_calls[0]
    with st.container(key="blk-approval-pending"):
        st.html(card("approval", f"{name}() wants to run:", mono=True))
        command = arguments.get("command") if name == "bash" else None
        st.code(command or json.dumps(arguments, indent=2), language="bash" if command else "json", wrap_lines=True)
        reason = st.text_input("Reason", key="deny_reason", placeholder="optional reason, sent to the model on deny",
                               label_visibility="collapsed")
        with st.container(horizontal=True):
            if st.button("Approve", icon=":material/check:", type="primary"):
                start_run(agent.approve)
                st.rerun()
            if st.button("Deny", icon=":material/block:"):
                start_run(agent.deny, reason)
                st.rerun()


def render_args(args: dict) -> None:
    """Short arguments in a key/value table; commands and long or multi-line strings as code blocks."""
    def is_long(k, v):
        return isinstance(v, str) and (k == "command" or "\n" in v or len(v) > LONG_ARG)

    short = {k: v for k, v in args.items() if not is_long(k, v)}
    if short or not args:
        st.html(kv_grid(short))
    for k, v in args.items():
        if is_long(k, v):
            st.html(eyebrow(k))
            st.code(v, language="bash" if k == "command" else None, wrap_lines=True)


def render_output(result: Entry) -> None:
    """A tool result's content: pretty JSON when it parses as JSON, height-capped when long, red when it failed."""
    content, language = str(mget(result.msg, "content")), None
    try:
        parsed = json.loads(content)
        if isinstance(parsed, (dict, list)):
            content, language = json.dumps(parsed, indent=2), "json"
    except ValueError:
        pass
    height = 420 if content.count("\n") > 20 else "content"
    with st.container(key=f"errout-{result.uid}") if is_error(result.msg) else nullcontext():
        st.code(content, language=language, wrap_lines=True, height=height)


def render_data() -> None:
    """The Raw data page: the files in DATA_DIR, read-only (data_page.py)."""
    files = data_files()
    pills = [pill(DATA_DIR.relative_to(Path.cwd()), cls="mono"), pill("files", bold=len(files)), pill("read-only")]
    st.html(f'<div class="hdr">{brand()}{"".join(pills)}</div>')
    if files:
        render_data_page()
    else:
        empty("▤", f"No .csv or .jsonl files in<br>{html.escape(str(DATA_DIR))}")


def render_database() -> None:
    """The Reconciled data page: the raw files with the claims in force applied, read-only (db_page.py)."""
    count = claims_in_force()
    pills = [pill(DB_PATH.relative_to(Path.cwd()), cls="mono"), pill("raw data +"),
             pill("claims in force", bold=count or 0), pill("rebuilt after every claim"), pill("read-only")]
    st.html(f'<div class="hdr">{brand()}{"".join(pills)}</div>')
    if count is None:
        empty("▤", f"No database at<br>{html.escape(str(DB_PATH))}")
    else:
        render_db_page()


def render_claims() -> None:
    """The Claims page: the project's claim log, read-only (claims_page.py)."""
    count = claim_count()
    pills = [pill(CLAIMS_LOG.relative_to(Path.cwd()), cls="mono"), pill("claims", bold=count or 0), pill("read-only")]
    st.html(f'<div class="hdr">{brand()}{"".join(pills)}</div>')
    if count is None:
        empty("▤", f"No claim log at<br>{html.escape(str(CLAIMS_LOG))}")
    else:
        render_claims_page()


def announce_compactions(agent) -> None:
    """Toast each compaction attempt that finished since the last full rerun, and a `/compact` notice.

    Runs in the full script, which reruns when a run ends, so a compaction at the end of a turn is noticed.
    """
    records = agent.compactions
    while st.session_state.compactions_seen < len(records) and records[st.session_state.compactions_seen]["status"]:
        st.toast(compaction_line(records[st.session_state.compactions_seen]), icon=":material/compress:")
        st.session_state.compactions_seen += 1
    if notice := st.session_state.run.pop("notice", None):
        st.toast(notice, icon=":material/compress:")


# ---------------------------------------------------------------- app

st.set_page_config(page_title=APP_NAME, page_icon="🚆", layout="wide")
st.html(CSS_PATH)
st.html(kind_css())

render_sidebar_top()
if "agent" not in st.session_state:
    new_chat()
    st.session_state.was_running = False
render_sidebar(st.session_state.agent)
announce_compactions(st.session_state.agent)
st.session_state.tree_seen = tree_state(st.session_state.agent)


def any_run_going() -> bool:
    return any(not done for _, done in st.session_state.tree_seen[0])


@st.fragment(run_every=POLL_SECONDS if is_running() or any_run_going() else None)
def live_view() -> None:
    agent = st.session_state.agent
    if st.session_state.was_running and not is_running():
        st.session_state.was_running = False
        st.rerun()  # full rerun: stop polling, re-enable the input and refresh the sidebar
    if tree_state(agent) != st.session_state.tree_seen:
        st.rerun()  # a run started or ended, or a result was delivered: refresh the sidebar; stop polling once none runs

    views = agent_views(agent)
    contexts = {path: list(v.agent.messages) for path, v in views.items()}  # snapshots: runs append concurrently
    for path, ctx in contexts.items():  # every agent, not only the one on view, so none misses a compaction
        sync_history(st.session_state.histories.setdefault(path, []), ctx)

    view = views.get(st.session_state.view) or views[agent.budget.path]
    entries = st.session_state.histories[view.path]
    running = is_running() if view.run is None else not view.run.done()
    pending = view.run is None and not running and bool(agent.pending_calls)  # only the main agent asks approval

    render_header(view, running)
    chat_col, work_col = st.columns(2, gap="large")

    with chat_col:
        st.html(eyebrow("CHAT" if view.run is None else f"CHAT · #{view.id} {view.profile.upper()}"))
        render_chat(entries, running, pending, view.agent)
        if view.run is not None:
            st.chat_input("Subagents take no messages: pick the main agent to chat", disabled=True)
        elif prompt := st.chat_input("Agent is working…" if running else "Ask about a sub-assembly or variant…", disabled=running):
            if prompt.strip() == "/compact":  # a UI command: never sent to the model as a message
                start_run(compact_now, agent, st.session_state.run)
            else:
                start_run(agent.run_turn, prompt)
            st.rerun()

    with work_col:
        st.html(eyebrow("AGENT WORK"))
        render_trace(entries, running, pending, view.agent)


if st.session_state.page == PAGES[1]:
    render_data()
elif st.session_state.page == PAGES[2]:
    render_database()
elif st.session_state.page == PAGES[3]:
    render_claims()
else:  # also when the page control is cleared
    live_view()
