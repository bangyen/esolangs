"""Boolean-function generator for BrainIf."""

from dataclasses import dataclass

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
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
    """A marker naming the next line ``OUT<which>``; it emits no line itself.

    ``OUT0`` is the output tail; the rest are spans a later equal span jumps to.
    """

    which: int


@dataclass
class _End:
    """The trailing blank line every program ends on."""


_Entry = _Cmd | _If | _MoveLeft | _Out | _End


#: The most levels the tree may branch on before the linear lookup takes
#: over.  An ignored level only reads, so a wide table that depends on at most
#: this many inputs stays a tree however many it reads.
_TREE_LEVELS = 4


class _TooWideError(Exception):
    """The tree reached a fifth branching level; build the linear lookup."""


def brainif(truth_table: str, width: int | None = None) -> str:
    """Choose the shorter BrainIf candidate, reading each input in order.

    The residual DAG reuses one input cell and shares equal cofactors.
    It cuts the three-input total from 319,576 to 292,492 characters and
    steps from 134,984 to 74,752, with no table growing or slowing.
    Width requests retain the tree/spatial construction.
    """
    plain = _brainif_tree(truth_table, width)
    if width is not None:
        return plain
    dag = _brainif_dag(truth_table)
    return dag if len(dag) < len(plain) else plain


def _residual_layers(table: str) -> list[list[tuple[int, int]]]:
    """Return distinct cofactor pairs, bottom layer first; leaves are 0/1."""
    _validate_truth_table(table)
    values = [int(bit) for bit in table]
    layers = []
    while len(values) > 1:
        names: dict[tuple[int, int], int] = {}
        following = []
        for i in range(0, len(values), 2):
            pair = (values[i], values[i + 1])
            following.append(names.setdefault(pair, len(names)))
        layers.append(list(names))
        values = following
    return layers


def _brainif_dag(table: str) -> str:
    """Emit every ordered read, discarding the prior bit before the next."""
    layers = _residual_layers(table)
    lines: list[str] = []
    addresses: dict[tuple[int, int], int] = {}
    for depth in reversed(range(len(layers))):
        for node in range(len(layers[depth])):
            addresses[depth, node] = len(lines) + 1
            lines.extend([""] * (3 if depth == len(layers) - 1 else 4))
    outputs = [len(lines) + 1]
    lines.append("if 49 move right")
    lines.extend(f"if {i} increment" for i in range(48))
    lines.extend(["if 48 output", ""])
    outputs.append(len(lines) + 1)
    lines.extend(["if 48 increment", "if 49 output", ""])
    end = len(lines) + 1
    lines[outputs[1] - 2] = f"if 48 goto {end}"
    lines[-1] = f"if 49 goto {end}"
    for depth, layer in enumerate(layers):
        for node, (zero, one) in enumerate(layer):
            children = [
                addresses[depth - 1, child] if depth else outputs[child]
                for child in (zero, one)
            ]
            block = (
                ["if 0 input"]
                if depth == len(layers) - 1
                else ["if 48 increment", "if 49 input"]
            )
            block.extend([f"if 48 goto {children[0]}", f"if 49 goto {children[1]}"])
            start = addresses[depth, node] - 1
            lines[start : start + len(block)] = block
    return "\n".join(lines)


def _brainif_tree(truth_table: str, width: int | None, *, prune: bool = True) -> str:
    """Build the tree/spatial candidate computing the given truth table.

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

    That is what makes the tree foldable: a level whose halves agree is read
    and stepped past but not tested, as Line's tree skips it, so an ignored
    input costs its three reading lines.  Every read still happens, or a
    caller feeding several programs from one stream would desync.  Equal
    spans at one level run the same code from the same cell, so the second
    is one guarded ``goto`` to the first.  A wide table stays a tree while
    it branches on at most :data:`_TREE_LEVELS` inputs.
    """
    n = _validate_truth_table(truth_table)
    if not prune and n > _TREE_LEVELS:
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
    shared: dict[tuple[int, str], int] = {}
    branching: set[int] = set()

    def build(lo: int, hi: int, k: int) -> list[_Entry]:
        """Emit a table span, entered with the pointer on cell n-k+1."""
        rest = n - (k - 1)
        span = (k, truth_table[lo:hi])
        # Entered on an unread cell (0), or on the answer byte (48) once
        # every input is read, so one guarded jump reuses an equal span.
        if prune and span in shared:
            return [
                _Cmd(f"if {_ASCII_ZERO if rest == 0 else 0} goto OUT{shared[span]}")
            ]
        body = _span(lo, hi, k, rest)
        if prune and len(body) > 1:
            shared[span] = len(shared) + 1
            body.insert(0, _Out(shared[span]))
        return body

    def _span(lo: int, hi: int, k: int, rest: int) -> list[_Entry]:
        if rest == 0:
            # The answer byte is 48: add one iff the entry is a 1 and join
            # the trampoline line whose guard that byte passes.
            if truth_table[lo] == "0":
                return [_Cmd(f"if {_ASCII_ZERO} goto 2")]
            return [
                _Cmd(f"if {_ASCII_ZERO} increment"),
                _Cmd(f"if {_ASCII_ONE} goto 3"),
            ]
        middle = (lo + hi) // 2
        if truth_table[lo:middle] == truth_table[middle:hi] and (
            prune or truth_table[lo:hi] == truth_table[lo] * (hi - lo)
        ):
            # The halves agree, so this input cannot change the answer: read
            # it, step past it and build the one half both values share.
            return [
                _Cmd("if 0 input"),
                _Cmd(f"if {_ASCII_ZERO} move left"),
                _Cmd(f"if {_ASCII_ONE} move left"),
                *build(lo, middle, k + 1),
            ]
        # Level ``k`` reads input ``k - 1`` into cell ``n - k + 1``, so the
        # bit it selects is the table's usual most-significant-first one --
        # the reads are in input order even though the pointer walks down.
        branching.add(k)
        if len(branching) > _TREE_LEVELS:
            raise _TooWideError
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

    try:
        entries += build(0, len(truth_table), 1)
    except _TooWideError:
        return _brainif_linear(truth_table)
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
    for entry in entries:
        if isinstance(entry, _Out):
            out_labels[entry.which] = line_no + 1
            continue
        line_no += 1
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
