"""Tests for the Interprogck8 Boolean generator."""

import random

import pytest

import esolangs
from esolangs.exceptions import GeneratorCapError
from esolangs.languages.interprogck8 import generator

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
def test_a_deep_path_keeps_its_flights_apart(one: int) -> None:
    """A one-hot table keeps a flight pending at every height of its path.

    Each flight's stop must sit at its own column, in a window past the
    rung's, so no flight lands on a shallower one's stop.
    """
    n = 22
    table = "0" * one + "1" + "0" * ((1 << n) - one - 1)
    program = esolangs.generate("Interprogck8", table)
    for row in (one, one ^ 1, one ^ (1 << (n - 1)), 0):
        assert _answer(program, n, row) == table[row], row


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(2))
def test_flights_land_on_their_stops_across_windows(seed: int) -> None:
    """Sparse eight-input tables put flights over several windows and clusters."""
    rng = random.Random(seed)
    n = 8
    table = "".join("1" if rng.random() < 0.1 else "0" for _ in range(1 << n))
    program = esolangs.generate("Interprogck8", table)
    assert len(str(program).split("\n")) > 126 * 4
    for row in range(1 << n):
        assert _answer(program, n, row) == table[row], (seed, row)


def test_three_input_program_keeps_its_measured_length() -> None:
    """Three inputs take one cluster window and a tail: 472 lines."""
    table = "00011110"
    program = esolangs.generate("Interprogck8", table)
    assert len(str(program).split("\n")) == 472
    for row in range(8):
        assert _answer(program, 3, row) == table[row], row


def test_parity_costs_the_same_per_entry_at_every_arity() -> None:
    """Windows are 126 lines whatever ``n``: a rung every 126 lines, and a flat size.

    Flat within 1%: parity spans 184.8-185.9 characters an entry at n = 8..12
    (185.4-185.9 before the overshoot spelling was retired).
    """
    sizes = {}
    for n in (8, 10, 12):
        parity = "".join(str(bin(i).count("1") % 2) for i in range(1 << n))
        program = str(esolangs.generate("Interprogck8", parity))
        lines = program.split("\n")
        assert all(lines[k] == "DownAccLines" for k in range(0, len(lines) - 82, 126))
        sizes[n] = len(program) / (1 << n)
    assert max(sizes.values()) / min(sizes.values()) < 1.01, sizes


def test_arith_adds_its_delta_mod_256() -> None:
    """Tens and ones add ``delta`` mod 256, even for deltas past a byte."""
    step = {"@id": 10, "@nd": 1, "@dd": -10, "@nt": -1}
    for delta in range(-600, 600):
        lines = generator._arith(delta)  # noqa: SLF001
        assert sum(step[line] for line in lines) % 256 == delta % 256, delta


def test_cluster_sizes_match_their_lines() -> None:
    """``size`` is the length of the cluster it prices, wherever that fits a window."""
    rng = random.Random(7)
    for n in (4, 5, 6, 7):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        plan = generator._Plan(table, n)  # noqa: SLF001
        for depth in range(n):
            for block in range(1 << depth):
                size = plan.size(depth, block)
                if size <= generator._FREE:  # noqa: SLF001
                    assert size == len(plan.cluster(depth, block)), (n, depth, block)


def test_the_input_cap_is_forty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forty inputs build; forty-one raise (a 2**40 table cannot be passed)."""
    monkeypatch.setattr(generator, "_validate_truth_table", lambda _: 41)
    with pytest.raises(GeneratorCapError):
        generator.interprogck8("0")
    monkeypatch.setattr(generator, "_validate_truth_table", lambda _: 40)
    monkeypatch.setattr(
        generator,
        "_Plan",
        lambda *_: type("P", (), {"lay": lambda *_: None, "text": lambda _: "ok"})(),
    )
    assert generator.interprogck8("0") == "ok"


def test_flight_columns_keep_the_stop_in_the_cursors_window() -> None:
    """A flight's column is at least 40 at every depth that holds a flight.

    The scaling bound's window recursion needs the stop (column + 1) past a
    cursor that sits at line 41 at most; flights live at height >= 3.
    """
    for n in range(4, generator._MAX_INPUTS + 1):  # noqa: SLF001
        assert min(generator._columns(n)[: n - 2]) >= 40, n  # noqa: SLF001


@pytest.mark.parametrize("n", [3, 5, 7])
def test_a_subtree_advances_at_most_two_to_the_h_minus_one_windows(n: int) -> None:
    """Height h >= 3 advances the cursor at most 2**(h-1) - 1 windows, below 3 one.

    The recursion behind the scaling bound 226T + 224 (window count <= T/2).
    """
    period = generator._PERIOD  # noqa: SLF001
    seen: list[tuple[int, int]] = []

    class Plan(generator._Plan):  # noqa: SLF001
        def lay(self, depth: int, block: int) -> None:
            start = self.cursor // period
            super().lay(depth, block)
            seen.append((self.n - depth, (self.cursor - 1) // period - start))

    rng = random.Random(n)
    width = 1 << n
    for _ in range(40):
        table = "".join(rng.choice(["00", "11", "01", "10"]) for _ in range(width // 2))
        Plan(table, n).lay(0, 0)
    assert seen
    for height, advance in seen:
        assert advance <= (1 if height <= 2 else (1 << (height - 1)) - 1)
    # Bound on the whole program: lines and code characters.
    for _ in range(10):
        table = "".join(rng.choice(["00", "11", "01", "10"]) for _ in range(width // 2))
        assert len(generator.interprogck8(table)) <= 226 * width + 224
