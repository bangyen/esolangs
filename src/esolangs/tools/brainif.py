"""Boolean-function generator for BrainIf."""

from dataclasses import dataclass

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
)


@dataclass
class _Cmd:
    """A line emitted verbatim, apart from its ``goto`` placeholder."""

    text: str


@dataclass
class _If:
    """An ``if <char> goto <label>`` line, resolved once labels are known."""

    char: int
    label: int


@dataclass
class _MoveLeft:
    """An ``if <char> move left`` line that also *defines* ``label``.

    There is no rightward mirror: the build walks out over zeroed cells
    before the tree runs, and every branch after that walks down.
    """

    char: int
    label: int


@dataclass
class _Out:
    """A marker defining output routine ``which``; it emits no line itself."""

    which: int


@dataclass
class _End:
    """The trailing blank line every program ends on."""


_Entry = _Cmd | _If | _MoveLeft | _Out | _End


def brainif(truth_table: str, width: int | None = None) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 49 goto``; zero falls
    through to its subtree without spelling a second destination.

    The answer byte is built *first*, on cell 0: 48 ``increment`` lines
    once, rather than a climb per digit.  There is no way to copy a byte in
    BrainIf, and a climb converges -- every entry value 0..47 leaves it
    holding 48 -- so one climb cannot serve both digits however it is
    entered.  Two climbs is 48 + 49 lines, which used to dominate: a
    ``11110000`` program was 97 increments out of 153 lines.

    Building first also fixes which way the tape runs.  The pointer steps
    out over cells that are still zero, where one ``if 0 move right``
    advances exactly one cell, and the tree reads its inputs from that far
    cell back down toward the answer.  So a level is a read, two branch
    tests and a step left, and a leaf is *there* already, adding one iff its
    entry is a ``1`` before joining a two-line tail.

    That is what makes the tree foldable: a subtree whose rows all agree
    becomes a leaf, and since a leaf spends no moves reaching the answer the
    saving is not handed back.  The skipped levels' *reads* still happen, or
    a caller feeding several programs from one stream would desync.  An
    earlier arrangement built the answer past the inputs and had each leaf
    walk out to it, costing two lines per skipped level -- exactly the fold.
    """
    n = _validate_truth_table(truth_table)
    if len(truth_table) > 16:
        return _brainif_linear(truth_table)
    # Initial zero skips the two-line output trampoline.  Leaves later return
    # with 48/49 to line 2, whose guards forward to the wide output-tail
    # address -- rendered twice, rather than once per leaf.
    entries: list[_Entry] = [
        _Cmd("if 0 goto 4"),
        _Cmd(f"if {_ASCII_ZERO} goto OUT0"),
        _Cmd(f"if {_ASCII_ONE} goto OUT0"),
    ]
    # The answer byte goes on cell 0 and the inputs above it, read from the
    # far end back down.
    entries += [_Cmd(f"if {v} increment") for v in range(_ASCII_ZERO)]
    entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
    entries += [_Cmd("if 0 move right") for _ in range(n - 1)]

    counter = [0]
    constant = constant_span_test(truth_table)

    def build(lo: int, hi: int, k: int) -> list[_Entry]:
        """Emit a table span, entered with the pointer on cell n-k+1."""
        rest = n - (k - 1)
        if rest == 0 or constant(lo, hi):
            # Consume the inputs this path never branched on, which walks
            # the pointer the rest of the way home; then add one iff the
            # answer is a 1 and join the tail.
            out: list[_Entry] = []
            for _ in range(rest):
                out.append(_Cmd("if 0 input"))
                out.append(_Cmd(f"if {_ASCII_ZERO} move left"))
                out.append(_Cmd(f"if {_ASCII_ONE} move left"))
            if int(truth_table[lo]):
                out.append(_Cmd(f"if {_ASCII_ZERO} increment"))
            out.append(_Cmd(f"if {_ASCII_ZERO} goto 2"))
            out.append(_Cmd(f"if {_ASCII_ONE} goto 2"))
            return out
        # Level ``k`` reads input ``k - 1`` into cell ``n - k + 1``, so the
        # bit it selects is the table's usual most-significant-first one --
        # the reads are in input order even though the pointer walks down.
        middle = (lo + hi) // 2
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        sub0 = build(lo, middle, k + 1)
        sub1 = build(middle, hi, k + 1)
        return [
            _Cmd("if 0 input"),
            _If(_ASCII_ONE, l1),
            _MoveLeft(_ASCII_ZERO, l0),
            *sub0,
            _MoveLeft(_ASCII_ONE, l1),
            *sub1,
        ]

    entries += build(0, len(truth_table), 1)
    # One shared tail: the answer cell already holds the byte to print, so
    # this is two lines rather than a climb per digit.
    entries.append(_Out(0))
    entries.append(_Cmd(f"if {_ASCII_ZERO} output"))
    entries.append(_Cmd(f"if {_ASCII_ONE} output"))
    entries.append(_End())

    # resolve labels from the actual line sequence (the "out" markers emit
    # no line, so the marker's target is the next line that does)
    labels: dict[int, int] = {}
    out_labels: dict[int, int] = {}
    line_no = 0
    pending: int | None = None
    for entry in entries:
        if isinstance(entry, _Out):
            pending = entry.which
            continue
        line_no += 1
        if pending is not None:
            out_labels[pending] = line_no
            pending = None
        if isinstance(entry, _MoveLeft):
            labels[entry.label] = line_no

    lines: list[str] = []
    for entry in entries:
        if isinstance(entry, _Cmd):
            text = entry.text
            if "goto OUT" in text:
                # keep the line's own guard: a leaf reaches the tail from a
                # cell holding 48 or 49, so it emits one goto for each
                guard, target = text.split(" goto OUT")
                text = f"{guard} goto {out_labels[int(target)]}"
            lines.append(text)
        elif isinstance(entry, _If):
            lines.append(f"if {entry.char} goto {labels[entry.label]}")
        elif isinstance(entry, _MoveLeft):
            lines.append(f"if {entry.char} move left")
        elif isinstance(entry, _Out):
            continue
        else:
            # _End, the trailing blank line.  Spelled as the fallback rather
            # than a fifth ``isinstance`` so that adding a variant to
            # ``_Entry`` without a branch here is a type error: mypy narrows
            # this to ``_End``, and a wider union would not narrow.
            _: _End = entry
            lines.append("")
    if width is not None and any(len(line) > width for line in lines):
        # The language's own short spellings, as the linear path uses
        # throughout: line count is unchanged, so goto targets stay valid.
        lines = [
            line.replace("increment", "inc")
            .replace("move right", "right")
            .replace("move left", "left")
            for line in lines
        ]
    return "\n".join(lines)


#: Levels whose walk becomes a marker-terminated ``goto`` loop instead of
#: ``2**(n-i)`` emitted ``left`` lines.  Measured over n=8..12: four is where
#: the per-entry constant bottoms out at 25.4 (three reads 25.8, five 25.5).
_LOOP_LEVELS = 4


def _top_level(n: int) -> int:
    """Return the deepest level that may loop, for an ``n``-input table.

    Levels ``i < j`` share a marker position exactly when ``j - i ==
    2**(n-1-j)``, and ``m_i = 2**(n-1-i)`` must be even for a two-cell loop
    iteration.  Halving the arity clears both at once: ``top <= (n-2)/2``
    leaves ``2**(n-1-top) >= 2**(n/2)``, which outgrows ``top``.
    """
    return min(_LOOP_LEVELS, (n - 2) // 2)


class _Strip:
    """The strip's cell values, and what a guard at a given class may see.

    A cell holds ``2 * (position % 2) + bit``; the parity keeps a two-line
    step from firing twice.  A *marker* cell holds its level's value plus the
    bit instead, which is what stops that level's loop.
    """

    def __init__(self, cells: str, n: int) -> None:
        """Place the markers and fix the alphabet for an ``n``-input table."""
        self.cells = cells
        size = len(cells)
        top = _top_level(n)
        self.levels = list(range(top + 1))
        #: ``2 * m_i``: the period of level ``i``'s marker class.
        self.period = {i: 1 << (n - i) for i in self.levels}
        #: Level ``i``'s walk starts at ``size - 2 - i`` (mod its period) and
        #: ends ``m_i`` cells left of it, which is where its marker goes.
        self.first = {
            i: (size - 2 - i - (1 << (n - 1 - i))) % self.period[i] for i in self.levels
        }
        # The deepest looped level has the most markers, so it takes the
        # cheapest value: a climb to v costs v lines, once per marker.
        self.value = {i: 4 + 2 * (top - i) for i in self.levels}
        self.level_at: dict[int, int] = {}
        for i in self.levels:
            for pos in range(self.first[i], size, self.period[i]):
                self.level_at[pos] = i
        self.alphabet: dict[int, set[int]] = {0: {0, 1}, 1: {2, 3}}
        for i in self.levels:
            self.alphabet[self.first[i] % 2] |= {self.value[i], self.value[i] + 1}

    def at(self, pos: int) -> int:
        """Return the value stored in cell ``pos``."""
        bit = int(self.cells[pos])
        level = self.level_at.get(pos)
        if level is None:
            return 2 * (pos % 2) + bit
        return self.value[level] + bit

    def seen(self, residue: int, modulus: int | None) -> list[int]:
        """Values a cell known only as ``residue`` mod ``modulus`` may hold.

        ``None`` means the position is exact -- the first read -- so the value
        is a compile-time constant.  Otherwise a level's markers are possible
        when the two classes can meet; an over-estimate costs a dead guard
        line, an under-estimate is a bug.
        """
        if modulus is None:
            return [self.at(residue)]
        parity = residue % 2
        out = {2 * parity, 2 * parity + 1}
        for i in self.levels:
            if self.first[i] % 2 != parity:
                continue
            coarse = min(modulus, self.period[i])
            if self.first[i] % coarse == residue % coarse:
                out |= {self.value[i], self.value[i] + 1}
        return sorted(out)


def _brainif_linear(truth_table: str) -> str:
    """Emit a linear spatial lookup for BrainIf.

    One cell an entry, carrying its bit *and* its parity -- ``{0, 1}`` even,
    ``{2, 3}`` odd -- so an emitted step left is two guarded moves, one per
    value the cell it leaves can hold.  The strip stores 0..3 rather than
    ``'0'``/``'1'`` because BrainIf cannot write a constant: a cell climbs by
    ``if v inc`` lines, so an ASCII digit an entry would be a 48-line climb an
    entry, and only the final ``output`` cares what the byte is.

    The build runs left to right and the selection right to left, reading the
    index in complement: a ``1`` stays put and a ``0`` walks its weight.  One
    padding cell an input keeps every read right of the answer cell.

    The top levels walk by *loop* rather than by emitted line.  Level ``i``
    ends ``m_i = 2**(n-1-i)`` cells left of a position fixed mod ``2*m_i``
    whatever the higher bits were, so a marker value planted on that whole
    residue class stops the loop exactly there: the class has period
    ``2*m_i`` and the window is ``m_i`` long, so the window holds one.  That
    trades ``2*m_i`` ``left`` lines for ``2**i`` marker climbs, which only the
    widest levels are worth (:data:`_LOOP_LEVELS`) -- level 0 alone is half
    the crossings and costs one marker.  Commands take the short spellings
    the interpreter matches by substring.
    """
    n = _validate_truth_table(truth_table)
    cells = truth_table + "0" * n
    size = len(cells)
    strip = _Strip(cells, n)
    lines: list[str] = []
    labels: dict[str, int] = {}

    def mark(name: str) -> None:
        labels[name] = len(lines) + 1

    def guard(residue: int, modulus: int | None, suffix: str) -> None:
        """Emit one guarded line per value the named cell may hold."""
        lines.extend(f"if {v} {suffix}" for v in strip.seen(residue, modulus))

    # The table, then one padding cell per input.  Padding takes the cheaper
    # bit; the last cell needs no ``right``, since the walk starts there.
    for index in range(size):
        value = strip.at(index)
        lines += [f"if {passed} inc" for passed in range(value)]
        if index + 1 < size:
            lines.append(f"if {value} right")

    # A read overwrites the cell it lands on, so its guard is every value that
    # cell's class admits.  The first step off it is one line, not two: the
    # byte just read says which branch is running.  The read for level ``i``
    # sits at ``size - 1 - i`` mod ``2**(n-i)`` -- exactly, for level 0.
    for i in range(n):
        far, after = f"far_{i}", f"after_{i}"
        known = None if i == 0 else 1 << (n - i)
        guard(size - 1 - i, known, "input")
        lines.append(f"if {_ASCII_ZERO} goto @{far}")
        lines.append(f"if {_ASCII_ONE} left")
        guard(size - 2 - i, known, f"goto @{after}")
        mark(far)
        lines.append(f"if {_ASCII_ZERO} left")
        if i in strip.levels:
            _emit_loop(lines, labels, strip, i, size)
        else:
            for k in range(1 << (n - 1 - i)):
                guard(size - 2 - i - k, known, "left")
        mark(after)

    # The walk ends on the selected cell, whose value is its bit in the low
    # place -- every marker value is even -- and the climbs converge, so
    # neither cares which class the cell came from.
    alphabet = strip.alphabet[0] | strip.alphabet[1]
    for value in sorted(v for v in alphabet if v % 2):
        lines.append(f"if {value} goto @one_out")
    for value in range(_ASCII_ZERO):
        lines.append(f"if {value} inc")
    lines.append(f"if {_ASCII_ZERO} output")
    lines.append(f"if {_ASCII_ZERO} goto @done")
    mark("one_out")
    for value in range(1, _ASCII_ONE):
        lines.append(f"if {value} inc")
    lines.append(f"if {_ASCII_ONE} output")
    mark("done")
    lines.append("")
    for i, line in enumerate(lines):
        if "goto @" in line:
            head, name = line.split("goto @")
            lines[i] = f"{head}goto {labels[name]}"
    return "\n".join(lines)


def _emit_loop(
    lines: list[str], labels: dict[str, int], strip: _Strip, level: int, size: int
) -> None:
    """Emit level ``level``'s walk as a loop that halts on its own marker.

    Three groups, entered and left on parity ``P``: cross one cell, cross a
    second, repeat unless the cell is the marker.  Two cells an iteration
    holds the parity, and ``m_i`` is even wherever a level may loop, so the
    walk lands on the marker rather than stepping over it.
    """
    name = f"loop_{level}"
    parity = (size - 2 - level) % 2
    own = {strip.value[level], strip.value[level] + 1}
    crossable = sorted(strip.alphabet[parity] - own)
    labels[name] = len(lines) + 1
    lines.extend(f"if {v} left" for v in crossable)
    lines.extend(f"if {v} left" for v in sorted(strip.alphabet[1 - parity]))
    lines.extend(f"if {v} goto @{name}" for v in crossable)
