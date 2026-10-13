"""Unit tests for Qoibl interpreter."""

import inspect
import io
import sys
from contextlib import redirect_stdout
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

import esolangs
from esolangs.languages.qoibl import interpreter as qoibl
from esolangs.languages.qoibl.interpreter import (
    _advance,
    _Machine,
    _NeedInput,
    run,
    tokenize,
)
from esolangs.runtime.io import IO, ScriptedIO
from tests.interpreters.contract import EmptyProgramContract, SnapshotContract
from tests.interpreters.runner import run_printing
from tests.support.event_io import EventIO

_SET1_3 = "we y we yy we"  # var[1] = 3
_SET1_7 = "we y we yyy we"  # var[1] = 7
_SET2_3 = "we ye we yy we"  # var[2] = 3


def _binary(op: str) -> str:
    """Print ``var[1] <op> var[2]``."""
    return f"tt qe y qe {op} qe ye qe tt"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (["tt yeeyeee tt"], "H"),
        (["we y we yyeeee we", "tt qe y qe tt"], "0"),
        *[
            ([f"tt {bits} tt"], chr(int(bits.replace("e", "0").replace("y", "1"), 2)))
            for bits in (
                *("ee", "ey", "ye", "yy", "eee", "eey"),
                *("eye", "eyy", "yee", "yey", "yye", "yyy"),
            )
        ],
        ([_SET1_3, _SET2_3, _binary("yr ee yr")], chr(1)),  # ==
        ([_SET1_7, _SET2_3, _binary("yr ey yr")], chr(1)),  # >
        ([_SET1_7, _SET2_3, _binary("yr yy yr")], chr(1)),  # != true
        ([_SET1_3, _SET2_3, _binary("yr yy yr")], chr(0)),  # != false
        # The orderings are strict: false when the operands are equal.
        ([_SET1_3, _SET2_3, _binary("yr ye yr")], chr(0)),
        ([_SET1_3, _SET2_3, _binary("yr ey yr")], chr(0)),
        ([_SET1_3, _SET2_3, _binary("ry ee ry")], chr(6)),  # +
        ([_SET1_7, _SET2_3, _binary("ry yy ry")], chr(2)),  # //
        (  # while loop decrements 3 -> 1
            [
                _SET1_3,
                "rr qe y qe yr ey yr y rr we y we qe y qe ry ey ry y we rr",
                "tt qe y qe tt",
            ],
            chr(1),
        ),
        (["tt qe yyy qe tt"], chr(0)),  # an undefined variable reads 0
        (  # nested: var[3] = var[1] + var[2]
            [
                _SET1_3,
                _SET2_3,
                "we yyy we qe y qe ry ee ry qe ye qe we",
                "tt qe yyy qe tt",
            ],
            chr(6),
        ),
    ],
)
def test_program_prints(code: list[str], expected: str) -> None:
    assert run_printing(run, code) == expected


