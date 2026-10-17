"""thisthat instruction and concurrency semantics."""

# ruff: noqa: SLF001 - instruction primitives are the semantic test surface.
import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.thisthat.generator import thisthat
from esolangs.languages.thisthat.interpreter import (
    _advance,
    _Machine,
    _NeedDrawError,
    _NeedInputError,
    _Pointer,
    run,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import FirstDraw, draw
from tests.support.paths import ROOT


def _advance_one(
    machine: _Machine, pointer: _Pointer, following: list[_Pointer]
) -> None:
    """Run one cell's handler for ``pointer``, as a tick does."""
    machine._workspace(following).advance(pointer)


def _merge(
    machine: _Machine, cell: str, arrived: list[_Pointer], following: list[_Pointer]
) -> None:
    """Merge ``arrived`` on ``cell``, drawing as a tick does."""
    saved = list(following)
    draws: tuple[int, ...] = ()
    while True:
        following[:] = saved
        step = machine._workspace(following)
        step.draws = draws
        try:
            step.merge(cell, arrived)
            return
        except _NeedDrawError as need:
            draws = (*draws, draw(machine.rng, need.upper))


class _EventIO(ScriptedIO):
    """A ``ScriptedIO`` that logs each read and write in order."""

    def __init__(self, stdin: str = "") -> None:
        super().__init__(stdin)
        self.events: list[str] = []

    def input_char(self, prompt: str = "Input: ") -> int:
        self.events.append("read")
        return super().input_char(prompt)

    def _write(self, value: object) -> None:
        self.events.append(f"write:{value}")
        super()._write(value)


def _print_then_read() -> tuple[list[str], tuple[_Pointer, ...]]:
    """A tick that prints 1, then reads, then prints 2, then reads again."""
    grid = ["▣─◇─◇─◇─◇"]
    pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((4, 0), (3, 0)),
        _Pointer((6, 0), (5, 0), "data", 2),
        _Pointer((8, 0), (7, 0)),
    )
    return grid, pointers


def test_a_tick_prints_before_it_reads() -> None:
    """A print already produced is written before the later read asks."""
    io = _EventIO("0\n")
    machine = _Machine(["▣─◇─◇"], io)
    machine.pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((4, 0), (3, 0)),
    )
    machine.step()
    assert io.events == ["write:1", "read"]
    assert io.getvalue() == "1"


def test_a_tick_keeps_output_when_a_later_read_hits_eof() -> None:
    io = _EventIO("")
    machine = _Machine(["▣─◇─◇"], io)
    machine.pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((4, 0), (3, 0)),
    )
    machine.step()
    assert io.events == ["write:1", "read"]
    assert io.getvalue() == "1"


def test_a_tick_keeps_output_when_a_later_read_is_invalid() -> None:
    """The prefix is flushed before the read's fault is re-raised."""
    io = _EventIO("x\n")
    machine = _Machine(["▣─◇─◇"], io)
    machine.pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((4, 0), (3, 0)),
    )
    with pytest.raises(HaltError, match="must be a bit"):
        machine.step()
    assert io.events == ["write:1", "read"]
    assert io.getvalue() == "1"


def test_a_retried_tick_flushes_each_print_once_in_order() -> None:
    """Two reads split the tick; each print lands once, in order."""
    grid, pointers = _print_then_read()
    io = _EventIO("01")
    machine = _Machine(grid, io)
    machine.pointers = pointers
    machine.step()
    assert io.getvalue() == "12"
    assert io.events == ["write:1", "read", "write:2", "read"]


@pytest.mark.parametrize(
    ("stdin", "grid", "expected"),
    [
        pytest.param("", ["▣─■═◇"], "1", id="constant_output_and_halt"),
        # ``◹`` always succeeds; ``◺`` sends 0 at ``k = 0`` and stays there.
        pytest.param(
            "",
            ["▣─◹─◺─◺", "  ║ ║ ║", "  ◇ ◇ ◇"],
            "110",
            id="cursor_moves_up_freely_and_fails_only_at_the_axis",
        ),
        pytest.param("", ["▣─◇═◇"], "", id="eof_is_an_empty_transfer"),
        # Only wires connect: a ``◇`` beside ``■`` never receives its 1.
        pytest.param(
            "", ["▣─■◇", "  ║", "  ◇"], "1", id="touching_nodes_do_not_connect"
        ),
        # ``◇`` reads, sends the bit, and goes on: two reads, two prints.
        pytest.param(
            "10",
            ["▣─◇─◇", "  ║ ║", "  ◇ ◇"],
            "10",
            id="a_data_sender_goes_on_down_execution_wires",
        ),
        # ``◉`` and a ``◇`` reached in the same cycle: the bit still prints.
        pytest.param("", ["▣─■─◉", "  ║", "  ◇"], "1", id="halt_lets_its_cycle_finish"),
    ],
)
def test_output(stdin: str, grid: list[str], expected: str) -> None:
    io = ScriptedIO(stdin)
    run(grid, io)
    assert io.getvalue() == expected


