"""Tests for the Interprogck8 Boolean generator."""

import random
from itertools import pairwise
from unittest.mock import patch

import pytest

import esolangs
from esolangs.exceptions import GeneratorCapError
from esolangs.languages.interprogck8 import descriptor, generator
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.execution import run_observed as execute
from tests.support.generator_support import assert_saved_rows, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def _answer(program: str, n: int, row: int) -> str:
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    stdin = esolangs.encode_inputs("Interprogck8", bits)
    got = execute("Interprogck8", program, stdin=stdin, timeout=30).output
    return esolangs.read_answer("Interprogck8", got)


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Interprogck8", table).source
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
    program = esolangs.generate("Interprogck8", table).source
    for row in (one, one ^ 1, one ^ (1 << (n - 1)), 0):
        assert _answer(program, n, row) == table[row], row


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(2))
def test_flights_land_on_their_stops_across_windows(seed: int) -> None:
    """Sparse eight-input tables put flights over several windows and clusters."""
    rng = random.Random(seed)
    n = 8
    table = "".join("1" if rng.random() < 0.1 else "0" for _ in range(1 << n))
    program = esolangs.generate("Interprogck8", table).source
    assert len(str(program).split("\n")) > 126 * 4
    for row in range(1 << n):
        assert _answer(program, n, row) == table[row], (seed, row)


def test_three_input_program_keeps_its_measured_length() -> None:
    """Three inputs take one cluster window and a tail: 472 lines."""
    assert_analysis_complement("Interprogck8", "subtree_ids")
    assert "_MAX_INPUTS" not in vars(generator) | vars(descriptor)
    table = "00011110"
    program = esolangs.generate("Interprogck8", table).source
    assert len(str(program).split("\n")) == 472
    for row in range(8):
        assert _answer(program, 3, row) == table[row], row


def test_parity_windows_keep_measured_lengths() -> None:
    """Parity packs three levels into52-line bands, with138-line periods."""
    language = esolangs.Language("Interprogck8")
    for witness in construction_boundaries(language.name)["parity_wide_window_entry"]:
        table = witness.table()
        with patch.object(generator, "_Plan", wraps=generator._Plan) as plan:
            artifact = language.generate(table)
        plan.assert_called_once_with(
            table, witness.arity, 40 if witness.arity == 2 else 52
        )
        assert_saved_rows(language, artifact, table, range(len(table)))

    sizes = {}
    for n in (8, 10, 12):
        parity = "".join(str(i.bit_count() % 2) for i in range(1 << n))
        program = str(esolangs.generate("Interprogck8", parity).source)
        lines = program.split("\n")
        assert all(lines[k] == "DownAccLines" for k in range(0, len(lines) - 82, 138))
        sizes[n] = len(program)
    assert sizes == {8: 35675, 10: 143940, 12: 578536}


def test_arith_adds_its_delta_mod_256() -> None:
    """Tens and ones add ``delta`` mod 256, even for deltas past a byte."""
    step = {"@id": 10, "@nd": 1, "@dd": -10, "@nt": -1}
    for delta in range(-600, 600):
        lines = generator._arith(delta)
        assert sum(step[line] for line in lines) % 256 == delta % 256, delta


def test_cluster_sizes_match_their_lines() -> None:
    """``size`` is the length of the cluster it prices, wherever that fits a window."""
    rng = random.Random(7)
    for n in (4, 5, 6, 7):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        plan = generator._Plan(table, n)
        for depth in range(n):
            for block in range(1 << depth):
                size = plan.size(depth, block)
                if size <= generator._FREE:
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
    assert generator.interprogck8("01") == "ok"
    language = esolangs.Language("Interprogck8")
    for bit in "01":
        source = generator.interprogck8(bit)
        assert source.splitlines().count("u") == 40
        artifact = esolangs.ProgramArtifact(source, language.name, input_arity=40)
        restored = language.load_program(language.dump_program(artifact))
        prepared = language.prepare(restored)
        for bits in ([0] * 40, [0, 1] * 20, [1] * 40):
            result = prepared.evaluate(bits)
            assert result.bit == bit
            assert result.observation.input_reads == 40


def test_flight_columns_keep_the_stop_in_the_cursors_window() -> None:
    """A flight's column is at least 40 at every depth that holds a flight.

    The scaling bound's window recursion needs the stop (column + 1) past a
    cursor that sits at line 41 at most; flights live at height >= 3.
    """
    for n in range(4, descriptor.MAX_INPUTS + 1):
        assert min(generator._columns(n)[: n - 2]) >= 40, n
    for n in range(4, 32):
        columns = generator._columns(n, 52)
        assert min(columns[: n - 3]) > 52
        assert all(0 <= c <= 80 for c in columns)
        assert all(a > b for a, b in pairwise(columns))
    # At n=32 the floor81 needs a zero-length body, unavailable below81.
    cost = len(generator._block(81))
    assert all(len(generator._block(c)) > cost for c in range(81))


@pytest.mark.parametrize("n", [3, 5, 7])
def test_a_subtree_advances_at_most_two_to_the_h_minus_one_windows(n: int) -> None:
    """Height h >= 3 advances the cursor at most 2**(h-1) - 1 windows, below 3 one.

    The recursion behind the scaling bound 226T + 224 (window count <= T/2).
    """
    period = generator._FREE + generator._ZONE
    seen: list[tuple[int, int]] = []

    class Plan(generator._Plan):
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


@pytest.mark.parametrize("n", [1, 3, 7, 8, 12])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constants_read_before_the_arithmetic_tail(n, bit) -> None:
    from esolangs.languages.interprogck8.interpreter import run

    program = esolangs.generate("Interprogck8", bit * (1 << n)).source
    assert len(program) == 2 * n + 28 + 4 * int(bit)
    rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
    for row in rows:
        io = ReadFirstIO("\n".join(format(row, f"0{n}b")) + "\nQ\n", expected=n)
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.input_str() == "Q"


def test_three_input_corpus_size() -> None:
    assert three_input_corpus_size("Interprogck8") == 339776


def test_flight_column_floor_above_the_ceiling_is_rejected() -> None:
    with pytest.raises(AssertionError, match="flight floor exceeds column ceiling"):
        generator._columns(32, 52)
