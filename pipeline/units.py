"""Written numbers and units: the base units, the fixed list of written units, and the two conversions.

A quantity is converted in two places with two sources. The rules use the fixed list below, before any claim
exists. The build uses the `converts_to` claims in force, so that a unit a person or the agent has explained
is converted too.
"""

from decimal import Decimal, InvalidOperation

from pipeline.claims import split

BASE_UNITS = ("pcs", "m", "kg")
# A written unit, lower case -> (base unit, how many base units one of it is).
UNIT_LIST = {"u": ("pcs", "1"), "pce": ("pcs", "1"), "ea": ("pcs", "1"), "mm": ("m", "0.001"), "g": ("kg", "0.001")}


def number(text: str | None) -> Decimal | None:
    """A written number, with a decimal point or a decimal comma. None if it is not one."""
    if text is None or not text.strip():
        return None
    try:
        return Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        return None


def to_base_by_list(quantity: str, unit: str) -> tuple[Decimal, str] | None:
    """A written quantity in its base unit, by the fixed list. None if the number or the unit is not understood."""
    amount = number(quantity)
    if amount is None:
        return None
    if unit in BASE_UNITS:
        return amount.normalize(), unit
    if unit.lower() in UNIT_LIST:
        base, factor = UNIT_LIST[unit.lower()]
        return (amount * Decimal(factor)).normalize(), base
    return None


def units_from_claims(converts_to: list[dict]) -> dict[str, tuple[str, Decimal]]:
    """Written unit -> (base unit, factor): the base units themselves, then one entry per converts_to claim."""
    units = {unit: (unit, Decimal(1)) for unit in BASE_UNITS}
    for claim in converts_to:
        units[split(claim["subject"])[1]] = (split(claim["object"])[1], Decimal(claim["value"]))
    return units


def to_base_by_claims(units: dict[str, tuple[str, Decimal]], quantity: Decimal | None,
                      unit: str | None) -> tuple[Decimal, str] | None:
    """A quantity in its base unit. None when the number is missing or the unit has no converts_to claim."""
    for _ in range(5):  # follows mm -> m; a chain longer than this is a mistake in the claims
        if quantity is None or unit not in units:
            return None
        base, factor = units[unit]
        quantity = quantity * factor
        if base == unit or base in BASE_UNITS:
            return round(quantity, 6).normalize(), base
        unit = base
    return None
