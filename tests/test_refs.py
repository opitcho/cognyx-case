"""The edge cases of reading a written reference: the normalised key, the two closeness tests, the shape looked
for in a note's text, and a supplier's loose name."""

import pytest

from pipeline.refs import REFERENCE_SHAPE, loose, normalise, one_apart, swapped


@pytest.mark.parametrize("written, key", [
    ("", ""),
    ("  ", ""),
    ("dr_1042/a", "DR1042A"),
    ("DR.1042", "DR1042"),
    ("DR-OO42", "DR0042"),
    ("OO-1O", "OO10"),         # the two letters of the prefix are never read as zeros
    ("ABC-1O2", "ABC1O2"),     # a three-letter prefix: the O is left alone
    ("DR-1O42-B", "DR1O42B"),  # a suffix letter: the O is left alone
    ("1O42", "1O42"),          # no prefix
])
def test_normalise(written, key):
    assert normalise(written) == key


@pytest.mark.parametrize("a, b, expected", [
    ("R1042", "DR1042", True),      # a character dropped at the start
    ("DR1042", "DR10423", True),    # a character added at the end
    ("DR1042", "DR10042", True),    # a character doubled in the middle
    ("DR1042", "XR1042", True),     # the first character changed
    ("", "A", True),
    ("DR1042", "DR104234", False),  # two characters added
    ("DR1042", "DR1024", False),    # two characters changed: that is a swap
    ("DR1042", "XDR1043", False),   # one added and one changed
    ("", "", False),
])
def test_one_apart_in_both_orders(a, b, expected):
    assert one_apart(a, b) is expected and one_apart(b, a) is expected


@pytest.mark.parametrize("a, b, expected", [
    ("AB", "BA", True),
    ("LR205", "RL205", True),     # the first two characters
    ("RL205", "RL250", True),     # the last two characters
    ("RL205", "RL502", False),    # swapped, but not neighbours
    ("RL205", "RL026", False),    # three characters differ
    ("RL205", "RL215", False),    # one character differs
    ("RL225", "RL225", False),    # the same key
    ("RL2055", "RL025", False),   # different lengths
    ("RL205", "RL016", False),
])
def test_swapped_in_both_orders(a, b, expected):
    assert swapped(a, b) is expected and swapped(b, a) is expected


@pytest.mark.parametrize("text, found", [
    ("Replace DR-1042.", ["DR-1042"]),
    ("(JT218) and FB-76, then DR 1O42", ["JT218", "FB-76", "DR 1O42"]),
    ("DR-1042/AC-501", ["DR-1042", "AC-501"]),
    ("XDR-1042", []),       # a third letter before
    ("DR-1042A", []),       # a letter after
    ("dr-1042", []),        # lower case
    ("DR-1", []),           # one digit
    ("DR-1234567", []),     # seven digits
    ("DR--1042", []),       # two separators
    ("DR_1042", []),
    ("DOOR-SYS-01", []),    # a system reference is not shaped like a part reference
])
def test_the_reference_shape_in_free_text(text, found):
    assert REFERENCE_SHAPE.findall(text) == found


def test_loose_drops_case_spaces_and_punctuation():
    assert loose("Sofra-Tec") == loose(" SOFRATEC ") == loose("sofra tec.") == "SOFRATEC"
    assert loose("S.A.S.") == "SAS" and loose("--") == ""
