"""Put the claim log back to the demo's starting point, and rebuild the database.

The starting point is `data/claims.demo_start.jsonl`: the rules' claims and the agent's, and no person's claim.
The log as it was is first copied to `out/`, so a reset loses nothing.

Run: uv run python -m pipeline.reset
"""

import argparse
import shutil
import time
from collections import Counter
from pathlib import Path

from pipeline.build import Summary, build
from pipeline.claims import load

START = Path("data/claims.demo_start.jsonl")


def reset(start: str | Path = START, log_path: str | Path = "data/claims.jsonl", raw_dir: str | Path = "data/raw",
          out_db: str | Path = "out/pilot.db") -> tuple[Path | None, Summary]:
    """Replace the log by `start` and rebuild. Returns where the old log was copied (None if there was none) and
    the build's summary. Raises ValueError if `start` holds a person's claim."""
    start, log_path, out_db = Path(start), Path(log_path), Path(out_db)
    people = [claim["id"] for claim in load(start) if claim["made_by"] == "person"]
    if people:
        raise ValueError(f"{start} holds claims made by a person: {people}")
    kept = None
    if log_path.exists():
        out_db.parent.mkdir(parents=True, exist_ok=True)
        kept = out_db.parent / f"claims.before-reset.{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        shutil.copy(log_path, kept)
    shutil.copy(start, log_path)
    return kept, build(raw_dir, log_path, out_db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default=str(START), help="the log to start from")
    args = parser.parse_args()
    kept, summary = reset(args.start)
    if kept:
        print(f"the log as it was: {kept}")
    makers = Counter(claim["made_by"] for claim in load("data/claims.jsonl"))
    print(f"data/claims.jsonl: {sum(makers.values())} claims, {makers['rule']} by rule, {makers['agent']} by agent, "
          f"{makers['person']} by person")
    print(f"out/pilot.db: {summary.line()}")
    print("open items:", summary.open_items)
