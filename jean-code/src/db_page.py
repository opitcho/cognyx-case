"""The Reconciled data page of the UI: what the raw files become once the claims in force are applied.

It reads `out/pilot.db` under the directory the UI was started from, the SQLite database the agent queries. The
project's build computes that file from the raw files and the claims, and computes it again after every claim.

The page is laid out like the Raw data page: a few tabs, one table each, with a sentence saying what one row is
and which raw file it comes from. The tabs are `SECTIONS`. The raw files and the claim log are also copied into
the database, and have their own pages, so they are not shown again here. Every table and view of the file is
listed at the bottom of the page.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path.cwd() / "out" / "pilot.db"
REFRESH_SECONDS = 2  # how often the page looks for a rebuilt database
TABLE_HEIGHT = 520
FILTER_COLUMN = "variant_id"  # a table with this column gets a filter on it
SHOWN_ELSEWHERE = {"raw_bom": "Raw data", "raw_erp": "Raw data", "raw_note": "Raw data", "claim": "Claims",
                   "claim_status": "Claims"}


@dataclass
class Section:
    """One tab: a table, and the sentence above it.

    Args:
        title: The tab's label.
        says: What the table holds, in one or two sentences. `{name}` is replaced by the number `counts` gives it.
        comes_from: The raw files it is computed from.
        reads: The tables and views of the database the query reads, named so the agent's queries can be followed.
        query: The rows of the table.
        counts: Queries that each return one number, for `says`.
        detail: A query for the rows behind a selected row, with `:column` for a value of that row.
        detail_title: What those rows are.
    """

    title: str
    says: str
    comes_from: str
    reads: str
    query: str
    counts: dict[str, str]
    detail: str = ""
    detail_title: str = ""


SECTIONS = [
    Section(
        "Parts",
        "{parts} parts: {systems} systems, {subs} sub-assemblies and {components} components. The raw files write "
        "them in {spellings} different spellings. `written_as` lists the spellings of each part.",
        "plm_bom_export.csv, erp_items.csv", "part, part_cost, v_purchasing",
        """SELECT p.canonical_ref AS reference, p.kind, p.description, p.spellings AS written_as, u.suppliers,
                  c.unit_cost_eur, c.status AS price
           FROM part p LEFT JOIN part_cost c ON c.part_id = p.part_id
                       LEFT JOIN v_purchasing u ON u.canonical_ref = p.canonical_ref
           ORDER BY p.kind DESC, p.canonical_ref""",
        {"parts": "SELECT COUNT(*) FROM part", "systems": "SELECT COUNT(*) FROM part WHERE kind = 'system'",
         "subs": "SELECT COUNT(*) FROM part WHERE kind = 'sub-assembly'",
         "components": "SELECT COUNT(*) FROM part WHERE kind = 'component'",
         "spellings": "SELECT COUNT(*) FROM resolution WHERE kind = 'ref'"},
    ),
    Section(
        "Suppliers",
        "{suppliers} suppliers, written {spellings} different ways in the purchasing file.",
        "erp_items.csv", "supplier, price",
        """SELECT s.name, s.spellings AS written_as, COUNT(DISTINCT p.part_id) AS parts_priced
           FROM supplier s LEFT JOIN price p ON p.supplier_id = s.supplier_id GROUP BY s.supplier_id ORDER BY s.name""",
        {"suppliers": "SELECT COUNT(*) FROM supplier",
         "spellings": "SELECT COUNT(*) FROM resolution WHERE kind = 'supplier'"},
    ),
    Section(
        "Bill of materials",
        "{lines} lines. One line is one component of one sub-assembly in one variant, each part under its one "
        "reference, the quantity in one unit per component, with the component's price.",
        "plm_bom_export.csv, erp_items.csv", "v_content",
        "SELECT * FROM v_content",
        {"lines": "SELECT COUNT(*) FROM v_content"},
    ),
    Section(
        "Relations from notes",
        "{relations} relations between parts. Each is stated by a note, in the words of `quote`, and was recorded "
        "as the claim in `claim_id`.",
        "technical_notes.jsonl", "relation",
        "SELECT type, ref_a, ref_b, option, as_of, note_id, quote, claim_id FROM relation ORDER BY as_of",
        {"relations": "SELECT COUNT(*) FROM relation"},
    ),
    Section(
        "Reuse verdicts",
        "{rows} rows. One row is one sub-assembly in one variant, with its verdict: {reused} reused (the same "
        "content is in two or more variants), {reusable} reusable (it differs from another design by 1 to 3 lines "
        "that no option requires, or a note says another design does the same job), {blocked} blocked (it "
        "contains an obsolete or superseded part), {specific} specific (an option requires the difference, or "
        "there is no counterpart). Select a row to see the facts behind its verdict.",
        "all three files", "v_verdict, v_subassembly_cost, v_evidence",
        """SELECT v.variant_id, v.system_ref, v.subassembly_ref, v.description, v.verdict, v.reason,
                  v.counterpart_ref, c.unit_cost_eur, c.train_cost_eur, c.blocked_by AS cost_blocked_by
           FROM v_verdict v LEFT JOIN v_subassembly_cost c
                ON c.variant_id = v.variant_id AND c.subassembly_ref = v.subassembly_ref""",
        {"rows": "SELECT COUNT(*) FROM v_verdict",
         **{v: f"SELECT COUNT(*) FROM v_verdict WHERE verdict = '{v}'" for v in ("reused", "reusable", "blocked", "specific")}},
        detail="""SELECT kind, detail, claim_id, source_file, source_row FROM v_evidence
                  WHERE variant_id = :variant_id AND subassembly_ref = :subassembly_ref""",
        detail_title="The facts behind the verdict of {subassembly_ref} in {variant_id}",
    ),
    Section(
        "Open items",
        "{items} items wait for a decision, from the agent or from a person. The agent's batch run works through "
        "this list.",
        "all three files", "v_queue",
        "SELECT kind, detail, source_rows, claim_id FROM v_queue",
        {"items": "SELECT COUNT(*) FROM v_queue"},
    ),
]


def connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


@st.cache_data(show_spinner=False)
def read(query: str, mtime: float, params: tuple = ()) -> pd.DataFrame:
    """The rows of a query. `mtime` is only there so a rebuilt database is read again."""
    conn = connect()
    df = pd.read_sql_query(query, conn, params=dict(params))
    conn.close()
    return df


def number(query: str, mtime: float) -> str:
    return f"{int(read(query, mtime).iloc[0, 0]):,}"


@st.cache_data(show_spinner=False)
def catalog(mtime: float) -> pd.DataFrame:
    """One line per table and view the `about` table describes: what one row is, and its row count."""
    conn = connect()
    rows = [{"name": name, "is_a": kind, "one_row_is": one_row_is, "shown_on_page": SHOWN_ELSEWHERE.get(name, ""),
             "rows": conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]}
            for name, kind, one_row_is in conn.execute(
                "SELECT a.name, m.type, a.one_row_is FROM about a JOIN sqlite_master m ON m.name = a.name ORDER BY a.name")]
    conn.close()
    return pd.DataFrame(rows)


def matching(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rows with `query` in any column, ignoring case."""
    if not query:
        return df
    hits = df.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False))
    return df[hits.any(axis=1)]


