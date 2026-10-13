"""build(): replays the claims in force over the raw files and writes the resolved model to a SQLite file.

Nothing here is kept between runs. Every build starts from the raw files and the claim log, so the database can
be deleted at any time, and a claim appended to the log changes the model at the next build. No model is involved.

The steps, and the file each one is in:
1. load the raw files, every value as text                                              ingest.py
2. load the claim log and work out which claims are in force                            claims.py
3. group the written values: spellings linked by same_as become one part (or supplier)  resolve.py
4. rewrite the BOM and the prices through those groups, with units converted and
   repeated rows left out                                                               resolve.py
5. compare sub-assemblies by content and give each design a verdict                     compare.py, verdict.py
6. list the open items, then write every table and view                                 reports.py, tables.py

Run: uv run python -m pipeline.build
"""

import argparse
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pipeline.claims import load, select, statuses
from pipeline.compare import Occurrence, build_designs, find_pairs
from pipeline.ingest import BOM_FILE, Raw, read_raw
from pipeline.model import Model
from pipeline.reports import queue
from pipeline.resolve import resolve
from pipeline.tables import write
from pipeline.verdict import VERDICTS, decide, describe_obsolete


def compute(raw: Raw, all_claims: list[dict], without_notes: bool = False) -> Model:
    """Steps 2 to 6 without the write: the model in memory."""
    chosen = select(all_claims, without_notes)
    m = Model(raw, chosen, statuses(chosen))
    resolve(m)
    compare_and_decide(m)
    m.open_items = queue(m)
    return m


def compare_and_decide(m: Model) -> None:
    """Step 5: designs, pairs, verdicts, and the obsolete parts each sub-assembly holds."""
    relations = m.relation_index
    content: dict[tuple[str, str], dict] = defaultdict(dict)
    for line in m.lines:
        if line["level"] == 3:
            m.occurrences.append(Occurrence(line["variant"], line["child"], line["parent"], line["quantity"], line["rows"]))
        elif line["level"] == 4:
            content[(line["variant"], line["parent"])][line["child"]] = line["quantity"]
    known = {(o.variant, o.part) for o in m.occurrences}
    for (variant, parent), lines in content.items():
        if (variant, parent) not in known:
            m.issue("orphan_lines", f"{variant}: {len(lines)} lines under {m.name(parent)}, which is not listed as a "
                    "sub-assembly of that variant", BOM_FILE)
    m.designs = build_designs(m.occurrences, content)
    m.pairs = find_pairs(m.designs, relations, m.cost, m.variants)
    for design in m.designs:
        mine = [pair for pair in m.pairs if design is pair.a or design is pair.b]
        m.verdicts[design.id] = decide(design, mine, m.name)
    for occurrence in m.occurrences:
        occurrence.obsolete_parts = describe_obsolete(occurrence, relations, m.name)


@dataclass
class Summary:
    """What a build produced, small enough to compare with the build before it."""

    parts: int
    designs: int
    verdicts: dict[tuple[str, str], str]  # (variant, sub-assembly reference) -> verdict of its design
    obsolete: dict[tuple[str, str], str]  # (variant, sub-assembly reference) -> obsolete_parts, where it is filled
    issues: dict[str, int]
    open_items: dict[str, int]
    content_changes: dict[int, str]  # claim id -> what an applied insert or delete did, in words
    not_applied: dict[int, str]      # claim id -> why an insert or delete was not applied
    seconds: float

    def line(self) -> str:
        counts = Counter(self.verdicts.values())
        return (f"{self.parts} parts, {self.designs} designs; verdicts: "
                + ", ".join(f"{counts[v]} {v}" for v in VERDICTS)
                + f"; {len(self.obsolete)} sub-assemblies with an obsolete or superseded part"
                + f"; {sum(self.open_items.values())} open items; {sum(self.issues.values())} issues")


def build(raw_dir: str | Path = "data/raw", log_path: str | Path = "data/claims.jsonl",
          out_db: str | Path = "out/pilot.db", without_notes: bool = False) -> Summary:
    """Rebuild the database from the raw files and the claim log.

    `without_notes` replays the log with every claim that rests on a note (it quotes one) left out.
    """
    started = time.perf_counter()
    raw, claims = read_raw(raw_dir), load(log_path)
    model = compute(raw, claims, without_notes)
    # The verdict from the BOM alone: the same replay without any claim that rests on a note.
    plain = model if without_notes else compute(raw, claims, True)
    # Matched by the BOM row that lists the sub-assembly, or by its reference when a person inserted it: it then
    # has no row, and a part id is not the same in the two replays.
    def key(m: Model, o: Occurrence) -> tuple:
        return o.variant, min(o.raw_rows) if o.raw_rows else m.name(o.part)

    bom_only = {key(plain, o): plain.verdicts[o.design.id].verdict for o in plain.occurrences}
    for occurrence in model.occurrences:
        occurrence.verdict_bom_only = bom_only.get(key(model, occurrence), "")
    out_db = Path(out_db)
    out_db.parent.mkdir(parents=True, exist_ok=True)
    write(model, out_db)
    return Summary(
        parts=sum(1 for p in model.parts.values() if p["known"]), designs=len(model.designs),
        verdicts={(o.variant, model.name(o.part)): model.verdicts[o.design.id].verdict for o in model.occurrences},
        obsolete={(o.variant, model.name(o.part)): o.obsolete_parts for o in model.occurrences if o.obsolete_parts},
        issues=dict(Counter(i["type"] for i in model.issues)),
        open_items=dict(Counter(i["kind"] for i in model.open_items)),
        content_changes={c["claim_id"]: c["detail"] for c in model.content_changes},
        not_applied=dict(model.not_applied), seconds=time.perf_counter() - started)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--log", default="data/claims.jsonl")
    parser.add_argument("--out", default="out/pilot.db")
    parser.add_argument("--without-notes", action="store_true", help="leave out every claim that rests on a note")
    args = parser.parse_args()
    summary = build(args.raw, args.log, args.out, args.without_notes)
    print(f"{args.out} built in {summary.seconds:.2f} s: {summary.line()}")
    print("issues:", summary.issues)
    print("open items:", summary.open_items)