def test_advance_is_pure_and_repeatable() -> None:
    """The transition is a function of its core and copies the bistack."""
    grid = ("▣─◧",)
    core = ((_Pointer((2, 0), (1, 0), "data", 1),), {}, 0, False, False)
    first, first_effects = _advance(core, grid)
    second, second_effects = _advance(core, grid)
    assert first == second
    assert first_effects == second_effects
    assert core[1] == {}  # the input mapping is not written through
    assert dict(first[1]) == {(0, 0): 1}


def test_advance_returns_prints_instead_of_writing() -> None:
    """A data-mode ``◇`` reports the number it prints."""
    grid = ("▣─◇",)
    core = ((_Pointer((2, 0), (1, 0), "data", 1),), {}, 0, False, False)
    _moved, effects = _advance(core, grid)
    assert effects == (1,)
    assert core[0][0].value == 1  # the pointer is unchanged


def test_advance_requests_input_rather_than_reading() -> None:
    """An execution ``◇`` raises until the shell supplies a character."""
    grid = ("▣─◇─◯",)
    core = ((_Pointer((2, 0), (1, 0)),), {}, 0, False, False)
    with pytest.raises(_NeedInputError):
        _advance(core, grid)
    moved, effects = _advance(core, grid, (None,))
    assert effects == ()  # EOF is an empty transfer
    assert moved[0]  # and the pointer still goes on


def test_loader_push_pop_and_horizontal_route() -> None:
    io = ScriptedIO("0\n")
    run(thisthat("01").splitlines(), io)
    assert io.getvalue() == "0"


def test_invalid_programs_abort() -> None:
    with pytest.raises(HaltError, match="at least one"):
        _Machine([], ScriptedIO(""))
    with pytest.raises(HaltError, match="must be a bit"):
        run(["▣─◇"], ScriptedIO("x\n"))


def test_multiple_starts_halt_everything() -> None:
    machine = _Machine(["▣─◉─▣"], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.pointers == ()


def test_pause_holds_a_pointer_for_one_cycle() -> None:
    machine = _Machine(["▣─◔─◉"], ScriptedIO(""))
    machine.step()
    machine.step()
    assert machine.pointers[0].position == (2, 0)
    machine.step()
    assert machine.pointers[0].position == (2, 0)
    machine.step()
    assert machine.pointers[0].position == (3, 0)


def test_bistack_head_tail_and_both_axes() -> None:
    machine = _Machine(["▣"], ScriptedIO(""))
    machine._head("row", 0)
    machine._head("row", 1)
    assert machine._head("row", None) == 1
    assert machine._tail("row", None) == 0
    machine._tail("column", 1)
    machine._tail("column", 0)
    assert machine._tail("column", None) == 0
    assert machine._head("column", None) == 1
    assert machine.cells == {}


@pytest.mark.parametrize(
    ("node", "zero", "one"),
    [("◐", "E", "W"), ("◑", "W", "E"), ("◒", "N", "S"), ("◓", "S", "N")],
)
def test_every_data_router_side(node: str, zero: str, one: str) -> None:
    machine = _Machine(["▣"], ScriptedIO(""))
    for value, expected in ((0, zero), (1, one)):
        pointer = _Pointer((0, 0), (-1, 0), "data", value)
        assert machine._router_direction(node, pointer) == expected


def test_barrier_waits_for_a_second_pointer() -> None:
    machine = _Machine(["▣"], ScriptedIO(""))
    pointer = _Pointer((0, 0), None)
    following: list[_Pointer] = []
    _merge(machine, "◈", [pointer], following)
    assert following == [pointer]
    following = []
    _merge(machine, "◈", [pointer, pointer], following)
    assert following == []


def test_specification_truth_machine() -> None:
    """0 prints once and halts; 1 loops on ``■``, printing 1 forever."""
    source = """     ◇
     ║
    ┌□─◉
▣─◇═◒  ┌┐
    └▶─■┘
       ║
       ◇""".splitlines()
    io = ScriptedIO("0\n")
    run(source, io)
    assert io.getvalue() == "0"
    machine = _Machine(source, ScriptedIO("1\n"))
    for _ in range(200):
        machine.step()
    assert not machine.halted
    assert machine.io.getvalue() == "1" * len(machine.io.getvalue())
    assert len(machine.io.getvalue()) > 50
    assert len(machine.pointers) <= 6


@pytest.mark.parametrize(
    ("node", "values", "expected"),
    [("□", (0, 0), "1"), ("■", (0, 1), "1"), ("▦", (1, 1), "0")],
)
def test_logic_nodes_merge_data(
    node: str, values: tuple[int, int], expected: str
) -> None:
    machine = _Machine([f"▣═{node}═◇"], ScriptedIO(""))
    machine.pointers = tuple(
        _Pointer((2, 0), (1, 0), "data", value) for value in values
    )
    while not machine.halted:
        machine.step()
    assert machine.io.getvalue() == expected


def test_random_merge_selects_one_pointer_and_nands_data() -> None:
    io = ScriptedIO("")
    machine = _Machine(["▣═◘═◇"], io, FirstDraw(1))
    machine.pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((2, 0), (3, 0), "data", 1),
    )
    machine.step()
    assert len(machine.pointers) == 1
    assert machine.pointers[0].value == 0


