"""One rule function gives every design its verdict: blocked, reused, reusable or specific.

- reused: the same content is in two or more variants, under one reference or several.
- reusable: not shared today, but it differs from another design by 1 to 3 lines that no option requires, or a
  claim says another design does the same job.
- blocked: reused or reusable on content, but it contains an obsolete or superseded part.
- specific: a difference is required by an option, or there is no counterpart.
"""

from dataclasses import dataclass, field
from typing import Callable

from pipeline.compare import Design, Occurrence, Pair, Relations

VERDICTS = ("blocked", "reused", "reusable", "specific")


@dataclass
class Verdict:
    verdict: str
    reason: str
    counterpart: Design | None = None
    claim_ids: list[int] = field(default_factory=list)  # the claims the verdict rests on
    pair: Pair | None = None


def decide(design: Design, pairs: list[Pair], relations: Relations, name: Callable[[str], str]) -> Verdict:
    """The verdict for one design. `pairs` are the pairs this design is in; `name` gives a part's reference."""
    verdict = _on_content(design, pairs, name)
    if verdict.verdict in ("reused", "reusable"):
        dead = [(part, *relations.dead(part)) for part in sorted(design.lines) if relations.dead(part)]
        if dead:
            why = "; ".join(f"contains {name(part)}, " + (f"superseded by {name(new)}" if new else "obsolete")
                            for part, _, new in dead)
            return Verdict("blocked", f"{why} (otherwise {verdict.verdict}: {verdict.reason})", verdict.counterpart,
                           [claim_id for _, claim_id, _ in dead] + verdict.claim_ids, verdict.pair)
    return verdict


def occurrence_verdict(occurrence: Occurrence, verdict: Verdict, relations: Relations, name: Callable[[str], str]) -> Verdict:
    """The verdict of one sub-assembly in one variant, from the verdict of the design it carries.

    The verdict of a design holds for each sub-assembly that carries it, with one exception: a sub-assembly
    whose own reference is obsolete or superseded is blocked, even when its content is shared and sound.
    """
    dead = relations.dead(occurrence.part)
    if dead and verdict.verdict in ("reused", "reusable"):
        claim_id, new = dead
        others = [name(p) for p in occurrence.design.parts if p != occurrence.part]
        why = (f"the reference {name(occurrence.part)} is " + (f"superseded by {name(new)}" if new else "obsolete")
               + (f"; the same content is carried by {', '.join(others)}" if others else ""))
        return Verdict("blocked", f"{why} (otherwise {verdict.verdict}: {verdict.reason})", verdict.counterpart,
                       [claim_id, *verdict.claim_ids], verdict.pair)
    return verdict


def _on_content(design: Design, pairs: list[Pair], name: Callable[[str], str]) -> Verdict:
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
