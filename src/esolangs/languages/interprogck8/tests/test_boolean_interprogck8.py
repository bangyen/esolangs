"""Tests for the Interprogck8 Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


def _answer(program: str, n: int, row: int) -> str:
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    stdin = esolangs.encode_inputs("Interprogck8", bits)
    got = esolangs.run("Interprogck8", program, stdin=stdin, timeout=30)
    return esolangs.read_answer("Interprogck8", got)


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Interprogck8", table)
    for row in range(len(table)):
        assert _answer(program, n, row) == table[row], (table, row)


@pytest.mark.medium
@pytest.mark.parametrize("one", [1, 1071414])
def test_a_deep_path_keeps_its_lanes_apart(one: int) -> None:
    """A one-hot table keeps an ancestor's lane in the air at every depth.

    Lanes along a path advance 4 a 0 step and 2 a 1 step mod 82, so two
    collide only some 21 levels apart: a read that ignored the air built
    these two at ``n = 22`` into a flight hitting another lane's stop.
    """
    n = 22
    table = "0" * one + "1" + "0" * ((1 << n) - one - 1)
    program = esolangs.generate("Interprogck8", table)
    for row in (one, one ^ 1, one ^ (1 << (n - 1)), 0):
        assert _answer(program, n, row) == table[row], row


def test_closed_form_addresses_match_the_scans_they_replaced() -> None:
    """The stop hop, leaf line and printer-code shift equal the old first-fit scans."""
    stride, ps, lane0, lane1 = 82, 66, 33, 1
    lanes = {lane0, lane1}
    print_lane = {0: lane0, 1: lane1}
    for start in range(400):
        for lane in range(1, stride, 2):
            scan = start + (lane - start) % stride
            while scan % ps in lanes:
                scan += stride
            hop = start + (lane - start) % stride
            hop += stride * (hop % ps in lanes)
            assert hop == scan, (start, lane)
        for value, plane in print_lane.items():
            even = start + start % 2
            scan = even
            while (scan + 1) % ps != plane:
                scan += 2
            assert even + (plane - 1 - even) % ps == scan, (start, value)
        one = start * ps + lane1
        code = one + 1
        while any((code + i) % 2 and (code + i) % ps == lane0 for i in range(15 + 20)):
            code += 1
        assert code == one + 1 + (lane0 - lane1) % ps


def test_entry_lanes_equal_the_first_fit_read_they_replace() -> None:
    """Sizes the first-fit read emitted (n=10 ``and``, n=8 parity), frozen.

    The entry-line read through 15 inputs is byte-identical to that scan;
    the 2d+1 rule that follows is only larger.
    """
    assert len(esolangs.generate("Interprogck8", "0" * 1023 + "1")) == 26904
    parity = "".join(str(bin(i).count("1") % 2) for i in range(256))
    assert len(esolangs.generate("Interprogck8", parity)) == 140771


@pytest.mark.parametrize("n", [15, 16])
def test_the_entry_rule_hands_over_to_depth_lanes_at_sixteen(n: int) -> None:
    """A one-hot table of ``n`` inputs builds on either side of the cutover."""
    table = "0" * 12345 + "1" + "0" * ((1 << n) - 12346)
    assert esolangs.generate("Interprogck8", table)
