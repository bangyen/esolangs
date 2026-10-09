"""Boolean-function generator for BrainIf."""

from dataclasses import dataclass

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    input_weights,
    read_at,
)
from esolangs.tools.wrap import balance_score


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
class _GotoOut:
    """An ``if <char> goto`` line aimed at the marker ``OUT<which>``."""

    char: int
    which: int


@dataclass
class _Out:
    """A marker naming the next line ``OUT<which>``; it emits no line itself.

    ``OUT0`` is the output tail; the rest are spans a later equal span jumps to.
    """

    which: int


@dataclass
class _End:
    """The trailing blank line every program ends on."""


_Entry = _Cmd | _If | _MoveLeft | _GotoOut | _Out | _End


#: The most levels the tree may branch on before the linear lookup takes
#: over.  An ignored level only reads, so a wide table that depends on at most
#: this many inputs stays a tree however many it reads.
_TREE_LEVELS = 4


def brainif(truth_table: str, width: int | None = None) -> str:
    """Build BrainIf, reading each input in order.

    The residual DAG reuses one input cell and shares equal cofactors.
    It cuts the three-input total from 319,576 to 291,524 characters and
    steps from 134,984 to 74,440, with no table growing or slowing.
    Width requests retain the tree/spatial construction.
    """
    if width is not None:
        plain = _brainif_tree(truth_table, width)
        n = _validate_truth_table(truth_table)
        if n <= 2 and max(map(len, plain.splitlines())) > width:
            # Two-digit output jumps overflow a narrow width; zero jumps are shorter.
            return _brainif_zero_jumps(truth_table)
        return plain
    return _brainif_dag(truth_table)


def _brainif_zero_jumps(table: str) -> str:
    """Route small trees through unread zero cells before each branch jump."""
    n = _validate_truth_table(table)
    lines: list[str] = []
    labels: dict[str, int] = {}

    def mark(label: str) -> None:
        labels[label] = len(lines) + 1

    # Cell0 stays zero for the output escape; cell1 holds 48, cell2 is
    # the final zero landing, and input cells lie above it. Two-input
    # addresses fit two digits; larger arities retain the scalable build
    # rather than O(T log T) jump text.
    lines.extend(["if 0 right", "if 0 goto @init"])
    mark("zero")
    lines.extend(["if 0 left", "if 48 output", "if 48 left", "if 0 goto @done"])
    mark("one")
    lines.extend(
        [
            "if 0 left",
            "if 48 inc",
            "if 49 output",
            "if 49 left",
            "if 0 goto @done",
        ]
    )
    mark("init")
    lines.extend(f"if {value} inc" for value in range(48))
    lines.append("if 48 right")
    lines.extend("if 0 right" for _ in range(n))

    def tree(start: int, end: int, depth: int) -> None:
        if depth == n:
            lines.append("if 0 goto @" + ("one" if table[start] == "1" else "zero"))
            return
        # A one moves onto the unread zero cell below it before jumping;
        # a zero stays on its input until the ordinary left step.
        label = f"branch_{start}_{end}"
        lines.extend(["if 0 input", "if 49 left", f"if 0 goto @{label}", "if 48 left"])
        middle = (start + end) // 2
        tree(start, middle, depth + 1)
        mark(label)
        tree(middle, end, depth + 1)

    tree(0, len(table), 0)
    mark("done")
    lines.append("")
    return "\n".join(
        line.split("@")[0] + str(labels[line.split("@")[1]]) if "@" in line else line
        for line in lines
    )


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
    """Emit every ordered read, discarding the prior bit before the next.

    An ignored input with an essential one after it has no layer: each node
    of that next layer reads it first and discards it, two lines a node
    against a layer of four-line nodes.  Trailing ones keep their layers,
    which are at most two nodes wide.
    """
    n = _validate_truth_table(table)
    essential = essential_inputs(table, n)
    last = essential[-1] if essential else -1
    kept = [i for i in range(n) if i in essential or i > last]
    layers = _residual_layers(read_at(table, kept, n))
    # Layer ``depth`` reads kept input ``kept[-1 - depth]``, after the
    # dropped ones between it and the kept input before it.
    skips = [b - a - 1 for a, b in zip([-1, *kept], kept, strict=False)][::-1]
    lines: list[str] = []
    addresses: dict[tuple[int, int], int] = {}

    def reads(depth: int) -> list[str]:
        """Read every input this layer owns, ending on its own bit."""
        first = (
            ["if 0 input"]
            if depth == len(layers) - 1
            else ["if 48 increment", "if 49 input"]
        )
        return first + ["if 48 increment", "if 49 input"] * skips[depth]

    for depth in reversed(range(len(layers))):
        for node in range(len(layers[depth])):
            addresses[depth, node] = len(lines) + 1
            lines.extend([""] * (len(reads(depth)) + 2))
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
            block = reads(depth)
            block.extend([f"if 48 goto {children[0]}", f"if 49 goto {children[1]}"])
            start = addresses[depth, node] - 1
            lines[start : start + len(block)] = block
    return "\n".join(lines)


