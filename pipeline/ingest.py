"""Loads the three raw files as text. Nothing here cleans, converts or drops a value.

A row's `row_no` is its position among the data rows of its file, starting at 1 (the header is not counted).
Claims point at raw rows with it: `bom:619`, `erp:236`, `cell:erp:236:unit_cost_eur`. Notes are pointed at by id.
"""

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.refs import REFERENCE_SHAPE

BOM_FILE, ERP_FILE, NOTE_FILE = "plm_bom_export.csv", "erp_items.csv", "technical_notes.jsonl"
BOM_COLUMNS = ["variant_id", "cars", "speed_class_kmh", "interior", "level", "parent_ref", "child_ref",
               "description", "quantity", "unit"]
ERP_COLUMNS = ["item_ref", "description", "supplier", "unit_cost_eur", "price_unit"]
NOTE_FIELDS = ["note_id", "date", "reference", "text"]
COLUMNS = {"bom": BOM_COLUMNS, "erp": ERP_COLUMNS}


@dataclass
class Raw:
    """The three files in memory: every value a string, as written."""

    bom: list[dict]
    erp: list[dict]
    notes: list[dict]
    _notes_by_id: dict[str, dict] = field(default_factory=dict, repr=False)
    _refs: dict[str, set[str]] | None = field(default=None, repr=False)  # written_refs(), computed once

    def __post_init__(self):
        self._notes_by_id = {note["note_id"]: note for note in self.notes}

    def note(self, note_id: str) -> dict | None:
        return self._notes_by_id.get(note_id)

    def rows(self, file: str) -> list[dict]:
        return {"bom": self.bom, "erp": self.erp}[file]

    def written_refs(self) -> dict[str, set[str]]:
        """Every reference as written, by where it is written: bom, erp, note (the field, and shapes found in text)."""
        if self._refs is not None:
            return self._refs
        found: dict[str, set[str]] = {"bom": set(), "erp": set(), "note": set()}
        for row in self.bom:
            found["bom"].add(row["child_ref"])
            if row["level"] != "2":  # the parent of a system row is the variant, not a part
                found["bom"].add(row["parent_ref"])
        found["erp"].update(row["item_ref"] for row in self.erp)
        for note in self.notes:
            if note["reference"]:
                found["note"].add(note["reference"])
            found["note"].update(REFERENCE_SHAPE.findall(note["text"]))
        self._refs = found
        return found

    def has_ref(self, ref: str) -> bool:
        """Whether `ref` is written, character for character, in a reference column or anywhere in a note's text."""
        if not ref.strip():
            return False
        refs = self.written_refs()
        return ref in refs["bom"] or ref in refs["erp"] or ref in refs["note"] or any(ref in n["text"] for n in self.notes)


def read_raw(raw_dir: str | Path) -> Raw:
    """Read the three files. A line that cannot be parsed stops the run: a skipped line would be a part or a
    note that silently never existed for everything built on top."""
    raw_dir = Path(raw_dir)
    bom = _read_csv(raw_dir / BOM_FILE, ",", BOM_COLUMNS)
    erp = _read_csv(raw_dir / ERP_FILE, ";", ERP_COLUMNS)
    notes = []
    with open(raw_dir / NOTE_FILE, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                note = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{NOTE_FILE} line {line_no} is not valid JSON: {e}") from e
            if set(note) != set(NOTE_FIELDS):
                raise ValueError(f"{NOTE_FILE} line {line_no} has fields {sorted(note)}, expected {NOTE_FIELDS}")
            notes.append({"row_no": len(notes) + 1, **{k: str(note[k]) for k in NOTE_FIELDS}})
    return Raw(bom, erp, notes)


def _read_csv(path: Path, delimiter: str, columns: list[str]) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader)
        if header != columns:
            raise ValueError(f"{path.name} has columns {header}, expected {columns}")
        rows = []
        for values in reader:
            if len(values) != len(columns):
                raise ValueError(f"{path.name} line {reader.line_num} has {len(values)} values, expected {len(columns)}")
            rows.append({"row_no": len(rows) + 1, **dict(zip(columns, values))})
    return rows


def ingest(conn: sqlite3.Connection, raw: Raw) -> dict[str, int]:
    """Write the raw tables, all values as text, and return the rows stored per table."""
    for table, columns, rows in (("raw_bom", BOM_COLUMNS, raw.bom), ("raw_erp", ERP_COLUMNS, raw.erp),
                                 ("raw_note", NOTE_FIELDS, raw.notes)):
        names = ["row_no", *columns]
        conn.execute(f"CREATE TABLE {table} (row_no INTEGER PRIMARY KEY, {', '.join(f'{c} TEXT' for c in columns)})")
        conn.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(names))})",
                         [[row[name] for name in names] for row in rows])
    return {"raw_bom": len(raw.bom), "raw_erp": len(raw.erp), "raw_note": len(raw.notes)}
