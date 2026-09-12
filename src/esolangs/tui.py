r"""A terminal step-through over the debugger."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeGuard

from esolangs.debugger import Debugger, make_debugger

# : Back to the terminal's own.
_OFF = "\x1b[0m"


def _style(*, run: bool, stopped: bool, picked: bool) -> str:
    r"""Return the escape for a cell in any combination of the three states."""
    params = []
    if stopped:
        params.append("41")
    if run:
        params.append("7")
    if stopped and run:
        params.append("1")
    if picked:
        params.append("4")
    return f"\x1b[{';'.join(params)}m" if params else ""


@dataclass(frozen=True)
class Mark:
    r"""Where the current op is on the screen, and how much of it to mark."""

    row: int
    col: int
    span: int = 1


@dataclass(frozen=True)
class Frame:
    r"""One VM state, between two commands."""

    language: str
    program: str
    ip: int | tuple[int, ...] | None
    step: int
    halted: bool
    memory: tuple[int, ...]
    stack: tuple[object, ...]
    output: str
    fault: str | None = None
    # : What the language says its.
    ip_shape: str = "offset"
    # : The machine's own named.
    views: tuple[tuple[str, str], ...] = ()

    @classmethod
    def of(
        cls,
        language: str,
        program: str,
        dbg: Debugger,
        step: int,
        fault: str | None = None,
    ) -> Frame:
        r"""Snapshot ``dbg`` into a frame, copying the views that are lists."""
        return cls(
            language=language,
            program=program,
            ip=dbg.ip,
            step=step,
            halted=dbg.halted,
            memory=tuple(dbg.memory),
            stack=tuple(dbg.stack),
            output=dbg.output,
            fault=fault,
            ip_shape=dbg.ip_shape,
            views=dbg.views,
        )


def grid(program: str) -> list[str]:
    r"""Return ``program``'s lines padded to a rectangle."""
    lines = program.splitlines() or [""]
    width = max(len(line) for line in lines)
    return [line.ljust(width) for line in lines]


def _is_index(value: object) -> TypeGuard[int]:
    r"""Whether ``value`` is usable as a position."""
    return isinstance(value, int) and not isinstance(value, bool)


def locate(
    program: str, ip: int | tuple[int, ...] | None, shape: str = "offset"
) -> Mark | None:
    r"""Return where ``ip`` sits in :func:`grid`, or ``None``."""
    rows = grid(program)
    if shape == "grid":
        if isinstance(ip, tuple) and len(ip) >= 2 and all(map(_is_index, ip[:2])):
            row, col = ip[0], ip[1]
            if 0 <= row < len(rows) and 0 <= col < len(rows[0]):
                return Mark(row, col)
        return None
    if shape == "line":
        first = ip[0] if isinstance(ip, tuple) and ip else ip
        if _is_index(first) and 0 <= first < len(rows):
            return Mark(first, 0, len(rows[first]))
        return None
    if shape == "offset" and _is_index(ip) and 0 <= ip < len(program):
        before = program[:ip]
        return Mark(before.count("\n"), ip - (before.rfind("\n") + 1))
    return None


def at_cell(program: str, shape: str, row: int, col: int) -> Mark | None:
    r"""Return the mark a breakpoint on ``(row, col)`` covers, or ``None``."""
    rows = grid(program)
    if shape not in {"offset", "grid", "line"}:
        return None
    if not 0 <= row < len(rows) or not 0 <= col < len(rows[0]):
        return None
    if shape == "line":
        return Mark(row, 0, len(rows[row]))
    return Mark(row, col)