def _brainif_tree_entries(truth_table: str, n: int, *, prune: bool) -> list[_Entry]:
    """Emit symbolic tree entries with one shared output tail."""
    # Initial zero skips the two-line output trampoline.  Leaves return with
    # 48/49 to line 2, whose guards forward to the wide output-tail address,
    # rendered twice rather than once per leaf.
    entries: list[_Entry] = [
        _Cmd("if 0 goto 4"),
        _GotoOut(_ASCII_ZERO, 0),
        _GotoOut(_ASCII_ONE, 0),
    ]
    # The answer byte goes on cell 0 and the inputs above it, read from the
    # far end back down.
    entries += [_Cmd(f"if {v} increment") for v in range(_ASCII_ZERO)]
    entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
    entries += [_Cmd("if 0 move right") for _ in range(n - 1)]

    next_label = 0
    shared: dict[tuple[int, str], int] = {}

    def build(lo: int, hi: int, k: int) -> list[_Entry]:
        """Emit a table span, entered with the pointer on cell n-k+1."""
        rest = n - (k - 1)
        span = (k, truth_table[lo:hi])
        # Entered on an unread cell (0), or on the answer byte (48) once
        # every input is read, so one guarded jump reuses an equal span.
        if prune and span in shared:
            return [_GotoOut(_ASCII_ZERO if rest == 0 else 0, shared[span])]
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
        nonlocal next_label
        l0, l1 = next_label, next_label + 1
        next_label += 2
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

    return entries


def _brainif_resolve(entries: list[_Entry], width: int | None) -> str:
    """Resolve symbolic addresses and shorten commands when a width requires it."""
    # ``_Out`` markers emit no line: each targets the next line that does.
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
            lines.append(entry.text)
        elif isinstance(entry, _GotoOut):
            # A leaf reaches the tail holding 48 or 49: one goto for each.
            lines.append(f"if {entry.char} goto {out_labels[entry.which]}")
        elif isinstance(entry, _If):
            lines.append(f"if {entry.char} goto {labels[entry.label]}")
        elif isinstance(entry, _MoveLeft):
            lines.append(f"if {entry.char} move left")
        elif isinstance(entry, _Out):
            continue
        else:
            # _End, the trailing blank line.  The fallback rather than an
            # ``isinstance``, so an ``_Entry`` variant without a branch here
            # is a type error: mypy narrows this to ``_End``.
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


def _brainif_tree(truth_table: str, width: int | None, *, prune: bool = True) -> str:
    """Build the tree/spatial candidate computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    BrainIf reads each input into a cell with ``if 0 input``; a recursive
    decision tree checks each cell with ``if 49 goto``, zero falling through
    to its subtree.  The answer byte is built first on cell 0 (48
    ``increment`` lines once; a climb converges, so one cannot serve both
    digits), the tape grows outward over zero cells, and the tree reads
    from the far cell back down.  A level whose halves agree is read and
    stepped past untested, so every read still happens; equal spans at one
    level share code via one guarded ``goto``.  A wide table stays a tree
    while it branches on at most :data:`_TREE_LEVELS` inputs.
    """
    n = _validate_truth_table(truth_table)
    # Equal halves skip exactly the nonessential inputs. Decide before
    # allocating entries; the unpruned tree retains its arity cutoff.
    if (len(essential_inputs(truth_table, n)) if prune else n) > _TREE_LEVELS:
        if prune:
            weights, projected = input_weights(truth_table, n)
            return _brainif_linear(projected, weights)
        return _brainif_linear(truth_table)
    entries = _brainif_tree_entries(truth_table, n, prune=prune)
    return _brainif_resolve(entries, width)


#: Levels whose walk becomes a marker-terminated ``goto`` loop instead of
#: ``2**(n-i)`` emitted ``left`` lines.  Measured over n=8..12: four is where
#: the per-entry constant bottoms out at 25.4 (three reads 25.8, five 25.5).
_LOOP_LEVELS = 4


