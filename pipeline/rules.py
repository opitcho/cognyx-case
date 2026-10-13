"""The programmatic first pass: the rules that turn what is mechanical in the raw files into claims.

Every rule is one function in the section "the rules" below, and `RULES` at the end of that section lists them
in the order they run. A rule asserts only what needs no judgement, and proposes the rest. It takes the raw files,
returns claims and writes nothing; `run_rules` appends them to the log. A rule's docstring is its description.

To change a rule, edit its function and look at what it now makes with --show. To add one, write the function
and add it to `RULES`.

Run:
    uv run python -m pipeline.rules                    append every rule's claims to the log
    uv run python -m pipeline.rules --list             each rule, what it says and the claims it makes
    uv run python -m pipeline.rules --show near_key    the claims one rule makes now, against the log

--list and --show write nothing.
"""

import argparse
import itertools
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.claims import ClaimLog, identity, load
from pipeline.ingest import Raw, read_raw
from pipeline.refs import loose, normalise, one_apart, swapped

BASE_UNITS = ("pcs", "m", "kg")
# A written unit, lower case -> (base unit, how many base units one of it is).
UNIT_LIST = {"u": ("pcs", "1"), "pce": ("pcs", "1"), "ea": ("pcs", "1"), "mm": ("m", "0.001"), "g": ("kg", "0.001")}
FILLERS = {"", "N/A", "NA", "UNKNOWN", "TBD", "?", "-"}


class RefIndex:
    """The written references grouped by normalised key, with one spelling chosen to stand for each key."""

    def __init__(self, raw: Raw):
        self.spellings: dict[str, set[str]] = defaultdict(set)
        self.first_row: dict[str, str] = {}  # spelling -> the first raw row that writes it
        uses = Counter()  # spelling -> times written in the BOM
        for row in raw.bom:
            for column in ("child_ref", "parent_ref"):
                if column == "parent_ref" and row["level"] == "2":
                    continue
                uses[row[column]] += 1
                self.first_row.setdefault(row[column], f"bom:{row['row_no']}")
        for row in raw.erp:
            self.first_row.setdefault(row["item_ref"], f"erp:{row['row_no']}")
        for note in raw.notes:
            for ref in sorted(raw.written_refs()["note"]):
                if ref == note["reference"] or ref in note["text"]:
                    self.first_row.setdefault(ref, f"note:{note['note_id']}")
        for refs in raw.written_refs().values():
            for ref in refs:
                self.spellings[normalise(ref)].add(ref)
        # The spelling that stands for a key: the one the BOM uses most, then alphabetical order.
        self.canonical = {key: min(group, key=lambda ref: (-uses[ref], ref)) for key, group in self.spellings.items()}
        self.siblings: set[frozenset[str]] = set()  # pairs of keys that are children of one parent in one variant
        children = defaultdict(set)
        for row in raw.bom:
            children[(row["variant_id"], normalise(row["parent_ref"]))].add(normalise(row["child_ref"]))
        for kids in children.values():
            self.siblings.update(frozenset(pair) for pair in itertools.combinations(sorted(kids), 2))

    def near_pairs(self) -> list[tuple[str, str, str]]:
        """Pairs of keys that are nearly the same, with how: (key, key, "one character apart" or "... swapped")."""
        pairs = []
        for a, b in itertools.combinations(sorted(self.spellings), 2):
            if one_apart(a, b):
                pairs.append((a, b, "one character apart"))
            elif swapped(a, b):
                pairs.append((a, b, "two neighbouring characters swapped"))
        return pairs

    def evidence(self, *refs: str) -> list[str]:
        return [self.first_row[ref] for ref in refs if ref in self.first_row]


def claim(rule, type, subject, object="", value="", standing="asserted", evidence=(), reason=""):
    return {"type": type, "subject": subject, "object": object, "value": value, "standing": standing,
            "made_by": "rule", "maker": rule, "evidence": list(evidence), "reason": reason}


def to_base(quantity: str, unit: str) -> tuple[Decimal, str] | None:
    """A written quantity in its base unit, by the fixed list. None if the number or the unit is not understood."""
    try:
        number = Decimal(quantity.replace(",", "."))
    except InvalidOperation:
        return None
    if unit in BASE_UNITS:
        return number.normalize(), unit
    if unit.lower() in UNIT_LIST:
        base, factor = UNIT_LIST[unit.lower()]
        return (number * Decimal(factor)).normalize(), base
    return None


# ---------------------------------------------------------------- the rules


