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


#: The two values a strip cell carries, standing in for ``'0'`` and ``'1'``.
#: Only the traversal guards read them before the end, so any distinct pair
#: does -- and the cheapest starts at the zero the cell already holds.
_STRIP_ZERO = 0
_STRIP_ONE = 1


def _brainif_linear(truth_table: str) -> str:
    """Emit a linear spatial lookup for BrainIf.

    Strip and scratch cells alternate, so a step is position-independent:
    three guarded moves cross one strip cell of either value.

    The strip carries 0 and 1, not ``'0'`` and ``'1'``.  BrainIf cannot
    write a constant -- a cell climbs by ``if v inc`` lines, one per value
    passed -- so an ASCII digit per cell was a 48-line climb an entry, the
    whole 915-character construction.  Only the final ``output`` cares what
    the bytes are, so the climb happens once, on the selected cell.  It is
    two climbs: they converge -- every value below 48 lands on 48 -- so that
    cell branches on its own value first.

    The pointer never walks the strip twice.  The build runs left to right
    and the *selection* right to left, from the far end, reading the index
    in complement: a ``1`` stays put and a ``0`` walks its weight.  Rewinding
    to the origin first was a third O(T) pass, three lines an entry, for
    nothing the walk could not do backwards.

    Commands take the language's short forms: the interpreter matches by
    substring and the wiki spells them this way, so the tree path's
    ``increment``/``move right`` are habit, not BrainIf's ask.
    """
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    labels: dict[str, int] = {}

    def mark(name: str) -> None:
        labels[name] = len(lines) + 1

    def cross(guard: int) -> None:
        """Step one scratch/strip pair left, entered on a cell holding ``guard``."""
        lines.append(f"if {guard} left")
        lines.append(f"if {_STRIP_ZERO} left")
        lines.append(f"if {_STRIP_ONE} left")

    # The table, then one padding pair per input for the walk to spend on
    # each read.  A ``0`` entry is two identical moves: the cell it leaves
    # behind is the zero it arrived at.
    for bit in truth_table + "0" * n:
        lines.append("if 0 right")
        if bit == "1":
            lines.append(f"if {_STRIP_ZERO} inc")
            lines.append(f"if {_STRIP_ONE} right")
        else:
            lines.append(f"if {_STRIP_ZERO} right")

    # Input is read at the current scratch cell, the build's far end.  Every
    # input spends one pair, so the reads land on distinct cells; a zero
    # spends its binary weight on top of that.  A walk's first step enters
    # on the byte just read, every later one on a zero.
    for i in range(n):
        far = f"input_{i}_far"
        after = f"input_{i}_after"
        lines.append("if 0 input")
        lines.append(f"if {_ASCII_ZERO} goto @{far}")
        cross(_ASCII_ONE)
        lines.append(f"if 0 goto @{after}")
        mark(far)
        for step in range(1 + (1 << (n - 1 - i))):
            cross(_ASCII_ZERO if step == 0 else 0)
        mark(after)

    # Every route ends one step right of the selected strip cell, which
    # holds 0 or 1 and has to print as a digit.
    lines.append("if 0 left")
    lines.append(f"if {_STRIP_ONE} goto @one_out")
    for value in range(_STRIP_ZERO, _ASCII_ZERO):
        lines.append(f"if {value} inc")
    lines.append(f"if {_ASCII_ZERO} output")
    lines.append(f"if {_ASCII_ZERO} goto @done")
    mark("one_out")
    for value in range(_STRIP_ONE, _ASCII_ONE):
        lines.append(f"if {value} inc")
    lines.append(f"if {_ASCII_ONE} output")
    mark("done")
    lines.append("")
    for i, line in enumerate(lines):
        if "goto @" in line:
            head, name = line.split("goto @")
            lines[i] = f"{head}goto {labels[name]}"
    return "\n".join(lines)