def _top_level(n: int) -> int:
    """Return the deepest level that may loop, for an ``n``-input table.

    Levels ``i < j`` share a marker position exactly when ``j - i ==
    2**(n-1-j)``, and ``m_i = 2**(n-1-i)`` must be even for a two-cell loop
    iteration.  Halving the arity clears both at once: ``top <= (n-2)/2``
    leaves ``2**(n-1-top) >= 2**(n/2)``, which outgrows ``top``.  ``n`` counts
    the essential inputs; :class:`_Strip` re-checks the pairs once ignored ones
    sit between the levels.
    """
    return min(_LOOP_LEVELS, (n - 2) // 2)


class _Strip:
    """The strip's cell values, and what a guard at a given class may see.

    A cell holds ``2 * (position % 2) + bit``; the parity keeps a two-line
    step from firing twice.  A *marker* cell holds its level's value plus the
    bit instead, which is what stops that level's loop.
    """

    def __init__(self, cells: str, weights: list[int]) -> None:
        """Place the markers and fix the alphabet; ``weights[i]`` is ``m_i``.

        An ignored input weighs 0 and only steps the pointer.  Levels ``i < j``
        share a marker cell exactly when ``(j - i) % (2 * m_j) == m_j``; the
        looped levels are the widest ones up to the first such pair.
        """
        self.cells = cells
        size = len(cells)
        essential = [i for i, w in enumerate(weights) if w]
        self.levels: list[int] = []
        for i in essential[: _top_level(len(essential)) + 1]:
            if any((i - j) % (2 * weights[i]) == weights[i] for j in self.levels):
                break
            self.levels.append(i)
        #: ``2 * m_i``: the period of level ``i``'s marker class.
        self.period = {i: 2 * weights[i] for i in self.levels}
        #: Level ``i``'s walk starts at ``size - 2 - i`` (mod its period) and
        #: ends ``m_i`` cells left of it, which is where its marker goes.
        self.first = {
            i: (size - 2 - i - weights[i]) % self.period[i] for i in self.levels
        }
        # The deepest looped level has the most markers, so it takes the
        # cheapest value: a climb to v costs v lines, once per marker.
        top = len(self.levels) - 1
        self.value = {i: 4 + 2 * (top - rank) for rank, i in enumerate(self.levels)}
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
        if modulus == 1:
            # Past the weight-1 level an ignored read's parity is unknown.
            return sorted(self.alphabet[0] | self.alphabet[1])
        parity = residue % 2
        out = {2 * parity, 2 * parity + 1}
        for i in self.levels:
            if self.first[i] % 2 != parity:
                continue
            coarse = min(modulus, self.period[i])
            if self.first[i] % coarse == residue % coarse:
                out |= {self.value[i], self.value[i] + 1}
        return sorted(out)


def _brainif_linear(truth_table: str, weights: list[int] | None = None) -> str:
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

    ``weights`` gives each input's row weight (see
    :func:`~esolangs.tools.helpers.input_weights`); an ignored input, weight 0,
    is read and stepped past, and ``truth_table`` is then its projection.
    The default is every input essential.
    """
    n = len(weights) if weights else _validate_truth_table(truth_table)
    weights = weights or [1 << (n - 1 - i) for i in range(n)]
    cells = truth_table + "0" * n
    size = len(cells)
    strip = _Strip(cells, weights)
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
        # Every higher bit moves the pointer a multiple of the smallest
        # higher weight, so the read cell's class is known modulo it.
        known = next((w for w in reversed(weights[:i]) if w), None)
        guard(size - 1 - i, known, "input")
        if not weights[i]:
            lines.append(f"if {_ASCII_ZERO} left")
            lines.append(f"if {_ASCII_ONE} left")
            continue
        lines.append(f"if {_ASCII_ZERO} goto @{far}")
        lines.append(f"if {_ASCII_ONE} left")
        guard(size - 2 - i, known, f"goto @{after}")
        mark(far)
        lines.append(f"if {_ASCII_ZERO} left")
        if i in strip.levels:
            _emit_loop(lines, labels, strip, i, size)
        else:
            for k in range(weights[i]):
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


def _balance(table: str, default: str) -> str:
    """Compare the DAG, full tree, short spellings and small zero-jump tree."""
    wide = _brainif_tree(table, None)
    short = brainif(table, max(1, grid_width(wide) - 1))
    return min(default, wide, short, brainif(table, 1), key=balance_score)


LANGUAGE = Language(
    "BrainIf",
    "tape_based.brainif",
    boolean=brainif,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    no_wrap="each line is one instruction and goto targets are line numbers",
)