def same_key(raw: Raw) -> list[dict]:
    """Two references equal after normalising are one part."""
    index = RefIndex(raw)
    return [claim("same_key", "same_as", f"ref:{ref}", f"ref:{index.canonical[key]}",
                  evidence=index.evidence(ref, index.canonical[key]),
                  reason="equal once case and separators are removed and O is read as 0")
            for key, group in sorted(index.spellings.items()) for ref in sorted(group) if ref != index.canonical[key]]


def near_key(raw: Raw) -> list[dict]:
    """Two references one character apart, or with two characters swapped, may be one part: a proposal only."""
    index = RefIndex(raw)
    return [claim("near_key", "same_as", f"ref:{index.canonical[a]}", f"ref:{index.canonical[b]}",
                  standing="proposed", evidence=index.evidence(index.canonical[a], index.canonical[b]), reason=how)
            for a, b, how in index.near_pairs()]


def sibling(raw: Raw) -> list[dict]:
    """Two nearly identical references under the same parent in the same variant are two parts: a typo replaces
    a spelling, it does not sit beside it."""
    index = RefIndex(raw)
    rows = defaultdict(dict)  # (variant, parent key) -> child key -> row
    for row in raw.bom:
        rows[(row["variant_id"], normalise(row["parent_ref"]))].setdefault(normalise(row["child_ref"]), row["row_no"])
    claims = []
    for a, b, _ in index.near_pairs():
        if frozenset((a, b)) in index.siblings:
            both = next(kids for kids in rows.values() if a in kids and b in kids)
            claims.append(claim("sibling", "not_same_as", f"ref:{index.canonical[a]}", f"ref:{index.canonical[b]}",
                                evidence=[f"bom:{both[a]}", f"bom:{both[b]}"],
                                reason="both are children of the same parent in the same variant"))
    return claims


def unit_list(raw: Raw) -> list[dict]:
    """Written units from a short fixed list convert to a base unit."""
    written = sorted({row["unit"] for row in raw.bom} | {row["price_unit"] for row in raw.erp})
    return [claim("unit_list", "converts_to", f"unit:{unit}", f"unit:{UNIT_LIST[unit.lower()][0]}",
                  value=UNIT_LIST[unit.lower()][1], reason="from the fixed list of units")
            for unit in written if unit not in BASE_UNITS and unit.lower() in UNIT_LIST]


def same_row(raw: Raw) -> list[dict]:
    """A BOM line written twice with the same quantity, once units are converted, is one line."""
    lines = defaultdict(list)
    for row in raw.bom:
        lines[(row["variant_id"], normalise(row["parent_ref"]), normalise(row["child_ref"]))].append(row)
    claims = []
    for rows in lines.values():
        first = rows[0]
        for row in rows[1:]:
            quantity = to_base(row["quantity"], row["unit"])
            if quantity is not None and quantity == to_base(first["quantity"], first["unit"]):
                claims.append(claim("same_row", "duplicate_of", f"bom:{row['row_no']}", f"bom:{first['row_no']}",
                                    evidence=[f"bom:{row['row_no']}", f"bom:{first['row_no']}"],
                                    reason="same variant, parent, child and quantity"))
    return claims


def filler(raw: Raw) -> list[dict]:
    """An ERP supplier or cost cell that is empty or holds a filler (N/A, NA, UNKNOWN, TBD, ? or -) holds no value."""
    return [claim("filler", "no_value", f"cell:erp:{row['row_no']}:{column}", evidence=[f"erp:{row['row_no']}"],
                  reason=f"{row[column]!r} is a filler" if row[column] else "the cell is empty")
            for row in raw.erp for column in ("supplier", "unit_cost_eur") if row[column].strip().upper() in FILLERS]


def supplier_key(raw: Raw) -> list[dict]:
    """Supplier names equal without case and punctuation are one supplier. When one name starts with another,
    that is a proposal."""
    uses = Counter(row["supplier"] for row in raw.erp if row["supplier"].strip().upper() not in FILLERS)
    first = {}
    for row in raw.erp:
        first.setdefault(row["supplier"], f"erp:{row['row_no']}")
    groups = defaultdict(list)
    for name in uses:
        groups[loose(name)].append(name)
    canonical = {key: min(names, key=lambda n: (-uses[n], n)) for key, names in groups.items()}
    claims = [claim("supplier_key", "same_as", f"supplier:{name}", f"supplier:{canonical[key]}",
                    evidence=[first[name], first[canonical[key]]], reason="equal without case and punctuation")
              for key, names in sorted(groups.items()) for name in sorted(names) if name != canonical[key]]
    for a, b in itertools.combinations(sorted(groups), 2):
        if a.startswith(b) or b.startswith(a):
            claims.append(claim("supplier_key", "same_as", f"supplier:{canonical[a]}", f"supplier:{canonical[b]}",
                                standing="proposed", evidence=[first[canonical[a]], first[canonical[b]]],
                                reason="one name starts with the other"))
    return claims