@pytest.mark.parametrize(
    ("stdin", "expected"), [("1\n0", "10"), ("10\n1", "11"), ("1", "1")]
)
def test_the_flag_switches_input_sets(stdin: str, expected: str) -> None:
    """``▦``'s empty transfer into ``◇`` skips the set's rest; a set ends at EOL."""
    flag = ["▣─◇─▦───◇", "  ║ ║   ║", "  ◇ ◇   ◇"]
    io = ScriptedIO(stdin)
    run(flag, io)
    assert io.getvalue() == expected
    io = ScriptedIO("1\n1")
    run(["▣─◇─◇", "  ║ ║", "  ◇ ◇"], io)
    assert io.getvalue() == "1"


def test_a_generated_program_reads_the_first_set_only() -> None:
    """Spaces are ignored, a newline is not: the stdin oracle refuses ``0\\n1``."""
    from esolangs.exceptions import ArgumentError
    from tests.support.stdin_check import _check_stdin

    xor = thisthat("0110").splitlines()
    for stdin, expected in (("0 1\n", "1"), ("0\n1", "")):
        io = ScriptedIO(stdin)
        run(xor, io)
        assert io.getvalue() == expected
    _check_stdin("thisthat", "0 1\n", "0110")
    with pytest.raises(ArgumentError, match="first line"):
        _check_stdin("thisthat", "0\n1", "0110")


def test_branching_protocol_covers_random_input_plain_and_halted() -> None:
    random = _Machine(["▣═◘═◇"], ScriptedIO(""))
    random.pointers = (
        _Pointer((2, 0), (1, 0), "data", 0),
        _Pointer((2, 0), (3, 0), "data", 1),
    )
    assert len(random.branching_successors(random.branching_snapshot(), 10) or ()) == 2

    reading = _Machine(["▣─◇"], ScriptedIO(""))
    reading.step()
    reading.step()
    assert reading.branching_successors(reading.branching_snapshot(), 10) is None

    plain = _Machine(["▣─◯"], ScriptedIO(""))
    assert len(plain.branching_successors(plain.branching_snapshot(), 10) or ()) == 1

    halted = _Machine(["▣─◉"], ScriptedIO(""))
    while not halted.halted:
        halted.step()
    state = halted.branching_snapshot()
    assert halted.branching_halted(state)
    assert halted.branching_successors(state, 10) == (state,)

    assert not halted.branching_halted(None)
    with pytest.raises(TypeError, match="branch state"):
        halted.branching_successors(None, 10)
    with pytest.raises(TimeoutError, match="random merges"):
        random.branching_successors(random.branching_snapshot(), 1)


def test_router_execution_and_empty_transfer_routes() -> None:
    machine = _Machine(["▣"], ScriptedIO(""))
    assert machine._router_direction("◑", _Pointer((0, 0), None)) is None
    assert machine._router_direction("◑", _Pointer((0, 0), (-1, 0), "data")) == "E"
    assert machine._router_direction("◑", _Pointer((0, 0), (-1, 0))) == "E"
    assert machine._router_direction("◑", _Pointer((0, 0), (1, 0))) == "E"
    assert machine._router_direction("◑", _Pointer((0, 0), (0, 1))) == "E"


