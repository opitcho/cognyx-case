"""Comparison of sub-assemblies by content: designs, near pairs, functional pairs and their differing lines.

Everything here works on parts that are already resolved (one id per real part) and quantities already in a base
unit. `resolve.py` prepares those and `tables.py` writes the results.
"""

import hashlib
import itertools
from dataclasses import dataclass, field
from decimal import Decimal

MAX_DIFF = 3    # a near pair differs by 1 to 3 lines
MIN_SHARED = 4  # and shares at least 4 components
OPTIONS = ("cars", "speed_class_kmh", "interior")


@dataclass
class Occurrence:
    """One sub-assembly in one variant."""

    variant: str
    part: str
    system: str
    per_train: Decimal | None
    raw_rows: list[int]
    design: "Design | None" = None
    verdict: "object | None" = None  # its Verdict: the design's, or blocked when its own reference is dead
    verdict_bom_only: str = ""       # the verdict of the same replay without any claim that rests on a note


@dataclass
class Design:
    """One distinct content: a set of (component, quantity in base unit), whatever the references that carry it."""

    id: str
    hash: str
    system: str
    lines: dict[str, Decimal | None]
    comparable: bool  # False when a line has no agreed quantity: the content is not known well enough to compare
    occurrences: list[Occurrence] = field(default_factory=list)

    @property
    def variants(self) -> list[str]:
        return sorted({o.variant for o in self.occurrences})

    @property
    def parts(self) -> list[str]:
        return sorted({o.part for o in self.occurrences})


@dataclass
class DiffLine:
    """One differing line of a pair. A swap of one component for another is one line, with both parts filled."""

    part_a: str | None
    part_b: str | None
    qty_a: Decimal | None
    qty_b: Decimal | None
    explanation: str = "unexplained"  # interchangeable, superseded, required_by_option or unexplained
    claim_id: int | None = None
    cost_gap: Decimal | None = None   # cost on side b minus cost on side a, None when a price is missing


@dataclass
class Pair:
    id: int
    a: Design
    b: Design
    kind: str  # near or functional
    n_shared: int
    n_differing: int
    lines: list[DiffLine]
    separating_options: list[str]
    claim_id: int | None = None  # for a functional pair, the claim that states it

    @property
    def cost_gap(self) -> Decimal | None:
        gaps = [line.cost_gap for line in self.lines]
        return None if any(gap is None for gap in gaps) else sum(gaps, Decimal(0))

    def other(self, design: Design) -> Design:
        return self.b if design is self.a else self.a


class Relations:
    """The relations between parts that are in force, indexed for the questions comparison and verdicts ask."""

    def __init__(self, relations: list[dict]):
        self.all = relations
        self._swap: dict[frozenset[str], tuple[str, int]] = {}
        self._required: dict[str, tuple[int, str]] = {}
        self._dead: dict[str, tuple[int, str | None]] = {}
        self.functional: list[tuple[str, str, int]] = []
        for r in relations:
            a, b = r["part_a"], r["part_b"]
            if a is None:
                continue
            if r["type"] == "interchangeable_with" and b:
                self._swap[frozenset((a, b))] = ("interchangeable", r["claim_id"])
            elif r["type"] == "superseded_by" and b:
                self._swap.setdefault(frozenset((a, b)), ("superseded", r["claim_id"]))
                self._dead[a] = (r["claim_id"], b)
            elif r["type"] == "obsolete":
                self._dead.setdefault(a, (r["claim_id"], None))
            elif r["type"] == "required_for":
                self._required[a] = (r["claim_id"], r["option"])
            elif r["type"] == "functionally_equivalent_to" and b:
                self.functional.append((a, b, r["claim_id"]))

    def swap(self, a: str, b: str) -> tuple[str, int] | None:
        """("interchangeable" or "superseded", claim id) when a relation links the two parts, in either order."""
        return self._swap.get(frozenset((a, b)))

    def required(self, part: str) -> tuple[int, str] | None:
        """(claim id, option) when a note says the part is required for an option."""
        return self._required.get(part)

    def dead(self, part: str) -> tuple[int, str | None] | None:
        """(claim id, replacement or None) when the part is obsolete or superseded."""
        return self._dead.get(part)

    def dead_parts(self) -> list[tuple[str, int]]:
        """Every obsolete or superseded part with the claim that says so, in order of part."""
        return [(part, claim_id) for part, (claim_id, _) in sorted(self._dead.items())]


