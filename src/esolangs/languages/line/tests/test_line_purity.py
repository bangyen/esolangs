"""The pure transition at Line's core, and the shell that wraps it."""

from itertools import product

import pytest

from esolangs.languages.line.interpreter.simulate import (
    IO,
    _advance,
    _Frame,
    _needs_input,
)

#: A hand-built program: ``+``, then ``o``, then ``i``.
FRAMES = (
    _Frame(
        ops=(("+", 1), ("o", 1), ("i", 1)),
        positions=((0, 0), (1, 1), (2, 2)),
        end=(3, 3),
        zero=None,
        nonzero=None,
        goto=None,
    ),
)


def test_advance_is_pure_and_repeatable() -> None:
    state = (0, 0, 0, ())
    first = _advance(state, FRAMES)
    second = _advance(state, FRAMES)
    # The state handed in is a value, untouched, and same args agree.
    assert state == (0, 0, 0, ())
    assert first == second
    assert first[1] is None


def test_output_is_returned_as_an_effect() -> None:
    state = (0, 1, 0, ((0, 5),))
    new_state, output = _advance(state, FRAMES)
    assert output == 5
    assert new_state[1] == 2
    assert state == (0, 1, 0, ((0, 5),))


def test_input_arrives_as_a_value() -> None:
    state = (0, 2, 0, ())
    with pytest.raises(ValueError, match="input transition requires a value"):
        _advance(state, FRAMES)
    new_state, output = _advance(state, FRAMES, 7)
    assert output is None
    assert dict(new_state[3]) == {0: 7}
    assert state == (0, 2, 0, ())


def test_the_shell_asks_the_pure_question_before_reading() -> None:
    """``_needs_input`` answers without calling the shell's IO."""
    assert not _needs_input(FRAMES, (0, 0, 0, ()))
    assert not _needs_input(FRAMES, (0, 1, 0, ()))
    assert _needs_input(FRAMES, (0, 2, 0, ()))
    assert not _needs_input(FRAMES, (None, 0, 0, ()))


def test_drive_is_the_shell_that_applies_the_effects() -> None:
    from esolangs.languages.line.interpreter.simulate import _drive

    values = iter([7])
    written: list[int] = []
    final = _drive(FRAMES, IO(read=values.__next__, write=written.append))
    # ``+`` makes 1, ``o`` writes 1, ``i`` stores the fed 7.
    assert written == [1]
    assert dict(final) == {0: 7}

    def frame(ops, *, zero=None, nonzero=None):
        return _Frame(
            ops=ops,
            positions=tuple((i, 0) for i in range(len(ops))),
            end=(len(ops), 0),
            zero=zero,
            nonzero=nonzero,
            goto=None,
        )

    for value, delta, other in product((-4, 0, 7), (-7, 0, 4), (-5, 0, 11)):
        adjust = ("+" if delta >= 0 else "-", abs(delta))
        frames = (
            frame((("i", 1), adjust), zero=1, nonzero=2),
            frame(((">", 1), ("i", 1), ("o", 1), ("<", 1), ("o", 1))),
            frame((("o", 1), (">", 1), ("i", 1), ("o", 1))),
        )
        supplied = iter((value, other))
        output = []
        cells = dict(_drive(frames, IO(read=supplied.__next__, write=output.append)))
        result = value + delta
        assert output == ([result, other] if result else [other, 0])
        assert cells == {0: result, 1: other}
        assert next(supplied, None) is None


def test_the_shell_writes_before_the_next_read() -> None:
    """The output effect is applied before the next input is requested."""
    from esolangs.languages.line.interpreter.simulate import _drive

    program = (
        _Frame(
            ops=(("o", 1), ("i", 1)),
            positions=((0, 0), (1, 1)),
            end=(2, 2),
            zero=None,
            nonzero=None,
            goto=None,
        ),
    )
    events: list[tuple[str, int | None]] = []

    def read() -> int:
        events.append(("read", None))
        return 7

    def write(value: int) -> None:
        events.append(("write", value))

    _drive(program, IO(read=read, write=write))
    assert events == [("write", 0), ("read", None)]
