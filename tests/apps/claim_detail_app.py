"""Draws the detail view of some claims of the log in the current directory, for the Claims page's test:
the first claims of each type, and the latest ones."""
from claims_page import load_log, load_raw, paths, render_claim

log_path, raw_dir = paths()
claims, status = load_log(str(log_path), log_path.stat().st_mtime)
raw = load_raw(str(raw_dir), tuple(p.stat().st_mtime for p in sorted(raw_dir.iterdir())))
seen = {}
for claim in claims:
    seen.setdefault(claim["type"], []).append(claim)
chosen = {c["id"]: c for group in seen.values() for c in group[:3]} | {c["id"]: c for c in claims[-40:]}
for claim in chosen.values():
    render_claim(claim, status[claim["id"]], raw, claims)
