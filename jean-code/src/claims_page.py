"""The Claims page of the UI: a read-only look at a project's claim log, with the raw rows each claim rests on.

The log is `data/claims.jsonl` under the directory the UI was started from, next to the `data/raw` files of the
Data page. A claim is one statement about the raw data ("these two spellings are one part"), with who made it and
its evidence; the log is only ever appended to.

What a claim's status is, and how a raw row is read, belong to the project, not to the UI: they come from the
project's `pipeline` package (`pipeline.claims`, `pipeline.ingest`), found in the same directory. The page and
the project's build therefore cannot disagree about which claims are in force.
"""

import html
import importlib
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st


REFRESH_SECONDS = 2  # how often the page looks for new lines in the log
TABLE_COLUMNS = ["id", "type", "subject", "object", "value", "status", "made_by", "maker", "reason"]
TABLE_HEIGHT = 420


def paths() -> tuple[Path, Path]:
    """The log and the raw files, under the directory the UI runs in."""
    return Path.cwd() / "data" / "claims.jsonl", Path.cwd() / "data" / "raw"


CLAIMS_LOG = paths()[0]  # where the UI was started, for the page header


def project(module: str):
    """A module of the project the UI was started in, such as `pipeline.claims`."""
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    return importlib.import_module(module)


def claim_count() -> int | None:
    """How many claims the log holds, for the page header. None when there is no log."""
    log_path = paths()[0]
    return sum(1 for line in open(log_path, encoding="utf-8") if line.strip()) if log_path.exists() else None


@st.cache_data(show_spinner=False)
def load_log(path: str, mtime: float) -> tuple[list[dict], dict[int, str]]:
    """The claims and the status of each. `mtime` is only there so a longer log is read again."""
    log = project("pipeline.claims")
    claims = log.load(path)
    return claims, {claim_id: str(status) for claim_id, status in log.statuses(claims).items()}


@st.cache_resource(show_spinner=False)
def load_raw(raw_dir: str, mtimes: tuple[float, ...]):
    return project("pipeline.ingest").read_raw(raw_dir)


