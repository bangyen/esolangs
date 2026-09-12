"""A terminal step-through over the debugger.

:func:`render` is a pure function from one :class:`Frame` -- a VM's state
between two commands -- to the text of a screen, and :func:`drive` is the
loop that repaints it and reads keys.  That loop takes its input and output
as arguments, so a test drives it with scripted keys and collects what it
paints; only :func:`run_tui`, which puts the terminal in raw mode and hands
it the real stdin, goes unexercised.

The one thing a stepper has to do that :mod:`esolangs.debugger` does not is say
*where in the program* execution is, and ``ip`` is not one type across the
registry.  :func:`locate` turns one into a place on the source, but it
cannot do that from the value alone: a cell, a call depth paired with a
cursor, and a stack of one position per frame are all tuples of small ints
and none of them can be told from the others by looking.  So the language
says which it means, through ``ip_shape`` on its machine, and a language
that says nothing while reporting a tuple is simply not highlighted.  The
header prints the raw ``ip`` either way, which is what keeps a missing
highlight readable rather than silent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeGuard

from esolangs.debugger import Debugger, make_debugger

#: Back to the terminal's own attributes, which ends every marked run.
_OFF = "\x1b[0m"


def _style(*, run: bool, stopped: bool, picked: bool) -> str:
    """Return the escape for a cell in any combination of the three states.

    Three things can be true of one cell at once -- the run is on it, a
    breakpoint is on it, and the selector is on it -- so the attributes
    compose rather than one winning.  Reverse video is the run, red is a
    breakpoint, and an underline is the selector.

    The bold is the awkward one, and it earns its place.  Reverse video over
    a red background swaps the red onto the *foreground*, so "run on a
    breakpoint" comes out as another mostly-red cell and reads the same as
    the breakpoint alone; bold is what separates them.  It is a shape rather
    than a hue, which is the same reason the selector is an underline: a
    reader who cannot tell two reds apart, or a terminal with its own
    palette, still sees three different things.
    """
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
    """Where the current op is on the screen, and how much of it to mark."""

    row: int
    col: int
    span: int = 1


@dataclass(frozen=True)
class Frame:
    """One VM state, between two commands.

    The views :class:`~esolangs.vm.VM` offers every language, the step
    count, and whatever else the machine names itself -- ``acc``, ``ptr``,
    ``ind`` -- in :attr:`views`.

    Those are read off the machine rather than inferred, which is the whole
    difference between showing them and guessing.  Only eighteen of the
    sixty-nine interpreters have a ``ptr`` at all and the ``ind`` thirty-three
    carry is usually an instruction index, so a "pointer" row invented for
    every language would be wrong more often than right; a row a language
    named itself cannot be.
    """

    language: str
    program: str
    ip: int | tuple[int, ...] | None
    step: int
    halted: bool
    memory: tuple[int, ...]
    stack: tuple[object, ...]
    output: str
    fault: str | None = None
    #: What the language says its ``ip`` counts; see :func:`locate`.
    ip_shape: str = "offset"
    #: The machine's own named state, already shortened to fit a row.
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
        """Snapshot ``dbg`` into a frame, copying the views that are lists."""
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
    """Return ``program``'s lines padded to a rectangle.

    Grid languages are written ragged -- a row's trailing blanks are not in
    the file -- but they step over the rectangle those lines imply, so a
    column routinely runs past the end of its own line.  Padding here is what
    lets :func:`locate` bounds-check a position against the shape the
    interpreter actually walks.
    """
    lines = program.splitlines() or [""]
    width = max(len(line) for line in lines)
    return [line.ljust(width) for line in lines]


def _is_index(value: object) -> TypeGuard[int]:
    """Whether ``value`` is usable as a position.

    ``bool`` is excluded even though it is an ``int``, since ``True`` would
    otherwise read as offset 1.  It is a :class:`~typing.TypeGuard` so the
    checker narrows the union ``ip`` arrives as, rather than each caller
    repeating the pair of ``isinstance`` calls to get the same effect.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def locate(
    program: str, ip: int | tuple[int, ...] | None, shape: str = "offset"
) -> Mark | None:
    """Return where ``ip`` sits in :func:`grid`, or ``None``.

    ``shape`` is the language's own answer to what its ``ip`` counts, taken
    from :attr:`~esolangs.vm.VM.ip_shape`, because the value cannot be read
    without it.  ``"offset"`` counts characters into the program text,
    ``"grid"`` is ``(row, col)`` with any rest a heading, and ``"line"``
    starts with a line number -- which marks the whole line, that being all
    such a language knows about where it is.

    ``"opaque"`` is a position that is not a place in the source at all: a
    frame stack, a call depth paired with a cursor, a 3-D point.  It is
    declared rather than left to the default so that an undeclared tuple
    stays distinguishable from one somebody has looked at and classified;
    both end up unmarked here, but only one of them is a question nobody
    has answered.  ``test_a_positional_ip_says_what_it_counts`` is what
    keeps them apart.

    A shape that is none of those, or a value that does not fit the shape it
    claims, is not located.  Guessing is what this function exists to avoid:
    those three all look exactly like a ``(row, col)``, so reading one as a
    cell marks a real character that is not the one running.
    """
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
    """Return the mark a breakpoint on ``(row, col)`` covers, or ``None``.

    The counterpart to :func:`locate`: that turns a machine's position into
    a place on the screen, and this turns a place on the screen into the
    mark a position there would produce.  Comparing the two is what lets a
    breakpoint put somewhere by hand be recognised when the run arrives.

    A line-counting language gets the whole line whichever column was
    picked, because a line is all it can distinguish; a language whose
    position is not on the source at all can hold no such breakpoint, and
    says so with ``None``.
    """
    rows = grid(program)
    if shape not in {"offset", "grid", "line"}:
        return None
    if not 0 <= row < len(rows) or not 0 <= col < len(rows[0]):
        return None
    if shape == "line":
        return Mark(row, 0, len(rows[row]))
    return Mark(row, col)


