"""Independent byte-escape checks; Circlefuck wiki revision 156668."""

import pytest

from esolangs.interpreters.tape_based.circlefuck import parse


@pytest.mark.parametrize("value", range(256))
def test_all_byte_escape_spellings(value):
    for source in (
        f"\\{value:03d}",
        f"\\o{value:03o}",
        f"\\x{value:02x}",
        f"\\x{value:02X}",
    ):
        assert parse(source) == [value]
        assert parse("A" + source + "Z") == [65, value, 90]
    if value < 16:
        assert parse("\\" + f"{value:X}") == [value]
    if 33 <= value <= 126 and value != 92:
        assert parse(chr(value)) == [value]


def test_named_escapes_and_nonprintable_filter():
    for spelling, value in (
        ("space", 32),
        (" ", 32),
        ("n", 10),
        ("r", 13),
        ("t", 9),
        ("b", 8),
        ("\\", 92),
    ):
        assert parse("\\" + spelling) == [value]
    for value in range(512):
        char = chr(value)
        if value == 92:
            continue
        assert parse(char) == ([value] if 33 <= value <= 126 else [])
    assert parse("\\0 00") == [0, 48, 48]
    assert parse("\\12") == [1, 50]
    assert parse("\\1٢3") == [1, 51]


@pytest.mark.parametrize("base", [8, 10])
def test_out_of_byte_range_escapes_are_rejected(base):
    for value in range(256, 512 if base == 8 else 1000):
        source = f"\\o{value:03o}" if base == 8 else f"\\{value:03d}"
        with pytest.raises(ValueError, match="invalid Circlefuck escape"):
            parse(source)


@pytest.mark.parametrize(
    "source",
    [
        "\\",
        "\\x",
        "\\x0",
        "\\xG0",
        "\\o",
        "\\o00",
        "\\o008",
        "\\q",
        "\\a",
        "\\f",
        "\\١٢٣",
        "\\\uff11\uff12\uff13",
        "\\²",
    ],
)
def test_malformed_and_nonascii_escape_digits(source):
    with pytest.raises(ValueError, match="invalid Circlefuck escape"):
        parse(source)
