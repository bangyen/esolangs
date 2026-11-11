"""Unit tests for the B-tapemark interpreter."""

import pytest

from esolangs.languages.b_tapemark import interpreter as native
from esolangs.languages.b_tapemark.interpreter import _workspace_grid
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState


def execute(source: str, stdin: str = "") -> str:
    """Run ``source`` and return its output."""
    io = ScriptedIO(stdin)
    native.run(source, io)
    return io.getvalue()


@pytest.mark.parametrize(("dialect", "ip"), [("new", (1, 0)), ("old", (0, 0))])
def test_prepared_runs_reuse_initial_grids(monkeypatch, dialect, ip) -> None:
    import esolangs
    from tests.support.prepared_support import check_image_reuse

    api = esolangs.Language("B-tapemark")
    settings = api.settings(swap_marker=dialect)
    check_image_reuse(api.name, ">-+!", native, "_load", monkeypatch, settings=settings)
    machine = api.prepare(">?", settings=settings).make_vm()
    machine.step()
    machine.step()
    assert machine.ip == ip


def test_documented_cat() -> None:
    io = ScriptedIO("A\nB\n")
    with pytest.raises(EOFError):
        native.run("/>-+|\\\n\\    /", io)
    assert io.getvalue() == "A\nB\n"


def test_copy_and_character_input() -> None:
    assert execute(">*A+!") == "A"
    assert execute(">-+!", "Z\n") == "Z"


def test_the_swap_marker_dialect_names_the_marker_that_moves() -> None:
    from .oracle_checks import check_raw_b_tapemark

    check_raw_b_tapemark()
    """After a swap, ``new`` steps the new grid's marker, ``old`` the old one's."""
    for reading, expected in (
        ("new", ((1, 0), (1, 0))),
        ("old", ((2, 0), (0, 0))),
    ):
        state = native._load(">?", reading)
        state = native._advance(native._advance(state)[0])[0]
        assert state.program == 1
        assert state.positions == expected


def test_quoted_text_is_blank() -> None:
    assert execute('>A"IGNORED"B!') == "AB"
    # a form feed is a column in a comment, not a row break (only LF/CRLF/CR split)
    assert execute('>A"\x0c"B!') == "AB"


def test_transition_does_not_mutate_its_input() -> None:
    state = native._load(">*A!")
    advanced, output = native._advance(state)
    assert state == native._load(">*A!")
    assert advanced != state
    assert output is None


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("!", "exactly one start"),
        ("> <!", "exactly one start"),
        ('>"', "unmatched quote"),
        (">a!", "invalid.*'a'"),
        (">²!", "invalid.*'²'"),
    ],
)
def test_malformed_program(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(source)


class TestTheGridIsAMapOfPoints:
    """The grid is keyed by point, and is still a value."""

    def test_a_blank_erases_the_mark(self) -> None:
        """Writing a blank removes the point rather than storing a space."""
        grid = native._Grid({(0, 0): "A", (1, 0): "B"})
        cleared = grid.marked((0, 0), " ")
        assert cleared.at((0, 0)) == " "
        assert cleared.at((1, 0)) == "B"
        assert cleared == native._Grid({(1, 0): "B"})

    def test_writing_leaves_the_original_alone(self) -> None:
        """A write returns a new grid; the old one is what a cycle compares."""
        grid = native._Grid({(0, 0): "A"})
        assert grid.marked((0, 0), "Z").at((0, 0)) == "Z"
        restored = _state_from_wire(_state_wire(grid))
        assert restored == grid
        assert hash(restored) == hash(grid)
        for payload in (
            (),
            frozenset({((0, 0), "a"), ((0, 0), "b")}),
            frozenset({((True, 0), "a")}),
        ):
            packet = _state_wire(grid)
            packet["owned"]["value"] = _state_wire(payload)
            with pytest.raises(ValueError, match="snapshot"):
                _state_from_wire(packet)
        assert grid.marked((0, 0), "Z") != restored
        assert grid.at((0, 0)) == "A"

    def test_a_missing_point_reads_blank(self) -> None:
        """Off the marks is a blank, not an error -- the scans rely on it."""
        assert native._Grid({}).at((9, 9)) == " "


def test_a_halted_state_advances_to_itself() -> None:
    """``_advance`` on a halted state is a no-op, not a step off the end."""
    state = native._load(">!")
    halted = native._advance(native._advance(state)[0])[0]
    while not halted.halted:
        halted = native._advance(halted)[0]
    assert native._advance(halted) == (halted, None)


def test_input_command_without_a_symbol_is_refused() -> None:
    """``-`` needs the byte the shell was supposed to have read for it."""
    state = native._load(">-!")
    for _ in range(3):
        state = native._advance(state)[0]
        if state.grids[state.program].at(state.positions[state.program]) == "-":
            break
    with pytest.raises(ValueError, match="input symbol required"):
        native._advance(state)


def test_copy_onto_an_occupied_cell_leaves_it() -> None:
    """``*`` copies only onto a blank data cell."""
    io = ScriptedIO("A\n")
    native.run(">-*+!", io)
    assert io.getvalue() == ""


def test_the_last_letter_is_a_command_symbol() -> None:
    """``Z`` is the top of the uppercase range: it loads and prints."""
    assert execute(">Z!") == "Z"


def test_a_nonblank_data_cell_keeps_the_question_mark_in_the_program() -> None:
    """``?`` hands control to the data tape only over a blank data cell."""
    state = native._load(">*A?!")
    for _ in range(3):
        state = native._advance(state)[0]
    assert state.program == 0
    assert native._advance(state)[0].halted


def test_the_data_tape_can_run_a_dash_command() -> None:
    """A ``-`` run from the data tape looks at the program tape, not itself."""
    # the data tape gets a ``-`` at its origin, steps back, and ``?`` jumps onto it
    machine = native._Machine(">*-\\\n /|/\n \\?", ScriptedIO(""))
    for _ in range(9):
        machine.step()
    assert machine.state.program == 1
    assert machine.ip == (1, 0)


def test_workspace_ignores_grid_hash_caches_and_readonly_dialect(monkeypatch):
    machine = native._Machine(">*A+!", ScriptedIO())
    alternate = native._Machine(">*A+!", ScriptedIO(), swap_marker="old")
    assert machine.workspace_snapshot() == alternate.workspace_snapshot()
    written = WrittenState(machine.workspace_snapshot())
    monkeypatch.setattr(native._Machine, "snapshot", lambda _self: ())
    while not machine.halted:
        saved = machine.workspace_snapshot()
        retained = {saved}
        _workspace_grid.cache_clear()
        for grid in machine.state.grids:
            grid._digest = None
        assert machine.workspace_snapshot() == saved
        machine.step()
        written.sample(machine.workspace_snapshot())
        assert saved in retained
    assert machine.io.getvalue() == "A"
    assert written.bits > 0
    assert _workspace_grid.cache_info().maxsize == 8
