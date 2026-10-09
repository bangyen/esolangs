"""Alight generator tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from esolangs.interpreters.grid_based.alight import run as alight_run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.alight.balance import _balance_postfix
from esolangs.tools.wrap import balance_score
from tests.generator_support import assert_an_ignored_input_costs


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``inp r;``, overwritten by the lookup."""
    assert_an_ignored_input_costs("Alight", 6, 6)


def test_alight_affine_fold_comparisons_and_empty_turn_rows():
    from esolangs.tools.alight import _alight_folded, _dimensions
    from esolangs.tools.alight.balance import _fold_shape

    pieces = [(0, 6)] * 3 + [(0, 8), (1, 20), (1, 20), (0, 6), (0, 4)]
    assert _fold_shape(pieces, (1, 90), 1, 31)[3] == 4
    for size in range(1, 31):
        units = [[command] for command in ("begin", "var r", "var i", "set i 0")]
        units += [[f'set r at{{"{"0" * size}", i+0.5}}']] * 2
        units += [["out r"], ["end"]]
        program = _alight_folded(units, size + 90)
        width, height, length, _ = _fold_shape(pieces, (1, 90), size, 31)
        assert (*_dimensions(program), len(program)) == (width, height, length)
        assert esolangs.run("Alight", program) == "0"


def test_alight_planned_layouts_render_and_execute():
    from esolangs.tools.alight.balance import _emit, _plans

    for plan in _plans(2):
        program = _emit("0110", 2, plan)
        assert _evaluate("Alight", program, inputs=2) == "0110"


@pytest.mark.parametrize("syntax", ["infix", "postfix"])
def test_alight_balance_drops_ignored_inputs(syntax):
    from esolangs.settings import DialectSettings

    settings = DialectSettings(expression_syntax=syntax)
    table = "0110" * 16  # 4 inputs ignored of 6
    program = str(esolangs.generate("Alight", table, balance=True, settings=settings))
    assert _evaluate("Alight", program, inputs=6, settings=settings) == table
    full = "0" * 31 + "1" + "0" * 32  # every input matters
    kept = esolangs.generate("Alight", full, balance=True, settings=settings)
    assert len(program) < len(str(kept))


