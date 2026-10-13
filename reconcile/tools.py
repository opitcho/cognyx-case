"""The agent's tools: read the resolved model with SQL, and append claims to the log.

The agent never edits the database or the raw files. It reads through a read-only connection, and its only way to
change anything is to append one claim, after which the database is rebuilt and the tool says what changed.
"""

import sqlite3
import time
from collections import Counter
from pathlib import Path

from llm import tool

from pipeline.build import Summary, build
from pipeline.claims import OPPOSITES, ClaimLog, ClaimRefused, pair_key, rests_on_note, split, statuses
from pipeline.ingest import read_raw
from pipeline.refs import RefIndex, normalise
from pipeline.verdict import VERDICTS

MAX_ROWS = 200       # rows a query returns
MAX_CELL = 300       # characters of one value shown
SQL_SECONDS = 5      # a query running longer is stopped
# What a query may do: read. Everything else is refused before it runs, including ATTACH and VACUUM INTO,
# which create a file even on a read-only connection.
READS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
PROPOSE = "Ask the person, or append it with standing=\"proposed\": it is then put to a person."


class Workbench:
    """The agent's access to the data: it reads the SQLite database and appends to the claim log.

    Its four `@tool` methods are what the model calls: `describe_tables` and `run_sql` read the database through
    a read-only connection, `append_claim` and `append_person_claim` write one checked claim to the log. After
    each claim the database is rebuilt from the raw files and the log, so the next query sees its effect.
    Building one also rebuilds the database, so it starts from the log as it is.

    Args:
        db_path: The SQLite file the tools query. Rebuilt on every claim, never edited.
        log_path: The claim log, a JSON Lines file. Only ever appended to.
        raw_dir: The folder with the three raw files. Read, never changed.
        agent_name: Recorded as the maker of the agent's claims, usually the model's id.
        person_name: Recorded as the maker of the claims written in a person's name.
    """

    def __init__(self, db_path: str | Path = "out/pilot.db", log_path: str | Path = "data/claims.jsonl",
                 raw_dir: str | Path = "data/raw", agent_name: str = "agent", person_name: str = "person"):
        self.db_path, self.log_path, self.raw_dir = Path(db_path), Path(log_path), Path(raw_dir)
        self.agent_name, self.person_name = agent_name, person_name
        self.raw = read_raw(self.raw_dir)
        self.siblings = RefIndex(self.raw).siblings
        self.summary: Summary = self.rebuild()

    def rebuild(self) -> Summary:
        self.summary = build(self.raw_dir, self.log_path, self.db_path)
        return self.summary

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    @tool
    def describe_tables(self) -> str:
        """List every table and view of the database: what one row is, its columns, and how many rows it has.
        Names starting with v_ are the ones to query first."""
        conn = self.connect()
        about = dict(conn.execute("SELECT name, one_row_is FROM about"))
        names = [name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
                 if name in about]
        names.sort(key=lambda name: (not name.startswith("v_"), name))  # the names to query first, then the others
        lines = []
        for name in names:
            columns = ", ".join(row[1] for row in conn.execute(f"PRAGMA table_info({name})"))
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            lines.append(f"{name} ({count} rows): {about[name]}\n    {columns}")
        conn.close()
        return "\n".join(lines)

    @tool
    def run_sql(self, query: str) -> str:
        """Run one SQLite query on the database and return the rows. The connection is read-only, and any
        statement other than a SELECT is refused.

        Args:
            query: A single SELECT statement.
        """
        conn = self.connect()
        conn.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in READS else sqlite3.SQLITE_DENY)
        deadline = time.monotonic() + SQL_SECONDS
        conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
        try:
            cursor = conn.execute(query)
            if cursor.description is None:
                return "The query returned no columns. Only SELECT statements are useful here."
            rows = cursor.fetchmany(MAX_ROWS + 1)
        except sqlite3.Error as e:
            if "authoriz" in str(e) or "prohibited" in str(e):  # the authorizer said no
                return "refused: only SELECT statements run here. Column names are in describe_tables."
            return f"error: {e}"
        finally:
            conn.close()
        header = " | ".join(column[0] for column in cursor.description)
        body = [" | ".join("" if value is None else str(value)[:MAX_CELL] for value in row) for row in rows[:MAX_ROWS]]
        more = f"\n(more than {MAX_ROWS} rows: only the first {MAX_ROWS} are shown, narrow the query)" if len(rows) > MAX_ROWS else ""
        return "\n".join([header, *body]) + (more or f"\n({len(body)} rows)")

    @tool
    def append_claim(self, type: str, subject: str, object: str = "", value: str = "", standing: str = "asserted",
                     evidence: list[str] | None = None, quote: str = "", reason: str = "") -> str:
        """Append one claim to the log in your own name. The database is rebuilt and you are told what changed.

        Args:
            type: The claim type, such as same_as, not_same_as, value_is, superseded_by, confirm, retract, reviewed.
            subject: What the claim is about, as a pointer: ref:DR-1042, supplier:Faiveley, cell:bom:53:quantity,
                note:TN-0132, claim:57.
            object: The second thing, for types that take one: ref:..., supplier:..., option:speed_class_kmh=200.
            value: The value, for value_is and converts_to.
            standing: "asserted" to apply the claim now, or "proposed" when the evidence does not decide and a
                person should.
            evidence: Pointers to the raw rows the claim rests on: bom:619, erp:236, note:TN-0132.
            quote: The words of the note that state the claim, copied character for character. The note must be
                in evidence.
            reason: Two or three short sentences for a person who has never seen the database: what the claim says
                about the parts, then the facts that show it, citing BOM rows, purchasing rows and notes. No design
                number, claim number, claim type or table name.
        """
        claim = dict(type=type, subject=subject, object=object, value=value, standing=standing,
                     evidence=evidence or [], quote=quote, reason=reason, made_by="agent", maker=self.agent_name)
        return self._append(claim)

    @tool
    def append_person_claim(self, type: str, subject: str, object: str = "", value: str = "",
                            evidence: list[str] | None = None, quote: str = "", reason: str = "") -> str:
        """Append one claim in the person's name, after the person has given their decision in the conversation.
        It is written at once, so call it only for a decision the person stated, and tell them what was recorded.

        Args:
            type: The claim type. To accept a proposed claim use confirm, to reject it use retract or not_same_as.
            subject: What the claim is about, as a pointer: claim:57, ref:DR-1042, supplier:Faiveley.
            object: The second thing, for types that take one.
            value: The value, for value_is and converts_to.
            evidence: Pointers to the raw rows the claim rests on.
            quote: The words of a note, copied character for character, when the claim rests on one.
            reason: The person's reason, in one sentence.
        """
        claim = dict(type=type, subject=subject, object=object, value=value, standing="asserted",
                     evidence=evidence or [], quote=quote, reason=reason, made_by="person", maker=self.person_name)
        return self._append(claim)

    def _append(self, claim: dict) -> str:
        log = ClaimLog(self.log_path, self.raw)
        notes = [self.raw.note(split(item)[1]) for item in claim["evidence"] if split(item)[0] == "note"]
        notes = [note for note in notes if note]
        quoted = [note for note in notes if claim["quote"] and claim["quote"] in note["text"]]
        if quoted:  # a claim that quotes a note speaks for the note's date
            claim["as_of"] = quoted[0]["date"]
        if claim["made_by"] == "agent" and claim["standing"] == "asserted":
            guard = self._guard(claim, log.claims)
            if guard:
                return f"refused: {guard} {PROPOSE}"
        try:
            claim_id = log.append(claim)
        except ClaimRefused as e:
            return f"refused: {e}"
        if not log.added:
            return f"Nothing written: the same claim is already in the log as claim {claim_id}."
        before = self.summary
        after = self.rebuild()
        if claim["standing"] == "proposed":
            return f"claim {claim_id} recorded as proposed. It is not applied until a person confirms it."
        return f"claim {claim_id} recorded and in force. {changes(before, after)}"

    def _guard(self, claim: dict, claims: list[dict]) -> str:
        """Why the agent may not assert this claim on its own, or an empty string."""
        status = statuses(claims)
        if claim["type"] == "same_as" and split(claim["subject"])[0] == "ref":
            keys = frozenset(normalise(split(claim[end])[1]) for end in ("subject", "object"))
            if keys in self.siblings:
                return "the two references are children of the same parent in the same variant, which marks two parts."
        # A claim that quotes a note may contradict another note's claim: both are recorded, and the later
        # date is applied. Only a claim of the agent's own judgement is stopped here.
        if claim["type"] in OPPOSITES and not (claim["quote"] and claim.get("as_of")):
            for other in claims:
                if (other["type"] == OPPOSITES[claim["type"]] and pair_key(other) == pair_key(claim)
                        and status[other["id"]].in_force and (other["made_by"] == "person" or rests_on_note(other))):
                    return (f"claim {other['id']} says the opposite and "
                            + ("was made by a person." if other["made_by"] == "person" else "rests on a note."))
        if claim["type"] == "value_is" and claim["subject"].startswith("cell:erp:") and claim["subject"].endswith(":unit_cost_eur"):
            return "which price holds is not in the data: purchasing decides."
        if claim["type"] == "retract" and split(claim["subject"])[1].isdigit():
            target = int(split(claim["subject"])[1])
            if 1 <= target <= len(claims) and claims[target - 1]["made_by"] == "person":
                return f"claim {target} was made by a person."
        return ""


