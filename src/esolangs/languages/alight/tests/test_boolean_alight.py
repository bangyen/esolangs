"""Alight generator tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run
from esolangs.generation.wrap import balance_score
from esolangs.languages.alight import generator as boolean
from esolangs.languages.alight.generator import (
    _alight_chunk,
    _alight_folded,
    _alight_units,
    _dimensions,
)
from esolangs.languages.alight.interpreter import _Machine
from esolangs.languages.alight.interpreter import run as alight_run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_saved_rows,
)


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``inp r;``, overwritten by the lookup."""
    assert_an_ignored_input_costs("Alight", 6, 6)


@pytest.mark.parametrize("syntax", ["infix", "postfix"])
def test_alight_balance_drops_ignored_inputs(syntax, monkeypatch) -> None:

    settings = esolangs.Language("Alight").settings(expression_syntax=syntax)
    table = "0110" * 16  # 4 inputs ignored of 6
    program = str(
        esolangs.generate("Alight", table, balance=True, settings=settings).source
    )
    assert _evaluate("Alight", program, inputs=6, settings=settings) == table
    full = "0" * 31 + "1" + "0" * 32  # every input matters
    kept = esolangs.generate("Alight", full, balance=True, settings=settings).source
    assert len(program) < len(str(kept))

    from esolangs.generation.helpers import input_weights

    assert boolean.input_weights is input_weights

    def complemented(table: str, n: int):
        weights, core = input_weights(table, n)
        return weights, core.translate(str.maketrans("01", "10"))

    monkeypatch.setattr(boolean, "input_weights", complemented)
    for balance in (False, True):
        damaged = esolangs.generate(
            "Alight", "00010001", balance=balance, settings=settings
        ).source
        assert _evaluate("Alight", damaged, inputs=3, settings=settings) == "11101110"


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 4, 8])
def test_alight_layouts_stay_near_the_exhaustive_column_selector(inputs) -> None:
    rng = random.Random(1025 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    flat = esolangs.generate("Alight", table).source
    # The retired selector: every column's fold, rendered once.
    forms = [(1, 0, "\n".join(flat)), (len(flat), 1, flat)]
    for columns in range(1, len(flat) + 1):
        program = _alight_folded(
            _alight_units(table, inputs, _alight_chunk(len(table), columns)), columns
        )
        width, _ = _dimensions(program)
        forms.append((max(width, columns), columns + 1, program))
        assert (
            run(
                "Alight", program, stdin=esolangs.encode_inputs("Alight", [0] * inputs)
            ).output
            == table[0]
        )
    ranked = []
    for ready, priority, program in forms:
        width, height = _dimensions(program)
        ranked.append(
            (
                ready,
                (max(width, height), width * height, len(program), priority),
                program,
            )
        )
    ceiling = max(ready for ready, _, _ in ranked)
    for width in range(1, ceiling + 1):
        built = esolangs.generate("Alight", table, width=width).source
        assert max(map(len, built.splitlines())) <= width
    balanced = esolangs.generate("Alight", table, balance=True).source
    winners = [flat] + [
        min((item for item in ranked if item[0] <= width), key=lambda item: item[1])[2]
        for width in range(1, ceiling + 1)
    ]
    assert balance_score(balanced)[0] <= 1.05 * min(map(balance_score, winners))[0]
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = run(
            "Alight", balanced, stdin=esolangs.encode_inputs("Alight", bits)
        ).output
        assert esolangs.read_answer("Alight", output) == table[row]


class TestAlightWidth:
    """Alight folds toward a square under the width bound."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:

        stdin = "".join(f"{bit}" for bit in bits)
        return run("Alight", program, stdin=stdin, timeout=5.0).output.strip()

    def test_a_width_turns_the_straight_walk_vertical(self) -> None:
        """A narrow program is one column and has no padding."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.alight(table)
            wide = max(len(row) for row in flat.splitlines())
            assert max(len(row) for row in boolean.alight(table, 1).splitlines()) == 1
            for width in (1, 40, 60, wide):
                narrow = boolean.alight(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= width, (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    @pytest.mark.parametrize("syntax", ["infix", "postfix"])
    def test_an_ignored_input_is_read_and_dropped_under_a_width(
        self, syntax: str
    ) -> None:
        """Dropping the first input of a 4-input table shrinks the area."""

        settings = esolangs.Language("Alight").settings(expression_syntax=syntax)

        def area(program: str) -> int:
            rows = program.splitlines()
            return max(map(len, rows)) * len(rows)

        ignored = "0110100101101001"
        full = "0110100110010110"
        built = boolean.alight(ignored, 30, expression_syntax=syntax)
        assert max(map(len, built.splitlines())) <= 30
        assert _evaluate("Alight", built, inputs=4, settings=settings) == ignored
        assert area(built) < area(boolean.alight(full, 30, expression_syntax=syntax))
        folded = boolean.alight(ignored, 80, expression_syntax=syntax)  # a fold plan
        assert _evaluate("Alight", folded, inputs=4, settings=settings) == ignored

    @pytest.mark.slow
    def test_a_width_is_met_at_every_arity(self) -> None:
        """Every requested width holds at every practical arity."""
        for n in (4, 5, 6, 7):
            table = "".join(str((i).bit_count() % 2) for i in range(2**n))
            for width in (60, 80):
                narrow = boolean.alight(table, width)
                assert max(len(row) for row in narrow.splitlines()) <= width, (n, width)

    @pytest.mark.parametrize(
        ("table", "width", "dimensions"),
        [
            ("0001", 30, (1, 77)),
            ("0001", 40, (36, 43)),
            ("0001", 80, (36, 43)),
            ("01101001", 80, (40, 54)),
            ("0110100110010110", 80, (48, 54)),
        ],
    )
    def test_the_longer_dimension_is_pinned(
        self, table: str, width: int, dimensions: tuple[int, int]
    ) -> None:
        """Pin each transition between the vertical and folded layouts."""
        rows = boolean.alight(table, width).splitlines()
        assert (max(map(len, rows)), len(rows)) == dimensions

    def test_postfix_ranks_candidates_by_area_alone(self) -> None:
        """The straight column (area 137) beats a 40-wide fold (area 1720)."""

        table = "00000011"
        built = boolean.alight(table, 40, expression_syntax="postfix")
        rows = built.splitlines()
        assert (max(map(len, rows)), len(rows)) == (1, 137)
        settings = esolangs.Language("Alight").settings(expression_syntax="postfix")
        assert _evaluate("Alight", built, inputs=3, settings=settings) == table

    def test_width_must_have_one_column(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            boolean.alight("0001", 0)


_TABLE = "00110110011010100101110010100110"


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 100])
def test_postfix_generated(width) -> None:
    source = boolean.alight(_TABLE, width, expression_syntax="postfix")
    if width is not None:
        assert max(map(len, source.splitlines())) <= width
    for row in range(len(_TABLE)):
        io = ScriptedIO(format(row, "05b"))
        alight_run(source, io, expression_syntax="postfix")
        assert io.getvalue() == _TABLE[row]


def test_postfix_settings_are_checked_and_do_not_leak() -> None:
    with pytest.raises(ValueError, match="expression_syntax"):
        boolean.alight("01", expression_syntax="mixed")
    with pytest.raises(ValueError, match="width"):
        boolean.alight("01", 0, expression_syntax="postfix")
    before = boolean.alight("0110")
    boolean.alight("0110", expression_syntax="postfix")
    assert boolean.alight("0110") == before


@pytest.mark.medium
@pytest.mark.parametrize("syntax", ["infix", "postfix"])
@pytest.mark.parametrize("update", ["in_place", "copy"])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_lookup_drops_every_index_input(syntax, update, bit) -> None:

    _check_native_constants(syntax, update, bit)
    table = bit * 256
    settings = esolangs.Language("Alight").settings(
        expression_syntax=syntax, list_update=update
    )
    program = esolangs.generate("Alight", table, settings=settings).source
    assert _evaluate("Alight", program, inputs=8, settings=settings) == table


# n=3 and 8 reach the small and wide layouts, bit "0" every arc the all-ones
# table does; either alone, or one syntax, loses arcs.
@pytest.mark.parametrize("syntax", ["infix", "postfix"])
@pytest.mark.parametrize("bit", ["0"])
@pytest.mark.parametrize("width", [None, 1, 8, 40, "balance"])
@pytest.mark.medium
@pytest.mark.parametrize("n", [3, 8])
def test_constant_lookup_executes_every_layout(syntax, bit, width, n) -> None:

    table = bit * (1 << n)
    settings = esolangs.Language("Alight").settings(expression_syntax=syntax)
    program = esolangs.generate(
        "Alight",
        table,
        settings=settings,
        **({"balance": True} if width == "balance" else {"width": width}),
    ).source
    assert _evaluate("Alight", program, inputs=n, settings=settings) == table


def test_alight_small_tables_at_width_40_keep_their_exact_silhouette() -> None:
    """Two layout boundaries the size race alone leaves unpinned.

    At width 40, table 01's next piece exactly fills the row's room:
    the packer must take it (splitting anyway costs 29 chars), and
    table 00's minimax root estimate (isqrt(length * 11)) sets its
    silhouette directly (a scale of 12 costs 22 chars).  Both mutant
    layouts still compute their tables at the same widths, so only
    the exact length and dimensions pin them.
    """
    packed = boolean.alight("01", 40)
    assert (len(packed), _dimensions(packed)) == (788, (34, 33))
    rooted = boolean.alight("00", 40)
    assert (len(rooted), _dimensions(rooted)) == (568, (24, 33))


def _check_native_constants(syntax: str, update: str, bit: str) -> None:
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Alight")["workspace"].formula
    settings = esolangs.Language("Alight").settings(
        expression_syntax=syntax, list_update=update
    )
    for n in range(1, 13):
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate(
                "Alight", bit * (1 << n), settings=settings, **options
            ).source
            if not options:
                assert (
                    program
                    == "begin;var r;"
                    + "inp r;" * n
                    + f"set r {48 + int(bit)};out r;end;"
                )
                assert len(program) == 6 * n + 31
            for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                machine = _Machine(
                    program, io, expression_syntax=syntax, list_update=update
                )
                written = WrittenState(machine.workspace_snapshot())
                steps = count_steps(machine, 1000, written=written)
                assert io.getvalue() == bit
                assert io.reads == n
                assert io.input_char() == ord("Q")
                assert written.bits <= workspace(n, program)
                if not options:
                    assert steps == n + 5
    assert (
        sum(len(esolangs.generate("Alight", f"{v:08b}").source) for v in range(256))
        == 24154
    )


def test_flat_lookup_packs_pairs_at_six_essential_inputs() -> None:
    language = esolangs.Language("Alight")
    records = construction_boundaries(language.name)
    for witness in records["flat_lookup_pair_packing"]:
        n, table = witness.arity, witness.table()
        with patch.object(
            boolean, "_packed_lookup", wraps=boolean._packed_lookup
        ) as pack:
            artifact = language.generate(table)
        assert pack.call_count == int(n == 6)
        assert_saved_rows(
            language, artifact, table, (0, 1, len(table) // 2, len(table) - 1)
        )

    for witness in records["narrow_literal_chunk_cutoff"]:
        table = witness.table()
        for width, entries in ((62, 15), (63, 32)):
            with patch.object(
                boolean, "_alight_chunk", wraps=boolean._alight_chunk
            ) as chunk:
                artifact = language.generate(table, width=width)
            chunk.assert_called_once_with(len(table), width)
            assert _alight_chunk(len(table), width) == entries
            assert_saved_rows(language, artifact, table, (0, 1, 16, 31))
