"""The terminal step-through's key loop over :mod:`esolangs.tui`'s frames.

:func:`drive` is the repaint-and-read loop, taking its input and output as
arguments so a test drives it; only :func:`run_tui` (raw mode, real stdin)
goes unexercised.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from esolangs.interpreters.source_hints import error_text
from esolangs.tui import Frame, History, Mark, at_cell, grid, locate, render

if TYPE_CHECKING:
    from esolangs._program import Program
    from esolangs.settings import DialectSettings


#: Wipe the screen and park the cursor, which is one repaint's worth of setup.
CLEAR = "\x1b[H\x1b[2J"

#: Which way each movement key sends the selector, as ``(down, across)``.
_MOVES = {"h": (0, -1), "j": (1, 0), "k": (-1, 0), "l": (0, 1)}

#: How far back a watch asks, before the row's own width cuts it down.
#: Generous, because asking is a slice of frames already held.
_WATCH_SPAN = 256

#: Play speeds in steps per second; ``+``/``-`` walk the list.  The top is
#: where a hand stops being able to follow the tape, which is the point:
#: play is for watching a loop breathe, not for reaching the halt sooner.
_SPEEDS = (1, 2, 4, 8, 16, 32, 64)

#: What each prompt line is labelled, by the state that opened it.
_PROMPTS = {
    "stdin": "stdin",
    "watch": "watch cell",
    "unwatch": "unwatch cell",
    "goto": "go to",
}


def _changed_cells(before: tuple[int, ...], after: tuple[int, ...]) -> frozenset[int]:
    """Return the indexes whose value differs between two tapes.

    A cell that grew into existence counts: absent reads as ``None``
    against whatever it now holds, the same spelling as a watch.
    """
    span = max(len(before), len(after))
    return frozenset(
        index
        for index in range(span)
        if (before[index] if index < len(before) else None)
        != (after[index] if index < len(after) else None)
    )


def _place(program: str, shape: str, text: str) -> Mark | None:
    """Return the mark ``goto`` text names, or ``None``.

    An offset (or a line number) is one integer; a grid position is
    ``row,col``.  Anything else is not a place rather than a guess.
    """
    try:
        if shape == "grid":
            row, col = text.split(",")
            return locate(program, (int(row), int(col)), shape)
        return locate(program, int(text), shape)
    except ValueError:
        return None


def breakpoint_for(
    at: int | tuple[int, ...] | None = None,
    cell: tuple[int, int] | None = None,
    output: str | None = None,
) -> Callable[[Frame], bool] | None:
    """Return one predicate over frames for the breakpoints asked for.

    ``None`` when none was.  Mirrors ``Debugger.break_at``,
    ``break_on_cell`` and ``break_on_output`` over a kept :class:`Frame`
    rather than a live machine.
    """
    tests: list[Callable[[Frame], bool]] = []
    if at is not None:
        tests.append(lambda frame: frame.ip == at)
    if cell is not None:
        index, value = cell
        tests.append(
            lambda frame: index < len(frame.memory) and frame.memory[index] == value
        )
    if output is not None:
        tests.append(lambda frame: output in frame.output)
    if not tests:
        return None
    return lambda frame: any(test(frame) for test in tests)


def _with_marks(
    stop: Callable[[Frame], bool] | None,
    marked: set[Mark],
) -> Callable[[Frame], bool] | None:
    """Add the marked positions to whatever the caller already asked for.

    Tests the *position*, not the raw ``ip``, so a grid cell stops on every
    heading.  Rebuilt per use because the set is edited between keys.
    """
    if not marked:
        return stop

    def hit(frame: Frame) -> bool:
        return locate(frame.program, frame.ip, frame.ip_shape) in marked

    if stop is None:
        return hit
    return lambda frame: hit(frame) or stop(frame)


def drive(
    history: History,
    read_key: Callable[[], str],
    write: Callable[[str], None],
    get_size: Callable[[], tuple[int, int]] = lambda: (24, 80),
    max_steps: int = 1_000_000,
    stop: Callable[[Frame], bool] | None = None,
    at: tuple[int | tuple[int, ...], ...] = (),
    watch: int | None = None,
    poll: Callable[[float], str | None] | None = None,
) -> None:
    """Repaint and read keys until asked to stop.

    Input and output are arguments so a test can drive it.  An empty key
    means input ended and quits.  ``hjkl`` move a selector (arrows are
    multi-byte, and a scripted test stays a plain string), ``t`` toggles a
    breakpoint under it; the selector snaps back to the run when the run
    moves.  ``at`` seeds breakpoints from the command line, ``watch`` one
    watched cell.  Digits prefix a count (``99l`` walks the selector 99
    cells, ``5`` then space steps five), ``G`` returns the selector to the
    run, ``g`` prompts for a place to jump it to.  ``w``/``W`` prompt for a
    cell to watch or stop watching, ``R`` prompts for stdin and restarts
    the run on it, ``p`` plays (auto-steps) while ``poll`` can wait for a
    key with a timeout, and ``+``/``-`` set the play speed.
    """
    step = 0
    frame = history.at(step)
    shape, program = frame.ip_shape, frame.program
    marked = {
        mark
        for mark in (locate(program, where, shape) for where in at)
        if mark is not None
    }
    picked = locate(program, frame.ip, shape)
    rows = grid(program)
    watched = [] if watch is None else [watch]
    count = ""
    prompt: str | None = None
    typed = ""
    notice: str | None = None
    playing = False
    speed = 3  # index into _SPEEDS: 8 steps a second
    previous: Frame | None = None

    def _move(down: int, across: int) -> Mark | None:
        spot = picked or locate(program, frame.ip, shape) or Mark(0, 0)
        return at_cell(
            program,
            shape,
            min(max(spot.row + down, 0), len(rows) - 1),
            min(max(spot.col + across, 0), len(rows[0]) - 1),
        )

    def _refresh() -> None:
        nonlocal frame, step, picked, playing
        frame = history.at(step)
        step = frame.step
        picked = locate(program, frame.ip, shape)
        if frame.halted:
            playing = False

    def _apply_prompt(kind: str, text: str) -> None:
        nonlocal step, picked, notice
        if kind == "stdin":
            try:
                history.restart(text)
            except Exception as exc:
                # The run being debugged is untouched (the fresh machine
                # is built before any state swaps), so this is a notice
                # to read, not a crash to leave raw mode for.
                notice = f"restart failed: {type(exc).__name__}: {error_text(exc)}"
                return
            step = 0
            _refresh()
            notice = "restarted"
            return
        if kind == "goto":
            mark = _place(program, shape, text)
            if mark is None:
                notice = f"no such place: {text!r}"
            else:
                picked = mark
            return
        try:
            index = int(text)
            if index < 0:
                raise ValueError
        except ValueError:
            notice = f"not a cell index: {text!r}"
            return
        if kind == "watch":
            if index in watched:
                notice = f"cell {index} already watched"
            else:
                watched.append(index)
                notice = f"watching cell {index}"
        elif index in watched:
            watched.remove(index)
            notice = f"cell {index} no longer watched"
        else:
            notice = f"cell {index} was not watched"

    while True:
        height, width = get_size()
        # Asked for at each repaint rather than accumulated, because the
        # trace is a view over the frames already kept: stepping back makes
        # it shorter, the way the run itself goes back.
        seen = tuple(
            (index, history.trace(index, step, _WATCH_SPAN)) for index in watched
        )
        changed = (
            frozenset()
            if previous is None or frame.step != previous.step + 1
            else _changed_cells(previous.memory, frame.memory)
        )
        if prompt is not None:
            status = f"{_PROMPTS[prompt]}> {typed}"
        elif notice is not None:
            status = notice
        elif playing:
            status = f"playing {_SPEEDS[speed]}/s"
        else:
            status = None
        screen = render(
            frame,
            height,
            width,
            tuple(sorted(marked, key=repr)),
            picked,
            seen,
            changed,
            status,
        )
        write(CLEAR + screen.replace("\n", "\r\n"))
        previous = frame

        if prompt is not None:
            key = read_key()
            if key == "":
                return
            if key == "\x1b":  # Escape: put the prompt down, keep the run.
                prompt = None
                continue
            if key in ("\r", "\n"):
                kind, text = prompt, typed
                prompt = None
                _apply_prompt(kind, text)
                continue
            if key in ("\x7f", "\x08"):
                typed = typed[:-1]
                continue
            if len(key) == 1 and key.isprintable():
                typed += key
            continue

        if playing and poll is not None:
            polled = poll(1.0 / _SPEEDS[speed])
            if polled is None:
                # A quiet timeout is a step: play is the loop repainting
                # without being asked, and it stops where a continue
                # would -- at a breakpoint, or the halt.
                step += 1
                _refresh()
                stopper = _with_marks(stop, marked)
                if stopper is not None and stopper(frame):
                    playing = False
                continue
            key = polled
        else:
            key = read_key()
        if key in ("q", "\x03", ""):
            return
        notice = None
        if key in "0123456789" and (count or key != "0"):
            count += key
            continue
        repeat = int(count) if count else 1
        count = ""
        if key in _MOVES:
            for _ in range(repeat):
                picked = _move(*_MOVES[key]) or picked
            continue
        if key == "t":
            # Nowhere to put one is a no-op rather than a mark on a nothing:
            # a language whose position is not on the source has no cell a
            # breakpoint could name.
            if picked is not None:
                marked.symmetric_difference_update({picked})
            continue
        if key == "G":
            picked = locate(program, frame.ip, shape)
            continue
        if key == "g":
            prompt, typed = "goto", ""
            continue
        if key == "w":
            prompt, typed = "watch", ""
            continue
        if key == "W":
            prompt, typed = "unwatch", ""
            continue
        if key == "R":
            # Prefilled with the running stdin, so Enter alone is a plain
            # restart and editing it is the other-input-row case.
            prompt, typed = "stdin", history.stdin
            continue
        if key == "p":
            playing = not playing
            continue
        if key in ("+", "="):
            speed = min(speed + 1, len(_SPEEDS) - 1)
            continue
        if key in ("-", "_"):
            speed = max(speed - 1, 0)
            continue
        if key == "b":
            step = max(0, step - repeat)
        elif key == "r":
            step = max_steps
        elif key == "c":
            # Continue means "to the next breakpoint, or the halt", so with
            # nothing set it is the run key -- which is why it is offered
            # whether or not the caller asked for a breakpoint.
            step = history.find(step, _with_marks(stop, marked), max_steps).step
        elif key in (" ", "\r", "\n"):
            step += repeat
        else:
            continue
        _refresh()


def run_tui(
    language: str,
    program: Program,
    stdin: str = "",
    max_steps: int = 1_000_000,
    stop: Callable[[Frame], bool] | None = None,
    at: tuple[int | tuple[int, ...], ...] = (),
    watch: int | None = None,
    *,
    settings: DialectSettings | None = None,
) -> None:  # pragma: no cover - the raw-terminal wrapper; the loop is tested
    """Step ``program`` interactively on this terminal.

    ``max_steps`` bounds the ``r`` key, since some languages never halt
    (``self_halts``).  Everything here is raw-mode handling; the stepping is
    :func:`drive`.  ``poll`` is what play mode waits on: a key, or
    ``None`` when the timeout passes quietly -- in raw mode a bare
    ``read`` would block forever and play would never advance.
    """
    import select
    import shutil
    import sys
    import termios
    import tty

    def size() -> tuple[int, int]:
        got = shutil.get_terminal_size((80, 24))
        return got.lines, got.columns

    def write(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def poll(timeout: float) -> str | None:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if ready else None

    # Built before the terminal is touched, so an unknown language is a clean
    # raise for the caller to report rather than a failure part-way into raw
    # mode with the screen already taken over.
    history = History(language, program, stdin, settings=settings)

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        drive(
            history,
            lambda: sys.stdin.read(1),
            write,
            size,
            max_steps,
            stop,
            at,
            watch,
            poll,
        )
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        write(CLEAR)
