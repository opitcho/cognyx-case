"""The Raw data page of the UI: a read-only look at the raw files, before any rule or claim.

The files are the ones in `data/raw` under the directory the UI was started from. Values are shown as the strings
in the file: nothing is parsed or cleaned. What the agent queries is the database computed from them, on the Reconciled data page (db_page.py).
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path.cwd() / "data" / "raw"
SUFFIXES = (".csv", ".jsonl")
FILTER_COLUMN = "variant_id"  # a file with this column gets a filter on it
LONG_TEXT = 120  # a file with a value longer than this lets you select a row and read it in full
TABLE_HEIGHT = 560


def data_files() -> list[Path]:
    if not DATA_DIR.is_dir():
        return []
    return sorted(p for p in DATA_DIR.iterdir() if p.suffix in SUFFIXES)


@st.cache_data(show_spinner=False)
def load(path: str, mtime: float) -> pd.DataFrame:
    """The file as a table of strings. `mtime` is only there so an edited file is read again."""
    if path.endswith(".jsonl"):
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        return pd.DataFrame(rows).fillna("").astype(str)
    return pd.read_csv(path, sep=None, engine="python", dtype=str, keep_default_na=False)  # sep=None: , or ;


def matching(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rows with `query` in any column, ignoring case."""
    if not query:
        return df
    hits = df.apply(lambda col: col.str.contains(query, case=False, regex=False))
    return df[hits.any(axis=1)]


def render_row(row: pd.Series, long_columns: list[str]) -> None:
    """One row in full: the short values on a line, then each long text."""
    with st.container(border=True):
        st.caption(" · ".join(f"{name}: {value}" for name, value in row.items() if name not in long_columns and value))
        for name in long_columns:
            st.markdown(row[name])


def render_file(path: Path) -> None:
    df = load(str(path), path.stat().st_mtime)
    search_col, filter_col = st.columns([2, 3], vertical_alignment="bottom")
    query = search_col.text_input("Search", key=f"search-{path.name}", placeholder="Search every column…",
                                  label_visibility="collapsed")
    shown = matching(df, query.strip())
    if FILTER_COLUMN in df.columns:
        values = sorted(df[FILTER_COLUMN].unique())
        picked = filter_col.pills(FILTER_COLUMN, values, selection_mode="multi", key=f"filter-{path.name}",
                                  label_visibility="collapsed")
        if picked:
            shown = shown[shown[FILTER_COLUMN].isin(picked)]

    long_columns = [c for c in df.columns if df[c].str.len().max() > LONG_TEXT]
    st.caption(f"{len(shown):,} of {len(df):,} rows · {len(df.columns)} columns"
               + (" · select a row to read it in full" if long_columns else ""))
    if not long_columns:
        st.dataframe(shown, hide_index=True, height=TABLE_HEIGHT)
        return
    event = st.dataframe(shown, hide_index=True, height=TABLE_HEIGHT // 2, key=f"table-{path.name}",
                         on_select="rerun", selection_mode="single-row")
    for pos in event.selection.rows:
        render_row(shown.iloc[pos], long_columns)


def render_data_page() -> None:
    files = data_files()
    for tab, path in zip(st.tabs([p.name for p in files]), files):
        with tab:
            render_file(path)