def test_alight_model_drift_aborts(monkeypatch):
    from esolangs.tools.alight import balance as module

    monkeypatch.setattr(module, "_alight_folded", lambda *_args: "begin;end;")
    with pytest.raises(AssertionError, match="fold model disagrees"):
        esolangs.generate("Alight", "0110", balance=True)


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 4, 8])
def test_alight_native_minimax_records_match_rendered_columns(inputs):
    from esolangs.tools.alight import (
        _alight_chunk,
        _alight_folded,
        _alight_units,
        _dimensions,
    )

    rng = random.Random(1025 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    flat = esolangs.generate("Alight", table)
    # Render each column once; this retains the old selector's full candidate set.
    forms = [(1, 0, "\n".join(flat)), (len(flat), 1, flat)]
    for columns in range(1, len(flat) + 1):
        program = _alight_folded(
            _alight_units(table, inputs, _alight_chunk(len(table), columns)), columns
        )
        width, _ = _dimensions(program)
        forms.append((max(width, columns), columns + 1, program))
        assert (
            esolangs.run(
                "Alight", program, stdin=esolangs.encode_inputs("Alight", [0] * inputs)
            )
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
    for width in range(1, max(ready for ready, _, _ in ranked) + 1):
        expected = min(
            (item for item in ranked if item[0] <= width), key=lambda item: item[1]
        )[2]
        assert esolangs.generate("Alight", table, width=width) == expected
    balanced = esolangs.generate("Alight", table, balance=True)
    winners = [flat] + [
        min((item for item in ranked if item[0] <= width), key=lambda item: item[1])[2]
        for width in range(1, max(ready for ready, _, _ in ranked) + 1)
    ]
    assert balance_score(balanced) == min(map(balance_score, winners))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            "Alight", balanced, stdin=esolangs.encode_inputs("Alight", bits)
        )
        assert esolangs.read_answer("Alight", output) == table[row]


class TestAlightWidth:
    """Alight minimizes its longer dimension under the width bound."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}" for bit in bits)
        return esolangs.run("Alight", program, stdin=stdin, timeout=5.0).strip()

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
        from esolangs.settings import DialectSettings

        settings = DialectSettings(expression_syntax=syntax)

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
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            for width in (60, 80):
                narrow = boolean.alight(table, width)
                assert max(len(row) for row in narrow.splitlines()) <= width, (n, width)

    @pytest.mark.parametrize(
        ("table", "width", "dimensions"),
        [
            ("0001", 30, (1, 77)),
            ("0001", 40, (36, 43)),
            ("0001", 80, (43, 33)),
            ("01101001", 80, (43, 43)),
            ("0110100110010110", 80, (49, 43)),
        ],
    )
    def test_the_longer_dimension_is_minimal(
        self, table: str, width: int, dimensions: tuple[int, int]
    ) -> None:
        """Pin each transition between the vertical and folded optima."""
        rows = boolean.alight(table, width).splitlines()
        assert (max(map(len, rows)), len(rows)) == dimensions

    def test_width_must_have_one_column(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            boolean.alight("0001", 0)


_TABLE = "00110110011010100101110010100110"


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 100])
def test_postfix_generated(width):
    source = boolean.alight(_TABLE, width, expression_syntax="postfix")
    if width is not None:
        assert max(map(len, source.splitlines())) <= width
    for row in range(len(_TABLE)):
        io = ScriptedIO(format(row, "05b"))
        alight_run(source, io, expression_syntax="postfix")
        assert io.getvalue() == _TABLE[row]


def test_postfix_settings_are_checked_and_do_not_leak():
    with pytest.raises(ValueError, match="expression_syntax"):
        boolean.alight("01", expression_syntax="mixed")
    with pytest.raises(ValueError, match="width"):
        boolean.alight("01", 0, expression_syntax="postfix")
    before = boolean.alight("0110")
    boolean.alight("0110", expression_syntax="postfix")
    assert boolean.alight("0110") == before


def test_postfix_balance_model_checks_rendering():
    with (
        patch("esolangs.tools.alight.balance._alight_folded", return_value="bad"),
        pytest.raises(AssertionError, match="postfix fold model"),
    ):
        _balance_postfix("0110", 2, "x" * 100)
    assert _balance_postfix("01", 1, "x") == "x"


@pytest.mark.medium
@pytest.mark.parametrize("syntax", ["infix", "postfix"])
@pytest.mark.parametrize("update", ["in_place", "copy"])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_lookup_drops_every_index_input(syntax, update, bit):
    import esolangs
    from esolangs._evaluate import _evaluate
    from esolangs.tools.alight import _program

    table = bit * 256
    settings = esolangs.DialectSettings(expression_syntax=syntax, list_update=update)
    program = esolangs.generate("Alight", table, settings=settings)
    assert len(program) < len(
        _program(table, expression_syntax=syntax, keep_constant_input=True)
    )
    assert _evaluate("Alight", program, inputs=8, settings=settings) == table


@pytest.mark.parametrize("syntax", ["infix", "postfix"])
@pytest.mark.parametrize("bit", ["0", "1"])
@pytest.mark.parametrize("width", [None, 1, 8, 40, "balance"])
@pytest.mark.medium
@pytest.mark.parametrize("n", [3, 4, 8])
def test_constant_lookup_executes_every_layout(syntax, bit, width, n):
    import esolangs
    from esolangs._evaluate import _evaluate
    from esolangs.tools.alight import _program
    from esolangs.tools.alight.balance import balance_alight
    from esolangs.tools.wrap import balance_score

    table = bit * (1 << n)
    settings = esolangs.DialectSettings(expression_syntax=syntax)
    program = esolangs.generate(
        "Alight",
        table,
        settings=settings,
        **({"balance": True} if width == "balance" else {"width": width}),
    )
    assert _evaluate("Alight", program, inputs=n, settings=settings) == table
    if width == "balance":
        old = _program(table, expression_syntax=syntax, keep_constant_input=True)
        legacy = balance_alight(
            table, old, expression_syntax=syntax, keep_constant_input=True
        )
        assert balance_score(program) <= balance_score(legacy)

    else:
        legacy = _program(
            table, width, expression_syntax=syntax, keep_constant_input=True
        )
        assert len(program) <= len(legacy)
        assert len(program.splitlines()) * max(map(len, program.splitlines())) <= (
            len(legacy.splitlines()) * max(map(len, legacy.splitlines()))
        )
