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

    BrainIf reads its inputs from the far cell back toward the answer, so a
    branch steps *left* onto the next input.  There is no rightward mirror:
    the build walks out over zeroed cells before the tree runs, and every
    branch after that walks down, so one direction is all the tree needs.
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
    BrainIf, and a climb of ``if v increment`` lines converges -- every
    entry value 0..47 leaves it holding 48 -- so one climb cannot serve both
    digits however it is entered.  Two climbs is 48 + 49 lines, which used
    to dominate: a ``11110000`` program was 97 increments out of 153 lines.

    Building first also fixes which way the tape runs.  The pointer steps
    out over cells that are still zero, where one ``if 0 move right``
    advances exactly one cell -- no digit is around to fire the next line
    too -- and the tree then reads its inputs from that far cell back down
    toward the answer.  So a level is a read, two branch tests, and a step
    left, and a leaf is *there* already: the reads have carried the pointer
    home, and it adds one iff its entry is a ``1`` before joining a two-line
    tail.

    That is what makes the tree foldable.  A subtree whose rows all agree
    becomes a leaf rather than branching on bits that cannot change the
    answer -- and since a leaf spends no moves getting to the answer, the
    saving is not handed back.  The skipped levels' *reads* still happen:
    consumption must not depend on the table, or a caller feeding several
    programs from one stream would desync.  An earlier arrangement built the
    answer past the inputs and had each leaf walk out to it, which cost two
    lines per skipped level and cancelled the fold exactly.
    """
    n = _validate_truth_table(truth_table)
    if len(truth_table) > 16:
        return _brainif_linear(truth_table, width)
    # Initial zero skips the two-line output trampoline.  Leaves later return
    # with 48/49 to line 2, where one of the two guards forwards to the wide
    # output-tail address; that address is rendered twice instead of per leaf.
    entries: list[_Entry] = [
        _Cmd("if 0 goto 4"),
        _Cmd(f"if {_ASCII_ZERO} goto OUT0"),
        _Cmd(f"if {_ASCII_ONE} goto OUT0"),
    ]
    # The answer byte goes on cell 0 and the inputs above it, read from the
    # far end back down.  Building first means stepping out over cells that
    # are still zero, where one ``if 0 move right`` advances exactly one
    # cell -- no digit is around to fire the next line as well.
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
            # answer is a 1 and join the tail.  Reading them is not optional:
            # a program whose input count depended on its table would desync
            # a caller feeding several programs from one stream.
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
        # The interpreter recognizes commands by substring, so these are the
        # language's short spellings, not abbreviations invented by the
        # generator.  Line count is unchanged; the resolved goto targets stay
        # valid.
        lines = [
            line.replace("increment", "inc")
            .replace("move right", "right")
            .replace("move left", "left")
            for line in lines
        ]
    return "\n".join(lines)


def _brainif_linear(truth_table: str, width: int | None) -> str:
    """Emit a linear spatial lookup for BrainIf."""
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    labels: dict[str, int] = {}

    def emit(line: str) -> None:
        lines.append(line)

    def mark(name: str) -> None:
        labels[name] = len(lines) + 1

    # Scratch and output cells alternate.  Every output is initialized once;
    # the pointer then returns through the same O(T) strip.
    layout = "0" * n + truth_table
    for bit in layout:
        emit("if 0 move right")
        for value in range(_ASCII_ZERO):
            emit(f"if {value} increment")
        if bit == "1":
            emit(f"if {_ASCII_ZERO} increment")
        emit(f"if {_ASCII_ZERO} move right")
        emit(f"if {_ASCII_ONE} move right")
    for _ in layout:
        emit("if 0 move left")
        emit(f"if {_ASCII_ZERO} move left")
        emit(f"if {_ASCII_ONE} move left")

    # Input is read at the current scratch cell.  A one walks its binary
    # weight in scratch/output pairs; a zero stays for the next read.
    for i in range(n):
        one = f"input_{i}_one"
        zero = f"input_{i}_zero"
        after = f"input_{i}_after"
        emit("if 0 input")
        emit(f"if {_ASCII_ONE} goto @{one}")
        emit(f"if {_ASCII_ZERO} goto @{zero}")
        mark(zero)
        emit(f"if {_ASCII_ZERO} move right")
        emit(f"if {_ASCII_ZERO} move right")
        emit(f"if {_ASCII_ONE} move right")
        emit(f"if 0 goto @{after}")
        mark(one)
        weight = 1 + (1 << (n - 1 - i))
        for step in range(weight):
            guard = _ASCII_ONE if step == 0 else 0
            emit(f"if {guard} move right")
            emit(f"if {_ASCII_ZERO} move right")
            emit(f"if {_ASCII_ONE} move right")
        mark(after)

    # Every route ends on a fresh zero scratch cell.
    emit("if 0 move right")
    emit(f"if {_ASCII_ZERO} output")
    emit(f"if {_ASCII_ONE} output")
    emit("")
    for i, line in enumerate(lines):
        if "goto @" in line:
            head, name = line.split("goto @")
            lines[i] = f"{head}goto {labels[name]}"
    if width is not None and any(len(line) > width for line in lines):
        lines = [
            line.replace("increment", "inc")
            .replace("move right", "right")
            .replace("move left", "left")
            for line in lines
        ]
    return "\n".join(lines)