def changes(before: Summary, after: Summary) -> str:
    """What one claim changed, in words: parts, designs, verdicts, obsolete parts and open items."""
    parts = []
    if after.parts != before.parts:
        parts.append(f"Parts: {before.parts} to {after.parts}.")
    if after.designs != before.designs:
        parts.append(f"Designs: {before.designs} to {after.designs}.")
    moved = [(key, before.verdicts.get(key), verdict) for key, verdict in sorted(after.verdicts.items())
             if before.verdicts.get(key) != verdict]
    if moved:
        shown = "; ".join(f"{ref} in {variant}, {old or 'new'} to {new}" for (variant, ref), old, new in moved[:8])
        parts.append(f"Verdicts changed ({len(moved)}): {shown}" + ("; ..." if len(moved) > 8 else "") + ".")
    held = [(key, before.obsolete.get(key, ""), after.obsolete.get(key, ""))
            for key in sorted(set(before.obsolete) | set(after.obsolete))
            if before.obsolete.get(key, "") != after.obsolete.get(key, "")]
    if held:
        shown = "; ".join(f"{ref} in {variant}, {old or 'none'} to {new or 'none'}" for (variant, ref), old, new in held[:8])
        parts.append(f"Obsolete parts changed ({len(held)}): {shown}" + ("; ..." if len(held) > 8 else "") + ".")
    open_before, open_after = sum(before.open_items.values()), sum(after.open_items.values())
    if open_after != open_before:
        parts.append(f"Open items: {open_before} to {open_after}.")
    for kind in sorted(set(before.issues) | set(after.issues)):
        if before.issues.get(kind, 0) != after.issues.get(kind, 0):
            parts.append(f"Issues of type {kind}: {before.issues.get(kind, 0)} to {after.issues.get(kind, 0)}.")
    return " ".join(parts) or "No change to parts, designs, verdicts, obsolete parts or open items."


def verdict_counts(summary: Summary) -> str:
    counts = Counter(summary.verdicts.values())
    return (", ".join(f"{counts[v]} {v}" for v in VERDICTS)
            + f"; {len(summary.obsolete)} sub-assemblies with an obsolete or superseded part")