def test_execution_merge_and_constant_gate() -> None:
    gate = _Machine(["▣═□═◇"], ScriptedIO(""))
    following: list[_Pointer] = []
    _merge(gate, "□", [_Pointer((2, 0), (1, 0))], following)
    assert following == [_Pointer((3, 0), (2, 0), "data", 0)]

    merge = _Machine(["▣─◘─◉"], ScriptedIO(""), FirstDraw(1))
    following = []
    _merge(
        merge,
        "◘",
        [_Pointer((2, 0), (1, 0)), _Pointer((2, 0), (3, 0))],
        following,
    )
    assert len(following) == 1
    assert following[0].channel == "execution"


def test_arrows_noop_and_cursor_data_behaviors() -> None:
    machine = _Machine(["▣▶─"], ScriptedIO(""))
    following: list[_Pointer] = []
    _advance_one(machine, _Pointer((1, 0), (0, 0)), following)
    assert following[0].position == (2, 0)

    machine = _Machine([" │", "▣▷─", " │"], ScriptedIO(""))
    following = []
    _advance_one(machine, _Pointer((1, 1), (1, 0)), following)
    assert [p.position for p in following] == [(1, 2)]
    following = []
    _advance_one(machine, _Pointer((1, 1), (2, 1)), following)
    assert following == []

    machine = _Machine(["▣◯─"], ScriptedIO(""))
    following = []
    _advance_one(machine, _Pointer((1, 0), (0, 0)), following)
    assert following[0].position == (2, 0)

    machine = _Machine(["▣◹─"], ScriptedIO(""))
    following = []
    _advance_one(machine, _Pointer((1, 0), (0, 0), "data", 0), following)
    assert following == []
    _advance_one(machine, _Pointer((1, 0), (0, 0), "data", 1), following)
    assert following[0].channel == "execution"


def test_an_unknown_cell_aborts_at_load_even_when_unreached() -> None:
    with pytest.raises(HaltError, match="unsupported thisthat cell: 'x'"):
        run(["▣◇", "  x"], ScriptedIO(""))


def test_unreachable_bad_cell_still_aborts() -> None:
    machine = _Machine(["▣─"], ScriptedIO(""))
    machine.grid = ("▣x",)
    with pytest.raises(HaltError, match="unsupported thisthat cell"):
        _advance_one(machine, _Pointer((1, 0), (0, 0)), [])


def test_popping_an_empty_head_shifts_the_stack_back() -> None:
    """Wiki: a pop removes the beginning element, even an empty one, and shifts."""
    machine = _Machine(["▣"], ScriptedIO(""))
    machine.cells = {(1, 0): 1}
    assert machine._head("row", None) is None
    assert machine.cells == {(0, 0): 1}


def test_branch_choices_follow_the_update_order() -> None:
    """Merges draw in priority/row/column order, not pointer order: 2*3 outcomes."""
    machine = _Machine(["▣═◘═◘═◇"], ScriptedIO(""))
    machine.pointers = (
        _Pointer((4, 0), (3, 0), "data", 1),
        _Pointer((4, 0), (5, 0), "data", 1),
        _Pointer((4, 0), (4, 1), "data", 1),
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((2, 0), (3, 0), "data", 1),
    )
    successors = machine.branching_successors(machine.branching_snapshot(), 100)
    assert len(set(successors or ())) == 6


def test_a_branch_from_another_program_is_rejected() -> None:
    """A state carries its grid, so it cannot be resumed on a different program."""
    other = _Machine(["▣─◯"], ScriptedIO(""))
    machine = _Machine(["▣─◉"], ScriptedIO(""))
    with pytest.raises(ValueError, match="another thisthat program"):
        machine.branching_successors(other.branching_snapshot(), 10)


def test_a_cursorless_read_loop_halts_at_eof() -> None:
    """Reads count in the snapshot: the 1-loop runs to EOF, not a false cycle."""
    from esolangs.vm import run_until_halt
    from tests.interpreters.cursorless_io import CursorlessIO

    io = CursorlessIO("11111111")
    loop = ["▣─▶─◇═◒", "  │   │", "  └───┘"]
    assert run_until_halt(_Machine(loop, io), limit=1000) is True
    assert io.exhausted