def note_field(raw: Raw) -> list[dict]:
    """A note whose reference field is filled is about that part."""
    return [claim("note_field", "mentions", f"note:{note['note_id']}", f"ref:{note['reference']}",
                  evidence=[f"note:{note['note_id']}"], reason="the note's reference field")
            for note in raw.notes if note["reference"]]


RULES = [same_key, near_key, sibling, unit_list, same_row, filler, supplier_key, note_field]


# ---------------------------------------------------------------- running them


def run_rules(log_path: str | Path, raw_dir: str | Path) -> dict[str, tuple[int, int]]:
    """Append every rule's claims to the log. Returns, per rule, the claims it made and how many were new."""
    raw = read_raw(raw_dir)
    log = ClaimLog(log_path, raw)
    counts = {}
    for rule in RULES:
        claims = rule(raw)
        new = 0
        for item in claims:
            log.append(item)
            new += log.added
        counts[rule.__name__] = (len(claims), new)
    return counts


def list_rules(raw: Raw) -> list[str]:
    """Two lines per rule: its name and description, then how many claims of each type and standing it makes."""
    lines = []
    for rule in RULES:
        made = Counter((c["type"], c["standing"]) for c in rule(raw))
        lines.append(f"{rule.__name__:13} {' '.join(rule.__doc__.split())}")
        lines.append(f"{'':13} makes " + (", ".join(f"{n} {t} {s}" for (t, s), n in sorted(made.items())) or "nothing"))
    return lines


def written(mark: str, claim: dict) -> str:
    about = claim["subject"] + (f" -> {claim['object']}" if claim["object"] else "")
    value = f" = {claim['value']}" if claim["value"] else ""
    evidence = f" ({', '.join(claim['evidence'])})" if claim["evidence"] else ""
    return f"{mark} {claim['type']} {about}{value} [{claim['standing']}] {claim['reason']}{evidence}"


def show(rule, raw: Raw, log_path: str | Path) -> list[str]:
    """The claims one rule makes now, one per line, each marked against what the log holds from that rule.

    A blank mark: the claim is in the log. `+`: it is not, and running the rules would append it. `~`: it is in
    the log with the other standing. `-`: it is in the log and the rule no longer makes it. The last line counts
    them.
    """
    logged = {identity(c): c for c in load(log_path) if c["made_by"] == "rule" and c["maker"] == rule.__name__}
    made = {identity(c): c for c in rule(raw)}
    lines, marks = [], Counter()
    for key, claim in made.items():
        mark = "+" if key not in logged else " " if logged[key]["standing"] == claim["standing"] else "~"
        marks[mark] += 1
        lines.append(written(mark, claim))
    for key, claim in logged.items():
        if key not in made:
            marks["-"] += 1
            lines.append(written("-", claim) + f" (claim {claim['id']})")
    lines.append(f"{rule.__name__}: {len(made)} claims made; {marks['+']} not in the log (+), {marks['~']} in the log "
                 f"with the other standing (~), {marks['-']} in the log and no longer made (-)")
    if marks["~"] or marks["-"]:
        lines.append("The log is only appended to: running the rules adds the + lines and leaves the ~ and - claims "
                     "as they are in the log.")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--log", default="data/claims.jsonl")
    what = parser.add_mutually_exclusive_group()
    what.add_argument("--list", action="store_true", help="print each rule and the claims it makes; write nothing")
    what.add_argument("--show", choices=[rule.__name__ for rule in RULES], metavar="RULE",
                      help="print the claims one rule makes now, against the log; write nothing")
    args = parser.parse_args()
    if args.list:
        print("\n".join(list_rules(read_raw(args.raw))))
    elif args.show:
        rule = next(rule for rule in RULES if rule.__name__ == args.show)
        print("\n".join(show(rule, read_raw(args.raw), args.log)))
    else:
        for name, (made, new) in run_rules(args.log, args.raw).items():
            print(f"{name:13} {made:4} claims, {new:4} new")
