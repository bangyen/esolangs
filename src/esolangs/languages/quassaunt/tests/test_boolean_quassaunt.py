"""Tests for the Quassaunt Boolean generator."""

import pytest

import esolangs
from esolangs.languages.quassaunt.generator import quassaunt

#: Every one- and two-input table; a diagram's sharing bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Quassaunt", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Quassaunt", bits)
        got = esolangs.run("Quassaunt", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("Quassaunt", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert quassaunt("0110100110010110").count("%%Ifpropersubset") == 7


def test_balance_cut_limits_are_the_priced_rungs() -> None:
    """_balance tries the cut limits (16, 24, 32, 48, 64, 96).

    A rung shifted by one changes which cut wins somewhere: at
    24 the constant table's balanced form is laid out
    differently, at 32 the three-one table's is, at 96 a wide
    table's balanced form renders 263 columns instead of 259,
    and at 64 a wide table's node line moves to another row.
    """
    from esolangs.languages.quassaunt.generator import _balance, quassaunt

    assert _balance("00", quassaunt("00")) == (
        "@@[z0]\n"
        "@@@@d?%%Inputchar?%%Empty?\n"
        "@@%%Makecontain?%%Store?\n"
        "%%Concatenate\n"
        "@@@@?@@?@@[z1]?%%Obtain?\n"
        "%%Concatenate\n"
        "@@@@?%%Concatenateall?\n"
        "%%Concatenate\n"
        "@@%%Evaluatereplace\n"
        "%%Concatenate %%Empty\n"
        "%%Makecontain %%Store @@[z1]\n"
        "@@@@0?%%Printtoconsole\n"
        "%%Empty %%Makecontain %%Store\n"
        "@@ @@ @@[z0] %%Obtain @@\n"
        "%%Concatenateall %%Evaluate"
    )
    assert _balance("1010", quassaunt("1010")) == (
        "@@[3] @@@@d?%%Inputchar?%%Empty?\n"
        "@@%%Makecontain?%%Store?@@?@@?\n"
        "%%Concatenate @@@@[2]?%%Obtain?@@?\n"
        "%%Concatenate @@%%Concatenateall?\n"
        "%%Concatenate @@%%Evaluatereplace\n"
        "%%Concatenate %%Empty %%Makecontain\n"
        "%%Store @@[2] @@@@?@@?@@[z2]?%%Obtain?@@?\n"
        "@@%%Concatenateall?@@2? %%Concatenate\n"
        "@@%%Inputchar?%%Empty? %%Concatenate\n"
        "@@%%Makecontain?%%Makecontain?@@?\n"
        "%%Concatenate @@@@?@@[o2]?%%Obtain?@@?\n"
        "%%Concatenate\n"
        "@@%%Concatenateall?@@1?%%Empty?\n"
        "%%Concatenate\n"
        "@@%%Makecontain?%%Ifpropersubset\n"
        "%%Concatenate %%Empty %%Makecontain\n"
        "%%Store @@[o2] @@@@1?%%Printtoconsole\n"
        "%%Empty %%Makecontain %%Store @@[z2]\n"
        "@@@@0?%%Printtoconsole %%Empty\n"
        "%%Makecontain %%Store @@ @@ @@[3]\n"
        "%%Obtain @@ %%Concatenateall %%Evaluate"
    )
    wide96 = (
        "010101101111110101010101100101110000111101100111111010100101001001110100"
        "110100001100111110010110011111000010111011100110101101000101110110101111"
        "111001100101110011000111100011010111001110011010111101011000001000110001"
        "111000001011011110001100100001111101110101111110111001011101000101101110"
        "000100111010000010101100111111110101101001111110110010000000100100100011"
        "011000101000111101110100101001101001010001001001010001011110010111111010"
        "010100111101010000000010001000001001100110111110111110011101010100110010"
        "01000010"
    )
    balanced = _balance(wide96, quassaunt(wide96))
    assert max(map(len, balanced.splitlines())) == 259
    wide64 = (
        "001101101001110101000000000011101010000001000001111011111000101101111101"
        "010011100010111101010100111110010000010011100011110011110100011110100000"
        "111011101001001101111000101000100011111010100001110110011111000001000111"
        "1001001000110100101111111001101001111101"
    )
    line = (
        "%%Concatenate %%Empty %%Makecontain %%Store @@[18] "
        "@@@@?@@?@@[5]?%%Obtain?@@?%%Concatenateall?@@2?%%Inputchar? "
        "@@%%Empty?%%Makecontain?%%Makecontain?@@?@@?@@[4]?%%Obtain?@@? "
        "%%Concatenate"
    )
    assert line in _balance(wide64, quassaunt(wide64)).splitlines()