def test_cat_and_kolakoski_wiki_examples() -> None:
    """The Cat echoes and halts; Kolakoski prints the sequence, 1 as 0, 2 as 1."""

    pages = ROOT / "src/esolangs/languages/thisthat/tests/fixtures"
    cat = (pages / "thisthat_cat.txt").read_text(encoding="utf-8").splitlines()
    for bits in ("", "0", "1", "0110"):
        io = ScriptedIO(bits)
        run(cat, io)
        assert io.getvalue() == bits
    kolakoski = [1, 2, 2]
    for i in range(2, 200):
        kolakoski += [3 - kolakoski[-1]] * kolakoski[i]
    source = (pages / "thisthat_kolakoski.txt").read_text(encoding="utf-8")
    machine = _Machine(source.splitlines(), ScriptedIO(""))
    for _ in range(4000):
        machine.step()
    printed = machine.io.getvalue()
    assert len(printed) > 60
    assert printed == "".join(str(term - 1) for term in kolakoski)[: len(printed)]


def test_cursor_moves_before_a_bistack_read_in_the_same_cycle() -> None:
    machine = _Machine(["▣ ◹ ◧═◇"], ScriptedIO(""))
    machine.cells = {(0, 0): 0, (0, 1): 1}
    machine.pointers = (_Pointer((2, 0), None), _Pointer((4, 0), None))
    for _ in range(3):
        machine.step()
    assert machine.io.getvalue() == "1"
    assert machine.cells == {(0, 0): 0}


def test_or_merge_of_two_ones_is_one() -> None:
    """``■`` is 1 when every input is 1, not only when some input is 0."""
    machine = _Machine(["▣═■═◇"], ScriptedIO(""))
    machine.pointers = tuple(_Pointer((2, 0), (1, 0), "data", 1) for _ in range(2))
    while not machine.halted:
        machine.step()
    assert machine.io.getvalue() == "1"


def test_only_a_random_merge_draws() -> None:
    """A ``◘`` with one pointer, or a logic node with two, needs no draw."""
    single = _Machine(["▣─◘─◉"], ScriptedIO(""))
    single.pointers = (_Pointer((2, 0), (1, 0)),)
    assert len(single.branching_successors(single.branching_snapshot(), 10) or ()) == 1
    logic = _Machine(["▣═■═◇"], ScriptedIO(""))
    logic.pointers = (
        _Pointer((2, 0), (1, 0), "data", 1),
        _Pointer((2, 0), (3, 0), "data", 1),
    )
    assert len(logic.branching_successors(logic.branching_snapshot(), 10) or ()) == 1


def test_a_random_merge_branches_each_channel_by_its_own_count() -> None:
    """Two execution and three data pointers on one ``◘``: 2 * 3 outcomes."""
    machine = _Machine(["▣║ ", "─◘═", " │ "], ScriptedIO(""))
    machine.pointers = (
        _Pointer((1, 1), (0, 1)),
        _Pointer((1, 1), (1, 2)),
        _Pointer((1, 1), (1, 0), "data", 1),
        _Pointer((1, 1), (2, 1), "data", 1),
        _Pointer((1, 1), (5, 5), "data", 1),
    )
    successors = machine.branching_successors(machine.branching_snapshot(), 100)
    assert len(set(successors or ())) == 6


def test_pushing_shifts_the_stack_one_place_away_from_the_head() -> None:
    machine = _Machine(["▣"], ScriptedIO(""))
    machine._head("row", 0)
    machine._head("row", 1)
    assert machine.cells == {(0, 0): 1, (1, 0): 0}
    assert machine._head("row", None) == 1
    assert machine._head("row", None) == 0


def test_the_stack_is_ordered_by_position_not_insertion() -> None:
    """A pop shifts a stack held in any dict order; so does a push."""
    machine = _Machine(["▣"], ScriptedIO(""))
    machine.cells = {(2, 0): 5, (1, 0): 4}
    machine._head("row", None)
    assert machine.cells == {(0, 0): 4, (1, 0): 5}
    machine.cells = {(1, 0): 4, (0, 0): 3}
    machine._head("row", 9)
    assert machine.cells == {(0, 0): 9, (1, 0): 3, (2, 0): 4}


def test_setting_the_pointers_keeps_the_cursor() -> None:
    machine = _Machine(["▣─◹"], ScriptedIO(""))
    for _ in range(3):
        machine.step()
    assert machine.cursor == 1
    machine.pointers = ()
    assert machine.cursor == 1