def _window(total: int, focus: int, size: int) -> int:
    r"""Return where a ``size``-wide window over ``total`` starts to show."""
    if total <= size:
        return 0
    return max(0, min(focus - size // 2, total - size))


def _cells(values: tuple[object, ...], width: int) -> str:
    r"""Render as many of ``values`` as fit in ``width``, noting what was."""
    if not values:
        return "(empty)"
    shown: list[str] = []
    used = 0
    for value in values:
        text = str(value)
        if used + len(text) + 1 > width and shown:
            break
        shown.append(text)
        used += len(text) + 1
    if len(shown) == len(values):
        return " ".join(shown)
    # The count of what was dropped.
    # items are given up for it, so.
    # than the row being cut.
    # off the end and leave a.
    while True:
        suffix = f" +{len(values) - len(shown)} more"
        if len(shown) <= 1 or used - 1 + len(suffix) <= width:
            return " ".join(shown) + suffix
        used -= len(shown.pop()) + 1


def _paint(
    text: str, row_marks: dict[int, tuple[int, bool, bool, bool]], left: int, reach: int
) -> str:
    r"""Wrap each marked run of ``text`` in the style that mark calls for."""
    for col in sorted(row_marks, reverse=True):
        span, run, stopped, picked = row_marks[col]
        cut = col - left
        if not 0 <= cut < reach:
            continue
        # A row shorter than the window.
        # rectangle's padding is.
        # is padded back out to the.
        width = min(span, reach - cut)
        end = min(cut + span, len(text))
        under = text[cut:end].ljust(width)
        code = _style(run=run, stopped=stopped, picked=picked)
        text = f"{text[:cut]}{code}{under}{_OFF}{text[end:]}"
    return text


def _recent(values: tuple[int | None, ...], width: int) -> str:
    r"""Render the newest of ``values`` that fit, oldest dropped first."""
    if not values:
        return "(none yet)"
    shown: list[str] = []
    used = 0
    for value in reversed(values):
        text = "-" if value is None else str(value)
        if used + len(text) + 1 > width and shown:
            break
        shown.insert(0, text)
        used += len(text) + 1
    if len(shown) == len(values):
        return " ".join(shown)
    # The marker for what was.
    # and the oldest value is what.
    # count is paid for in.
    # off the newest value, which.
    marker = "... "
    while len(shown) > 1 and used - 1 + len(marker) > width:
        used -= len(shown.pop(0)) + 1
    return marker + " ".join(shown)


def render(
    frame: Frame,
    height: int = 24,
    width: int = 80,
    breaks: tuple[Mark, ...] = (),
    picked: Mark | None = None,
    watch: tuple[int, tuple[int | None, ...]] | None = None,
) -> str:
    r"""Return the screen for ``frame``, windowed to ``height`` by."""
    rows = grid(program := frame.program)
    at = locate(program, frame.ip, frame.ip_shape)
    # The pane follows the selector.
    # the screen would otherwise be.
    # otherwise.
    focus = picked or at
    row, col = (focus.row, focus.col) if focus is not None else (0, 0)

    # Where each mark goes, keyed.
    # width and which of the three.
    # three at once, so they are.
    # others: a breakpoint the run.
    # does the selector resting on.
    marks: dict[int, dict[int, tuple[int, bool, bool, bool]]] = {}

    def _mark(spot: Mark | None, index: int) -> None:
        if spot is None:
            return
        row_marks = marks.setdefault(spot.row, {})
        span, *flags = row_marks.get(spot.col, (spot.span, False, False, False))
        flags[index] = True
        row_marks[spot.col] = (max(span, spot.span), *flags)  # type: ignore[assignment]

    for where in breaks:
        _mark(where, 1)
    _mark(at, 0)
    _mark(picked, 2)

    state = "halted" if frame.halted else "running"
    head = f"{frame.language}  step {frame.step}  ip {frame.ip}  {state}"
    if breaks:
        head += f"  {len(breaks)} break" + ("s" if len(breaks) > 1 else "")
    rule = "-" * width
    foot = "hjkl move | t break | space step | c continue | r run | b back | q quit"

    # The panes below the program.
    # the program gets; the two.
    tail = ["memory", "stack", "output"] + ([" fault"] if frame.fault else [])
    if frame.views:
        tail.append("views")
    if watch is not None:
        tail.append("watch")
    body = max(1, height - len(tail) - 5)

    gutter = len(str(len(rows)))
    reach = max(1, width - gutter - 3)
    top = _window(len(rows), row, body)
    left = _window(len(rows[0]), col, reach)

    out = [head[:width], rule]
    for index in range(top, min(top + body, len(rows))):
        out.append(
            f"{index + 1:>{gutter}} | "
            + _paint(
                rows[index][left : left + reach], marks.get(index, {}), left, reach
            )
        )
    out.append(rule)

    # ``_cells`` fits its own.
    # narrow that even one value.
    label = width - 9
    out.append(f"memory   {_cells(frame.memory, label)}"[:width])
    out.append(f"stack    {_cells(frame.stack, label)}"[:width])
    out.append(f"output   {frame.output!r}"[:width])
    if watch is not None:
        index, values = watch
        tag = f"cell {index}"
        out.append(f"watch    {tag}: {_recent(values, label - 2 - len(tag))}"[:width])
    if frame.views:
        # One row rather than one per.
        # worth showing, but not at the.
        named = "  ".join(f"{name}={text}" for name, text in frame.views)
        out.append(f"views    {named}"[:width])
    if frame.fault:
        out.append(f"fault    {frame.fault}"[:width])
    out.append(foot[:width])
    return "\n".join(out)


def replay(language: str, program: str, stdin: str, step: int) -> Frame:
    r"""Return the frame ``step`` commands into a fresh run."""
    dbg = make_debugger(language, program, stdin)
    fault = None
    taken = 0
    for _ in range(step):
        if dbg.halted:
            break
        try:
            dbg.step()
        except Exception as exc:
            fault = f"{type(exc).__name__}: {exc}"
            break
        taken += 1
    # The count is what was.
    # past the halt reports where.
    # asks for its whole bound, and.
    # the last real step rather.
    return Frame.of(language, program, dbg, taken, fault)


def _frame_bytes(frame: Frame) -> int:
    r"""Estimate what retaining ``frame`` costs, cheaply enough to do per."""
    return (
        200
        + len(frame.memory) * 32
        + len(frame.stack) * 32
        + len(frame.output)
        + sum(len(name) + len(text) + 64 for name, text in frame.views)
    )


class History:
    r"""The frames stepped through so far, so going back is a lookup."""

    # : What the retained frames.
    budget = 64 << 20

    def __init__(self, language: str, program: str, stdin: str = "") -> None:
        r"""Start a history at step 0 of a fresh run."""
        self._language = language
        self._program = program
        self._stdin = stdin
        self._dbg = make_debugger(language, program, stdin)
        self._fault: str | None = None
        self._frames: list[Frame] = []
        self._base = 0
        self._bytes = 0
        self._top = 0
        self._remember(Frame.of(language, program, self._dbg, 0))

    @property
    def top(self) -> int:
        r"""The furthest step reached, which is where the machine itself sits."""
        return self._top

    @property
    def retained(self) -> int:
        r"""How many frames are held right now, which :attr:`budget` bounds."""
        return len(self._frames)

    def at(self, step: int) -> Frame:
        r"""Return the frame at ``step``, running forward only if it is new."""
        step = max(0, step)
        if self._base <= step < self._base + len(self._frames):
            return self._frames[step - self._base]
        if step < self._base:
            # Rewound past what is still.
            # replaying reaches the same.
            return replay(self._language, self._program, self._stdin, step)
        while self._top < step and not self._dbg.halted and self._fault is None:
            self._advance()
        return self._frames[-1]

    def find(
        self, step: int, stop: Callable[[Frame], bool] | None, limit: int
    ) -> Frame:
        r"""Return the first frame after ``step`` where ``stop`` holds."""
        current = step
        while current < limit:
            current += 1
            frame = self.at(current)
            if frame.step < current:
                return frame  # halted or faulted before.
            if stop is not None and stop(frame):
                return frame
        return self.at(limit)

    def trace(self, index: int, upto: int, span: int) -> tuple[int | None, ...]:
        r"""Return up to ``span`` values of cell ``index``, ending at ``upto``."""
        if not self._frames:
            return ()
        last = min(upto, self._base + len(self._frames) - 1)
        first = max(self._base, last - span + 1)
        if last < first:
            return ()
        return tuple(
            frame.memory[index] if index < len(frame.memory) else None
            for frame in self._frames[first - self._base : last - self._base + 1]
        )

    def _advance(self) -> None:
        r"""Run the machine one command and keep the frame it produces."""
        try:
            self._dbg.step()
        except Exception as exc:
            # The fault belongs to the step.
            # attached to the frame already.
            # what ``replay`` reports for.
            self._fault = f"{type(exc).__name__}: {exc}"
            self._bytes -= _frame_bytes(self._frames.pop())
            self._remember(
                Frame.of(
                    self._language, self._program, self._dbg, self._top, self._fault
                )
            )
            return
        self._top += 1
        self._remember(
            Frame.of(self._language, self._program, self._dbg, self._top, self._fault)
        )

    def _remember(self, frame: Frame) -> None:
        r"""Append ``frame``, dropping the oldest quarter once over budget."""
        self._frames.append(frame)
        self._bytes += _frame_bytes(frame)
        if self._bytes <= self.budget or len(self._frames) < 4:
            return
        # Trimming a quarter at a time.
        # the cost of the shift.
        # because the lookup above has.
        drop = len(self._frames) // 4
        self._bytes -= sum(_frame_bytes(f) for f in self._frames[:drop])
        del self._frames[:drop]
        self._base += drop


# : Wipe the screen and park.
CLEAR = "\x1b[H\x1b[2J"

# : Which way each movement key.
_MOVES = {"h": (0, -1), "j": (1, 0), "k": (-1, 0), "l": (0, 1)}

# : How far back a watch asks,.
# : Generous, because asking is.
_WATCH_SPAN = 256


def breakpoint_for(
    at: int | tuple[int, ...] | None = None,
    cell: tuple[int, int] | None = None,
    output: str | None = None,
) -> Callable[[Frame], bool] | None:
    r"""Return one predicate over frames for the breakpoints asked for."""
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
    r"""Add the marked positions to whatever the caller already asked for."""
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
) -> None:
    r"""Repaint and read keys until asked to stop."""
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

    def _move(down: int, across: int) -> Mark | None:
        spot = picked or locate(program, frame.ip, shape) or Mark(0, 0)
        return at_cell(
            program,
            shape,
            min(max(spot.row + down, 0), len(rows) - 1),
            min(max(spot.col + across, 0), len(rows[0]) - 1),
        )

    while True:
        height, width = get_size()
        # Asked for at each repaint.
        # trace is a view over the.
        # it shorter, the way the run.
        seen = (
            None if watch is None else (watch, history.trace(watch, step, _WATCH_SPAN))
        )
        screen = render(
            frame, height, width, tuple(sorted(marked, key=repr)), picked, seen
        )
        write(CLEAR + screen.replace("\n", "\r\n"))
        key = read_key()
        if key in ("q", "\x03", ""):
            return
        if key in _MOVES:
            picked = _move(*_MOVES[key]) or picked
            continue
        if key == "t":
            # Nowhere to put one is a no-op.
            # a language whose position is.
            # breakpoint could name.
            if picked is not None:
                marked.symmetric_difference_update({picked})
            continue
        if key == "b":
            step = max(0, step - 1)
        elif key == "r":
            step = max_steps
        elif key == "c":
            # Continue means "to the next.
            # nothing set it is the run key.
            # whether or not the caller.
            step = history.find(step, _with_marks(stop, marked), max_steps).step
        elif key in (" ", "\r", "\n"):
            step += 1
        else:
            continue
        frame = history.at(step)
        step = frame.step
        picked = locate(program, frame.ip, shape)


def run_tui(
    language: str,
    program: str,
    stdin: str = "",
    max_steps: int = 1_000_000,
    stop: Callable[[Frame], bool] | None = None,
    at: tuple[int | tuple[int, ...], ...] = (),
    watch: int | None = None,
) -> None:  # pragma: no cover - the raw-terminal wrapper; the loop is tested
    r"""Step ``program`` interactively on this terminal."""
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

    # Built before the terminal is.
    # raise for the caller to.
    # mode with the screen already.
    history = History(language, program, stdin)

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        drive(
            history, lambda: sys.stdin.read(1), write, size, max_steps, stop, at, watch
        )
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        write(CLEAR)