def matching(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rows with `query` in any column, ignoring case."""
    if not query:
        return df
    hits = df.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False))
    return df[hits.any(axis=1)]


def state_of(status: str) -> str:
    """`retracted by claim 7` -> `retracted`."""
    return status.split(" by ")[0]


def render_target(target: str, raw, claims: list[dict], quote: str = "") -> None:
    """What a pointer such as bom:619 or note:TN-0132 points at, as written in the raw files."""
    split, columns = project("pipeline.claims").split, project("pipeline.ingest").COLUMNS
    kind, rest = split(target)
    if kind in ("bom", "erp") and rest.isdigit() and 1 <= int(rest) <= len(raw.rows(kind)):
        row = raw.rows(kind)[int(rest) - 1]
        st.caption(f"`{target}` · " + " · ".join(f"{name}: {row[name]}" for name in columns[kind] if row[name]))
    elif kind == "cell":
        file, _, more = rest.partition(":")
        row_no, _, column = more.partition(":")
        row = raw.rows(file)[int(row_no) - 1]
        st.caption(f"`{target}` · written value: {row[column]!r} · "
                   + " · ".join(f"{name}: {row[name]}" for name in columns[file] if row[name] and name != column))
    elif kind == "note" and raw.note(rest):
        note = raw.note(rest)
        text = html.escape(note["text"])
        if quote and html.escape(quote) in text:
            text = text.replace(html.escape(quote), f"<mark>{html.escape(quote)}</mark>")
        reference = f" · reference field: {html.escape(note['reference'])}" if note["reference"] else ""
        st.html(f"<div><code>{html.escape(target)}</code> · {note['date']}{reference}<br>{text}</div>")
    elif kind == "claim" and rest.isdigit() and 1 <= int(rest) <= len(claims):
        other = claims[int(rest) - 1]
        st.caption(f"`{target}` · {other['type']}({other['subject']}"
                   + (f", {other['object']}" if other["object"] else "") + f") · by {other['made_by']} {other['maker']}")
    else:
        st.caption(f"`{target}`")


def render_claim(claim: dict, status: str, raw, claims: list[dict]) -> None:
    """One claim in full: what it says, who made it, and the raw rows behind it."""
    with st.container(border=True):
        types, split = project("pipeline.claims").TYPES, project("pipeline.claims").split
        says = types[claim["type"]].says if claim["type"] in types else ""
        about = claim["subject"] + (f", {claim['object']}" if claim["object"] else "")
        value = f" = {claim['value']}" if claim["value"] else ""
        st.markdown(f"**Claim {claim['id']}** · `{claim['type']}({about}){value}` · {status}")
        st.caption(f"{says} · made by {claim['made_by']} ({claim['maker']}) · standing: {claim['standing']}"
                   + (f" · as of {claim['as_of']}" if claim["as_of"] else ""))
        if claim["reason"]:
            st.markdown(f"Reason: {claim['reason']}")
        pointers = [t for t in (claim["subject"], claim["object"]) if split(t)[0] in ("bom", "erp", "cell", "note", "claim")]
        pointers += [item for item in claim["evidence"] if item not in pointers]
        if pointers:
            st.markdown("Evidence, as written in the raw files:")
            for target in pointers:
                render_target(target, raw, claims, claim["quote"])
        elif claim["quote"]:
            st.markdown(f"Quote: {claim['quote']}")
        targeting = [c for c in claims if c["type"] in ("confirm", "retract") and c["subject"] == f"claim:{claim['id']}"]
        for other in targeting:
            st.caption(f"Claim {other['id']}: {other['type']} by {other['made_by']} ({other['maker']})"
                       + (f" · {other['reason']}" if other["reason"] else ""))


@st.fragment(run_every=REFRESH_SECONDS)
def render_claims_page() -> None:
    """The whole page. It reruns on its own every few seconds, so claims appear while the agent works."""
    log_path, raw_dir = paths()
    if not log_path.exists():
        st.info(f"No claim log yet at {log_path}.")
        return
    try:
        project("pipeline.claims")
    except ImportError:
        st.info(f"The log at {log_path} needs the project's `pipeline` package to be read, and {Path.cwd()} has none.")
        return
    claims, status = load_log(str(log_path), log_path.stat().st_mtime)
    raw = load_raw(str(raw_dir), tuple(p.stat().st_mtime for p in sorted(raw_dir.iterdir())))

    makers = Counter(claim["made_by"] for claim in claims)
    states = Counter(state_of(status[claim["id"]]) for claim in claims)
    waiting = sum(1 for claim in claims if status[claim["id"]] == "proposed")
    st.caption(f"{len(claims):,} claims · " + " · ".join(f"{makers[m]:,} by {m}" for m in ("rule", "agent", "person"))
               + f" · {waiting} proposed and waiting · {states['retracted']} retracted · {states['overridden']} overridden")

    df = pd.DataFrame([{**claim, "status": status[claim["id"]]} for claim in reversed(claims)])[TABLE_COLUMNS]
    search_col, maker_col, state_col = st.columns([2, 2, 3], vertical_alignment="bottom")
    query = search_col.text_input("Search", key="claims-search", placeholder="Search every field, e.g. DR-1042",
                                  label_visibility="collapsed")
    picked_makers = maker_col.pills("made_by", ["rule", "agent", "person"], selection_mode="multi",
                                    key="claims-makers", label_visibility="collapsed")
    picked_states = state_col.pills("status", ["in force", "proposed", "confirmed", "retracted", "overridden"],
                                    selection_mode="multi", key="claims-states", label_visibility="collapsed")
    picked_types = st.pills("type", sorted(df["type"].unique()), selection_mode="multi", key="claims-types",
                            label_visibility="collapsed")
    shown = matching(df, query.strip())
    if picked_makers:
        shown = shown[shown["made_by"].isin(picked_makers)]
    if picked_states:
        shown = shown[shown["status"].map(state_of).isin(picked_states)]
    if picked_types:
        shown = shown[shown["type"].isin(picked_types)]

    st.caption(f"{len(shown):,} of {len(df):,} claims, newest first · select a row to see its evidence")
    event = st.dataframe(shown, hide_index=True, height=TABLE_HEIGHT, key="claims-table", on_select="rerun",
                         selection_mode="single-row")
    for pos in event.selection.rows:
        if pos < len(shown):
            claim = claims[int(shown.iloc[pos]["id"]) - 1]
            render_claim(claim, status[claim["id"]], raw, claims)
