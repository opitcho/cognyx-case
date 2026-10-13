"""How part references are spelled: making new ones, mistyping them, comparing them."""


def distance(a, b):
    """Number of single-character edits to turn a into b (Levenshtein)."""
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def erp_form(ref):
    """The ERP writes the same reference without the hyphen: DR-1042 -> DR1042."""
    return ref.replace("-", "")


def new_ref(prefix, taken, rng):
    """A new reference such as DR-1042, at least two characters away from every existing one."""
    while True:
        ref = f"{prefix}-{rng.randint(100, 9999)}"
        if all(distance(ref, other) >= 2 for other in taken):
            taken.add(ref)
            return ref


def _drop_digit(prefix, digits, rng):
    i = rng.randrange(len(digits))
    return f"{prefix}-{digits[:i]}{digits[i + 1:]}"


def _double_digit(prefix, digits, rng):
    i = rng.randrange(len(digits))
    return f"{prefix}-{digits[:i]}{digits[i]}{digits[i:]}"


def _lookalike_character(prefix, digits, rng):
    places = [i for i, d in enumerate(digits) if d in "01"]
    if not places:
        return None
    i = rng.choice(places)
    return f"{prefix}-{digits[:i]}{'O' if digits[i] == '0' else 'I'}{digits[i + 1:]}"


def _swap_digits(prefix, digits, rng):
    i = rng.randrange(len(digits) - 1)
    return f"{prefix}-{digits[:i]}{digits[i + 1]}{digits[i]}{digits[i + 2:]}"


def _separator(prefix, digits, rng):
    return f"{prefix}{rng.choice([' ', ''])}{digits}"


TYPO_STYLES = [_drop_digit, _double_digit, _lookalike_character, _swap_digits, _separator]


def typo(ref, true_refs, taken, rng):
    """A mistyped copy of ref, in one of the styles seen in real data.

    The copy is never an existing reference, and it stays closer to ref than to
    any other true reference, so it can only be resolved to one part.
    """
    prefix, digits = ref.split("-")
    for _ in range(500):
        written = rng.choice(TYPO_STYLES)(prefix, digits, rng)
        if written is None or written == ref or written in taken or erp_form(written) in taken:
            continue
        own = distance(written, ref)
        if all(distance(written, other) > own for other in true_refs if other != ref):
            taken.add(written)
            return written
    raise ValueError(f"no safe typo found for {ref}")
