"""Normalising a written reference, and the two tests for "nearly the same reference"."""

import re

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