def content_hash(lines: dict[str, Decimal | None]) -> str:
    """A hash of a content. Quantities are hashed as decimals rounded to 6 places in the base unit, so 2.4 m and
    2400 mm, once converted, give the same hash, and float noise cannot make two contents differ."""
    text = "|".join(f"{part}:{'?' if qty is None else format(round(qty, 6).normalize(), 'f')}"
                    for part, qty in sorted(lines.items()))
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def build_designs(occurrences: list[Occurrence], content: dict[tuple[str, str], dict]) -> list[Design]:
    """Group the occurrences by content. `content` maps (variant, sub-assembly part) to its lines.

    A content with a line that has no agreed quantity is kept apart from every other occurrence: it is not
    comparable, and must not look identical to another by accident.
    """
    by_hash: dict[tuple, Design] = {}
    for occurrence in sorted(occurrences, key=lambda o: (o.system, o.part, o.variant)):
        lines = content.get((occurrence.variant, occurrence.part), {})
        comparable = bool(lines) and all(qty is not None for qty in lines.values())
        digest = content_hash(lines)
        key = (occurrence.system, digest) if comparable else (occurrence.system, digest, occurrence.variant, occurrence.part)
        design = by_hash.get(key)
        if design is None:
            design = by_hash[key] = Design("", digest, occurrence.system, lines, comparable)
        design.occurrences.append(occurrence)
        occurrence.design = design
    designs = list(by_hash.values())
    for number, design in enumerate(designs, 1):
        design.id = f"D{number:03d}"
    return designs


def diff_lines(a: Design, b: Design, relations: Relations, cost: dict[str, Decimal | None]) -> list[DiffLine]:
    """The differing lines between two contents, each with its explanation and cost gap.

    Parts on one side only are paired into swaps: first those a relation links (interchangeable, superseded),
    then the rest in order. What is left over is a line with one side empty.
    """
    only_a = sorted(part for part in a.lines if part not in b.lines)
    only_b = sorted(part for part in b.lines if part not in a.lines)
    lines = []
    for part_a in list(only_a):
        for part_b in list(only_b):
            if relations.swap(part_a, part_b):
                how, claim_id = relations.swap(part_a, part_b)
                lines.append(DiffLine(part_a, part_b, a.lines[part_a], b.lines[part_b], how, claim_id))
                only_a.remove(part_a)
                only_b.remove(part_b)
                break
    for part_a, part_b in itertools.zip_longest(only_a, only_b):
        lines.append(DiffLine(part_a, part_b, a.lines.get(part_a), b.lines.get(part_b)))
    for part in sorted(set(a.lines) & set(b.lines)):
        if a.lines[part] != b.lines[part]:
            lines.append(DiffLine(part, part, a.lines[part], b.lines[part]))
    for line in lines:
        if line.explanation == "unexplained":
            for part in (line.part_a, line.part_b):
                if part and relations.required(part):
                    line.explanation, line.claim_id = "required_by_option", relations.required(part)[0]
        line.cost_gap = _gap(line, cost)
    return lines


def _gap(line: DiffLine, cost: dict[str, Decimal | None]) -> Decimal | None:
    total = Decimal(0)
    for part, qty, sign in ((line.part_a, line.qty_a, -1), (line.part_b, line.qty_b, 1)):
        if part is None:
            continue
        if qty is None or cost.get(part) is None:
            return None
        total += sign * qty * cost[part]
    return total


def separating(a: Design, b: Design, variants: dict[str, dict]) -> list[str]:
    """The options that split the two designs cleanly: every variant using one has a value no variant using the
    other has. Shown as a fact; it does not change a verdict on its own."""
    return [option for option in OPTIONS
            if not {variants[v][option] for v in a.variants} & {variants[v][option] for v in b.variants}]


def find_pairs(designs: list[Design], relations: Relations, cost: dict[str, Decimal | None],
               variants: dict[str, dict]) -> list[Pair]:
    """Near pairs (same system, 1 to MAX_DIFF differing lines, at least MIN_SHARED shared components) and
    functional pairs (two sub-assemblies a claim says do the same job)."""
    pairs: list[Pair] = []

    def add(a, b, kind, claim_id=None):
        a, b = sorted((a, b), key=lambda d: (-len(d.variants), d.id))  # side a is the design used most
        lines = diff_lines(a, b, relations, cost)
        shared = len(set(a.lines) & set(b.lines))
        pairs.append(Pair(len(pairs) + 1, a, b, kind, shared, len(lines), lines, separating(a, b, variants), claim_id))

    comparable = [d for d in designs if d.comparable]
    seen = set()
    for a, b in itertools.combinations(comparable, 2):
        if a.system != b.system or len(set(a.lines) & set(b.lines)) < MIN_SHARED:
            continue
        if 1 <= len(diff_lines(a, b, relations, cost)) <= MAX_DIFF:
            add(a, b, "near")
            seen.add(frozenset((a.id, b.id)))
    by_part: dict[str, list[Design]] = {}
    for design in designs:
        for part in design.parts:
            by_part.setdefault(part, []).append(design)
    for part_a, part_b, claim_id in relations.functional:
        for a in by_part.get(part_a, []):
            for b in by_part.get(part_b, []):
                if a is not b and frozenset((a.id, b.id)) not in seen:
                    add(a, b, "functional", claim_id)
                    seen.add(frozenset((a.id, b.id)))
    return pairs