def _window(total: int, focus: int, size: int) -> int:
    """Return where a ``size``-wide window over ``total`` starts to show ``focus``."""
    if total <= size:
        return 0
    return max(0, min(focus - size // 2, total - size))


def _cells(values: tuple[object, ...], width: int) -> str:
    """Render as many of ``values`` as fit in ``width``, noting what was dropped."""
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
    # The count of what was dropped has to fit as well, and it grows as
    # items are given up for it, so the two are settled together rather
    # than the row being cut afterwards -- a cut would take the "+N more"
    # off the end and leave a truncated tape looking complete.
    while True:
        suffix = f" +{len(values) - len(shown)} more"
        if len(shown) <= 1 or used - 1 + len(suffix) <= width:
            return " ".join(shown) + suffix
        used -= len(shown.pop()) + 1


def _paint(
    text: str, row_marks: dict[int, tuple[int, bool, bool, bool]], left: int, reach: int
) -> str:
    """Wrap each marked run of ``text`` in the style that mark calls for.

    The runs are applied right to left so that inserting the escapes for one
    cannot shift the offsets of the next, which is the whole reason this is
    a separate pass rather than done while the row is sliced.
    """
    for col in sorted(row_marks, reverse=True):
        span, run, stopped, picked = row_marks[col]
        cut = col - left
        if not 0 <= cut < reach:
            continue
        # A row shorter than the window still has the position in it -- the
        # rectangle's padding is trimmed by the slice -- so the marked run
        # is padded back out to the length it should cover.
        width = min(span, reach - cut)
        end = min(cut + span, len(text))
        under = text[cut:end].ljust(width)
        code = _style(run=run, stopped=stopped, picked=picked)
        text = f"{text[:cut]}{code}{under}{_OFF}{text[end:]}"
    return text


def _recent(values: tuple[int | None, ...], width: int) -> str:
    """Render the newest of ``values`` that fit, oldest dropped first.

    The opposite end from :func:`_cells`, and for a different reason: a
    tape is read from cell zero outwards, but a trace is read from *now*
    backwards, so what has to survive a narrow row is the other end of it.
    """
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
    # The marker for what was dropped has to fit inside the budget too,
    # and the oldest value is what pays for it -- exactly as the dropped
    # count is paid for in ``_cells``.  Getting this wrong cuts a digit
    # off the newest value, which is the one the row exists to show.
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
    """Return the screen for ``frame``, windowed to ``height`` by ``width``.

    The program pane scrolls in both directions around the highlighted cell,
    because the registry's programs run to hundreds of lines and thousands of
    columns.  The column window is shared by every visible line so a grid
    language's rows stay aligned under each other.
    """
    rows = grid(program := frame.program)
    at = locate(program, frame.ip, frame.ip_shape)
    # The pane follows the selector when there is one, since moving it off
    # the screen would otherwise be the same as losing it, and the run
    # otherwise.
    focus = picked or at
    row, col = (focus.row, focus.col) if focus is not None else (0, 0)

    # Where each mark goes, keyed by row and then by column, carrying its
    # width and which of the three things are true of it.  A cell can be all
    # three at once, so they are merged rather than one overwriting the
    # others: a breakpoint the run is sitting on has to stay visible, and so
    # does the selector resting on either.
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

    # The panes below the program are fixed, so whatever is left over is what
    # the program gets; the two rules and the blank line are counted here.
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

    # ``_cells`` fits its own budget; the cut is the guard for a width so
    # narrow that even one value overruns it.
    label = width - 9
    out.append(f"memory   {_cells(frame.memory, label)}"[:width])
    out.append(f"stack    {_cells(frame.stack, label)}"[:width])
    out.append(f"output   {frame.output!r}"[:width])
    if watch is not None:
        index, values = watch
        tag = f"cell {index}"
        out.append(f"watch    {tag}: {_recent(values, label - 2 - len(tag))}"[:width])
    if frame.views:
        # One row rather than one per name: the language's own vocabulary is
        # worth showing, but not at the cost of the program pane's height.
        named = "  ".join(f"{name}={text}" for name, text in frame.views)
        out.append(f"views    {named}"[:width])
    if frame.fault:
        out.append(f"fault    {frame.fault}"[:width])
    out.append(foot[:width])
    return "\n".join(out)


def replay(language: str, program: str, stdin: str, step: int) -> Frame:
    """Return the frame ``step`` commands into a fresh run.

    This derives a frame from nothing, which is exact because every VM here
    is deterministic -- the adapters hand a seeded source to the languages
    with a random instruction -- so re-running from the start reaches the
    same state and no snapshot of a language's private state is needed.

    It is not how the stepper goes backwards.  :class:`History` keeps the
    frames it has already built, which is a lookup rather than a re-run;
    this is the fallback for a step so old it has been dropped, and the
    reference the tests check that lookup against.
    """
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
    # The count is what was *executed*, not what was asked for, so a request
    # past the halt reports where the program really stopped.  The run key
    # asks for its whole bound, and stepping back from there has to land on
    # the last real step rather than one short of a million.
    return Frame.of(language, program, dbg, taken, fault)


def _frame_bytes(frame: Frame) -> int:
    """Estimate what retaining ``frame`` costs, cheaply enough to do per step."""
    return (
        200
        + len(frame.memory) * 32
        + len(frame.stack) * 32
        + len(frame.output)
        + sum(len(name) + len(text) + 64 for name, text in frame.views)
    )


class History:
    """The frames stepped through so far, so going back is a lookup.

    A :class:`Frame` is already an immutable snapshot of everything the
    screen draws, and one is built per step regardless, so keeping them
    costs nothing beyond the memory.  That is what makes stepping cheap:
    the machine only ever runs forward, and every key that lands on a step
    already visited reads it out of the list.

    Retention is bounded in *bytes* rather than in frames, because a frame
    is not a fixed size -- the median across the registry is about 260
    bytes, but NoComment's four-thousand-cell tape makes one 147 KB, and
    the run key's million-step bound would turn that into 148 GB.  When the
    budget is spent the oldest quarter is dropped, and a step older than
    what is left falls back to :func:`replay`, which is exact because the
    VMs are deterministic.
    """

    #: What the retained frames may occupy before the oldest are dropped.
    budget = 64 << 20

    def __init__(self, language: str, program: str, stdin: str = "") -> None:
        """Start a history at step 0 of a fresh run."""
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
        """The furthest step reached, which is where the machine itself sits."""
        return self._top

    @property
    def retained(self) -> int:
        """How many frames are held right now, which :attr:`budget` bounds."""
        return len(self._frames)

    def at(self, step: int) -> Frame:
        """Return the frame at ``step``, running forward only if it is new."""
        step = max(0, step)
        if self._base <= step < self._base + len(self._frames):
            return self._frames[step - self._base]
        if step < self._base:
            # Rewound past what is still held; the run is deterministic, so
            # replaying reaches the same state the dropped frame held.
            return replay(self._language, self._program, self._stdin, step)
        while self._top < step and not self._dbg.halted and self._fault is None:
            self._advance()
        return self._frames[-1]

    def find(
        self, step: int, stop: Callable[[Frame], bool] | None, limit: int
    ) -> Frame:
        """Return the first frame after ``step`` where ``stop`` holds.

        Without a ``stop`` this is a plain run to the halt, which is what
        makes the continue key the same thing as the run key for a program
        with no breakpoints on it.

        The predicate is read off a *frame*, which is the state between two
        commands, so it sees the same instant
        :meth:`~esolangs.debugger.Debugger.run` checks before stepping -- a
        breakpoint therefore stops with its condition still true, and the
        screen and the command line agree about where a program stopped.

        Stepping goes through :meth:`at`, so a frame already kept is a
        lookup and only the ones past the furthest step run the machine.
        """
        current = step
        while current < limit:
            current += 1
            frame = self.at(current)
            if frame.step < current:
                return frame  # halted or faulted before getting there
            if stop is not None and stop(frame):
                return frame
        return self.at(limit)

    def trace(self, index: int, upto: int, span: int) -> tuple[int | None, ...]:
        """Return up to ``span`` values of cell ``index``, ending at ``upto``.

        A watch needs no bookkeeping of its own here.  ``Debugger`` records
        one by appending a value per step, but every frame this class keeps
        already holds the whole tape, so the history of a cell is a view
        over what is retained rather than a second copy of it.

        That also sets the limit honestly: the trace reaches back only as
        far as the retained window, which the byte budget bounds.  A cell
        the tape has not grown to yet reads ``None``, the same absence
        ``Debugger.watch_cell`` records for it.
        """
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
        """Run the machine one command and keep the frame it produces."""
        try:
            self._dbg.step()
        except Exception as exc:
            # The fault belongs to the step that did not complete, so it is
            # attached to the frame already standing at this count, matching
            # what ``replay`` reports for the same request.
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
        """Append ``frame``, dropping the oldest quarter once over budget."""
        self._frames.append(frame)
        self._bytes += _frame_bytes(frame)
        if self._bytes <= self.budget or len(self._frames) < 4:
            return
        # Trimming a quarter at a time rather than one frame at a time keeps
        # the cost of the shift amortised; a list is used over a deque
        # because the lookup above has to be O(1) at any offset.
        drop = len(self._frames) // 4
        self._bytes -= sum(_frame_bytes(f) for f in self._frames[:drop])
        del self._frames[:drop]
        self._base += drop


#: Wipe the screen and park the cursor, which is one repaint's worth of setup.
CLEAR = "\x1b[H\x1b[2J"

#: Which way each movement key sends the selector, as ``(down, across)``.
_MOVES = {"h": (0, -1), "j": (1, 0), "k": (-1, 0), "l": (0, 1)}

#: How far back a watch asks, before the row's own width cuts it down.
#: Generous, because asking is a slice of frames already held.
_WATCH_SPAN = 256


def breakpoint_for(
    at: int | tuple[int, ...] | None = None,
    cell: tuple[int, int] | None = None,
    output: str | None = None,
) -> Callable[[Frame], bool] | None:
    """Return one predicate over frames for the breakpoints asked for.

    ``None`` when none was, which is what leaves the continue key running
    to the halt.  Several together stop at whichever is reached first, the
    way :class:`~esolangs.debugger.Debugger`'s list of conditions does.

    These mirror ``Debugger.break_at``, ``break_on_cell`` and
    ``break_on_output`` rather than reaching for them, because the screen
    tests a :class:`Frame` it has already kept, not a live machine -- which
    is what lets a breakpoint be found among steps that have been run
    without running them again.
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

    The test is on the *position* the frame is at, not on its raw ``ip``.
    That is what makes the drawing and the stopping agree: a grid language's
    ``ip`` carries a heading, so matching the raw value would stop only on
    one approach to a cell while the screen had the whole cell marked.  A
    breakpoint on a cell now means the cell, however the run arrives at it.

    Rebuilt on each use rather than kept, because the set is edited between
    keys and a predicate closed over a stale copy would stop in last
    minute's places.
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
) -> None:
    """Repaint and read keys until asked to stop.

    The loop takes its input and output as arguments rather than reaching
    for the terminal, which is what lets it be driven from a test with
    scripted keys.  What is left in :func:`run_tui` is the raw-mode wrapper
    around it, and that is the only part no test exercises.

    An empty key means the input ended, and is treated as a quit so a closed
    stream stops the loop instead of spinning on it.

    ``hjkl`` move a selector over the program and ``t`` toggles a breakpoint
    under it, so a breakpoint can be put somewhere the run has not reached.
    The selector starts on the run and snaps back to it whenever the run
    moves, which is what keeps "where am I" and "where am I pointing" from
    drifting apart over a long session.

    Those keys rather than the arrows because an arrow is a multi-byte
    escape and ``read_key`` returns one character; hjkl also keeps a
    scripted test a plain string.  ``at`` seeds the breakpoints from the
    command line, so the flag and the key put them in the same place.
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
        # Asked for at each repaint rather than accumulated, because the
        # trace is a view over the frames already kept: stepping back makes
        # it shorter, the way the run itself goes back.
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
            # Nowhere to put one is a no-op rather than a mark on a nothing:
            # a language whose position is not on the source has no cell a
            # breakpoint could name.
            if picked is not None:
                marked.symmetric_difference_update({picked})
            continue
        if key == "b":
            step = max(0, step - 1)
        elif key == "r":
            step = max_steps
        elif key == "c":
            # Continue means "to the next breakpoint, or the halt", so with
            # nothing set it is the run key -- which is why it is offered
            # whether or not the caller asked for a breakpoint.
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
    """Step ``program`` interactively on this terminal.

    ``max_steps`` bounds the ``r`` key.  It is not a nicety: some languages
    here never halt on their own (``self_halts`` on the VM protocol says so),
    and a run key without a bound would hang the terminal on them.

    Everything here is the terminal itself -- raw mode on, restore it
    whatever happens, and where to read and write.  The stepping is
    :func:`drive`.
    """
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

    # Built before the terminal is touched, so an unknown language is a clean
    # raise for the caller to report rather than a failure part-way into raw
    # mode with the screen already taken over.
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
