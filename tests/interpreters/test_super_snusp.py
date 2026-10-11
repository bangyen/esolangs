"""Execution tests for Super SNUSP and its boolean generator."""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.super_snusp import _advance, _floor_root, run
from esolangs.interpreters.grid_based.super_snusp import _Machine as SuperSnusp
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from esolangs.tools.super_snusp import super_snusp
from esolangs.vm import run_until_halt_or_all_branches_cycle, run_until_halt_or_cycle
from tests.interpreters.runner import run_program
from tests.support.raises import assert_halts_with_hint


def run_super(program: str, stdin: str = "") -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin)


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        pytest.param('"65.', "A", id="start_marker_and_literal_emit"),
        pytest.param(
            '"65\\\n   .', "A", id="lurd_mirror_turns_rightward_flow_downward"
        ),
        pytest.param(
            "\"1\u06612#'", "2", id="non_ascii_digit_breaks_an_ascii_literal_run"
        ),
        # Letters load as ``H.``, other bytes as decimal literals, in one run.
        pytest.param(
            '"H.e.l..o.44.32.W.o.r.l.d.33.10.0.255.',
            "Hello, World!\n\x00\xff",
            id="character_and_decimal_loads_mix_in_one_program",
        ),
        # After a double quote (34), ``!`` is one decrement and output.
        pytest.param(
            '"34.(.', '"!', id="a_decrement_is_shorter_than_reloading_a_nearby_byte"
        ),
        # ``"`` alone sets character mode and halts; the empty program raises.
        pytest.param('"', "", id="a_bare_mode_switch_outputs_nothing"),
        ('"!965.', "A"),  # SKIP steps over the 9, leaving 65 to build.
        ("\"65.'99.", "A"),  # HALT ends the run before the second emit.
        ('"1{$65.', "A"),  # DROP discards the pushed 1 without reading it.
        ('"100{365%.', "A"),  # MOD: 365 % 100.
        ('"5{13*.', "A"),  # MUL reads the stack top.
        ('"5{325:.', "A"),  # DIV floors toward the operand.
        ('"2{4225;.', "A"),  # ROOT: the square root of 4225.
        ('"6{1[.', "@"),  # SHL by the stack top.
        ('"1{130].', "A"),  # SHR by the stack top.
        ('"66~_.', "C"),  # NOT gives -67; negating it emits 67.
        ('"66(.', "A"),  # DEC steps the cell down one.
        ('"64).', "A"),  # INC steps it up one.
        ('   .\n"65/', "A"),  # RULD mirror turns rightward flow upward.
        ('"1_`65.\n', chr(5)),  # NEGSKIP steps over the 6 when the cell is < 0.
        ('"65_`.9.', "\t"),  # a negative cell skips the emit and builds 9.
        ('"100{365_%#', "-65"),  # MOD keeps the dividend's sign.
        ('"3{27_;#', "-3"),  # an exact odd root of a negative value.
        ('"3{9_;#', "-3"),  # an inexact one floors away from zero.
    ],
)
def test_output(program: str, expected: str) -> None:
    assert run_super(program) == expected


def test_without_a_start_marker_the_ip_starts_rightward_on_the_last_character() -> None:
    """The page's "Starts at bottom right" is the last line's last non-space
    cell, heading right: what makes the wiki's marker-less Cat copy input.
    The ``/`` turns the IP up to ``#``; from the padded corner it would
    meet ``/`` moving left and leave downward, printing nothing.
    """
    assert run_super("#\n/  ") == "0"


def test_wiki_hello_world_reflects_at_both_mirrors() -> None:
    """The wiki's Hello World (Super_SNUSP rev 194514) needs real reflection."""
    hello = [
        "\"33>d>l>r>o>W>32>44>o>l>l>e>H!/ ?\\' ",
        " " * 30 + "\\<./",
    ]
    assert run_program(run, hello) == "Hello, World!"


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ('"?65.', chr(5)),  # zero skips the 6 and emits the literal 5.
        ('"1?65.', "A"),  # nonzero falls through and builds 65.
        ('"1{2+.', chr(3)),  # ADD reads the stack top without consuming it.
        ('"5{1=.', chr(3)),  # RAND alone consumes its stack argument.
    ],
)
def test_core_linear_opcodes(program: str, expected: str) -> None:
    if "=" in program:
        io = ScriptedIO()
        run(program.splitlines(), io, rng=FirstDraw(2))
        assert io.getvalue() == expected
    else:
        assert run_super(program) == expected


@pytest.mark.parametrize("character", ["\u0661", "²", "\U0001d7da", "é", "中"])
def test_non_ascii_digits_and_letters_are_not_literals(character: str) -> None:
    assert run_super('"' + character + "#'") == "0"


def test_decimal_io_and_output() -> None:
    assert run_super('"@#', "-42\n") == "-42"


