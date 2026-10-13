"""Normalising a written reference, and the two tests for "nearly the same reference"."""

import itertools
import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.ingest import Raw

# Anything shaped like a part reference inside free text: two capitals, an optional separator, then digits.
# The letters O and I are allowed among the digits because typos put them there.
REFERENCE_SHAPE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}[- ]?[0-9OI]{2,6}(?![A-Za-z0-9])")


def normalise(ref: str) -> str:
    """The key two spellings share when they differ only by case, separators, or a letter O typed for a zero.

    `DR-1O42` and `dr 1042` both give `DR1042`. The O is only read as 0 after a two-letter prefix followed by
    digits, so the letters of `DOOR-SYS-01` are left alone.
    """
    key = re.sub(r"[^A-Z0-9]", "", ref.upper())
    if re.fullmatch(r"[A-Z]{2}[0-9O]+", key):
        key = key[:2] + key[2:].replace("O", "0")
    return key


def one_apart(a: str, b: str) -> bool:
    """Whether two different keys differ by one character added, dropped or changed."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long = sorted((a, b), key=len)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


def swapped(a: str, b: str) -> bool:
    """Whether two keys differ by two neighbouring characters swapped, as in `RL205` and `RL025`."""
    if len(a) != len(b):
        return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


def loose(text: str) -> str:
    """A name without case, spaces or punctuation: `Sofra-Tec` and `SOFRATEC` both give `SOFRATEC`."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


class RefIndex:
    """The written references grouped by normalised key, with one spelling chosen to stand for each key."""

    def __init__(self, raw: "Raw"):
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