def claims_in_force() -> int | None:
    """How many claims the database applies, for the page header. None when there is no database."""
    if not DB_PATH.exists():
        return None
    return int(read("SELECT COUNT(*) FROM v_claim_effect", DB_PATH.stat().st_mtime).iloc[0, 0])


def render_section(section: Section, mtime: float) -> None:
    key = section.title
    st.markdown(section.says.format(**{name: number(query, mtime) for name, query in section.counts.items()}))
    st.caption(f"Computed from {section.comes_from} · in the database: {section.reads}")
    df = read(section.query, mtime)
    search_col, filter_col = st.columns([2, 3], vertical_alignment="bottom")
    query = search_col.text_input("Search", key=f"db-search-{key}", placeholder="Search every column…",
                                  label_visibility="collapsed")
    shown = matching(df, query.strip())
    if FILTER_COLUMN in df.columns:
        picked = filter_col.pills(FILTER_COLUMN, sorted(df[FILTER_COLUMN].unique()), selection_mode="multi",
                                  key=f"db-filter-{key}", label_visibility="collapsed")
        if picked:
            shown = shown[shown[FILTER_COLUMN].isin(picked)]
    st.caption(f"{len(shown):,} of {len(df):,} rows")
    height = min(TABLE_HEIGHT, 38 * (len(shown) + 1) + 3)  # a short table takes only the room it needs
    if not section.detail:
        st.dataframe(shown, hide_index=True, height=height, key=f"db-table-{key}")
        return
    event = st.dataframe(shown, hide_index=True, height=height, key=f"db-table-{key}", on_select="rerun",
                         selection_mode="single-row")
    for pos in event.selection.rows:
        if pos < len(shown):
            row = shown.iloc[pos].to_dict()
            wanted = tuple((name, str(row[name])) for name in row if f":{name}" in section.detail)
            with st.container(border=True):
                st.markdown(section.detail_title.format(**row))
                st.dataframe(read(section.detail, mtime, wanted), hide_index=True)


@st.fragment(run_every=REFRESH_SECONDS)
def render_db_page() -> None:
    """The whole page. It reruns on its own every few seconds, so a claim's effect appears while the agent works."""
    mtime = DB_PATH.stat().st_mtime
    for tab, section in zip(st.tabs([s.title for s in SECTIONS]), SECTIONS):
        with tab:
            render_section(section, mtime)
    tables = catalog(mtime)
    with st.expander(f"Every table and view of the SQLite file ({len(tables)})"):
        st.caption("The tabs above read from these. The agent can query all of them. The raw files and the claim "
                   "log are copied in as written, and have their own pages.")
        st.dataframe(tables, hide_index=True, height=TABLE_HEIGHT,
                     column_config={"one_row_is": st.column_config.TextColumn("one row is", width="large")})