@pytest.mark.parametrize(
    "program",
    [
        '"+',
        '"0{1:',
        '"1_{1[',
        '"0{1%.',  # MOD by zero.
        '"1_{1[.',  # SHL by a negative amount.
        '"1_{1].',  # SHR by a negative amount.
        '"0{4;.',  # ROOT of degree zero.
        '"2{65_;#',  # an even root of a negative value.
        '"1_.',  # chr() of a negative cell.
    ],
)
def test_invalid_stack_and_arithmetic_operations_raise_halt_error(program: str) -> None:
    with pytest.raises(HaltError):
        run(program.splitlines(), IO())


def _run_boolean(program: str, bits: tuple[int, ...]) -> str:
    stdin = "".join(f"{bit}" for bit in bits)
    return run_super(program, stdin)


def test_generator_reduces_unused_inputs_but_reads_them() -> None:
    """Ignored inputs are still read from the stream."""
    reduced = super_snusp("00001111")  # depends only on the first input
    parity = super_snusp("01101001")
    assert reduced.count(",") == 3
    assert len(reduced) < len(parity)
    for bits in product((0, 1), repeat=3):
        assert _run_boolean(reduced, bits) == str(bits[0])


def test_generator_rejects_invalid_table() -> None:
    with pytest.raises(ValueError, match="power-of-two"):
        super_snusp("011")


@pytest.mark.parametrize(("value", "degree"), [(5, 0), (-9, 2), (-1, 4)])
def test_the_integer_root_refuses_what_it_cannot_answer(
    value: int, degree: int
) -> None:
    """A non-positive degree, and an even root of a negative value."""
    with pytest.raises(HaltError):
        _floor_root(value, degree)


def test_char_input_writes_the_byte_it_read() -> None:
    assert run_super('",.', "A") == "A"


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([""], IO())


def test_advance_short_circuits_once_the_cursor_has_left_the_grid() -> None:
    """A done state is its own successor, so the shell can stop on it."""
    done = ((0, 0, 0), (0, ()), (), False, True)
    assert _advance(done, ['"']) == (done, None)


@pytest.mark.parametrize(
    ("command", "offset"),
    [
        (",", None),  # no byte was read.
        ("@", None),  # no number was read.
        ("=", None),  # no draw was made.
        ("=", 99),  # a draw outside the two operands' span.
    ],
)
def test_advance_refuses_an_input_the_shell_did_not_supply(
    command: str, offset: int | None
) -> None:
    """The shell always supplies these, so only a direct call reaches the guard."""
    state = ((0, 0, 0), (0, ((0, 5),)), (1,), False, False)
    with pytest.raises(HaltError):
        _advance(state, [command], random_offset=offset)


@pytest.mark.medium
def test_hints_for_bad_programs_and_input():
    assert_halts_with_hint("Super SNUSP", '"1_{1[', "negative", "nonnegative shift")


def test_root_hint_does_not_require_an_exact_root():
    assert _floor_root(2, 2) == 1
    with pytest.raises(HaltError) as caught:
        _floor_root(-2, 2)
    assert "even degrees need nonnegative radicands" in caught.value.__notes__[0]


def _read_cell(state: object) -> int:
    """Return the cell under the pointer of a Super SNUSP branching state."""
    _cursor, (pointer, cells), *_rest = state  # type: ignore[misc]
    return next((value for index, value in cells if index == pointer), 0)


def test_super_snusp_mirror_ring_loops_under_every_draw() -> None:
    """A mirror ring circulates forever, and no draw escapes it."""
    code = ['/"\\', "\\ /"]
    machine = SuperSnusp(code, ScriptedIO())
    assert run_until_halt_or_all_branches_cycle(machine, limit=3000) is False
    with pytest.raises(TypeError, match="random machines"):
        run_until_halt_or_cycle(SuperSnusp(code, ScriptedIO()))


def test_super_snusp_forks_every_value_equals_could_store() -> None:
    """``=`` picks from the span between the cell and the stack top."""
    machine = SuperSnusp(['"3{(='], ScriptedIO())
    state = machine.branching_snapshot()
    for _ in range(4):  # '"', '3', '{', '(' -- all deterministic
        successors = machine.branching_successors(state, 100)
        assert successors is not None
        assert len(successors) == 1, "only '=' draws"
        (state,) = successors

    at_equals = machine.branching_successors(state, 100)
    assert at_equals is not None
    stored = sorted(_read_cell(nxt) for nxt in at_equals)
    assert stored == [2, 3], "both ends of the span are reachable"


def test_super_snusp_declines_input_and_caps_a_wide_span() -> None:
    """The two undecided cases, both raising rather than guessing."""
    for code, stdin in (('",', "A\n"), ('"@', "1\n")):
        machine = SuperSnusp([code], ScriptedIO(stdin))
        with pytest.raises(TimeoutError, match="needs input"):
            run_until_halt_or_all_branches_cycle(machine)

    # '999{' pushes 999 and '>' moves to a fresh zero cell, so '=' spans
    # 1000 values -- past the per-transition cap whatever the budget.
    wide = SuperSnusp(['"999{>='], ScriptedIO())
    with pytest.raises(TimeoutError, match=r"exceeds the .* cap") as caught:
        run_until_halt_or_all_branches_cycle(wide, limit=100000)
    assert "cap on a single transition" in str(caught.value)
    assert "limit does not raise this transition cap" in caught.value.__notes__[0]
