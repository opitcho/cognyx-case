"""The claim log: one line per statement about the raw data, only ever appended to.

A claim says something about what is written in the raw files ("these two spellings are one part", "this unit is
0.001 m", "this part is superseded by that one"), with who made it and the evidence. Nothing here applies a claim:
`build.py` does. This module holds the fixed list of claim types, the checks a claim passes before it is written,
the only code that writes the log, and the logic that says which claims are in force.

Subjects and objects point at raw data, never at computed parts:
    ref:DR-1042                    a reference as written
    supplier:FAIVELEY TRANSPORT SAS a supplier name as written
    unit:mm                        a unit as written
    bom:619, erp:236               a raw row, by its row_no
    cell:erp:236:unit_cost_eur     one value of a raw row
    note:TN-0132                   a note
    claim:57                       an earlier claim
    option:speed_class_kmh=200     a variant option
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.ingest import COLUMNS, Raw

FIELDS = ["id", "type", "subject", "object", "value", "standing", "made_by", "maker", "evidence", "quote", "reason",
          "as_of"]
STANDINGS = ("asserted", "proposed")
MAKERS = ("rule", "agent", "person")  # weakest first: on a tie, a person's claim is applied over an agent's
RANK = {maker: rank for rank, maker in enumerate(MAKERS)}


@dataclass(frozen=True)
class Shape:
    """What a claim type needs: the kinds its subject and object may be, and whether it carries a value."""

    subject: tuple[str, ...]
    object: tuple[str, ...] = ()
    value: bool = False
    says: str = ""


TYPES: dict[str, Shape] = {
    "same_as": Shape(("ref", "supplier"), ("ref", "supplier"), says="two written values are one thing"),
    "not_same_as": Shape(("ref", "supplier"), ("ref", "supplier"), says="two written values that look alike are two things"),
    "converts_to": Shape(("unit",), ("unit",), value=True, says="one of this unit is `value` of that unit"),
    "duplicate_of": Shape(("bom",), ("bom",), says="this row repeats that row"),
    "value_is": Shape(("cell",), value=True, says="the right value of this cell is `value`"),
    "no_value": Shape(("cell",), says="this cell holds a filler, not a value"),
    "mentions": Shape(("note",), ("ref",), says="this note is about this part"),
    "interchangeable_with": Shape(("ref",), ("ref",), says="two components can replace each other"),
    "functionally_equivalent_to": Shape(("ref",), ("ref",), says="two sub-assemblies do the same job"),
    "superseded_by": Shape(("ref",), ("ref",), says="the first part was replaced by the second"),
    "obsolete": Shape(("ref",), says="not to be used on new designs"),
    "required_for": Shape(("ref",), ("option",), says="the part is needed because of an option"),
    "confirm": Shape(("claim",), says="a proposed claim should be applied"),
    "retract": Shape(("claim",), says="a claim should no longer be applied"),
    "reviewed": Shape(("note",), says="this note was read and holds nothing more to claim"),
}
SYMMETRIC = {"same_as", "not_same_as", "interchangeable_with", "functionally_equivalent_to"}  # order has no meaning
RELATIONS = {"interchangeable_with", "functionally_equivalent_to", "superseded_by", "obsolete", "required_for"}
ALWAYS_ASSERTED = {"confirm", "retract", "reviewed"}
OPPOSITES = {"same_as": "not_same_as", "not_same_as": "same_as"}


class ClaimRefused(ValueError):
    """A claim failed a check. The message is one sentence saying why, written for whoever made the claim."""


def split(target: str) -> tuple[str, str]:
    """`ref:DR-1042` -> (`ref`, `DR-1042`). A target without a kind gives an empty kind."""
    kind, sep, rest = target.partition(":")
    return (kind, rest) if sep else ("", target)


def pair_key(claim: dict) -> tuple:
    """What a claim is about, in a form that ignores the order of a symmetric type."""
    ends = (claim["subject"], claim["object"])
    return tuple(sorted(ends)) if claim["type"] in SYMMETRIC else ends


def identity(claim: dict) -> tuple:
    """What makes two claims the same claim: type, what it is about, value and maker."""
    return claim["type"], pair_key(claim), str(claim["value"]), claim["maker"]


def rests_on_note(claim: dict) -> bool:
    """Whether a note's words are the basis of the claim: it quotes a note, or it is about one. A claim that only
    lists a note among other evidence stands without it."""
    return bool(claim["quote"]) or split(claim["subject"])[0] == "note"


def load(log_path: str | Path) -> list[dict]:
    """Every claim in the log, in order. A missing file is an empty log."""
    path = Path(log_path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class ClaimLog:
    """The log file, and the only code that writes to it: one checked claim per call, appended as one line."""

    def __init__(self, log_path: str | Path, raw: Raw):
        self.path = Path(log_path)
        self.raw = raw
        self.claims = load(self.path)
        self.added = False  # whether the last append wrote a line (False: the same claim was already there)

    def append(self, claim: dict) -> int:
        """Check `claim`, append it, and return its id. Raises ClaimRefused with the reason if a check fails.

        A claim already in the log (same type, subject, object, value and maker) is not written again: its id is
        returned, so running the rules twice is harmless.
        """
        claim = self._checked(claim)
        for old in self.claims:
            if identity(old) == identity(claim):
                self.added = False
                return old["id"]
        claim["id"] = len(self.claims) + 1
        line = json.dumps({name: claim[name] for name in FIELDS}, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.claims.append(claim)
        self.added = True
        return claim["id"]

    def _checked(self, claim: dict) -> dict:
        claim = {"object": "", "value": "", "standing": "asserted", "evidence": [], "quote": "", "reason": "",
                 "as_of": "", **claim}
        unknown = set(claim) - set(FIELDS)
        if unknown:
            raise ClaimRefused(f"unknown fields: {', '.join(sorted(unknown))}")
        claim["value"] = str(claim["value"])
        kind = claim.get("type")
        if kind not in TYPES:
            raise ClaimRefused(f"unknown claim type {kind!r}; the types are {', '.join(TYPES)}")
        shape = TYPES[kind]
        if claim["standing"] not in STANDINGS:
            raise ClaimRefused(f"standing must be one of {', '.join(STANDINGS)}")
        if kind in ALWAYS_ASSERTED and claim["standing"] != "asserted":
            raise ClaimRefused(f"a {kind} claim is always asserted")
        if claim.get("made_by") not in MAKERS or not claim.get("maker"):
            raise ClaimRefused(f"made_by must be one of {', '.join(MAKERS)}, with a maker")

        subject_kind = self._target(claim["subject"], shape.subject, "subject")
        if shape.object:
            object_kind = self._target(claim["object"], shape.object, "object")
            if kind in OPPOSITES and object_kind != subject_kind:
                raise ClaimRefused(f"{kind} needs two targets of the same kind, got {subject_kind} and {object_kind}")
            if claim["object"] == claim["subject"]:
                raise ClaimRefused("subject and object are the same")
        elif claim["object"]:
            raise ClaimRefused(f"{kind} takes no object")
        if shape.value and not claim["value"]:
            raise ClaimRefused(f"{kind} needs a value")
        if not shape.value and claim["value"]:
            raise ClaimRefused(f"{kind} takes no value")
        if kind == "converts_to":
            try:
                if float(claim["value"]) <= 0:
                    raise ValueError
            except ValueError:
                raise ClaimRefused(f"the factor {claim['value']!r} is not a positive number") from None

        if not isinstance(claim["evidence"], list):
            raise ClaimRefused("evidence must be a list of pointers such as bom:619 or note:TN-0132")
        for item in claim["evidence"]:
            self._target(item, ("bom", "erp", "note", "claim", "cell"), "evidence")
        if claim["quote"]:
            notes = [self.raw.note(split(item)[1]) for item in claim["evidence"] if split(item)[0] == "note"]
            if not notes:
                raise ClaimRefused("a quote needs the note it comes from in evidence, as note:<id>")
            if not any(claim["quote"] in note["text"] for note in notes):
                raise ClaimRefused(f"the quote is not in {', '.join(n['note_id'] for n in notes)} word for word")
        return claim

    def _target(self, target: str, kinds: tuple[str, ...], role: str) -> str:
        """Check that `target` is of one of `kinds` and points at something that exists. Returns its kind."""
        kind, rest = split(target)
        if kind not in kinds:
            raise ClaimRefused(f"the {role} {target!r} must be one of: {', '.join(k + ':...' for k in kinds)}")
        raw = self.raw
        if kind == "ref" and not raw.has_ref(rest):
            raise ClaimRefused(f"the reference {rest!r} is not written anywhere in the raw files")
        if kind == "supplier" and rest not in {row["supplier"] for row in raw.erp}:
            raise ClaimRefused(f"the supplier {rest!r} is not written in the ERP file")
        if kind == "unit" and rest not in {r["unit"] for r in raw.bom} | {r["price_unit"] for r in raw.erp}:
            raise ClaimRefused(f"the unit {rest!r} is not written in the BOM or the ERP file")
        if kind in ("bom", "erp") and not (rest.isdigit() and 1 <= int(rest) <= len(raw.rows(kind))):
            raise ClaimRefused(f"there is no row {target}")
        if kind == "cell":
            file, _, more = rest.partition(":")
            row, _, column = more.partition(":")
            if file not in COLUMNS or not row.isdigit() or not 1 <= int(row) <= len(raw.rows(file)):
                raise ClaimRefused(f"there is no row for {target!r}; a cell is cell:<bom|erp>:<row>:<column>")
            if column not in COLUMNS[file]:
                raise ClaimRefused(f"{column!r} is not a column of the {file} file; they are {', '.join(COLUMNS[file])}")
        if kind == "note" and raw.note(rest) is None:
            raise ClaimRefused(f"there is no note {rest!r}")
        if kind == "claim" and not (rest.isdigit() and 1 <= int(rest) <= len(self.claims)):
            raise ClaimRefused(f"there is no claim {rest!r}")
        if kind == "option" and not rest.strip():
            raise ClaimRefused("the option is empty")
        return kind


def append_claim(log_path: str | Path, raw: Raw, claim: dict) -> int:
    """Check one claim and append it to the log. See `ClaimLog.append`."""
    return ClaimLog(log_path, raw).append(claim)


@dataclass(frozen=True)
class Status:
    """Where a claim stands: `state` is in force, proposed, confirmed, retracted or overridden; `by` is the claim
    that confirmed, retracted or overrode it."""

    state: str
    by: int | None = None

    @property
    def in_force(self) -> bool:
        return self.state in ("in force", "confirmed")

    def __str__(self) -> str:
        return self.state if self.by is None else f"{self.state} by claim {self.by}"


def select(claims: list[dict], without_notes: bool = False) -> list[dict]:
    """The claims a replay looks at: all of them, or all but those that rest on a note."""
    return [c for c in claims if not (without_notes and rests_on_note(c))]


def statuses(claims: list[dict]) -> dict[int, Status]:
    """The status of every claim, worked out from the claims alone.

    A claim is in force when it is asserted, or proposed and confirmed, and no retract targets it. A confirm or
    a retract only counts while it is itself in force. Then, when two claims in force say opposite things about
    the same pair (same_as against not_same_as), or give two values to one cell, one is applied and the others
    are overridden: the later `as_of` date if all have one, otherwise a person's over an agent's over a rule's,
    then the later id.
    """
    result: dict[int, Status] = {}
    targeting: dict[int, list[dict]] = {}
    for claim in claims:
        if claim["type"] in ("confirm", "retract"):
            targeting.setdefault(int(split(claim["subject"])[1]), []).append(claim)
    for claim in sorted(claims, key=lambda c: c["id"], reverse=True):  # later claims decide earlier ones
        later = [c for c in targeting.get(claim["id"], []) if result[c["id"]].in_force]
        retracts = [c["id"] for c in later if c["type"] == "retract"]
        confirms = [c["id"] for c in later if c["type"] == "confirm"]
        if retracts:
            result[claim["id"]] = Status("retracted", max(retracts))
        elif claim["standing"] == "asserted":
            result[claim["id"]] = Status("in force")
        elif confirms:
            result[claim["id"]] = Status("confirmed", max(confirms))
        else:
            result[claim["id"]] = Status("proposed")

    groups: dict[tuple, list[dict]] = {}
    for claim in claims:
        if result[claim["id"]].in_force:
            if claim["type"] in OPPOSITES:
                groups.setdefault(("pair", pair_key(claim)), []).append(claim)
            elif claim["type"] == "value_is":
                groups.setdefault(("cell", claim["subject"]), []).append(claim)
    for (what, _), group in groups.items():
        sides = {c["type"] if what == "pair" else c["value"] for c in group}
        if len(sides) < 2:
            continue
        dated = all(c["as_of"] for c in group)
        winner = max(group, key=lambda c: ((c["as_of"],) if dated else ()) + (RANK[c["made_by"]], c["id"]))
        winning_side = winner["type"] if what == "pair" else winner["value"]
        for claim in group:
            if (claim["type"] if what == "pair" else claim["value"]) != winning_side:
                result[claim["id"]] = Status("overridden", winner["id"])
    return result


def in_force(claims: list[dict], without_notes: bool = False) -> list[dict]:
    """The claims a build applies, in log order."""
    chosen = select(claims, without_notes)
    status = statuses(chosen)
    return [c for c in chosen if status[c["id"]].in_force]