class TestQoiblBehaviour:
    def test_input_operation(self) -> None:
        code: list[str] = [
            "we y we et we",
            "tt qe y qe tt",
        ]  # input -> var[1], print var[1]
        with (
            patch("builtins.input", return_value="A"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(code, IO())
        assert f.getvalue() == "A"

    def test_a_trailing_fragment_after_a_statement_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="malformed Qoibl expression"):
            run(["tt y tt w"], IO())

    def test_one_digit_adder(self) -> None:
        code: list[str] = [
            "we e we yyeeee we",  # var[0] = 2
            "we y we et ry ey ry qe e qe we",  # var[1] = input - 2
            "we ye we et ry ey ry qe e qe we",  # var[2] = input - 2
            "we y we qe y qe ry ee ry qe ye qe we",  # var[1] = var[1] + var[2]
            "we y we qe y qe ry ee ry qe e qe we",  # var[1] = var[1] + 2
            "tt qe y qe tt",  # print var[1]
        ]

        # Test 2 + 3 = 5
        with (
            patch("builtins.input", side_effect=["23"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(code, IO())
        assert f.getvalue() == "5"  # Should print 5

    def test_variable_indices_stay_within_the_256_cell_list(self) -> None:
        from esolangs.exceptions import HaltError
        from esolangs.languages.qoibl.interpreter import _eval

        with pytest.raises(HaltError, match="variable index"):
            _eval(["we", "yeeeeeeee", "we", "y", "we"], {}, (), 0, [])
        with pytest.raises(HaltError, match="variable index"):
            _eval(["qe", "yeeeeeeee", "qe"], {}, (), 0, [])
        # 2**20000 has 6021 digits, past CPython's 4300-digit str() cap: the
        # diagnostic used to raise ValueError instead of HaltError (a7f6680e).
        with pytest.raises(
            HaltError, match=r"variable index 3980276840\d{6011} is outside"
        ):
            _eval(["qe", "y" + "e" * 20000, "qe"], {}, (), 0, [])

    def test_division_by_zero(self) -> None:
        from esolangs.exceptions import HaltError

        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we e we",  # var[2] = 0
            "tt qe y qe ry yy ry qe ye qe tt",  # print var[1] // var[2]
        ]
        with pytest.raises(HaltError):
            run(code, IO())

    def test_unrecognized_operator_rejected(self) -> None:
        """An unrecognized arithmetic operator is a malformed program."""
        code: list[str] = ["tt y ry qe y y tt"]
        with pytest.raises(ValueError, match="operator"):
            run(code, IO())

    def test_truncated_operator_rejected(self) -> None:
        """A comparison or arithmetic operator with no operand is malformed."""
        with pytest.raises(ValueError, match="comparison"):
            run(["yr"], IO())
        with pytest.raises(ValueError, match="arithmetic"):
            run(["ry"], IO())


class TestContract(EmptyProgramContract, SnapshotContract):
    run = staticmethod(lambda code: run_printing(run, code))
    empty_program: ClassVar[Any] = []
    machine = staticmethod(lambda code: _Machine(code, ScriptedIO("")))
    stepping_program = "we y we yyeeee we\ntt qe y qe tt"


WIKI_PROGRAMS = {
    "adder": (
        "we e we yyeeee we\n"
        "we y we et ry ey ry qe e qe we\n"
        "we ye we et ry ey ry qe e qe we\n"
        "we y we qe y qe ry ee ry qe ye qe we\n"
        "we y we qe y qe ry ee ry qe e qe we\n"
        "tt qe y qe tt"
    ),
    "truth": (
        "we e we et we\nrr qe e qe yr ee yr yyeeey rr tt yyeeey tt rr\ntt yyeeee tt"
    ),
    "cat": "rr e yr ee yr e rr tt et tt rr",
    "hello": (
        "tt yeeyeee tt\ntt yyeeyey tt\ntt yyeyyee tt\ntt yyeyyee tt\n"
        "tt yyeyyyy tt\ntt yeyyee tt\ntt yeeeee tt\ntt yyyeyyy tt\n"
        "tt yyeyyyy tt\ntt yyyeeye tt\ntt yyeyyee tt\ntt yyeeyee tt\n"
        "tt yeeeey tt\ntt yeye tt"
    ),
}


class TestQoiblTokenizer:
    """The wiki calls spaces ignorable, so a program may omit them entirely."""

    @pytest.mark.parametrize("name", sorted(WIKI_PROGRAMS))
    def test_spacing_does_not_change_statements(self, name: str) -> None:
        """Spaced, space-free, and single-stream sources tokenize alike."""
        source = WIKI_PROGRAMS[name]
        expected = [line.split() for line in source.splitlines()]
        squeezed = source.replace(" ", "")
        assert tokenize(source) == expected
        assert tokenize(squeezed) == expected
        assert tokenize(squeezed.replace("\n", "")) == expected

    def test_output_matches_without_spaces(self) -> None:
        """A program run as one unbroken string prints what the spaced one does."""
        source = WIKI_PROGRAMS["hello"]
        stream = source.replace(" ", "").replace("\n", "")
        with redirect_stdout(io.StringIO()) as spaced:
            run(source, IO())
        with redirect_stdout(io.StringIO()) as fused:
            run(stream, IO())
        assert spaced.getvalue() == fused.getvalue() == "Hello, world!\n"

    def test_input_instruction_reclaims_its_character(self) -> None:
        """An odd run of `t` spells `et`, which claims the preceding `e`."""
        assert tokenize("rrttetttrr")[0] == ["rr", "tt", "et", "tt", "rr"]

    def test_comparison_marker_closes_its_pair(self) -> None:
        """`yr ee yr` must not read as `yr eey ry`, which strands the operand."""
        assert tokenize("qeeqeyreeyryyeeey")[0] == [
            "qe",
            "e",
            "qe",
            "yr",
            "ee",
            "yr",
            "yyeeey",
        ]

    def test_ignores_characters_outside_the_alphabet(self) -> None:
        """The spec ignores anything that is not part of an instruction."""
        assert tokenize("tt! yeeyeee? tt") == [["tt", "yeeyeee", "tt"]]


class TestQoiblIncompleteTokens:
    def test_a_lone_prefix_yields_an_empty_statement(self) -> None:
        """``w`` and ``q`` only mean something before ``e``."""
        assert tokenize("w") == [[]]
        assert tokenize("q") == [[]]

    def test_stepping_an_empty_statement_advances_the_cursor(self) -> None:
        """An empty statement is a no-op, not a parse of nothing."""
        from esolangs.languages.qoibl.interpreter import _Machine
        from esolangs.runtime.io import ScriptedIO

        state = _Machine("w", ScriptedIO(""))
        assert state.code == ([],)
        state.step()
        assert state.halted


class TestQoiblParserGuards:
    """The three conditions a mutation survived, each pinned by behaviour."""

    @pytest.mark.parametrize(
        "source",
        [
            "tt y qe",
            "qe y tt",
            "we y we y tt",
            "rr e rr y tt",
            "tt e yr ee ry y tt",
            "tt e ry ee yr y tt",
        ],
    )
    def test_mismatched_markers_are_rejected_at_execution(self, source: str) -> None:
        with pytest.raises(esolangs.ProgramError):
            esolangs.run("Qoibl", source)

    def test_matched_markers_execute(self) -> None:
        assert esolangs.run("Qoibl", "tt y tt") == chr(1)
        assert esolangs.run("Qoibl", "tt e yr ee yr y tt") == chr(0)
        assert esolangs.run("Qoibl", "tt e ry ee ry y tt") == chr(1)

    def test_steal_declines_a_literal_without_the_character(self) -> None:
        """Nothing is given back unless the literal actually ends in it."""
        from esolangs.languages.qoibl.interpreter import _steal

        assert _steal(["yy"], "e") is None  # no trailing 'e' to give back
        assert _steal(["e"], "e") == []  # a one-character literal vanishes
        assert _steal(["ye"], "e") == ["y"]  # a longer one is shortened

    def test_steal_declines_an_empty_token_list(self) -> None:
        """The emptiness check has to come first, or indexing raises."""
        from esolangs.languages.qoibl.interpreter import _steal

        assert _steal([], "e") is None

    def test_a_binary_operator_needs_its_closing_marker(self) -> None:
        """``yr``/``ry`` wrap an operator, and both ends must be the same one."""
        from esolangs.languages.qoibl.interpreter import _Reading

        def _wellformed(expr: list[str]) -> bool:
            # :func:`_eval`'s split points and arm order, without effects.
            return _Reading(expr).at(0, len(expr))

        assert _wellformed(["e", "yr", "ee", "yr", "y"]) is True
        assert _wellformed(["e", "yr", "ee", "ry", "y"]) is False  # wrong close
        assert _wellformed(["e", "yr", "ee"]) is False  # no close at all

    def test_an_unrecognised_token_is_rejected(self) -> None:
        """A hand-built token no keyword claims is not a binary literal."""
        from esolangs.languages.qoibl.interpreter import _eval

        with pytest.raises(ValueError, match="invalid literal"):
            _eval(["zz"], {"e": 1}, (), 0, [])


# 1.9s over 51 tests: runs the generated program.
@pytest.mark.medium
@pytest.mark.slow
class TestTheTokenizerCarriesItsOwnStack:
    """The search used to spend one Python frame per character."""

    @staticmethod
    def _majority(n: int) -> str:
        return "".join(str(int(bin(r).count("1") * 2 > n)) for r in range(2**n))

    def test_a_program_past_the_old_wall_tokenizes(self) -> None:
        """4929 characters, against a default limit of 1000."""
        program = esolangs.generate("Qoibl", self._majority(12))
        assert len(program) > 3000
        assert tokenize(program)

    def test_it_runs_under_a_limit_far_below_the_old_need(self) -> None:
        """The direct measure of shallowness, and it needed 1375 before."""
        program = esolangs.generate("Qoibl", self._majority(6))
        stdin = esolangs.encode_inputs("Qoibl", [0] * 6, truth_table=self._majority(6))
        live = len(inspect.stack())
        previous = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(live + 200)
            assert esolangs.run("Qoibl", program, stdin=stdin, timeout=120).endswith(
                "0"
            )
        finally:
            sys.setrecursionlimit(previous)

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("yr", [["yr"]]),
            ("et", [["et"]]),
            ("eet", [["e"], ["et"]]),
            # A trailing `r` has no `y` after it to open `ry` (a7f6680e: the
            # old scan matched "" in "ry"), so the literal lends its `y`.
            ("eyr ", [["e", "yr"]]),
            ("eeyr", [["ee", "yr"]]),
            ("yyr", [["y", "yr"]]),
            # Whitespace is a boundary, so the backwards reach cannot cross
            # it and the same characters read differently.
            ("e yr", [["e", "yr"]]),
            ("ey et", [["ey"], ["et"]]),
            ("y ttyytt", [["y"], ["tt", "yy", "tt"]]),
            ("tt", [["tt"]]),
            ("we", [["we"]]),
            ("qe", [["qe"]]),
            ("\nrr", [["rr"]]),
        ],
    )
    def test_the_reading_order_is_unchanged(
        self, source: str, expected: list[list[str]]
    ) -> None:
        """A backtracking search is only equal to another in the same order."""
        assert tokenize(source) == expected

    def test_an_unparseable_program_is_still_empty(self) -> None:
        """A failed scan with no literal or opcode returns no statements."""
        assert tokenize("qt\nrt") == [[]]

    @pytest.mark.parametrize("source", ["qt y\nqrt\nrt", "tt y tt w", "e\n\nr\n"])
    def test_a_failed_scan_with_data_is_rejected(self, source: str) -> None:
        """A dead scan must not erase a literal or a complete ``tt y tt``."""
        with pytest.raises(ValueError, match="malformed Qoibl expression"):
            tokenize(source)


@pytest.mark.parametrize(
    ("function", "expression", "message", "hint"),
    [
        ("_eval", [], "malformed expression", "nonempty"),
        ("_eval", ["e", "yr"], "malformed comparison", "operator"),
        ("_eval", ["e", "ry"], "malformed arithmetic", "operator"),
        (
            "_compare",
            ["e", "yr", "BAD", "yr", "e"],
            "unrecognized comparison operator",
            "after yr",
        ),
        (
            "_arithmetic",
            ["e", "ry", "BAD", "ry", "e"],
            "unrecognized arithmetic operator",
            "after ry",
        ),
    ],
)
def test_qoibl_hand_built_expression_guards(
    function, expression, message, hint
) -> None:
    with pytest.raises(ValueError, match=message) as caught:
        getattr(qoibl, function)(expression, {}, (), 0, [])
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


class TestPureTransition:
    """``_advance`` is a function of its arguments, and only of them."""

    def test_same_state_and_inputs_give_the_same_result(self) -> None:
        state = ({1: 2}, 0)
        code = (["tt", "qe", "y", "qe", "tt"],)
        assert _advance(state, code) == _advance(state, code)
        assert _advance(state, code) == (({1: 2}, 1), (chr(2),))

    def test_the_transition_leaves_its_arguments_unchanged(self) -> None:
        var = {1: 5}
        state = (var, 0)
        inputs = (65,)
        _advance(state, (["we", "y", "we", "et", "we"],), inputs)
        assert var == {1: 5}
        assert state == ({1: 5}, 0)
        assert inputs == (65,)

    def test_a_read_comes_from_the_explicit_input(self) -> None:
        code = (["we", "y", "we", "et", "we"], ["tt", "qe", "y", "qe", "tt"])
        state, out = _advance(({}, 0), code, (66,))
        assert out == ()
        state, out = _advance(state, code, ())
        assert out == ("B",)

    def test_an_unfed_read_asks_for_input_rather_than_reading(self) -> None:
        with pytest.raises(_NeedInput):
            _advance(({}, 0), (["we", "y", "we", "et", "we"],), ())

    def test_the_transition_reports_output_instead_of_printing(self) -> None:
        """No port is reachable from ``_advance``: output is a value."""
        _state, out = _advance(({}, 0), (["tt", "y", "tt"],))
        assert out == (chr(1),)


class TestOutputOrdering:
    """Output computed before a later read or fault is still written."""

    def test_output_before_eof_is_written_and_ordered(self) -> None:
        """``we tt y tt we et we`` prints chr(1), then reads and hits EOF."""
        io = EventIO("")
        with pytest.raises(EOFError):
            run(["we tt y tt we et we"], io)
        assert io.events == [("out", chr(1)), ("in", "")]

    def test_output_before_a_halt_is_written_and_ordered(self) -> None:
        """The same target prints before the value's division by zero halts."""
        from esolangs.exceptions import HaltError

        io = EventIO("")
        with pytest.raises(HaltError, match="division by zero"):
            run(["we tt y tt we e ry yy ry qe e qe we"], io)
        assert io.events == [("out", chr(1))]

    def test_a_later_statement_still_prints_before_its_own_fault(self) -> None:
        """Two statements: the first prints, the second prints then faults."""
        from esolangs.exceptions import HaltError

        io = EventIO("")
        with pytest.raises(HaltError, match="division by zero"):
            run(
                [
                    "tt y tt",
                    "we tt yyeeeee tt we e ry yy ry e we",
                ],
                io,
            )
        assert io.events == [
            ("out", chr(1)),
            ("out", chr(96)),
        ]
