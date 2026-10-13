"""The resolved model in memory: what a build works out from the raw files and the claims, before it is written.

`resolve.py` fills it up to the relations, `build.py` adds designs, pairs and verdicts, `tables.py` writes it.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property

from pipeline.claims import split
from pipeline.compare import Design, Occurrence, Pair, Relations
from pipeline.ingest import Raw
from pipeline.units import to_base_by_claims
from pipeline.verdict import Verdict


@dataclass
class Model:
    """The resolved model in memory, before it is written."""

    raw: Raw
    claims: list[dict]                       # the claims this replay looks at
    status: dict                             # claim id -> Status
    part_of: dict[str, str] = field(default_factory=dict)       # written reference -> part id
    parts: dict[str, dict] = field(default_factory=dict)
    supplier_of: dict[str, str] = field(default_factory=dict)   # written supplier name -> supplier id
    suppliers: dict[str, dict] = field(default_factory=dict)
    variants: dict[str, dict] = field(default_factory=dict)
    units: dict[str, tuple[str, Decimal]] = field(default_factory=dict)
    lines: list[dict] = field(default_factory=list)
    content_changes: list[dict] = field(default_factory=list)   # the inserts and deletes applied to the lines
    not_applied: dict[int, str] = field(default_factory=dict)   # claim id -> why an insert or delete was not applied
    prices: list[dict] = field(default_factory=list)
    cost: dict[str, Decimal | None] = field(default_factory=dict)  # part id -> unit cost, None if unknown or disputed
    cost_status: dict[str, str] = field(default_factory=dict)      # part id -> agreed, disputed or missing
    relations: list[dict] = field(default_factory=list)
    relation_index: Relations = field(default_factory=lambda: Relations([]))  # the same relations, indexed
    occurrences: list[Occurrence] = field(default_factory=list)
    designs: list[Design] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    verdicts: dict[str, Verdict] = field(default_factory=dict)   # design id -> verdict
    issues: list[dict] = field(default_factory=list)
    open_items: list[dict] = field(default_factory=list)         # the queue, worked out once the rest is known

    def name(self, part_id: str | None) -> str:
        return self.parts[part_id]["canonical_ref"] if part_id in self.parts else ""

    def issue(self, type: str, detail: str, source_file: str = "", rows=()) -> None:
        self.issues.append({"type": type, "detail": detail, "source_file": source_file,
                            "source_rows": ", ".join(str(r) for r in rows)})

    @property
    def force(self) -> list[dict]:
        return [c for c in self.claims if self.status[c["id"]].in_force]

    @cached_property
    def by_type(self) -> dict[str, list[dict]]:
        """The claims in force, per type."""
        by_type = defaultdict(list)
        for claim in self.force:
            by_type[claim["type"]].append(claim)
        return by_type

    @cached_property
    def _overrides(self) -> dict[tuple, str]:
        return {tuple(split(c["subject"])[1].split(":", 2)): c["value"] for c in self.by_type["value_is"]}

    @cached_property
    def _emptied(self) -> set[tuple]:
        return {tuple(split(c["subject"])[1].split(":", 2)) for c in self.by_type["no_value"]}

    def cell(self, file: str, row: dict, column: str) -> str | None:
        """A cell as the claims leave it: a value_is claim replaces a written value, a no_value claim empties it."""
        key = (file, str(row["row_no"]), column)
        if key in self._overrides:  # a value someone supplied also fills a cell a rule marked as holding no value
            return self._overrides[key]
        return None if key in self._emptied else row[column]

    def to_base(self, quantity: Decimal | None, unit: str | None) -> tuple[Decimal, str] | None:
        """A quantity in its base unit, by the converts_to claims in force. None when it cannot be converted."""
        return to_base_by_claims(self.units, quantity, unit)

    def used_components(self) -> set[str]:
        """The parts that are a component of some sub-assembly in the BOM."""
        return {line["child"] for line in self.lines if line["level"] == 4}
