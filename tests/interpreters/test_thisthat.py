"""thisthat instruction and concurrency semantics."""

# ruff: noqa: SLF001 - instruction primitives are the semantic test surface.

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.thisthat import _Machine, _Pointer, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from esolangs.tools.thisthat import thisthat


def test_constant_output_and_halt() -> None:
    io = ScriptedIO("")
    run(["▣─■═◇"], io)
    assert io.getvalue() == "1"


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
    machine._merge("◈", [pointer], following)
    assert following == [pointer]
    following = []
    machine._merge("◈", [pointer, pointer], following)
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


def test_cursor_moves_up_freely_and_fails_only_at_the_axis() -> None:
    """``◹`` always succeeds; ``◺`` sends 0 at ``k = 0`` and stays there."""
    io = ScriptedIO("")
    run(["▣─◹─◺─◺", "  ║ ║ ║", "  ◇ ◇ ◇"], io)
    assert io.getvalue() == "110"


def test_eof_is_an_empty_transfer() -> None:
    io = ScriptedIO("")
    run(["▣─◇═◇"], io)
    assert io.getvalue() == ""


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
    from tests.stdin_check import _check_stdin

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
    gate._merge("□", [_Pointer((2, 0), (1, 0))], following)
    assert following == [_Pointer((3, 0), (2, 0), "data", 0)]

    merge = _Machine(["▣─◘─◉"], ScriptedIO(""), FirstDraw(1))
    following = []
    merge._merge(
        "◘",
        [_Pointer((2, 0), (1, 0)), _Pointer((2, 0), (3, 0))],
        following,
    )
    assert len(following) == 1
    assert following[0].channel == "execution"


def test_arrows_noop_and_cursor_data_behaviors() -> None:
    machine = _Machine(["▣▶─"], ScriptedIO(""))
    following: list[_Pointer] = []
    machine._advance_one(_Pointer((1, 0), (0, 0)), following)
    assert following[0].position == (2, 0)

    machine = _Machine([" │", "▣▷─", " │"], ScriptedIO(""))
    following = []
    machine._advance_one(_Pointer((1, 1), (1, 0)), following)
    assert [p.position for p in following] == [(1, 2)]
    following = []
    machine._advance_one(_Pointer((1, 1), (2, 1)), following)
    assert following == []

    machine = _Machine(["▣◯─"], ScriptedIO(""))
    following = []
    machine._advance_one(_Pointer((1, 0), (0, 0)), following)
    assert following[0].position == (2, 0)

    machine = _Machine(["▣◹─"], ScriptedIO(""))
    following = []
    machine._advance_one(_Pointer((1, 0), (0, 0), "data", 0), following)
    assert following == []
    machine._advance_one(_Pointer((1, 0), (0, 0), "data", 1), following)
    assert following[0].channel == "execution"


def test_an_unknown_cell_aborts_at_load_even_when_unreached() -> None:
    with pytest.raises(HaltError, match="unsupported thisthat cell: 'x'"):
        run(["▣◇", "  x"], ScriptedIO(""))


def test_unreachable_bad_cell_still_aborts() -> None:
    machine = _Machine(["▣─"], ScriptedIO(""))
    machine.grid = ("▣x",)
    with pytest.raises(HaltError, match="unsupported thisthat cell"):
        machine._advance_one(_Pointer((1, 0), (0, 0)), [])


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
    from esolangs.vm import run_until_halt_or_cycle
    from tests.interpreters.cursorless_io import CursorlessIO

    io = CursorlessIO("11111111")
    loop = ["▣─▶─◇═◒", "  │   │", "  └───┘"]
    assert run_until_halt_or_cycle(_Machine(loop, io)) is True
    assert io.exhausted


def test_cat_and_kolakoski_wiki_examples() -> None:
    """The Cat echoes and halts; Kolakoski prints the sequence, 1 as 0, 2 as 1."""
    from pathlib import Path

    pages = Path(__file__).parent.parent / "fixtures" / "wiki_examples"
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


def test_touching_nodes_do_not_connect() -> None:
    """Only wires connect: a ``◇`` beside ``■`` never receives its 1."""
    io = ScriptedIO("")
    run(["▣─■◇", "  ║", "  ◇"], io)
    assert io.getvalue() == "1"


def test_a_data_sender_goes_on_down_execution_wires() -> None:
    """``◇`` reads, sends the bit, and goes on: two reads, two prints."""
    io = ScriptedIO("10")
    run(["▣─◇─◇", "  ║ ║", "  ◇ ◇"], io)
    assert io.getvalue() == "10"


def test_halt_lets_its_cycle_finish() -> None:
    """``◉`` and a ``◇`` reached in the same cycle: the bit still prints."""
    io = ScriptedIO("")
    run(["▣─■─◉", "  ║", "  ◇"], io)
    assert io.getvalue() == "1"
