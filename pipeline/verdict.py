"""One rule function gives every design its verdict: reused, reusable or specific. The verdict says only whether
the content is shared. The obsolete or superseded parts a sub-assembly holds are listed apart.

- reused: the same content is in two or more variants, under one reference or several.
- reusable: not shared today, but it differs from another design by 1 to 3 lines that no option requires, or a
  claim says another design does the same job.
- specific: a difference is required by an option, or there is no counterpart.
"""

from dataclasses import dataclass, field
from typing import Callable

from pipeline.compare import Design, Occurrence, Pair, Relations

VERDICTS = ("reused", "reusable", "specific")


@dataclass
class Verdict:
    verdict: str
    reason: str
    counterpart: Design | None = None
    claim_ids: list[int] = field(default_factory=list)  # the claims the verdict rests on
    pair: Pair | None = None


def obsolete_components(design: Design, relations: Relations) -> list[tuple[str, int, str | None]]:
    """(part, claim id, replacement or None) for each component of the design that is obsolete or superseded.

    The same for every sub-assembly that carries the design.
    """
    return [(part, *relations.dead(part)) for part in sorted(design.lines) if relations.dead(part)]


def describe_obsolete(occurrence: Occurrence, relations: Relations, name: Callable[[str], str]) -> str:
    """The obsolete or superseded parts one sub-assembly holds, in words: its own reference first, then its
    components. Empty when there is none.

    The two are told apart because they ask for different things: a component means the content has to change;
    an own reference means the content is sound, and "(same content under ...)" names where else it is available.
    """
    def state(new: str | None) -> str:
        return f"superseded by {name(new)}" if new else "obsolete"

    found = []
    own = relations.dead(occurrence.part)
    if own:
        others = [name(part) for part in occurrence.design.parts if part != occurrence.part]
        found.append(f"own reference {name(occurrence.part)}, {state(own[1])}"
                     + (f" (same content under {', '.join(others)})" if others else ""))
    found += [f"{name(part)}, {state(new)}" for part, _, new in obsolete_components(occurrence.design, relations)]
    return "; ".join(found)


def decide(design: Design, pairs: list[Pair], name: Callable[[str], str]) -> Verdict:
    """The verdict for one design. `pairs` are the pairs this design is in; `name` gives a part's reference."""
    variants = design.variants
    if len(variants) >= 2:
        refs = [name(part) for part in design.parts]
        under = f" under references {', '.join(refs)}" if len(refs) > 1 else ""
        return Verdict("reused", f"same content in {', '.join(variants)}{under}")
    if not design.comparable:
        return Verdict("specific", "not comparable: a line has no agreed quantity")

    def others(pair: Pair) -> str:
        return ", ".join(name(part) for part in pair.other(design).parts)

    near = sorted((p for p in pairs if p.kind == "near"),
                  key=lambda p: (-len(p.other(design).variants), p.n_differing, p.id))
    free = [p for p in near if all(line.explanation != "required_by_option" for line in p.lines)]
    if free:
        pair = free[0]
        kinds = sorted({line.explanation for line in pair.lines})
        return Verdict("reusable", f"differs from {others(pair)} by {pair.n_differing} line(s): {', '.join(kinds)}",
                       pair.other(design), [line.claim_id for line in pair.lines if line.claim_id], pair)
    functional = [p for p in pairs if p.kind == "functional"]
    if functional:
        pair = functional[0]
        return Verdict("reusable", f"a note says it does the same job as {others(pair)}", pair.other(design),
                       [pair.claim_id] if pair.claim_id else [], pair)
    if near:
        pair = near[0]
        return Verdict("specific", f"its difference from {others(pair)} is required by an option", pair.other(design),
                       [line.claim_id for line in pair.lines if line.claim_id], pair)
    return Verdict("specific", "no counterpart in another variant")
