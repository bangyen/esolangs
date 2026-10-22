"""BrainIf Boolean program generator: guarded gotos over input cells.

Each input is read with ``if 0 input`` and tested with ``if 49 goto``.  Up to
four essential inputs the residual DAG shares equal cofactors; beyond that a
linear spatial lookup stores the table one cell an entry and walks to the
selected one, its widest levels by loop.  Width requests keep the tree.

Size:
    O(T) lines for the lookup; n=10 parity: 1,893 chars, n=10 random 1847:
    14,671 chars.

Decisions:
    The residual DAG cuts the three-input total from 319,576 to 291,524
    characters and steps from 134,984 to 74,440.  The looped levels follow
    a cost model (:func:`_top_level`), not a fixed count.
"""

from collections.abc import Iterable
from itertools import count, pairwise

from esolangs.generation.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    input_weights,
    read_at,
)
from esolangs.languages.brainif.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _resolve(lines: list[str], width: int | None = None) -> str:
    """Resolve zero-width ``@label`` markers and shorten commands for width."""
    labels: dict[str, int] = {}
    emitted: list[str] = []
    for line in lines:
        if line.startswith("@"):
            labels[line[1:]] = len(emitted) + 1
        else:
            emitted.append(line)
    for i, line in enumerate(emitted):
        if "goto @" in line:
            head, label = line.split("goto @")
            emitted[i] = f"{head}goto {labels[label]}"
    if width is not None and any(len(line) > width for line in emitted):
        emitted = [
            line.replace("increment", "inc")
            .replace("move right", "right")
            .replace("move left", "left")
            for line in emitted
        ]
    return "\n".join(emitted)


class _Lines:
    """BrainIf lines under construction, with zero-width label markers."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def mark(self, name: str) -> None:
        """Append the zero-width marker ``@name``."""
        self.lines.append(f"@{name}")

    def add(self, line: str) -> None:
        """Append one instruction line."""
        self.lines.append(line)

    def extend(self, lines: Iterable[str]) -> None:
        """Append instruction lines in order."""
        self.lines.extend(lines)


#: The most levels the tree branches on before the linear lookup joins it.
#: An ignored level only reads, so a wide table that depends on at most this
#: many inputs stays a tree however many it reads.
_TREE_LEVELS = 4


def brainif(truth_table: str, width: int | None = None) -> str:
    """Build BrainIf, reading each input in order.

    The residual DAG reuses one input cell and shares equal cofactors, with
    no table growing or slowing.  Width requests retain the tree/spatial
    construction.
    """
    if width is not None:
        plain = _brainif_tree(truth_table, width)
        n = _validate_truth_table(truth_table)
        if len(essential_inputs(truth_table, n)) > _TREE_LEVELS:
            # The lookup is the narrow fallback; where the tree fits it is
            # 25-59% shorter at n=3..14 ([ablations.wide_tree_race]).
            tree = _resolve(_brainif_tree_entries(truth_table, n, prune=True), width)
            if grid_width(tree) <= width and len(tree) < len(plain):
                return tree
        if n <= 2 and grid_width(plain) > width:
            # Two-digit output jumps overflow a narrow width; zero jumps are shorter.
            return _brainif_zero_jumps(truth_table)
        return plain
    return _brainif_dag(truth_table)


def _climb(verb: str) -> list[str]:
    """Return the lines that raise a zero cell to the byte ``'0'``."""
    return [f"if {value} {verb}" for value in range(_ASCII_ZERO)]


def _zero_jump_tree(
    out: _Lines, table: str, n: int, start: int, end: int, depth: int
) -> None:
    """Emit one zero-jump tree node and, recursively, its two subtrees."""
    if depth == n:
        out.add("if 0 goto @" + ("one" if table[start] == "1" else "zero"))
        return
    # A one moves onto the unread zero cell below it before jumping;
    # a zero stays on its input until the ordinary left step.
    label = f"branch_{start}_{end}"
    out.extend(
        [
            "if 0 input",
            f"if {_ASCII_ONE} left",
            f"if 0 goto @{label}",
            f"if {_ASCII_ZERO} left",
        ]
    )
    middle = (start + end) // 2
    _zero_jump_tree(out, table, n, start, middle, depth + 1)
    out.mark(label)
    _zero_jump_tree(out, table, n, middle, end, depth + 1)


def _brainif_zero_jumps(table: str) -> str:
    """Route small trees through unread zero cells before each branch jump."""
    n = _validate_truth_table(table)
    out = _Lines()

    # Cell0 stays zero for the output escape; cell1 holds 48, cell2 is
    # the final zero landing, and input cells lie above it. Two-input
    # addresses fit two digits; larger arities retain the scalable build
    # rather than O(T log T) jump text.
    out.extend(["if 0 right", "if 0 goto @init"])
    out.mark("zero")
    out.extend(
        [
            "if 0 left",
            f"if {_ASCII_ZERO} output",
            f"if {_ASCII_ZERO} left",
            "if 0 goto @done",
        ]
    )
    out.mark("one")
    out.extend(
        [
            "if 0 left",
            f"if {_ASCII_ZERO} inc",
            f"if {_ASCII_ONE} output",
            f"if {_ASCII_ONE} left",
            "if 0 goto @done",
        ]
    )
    out.mark("init")
    out.extend(_climb("inc"))
    out.add(f"if {_ASCII_ZERO} right")
    out.extend("if 0 right" for _ in range(n))

    _zero_jump_tree(out, table, n, 0, len(table), 0)
    out.mark("done")
    out.add("")
    return _resolve(out.lines)


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
    skips = [b - a - 1 for a, b in pairwise([-1, *kept])][::-1]
    lines: list[str] = []
    for depth in reversed(range(len(layers))):
        pair = [f"if {_ASCII_ZERO} increment", f"if {_ASCII_ONE} input"]
        first = ["if 0 input"] if depth == len(layers) - 1 else pair
        reads = first + pair * skips[depth]
        for node, children in enumerate(layers[depth]):
            lines.append(f"@node_{depth}_{node}")
            lines.extend(reads)
            for char, child in zip((_ASCII_ZERO, _ASCII_ONE), children, strict=True):
                target = f"node_{depth - 1}_{child}" if depth else f"out_{child}"
                lines.append(f"if {char} goto @{target}")
    lines.extend(["@out_0", f"if {_ASCII_ONE} move right"])
    lines.extend(_climb("increment"))
    lines.extend(
        [
            f"if {_ASCII_ZERO} output",
            f"if {_ASCII_ZERO} goto @done",
            "@out_1",
            f"if {_ASCII_ZERO} increment",
            f"if {_ASCII_ONE} output",
            f"if {_ASCII_ONE} goto @done",
            "@done",
        ]
    )
    return _resolve(lines)


class _SpanBuilder:
    """Recursive tree spans for one table, sharing equal spans at a level.

    ``shared`` maps each span already emitted at a level to its label
    number, assigned in first-emission order; ``labels`` numbers the
    branch labels in the order spans split.
    """

    def __init__(self, truth_table: str, n: int, *, prune: bool) -> None:
        self.truth_table = truth_table
        self.n = n
        self.prune = prune
        self.labels = count()
        self.shared: dict[tuple[int, str], int] = {}

    def build(self, lo: int, hi: int, k: int) -> list[str]:
        """Emit a table span, entered with the pointer on cell n-k+1."""
        rest = self.n - (k - 1)
        span = (k, self.truth_table[lo:hi])
        # Entered on an unread cell (0), or on the answer byte (48) once
        # every input is read, so one guarded jump reuses an equal span.
        if self.prune and span in self.shared:
            return [
                f"if {_ASCII_ZERO if rest == 0 else 0} goto @out_{self.shared[span]}"
            ]
        body = self.span(lo, hi, k, rest)
        if self.prune and len(body) > 1:
            self.shared[span] = len(self.shared) + 1
            body.insert(0, f"@out_{self.shared[span]}")
        return body

    def span(self, lo: int, hi: int, k: int, rest: int) -> list[str]:
        """Emit one span's own lines, before any shared-label prefix."""
        if rest == 0:
            # The answer byte is 48: add one iff the entry is a 1 and join
            # the trampoline line whose guard that byte passes.
            if self.truth_table[lo] == "0":
                return [f"if {_ASCII_ZERO} goto 2"]
            return [
                f"if {_ASCII_ZERO} increment",
                f"if {_ASCII_ONE} goto 3",
            ]
        middle = (lo + hi) // 2
        if self.truth_table[lo:middle] == self.truth_table[middle:hi] and (
            self.prune or self.truth_table[lo:hi] == self.truth_table[lo] * (hi - lo)
        ):
            # The halves agree, so this input cannot change the answer: read
            # it, step past it and build the one half both values share.
            return [
                "if 0 input",
                f"if {_ASCII_ZERO} move left",
                f"if {_ASCII_ONE} move left",
                *self.build(lo, middle, k + 1),
            ]
        # Level ``k`` reads input ``k - 1`` into cell ``n - k + 1``, so the
        # bit it selects is the table's usual most-significant-first one --
        # the reads are in input order even though the pointer walks down.
        label = next(self.labels)
        sub0 = self.build(lo, middle, k + 1)
        sub1 = self.build(middle, hi, k + 1)
        return [
            "if 0 input",
            f"if {_ASCII_ONE} goto @branch_{label}",
            f"if {_ASCII_ZERO} move left",
            *sub0,
            f"@branch_{label}",
            f"if {_ASCII_ONE} move left",
            *sub1,
        ]


def _brainif_tree_entries(truth_table: str, n: int, *, prune: bool) -> list[str]:
    """Emit symbolic tree entries with one shared output tail."""
    # Initial zero skips the two-line output trampoline.  Leaves return with
    # 48/49 to line 2, whose guards forward to the wide output-tail address,
    # rendered twice rather than once per leaf.
    entries: list[str] = [
        "if 0 goto 4",
        f"if {_ASCII_ZERO} goto @out_0",
        f"if {_ASCII_ONE} goto @out_0",
    ]
    # The answer byte goes on cell 0 and the inputs above it, read from the
    # far end back down.
    entries += _climb("increment")
    entries.append(f"if {_ASCII_ZERO} move right")
    entries += ["if 0 move right" for _ in range(n - 1)]

    entries += _SpanBuilder(truth_table, n, prune=prune).build(0, len(truth_table), 1)
    # One shared tail: the answer cell already holds the byte to print, so
    # this is two lines rather than a climb per digit.
    entries.append("@out_0")
    entries.append(f"if {_ASCII_ZERO} output")
    entries.append(f"if {_ASCII_ONE} output")
    entries.append("")

    return entries


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
    return _resolve(entries, width)


def _top_level(n: int) -> int:
    """Return the deepest level that loops, for an ``n``-input table.

    Cost model, in lines: adding level ``K`` (``K`` levels already looped)
    saves its walk, ``2**(n-K)`` guarded ``left`` lines, and costs a loop of
    about ``19 + 5K`` lines plus ``5 * 2**K - 2`` more marker-climb lines
    (rank ``r`` has ``2**r`` markers climbing ``3 + 2(K-1-r)`` extra each,
    summing to ``5 * 2**K - 2K - 5``).  Dropping the linear terms, it pays
    while ``2**(n-K) > 5 * 2**K``, i.e. ``K < (n - log2 5) / 2``, so the
    looped levels number ``(n - 1) // 2`` and the deepest is ``(n - 3) // 2``.
    Measured on seeded random tables the best top level is that at n=6, 8,
    10..14, and one lower at n=5, 7, 9 (0.9% to 3.6% smaller than the formula,
    hence the ``n < 10`` term); the old fixed cap of 4 was 2.3% to 7.6% larger
    at n=6, 8, 10 and 0.2% to 0.8% at n=13, 14.

    The cap also clears the pair condition: levels ``i < j`` share a marker
    position exactly when ``j - i == 2**(n-1-j)``, and ``m_i = 2**(n-1-i)``
    must be even for a two-cell loop iteration.  ``top <= (n-2)/2`` leaves
    ``2**(n-1-top) >= 2**(n/2)``, which outgrows ``top``, and ``(n-3)//2``
    stays under it.  ``n`` counts the essential inputs; :class:`_Strip`
    re-checks the pairs once ignored ones sit between the levels.
    """
    return max(0, (n - 3 - (n < 10)) // 2)


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


def _emit_guarded(
    out: _Lines, strip: _Strip, residue: int, modulus: int | None, suffix: str
) -> None:
    """Emit one guarded line per value the named cell may hold."""
    out.extend(f"if {v} {suffix}" for v in strip.seen(residue, modulus))


def _emit_strip_cells(out: _Lines, strip: _Strip, size: int) -> None:
    """Emit the strip: the table, then one padding cell per input."""
    # Padding takes the cheaper bit; the last cell needs no ``right``,
    # since the walk starts there.
    for index in range(size):
        value = strip.at(index)
        out.extend(f"if {passed} inc" for passed in range(value))
        if index + 1 < size:
            out.add(f"if {value} right")


def _emit_linear_read(
    out: _Lines, strip: _Strip, weights: list[int], size: int, i: int
) -> None:
    """Emit input ``i``'s read and the walk its zero branch takes."""
    far, after = f"far_{i}", f"after_{i}"
    # Every higher bit moves the pointer a multiple of the smallest
    # higher weight, so the read cell's class is known modulo it.
    known = next((w for w in reversed(weights[:i]) if w), None)
    _emit_guarded(out, strip, size - 1 - i, known, "input")
    if not weights[i]:
        out.add(f"if {_ASCII_ZERO} left")
        out.add(f"if {_ASCII_ONE} left")
        return
    out.add(f"if {_ASCII_ZERO} goto @{far}")
    out.add(f"if {_ASCII_ONE} left")
    _emit_guarded(out, strip, size - 2 - i, known, f"goto @{after}")
    out.mark(far)
    out.add(f"if {_ASCII_ZERO} left")
    if i in strip.levels:
        _emit_loop(out.lines, strip, i, size)
    else:
        for k in range(weights[i]):
            _emit_guarded(out, strip, size - 2 - i - k, known, "left")
    out.mark(after)


def _emit_linear_output(out: _Lines, strip: _Strip) -> None:
    """Emit the output tail for the selected cell the walk ends on."""
    # The selected cell's value is its bit in the low place -- every
    # marker value is even -- and the climbs converge, so neither the
    # branch nor the climb cares which class the cell came from.
    alphabet = strip.alphabet[0] | strip.alphabet[1]
    for value in sorted(v for v in alphabet if v % 2):
        out.add(f"if {value} goto @one_out")
    out.extend(_climb("inc"))
    out.add(f"if {_ASCII_ZERO} output")
    out.add(f"if {_ASCII_ZERO} goto @done")
    out.mark("one_out")
    for value in range(1, _ASCII_ONE):
        out.add(f"if {value} inc")
    out.add(f"if {_ASCII_ONE} output")
    out.mark("done")
    out.add("")


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
    widest levels are worth (:func:`_top_level`) -- level 0 alone is half
    the crossings and costs one marker.  Commands take the short spellings
    the interpreter matches by substring.

    ``weights`` gives each input's row weight (see
    :func:`~esolangs.generation.helpers.input_weights`); an ignored input, weight 0,
    is read and stepped past, and ``truth_table`` is then its projection.
    The default is every input essential.
    """
    n = len(weights) if weights else _validate_truth_table(truth_table)
    weights = weights or [1 << (n - 1 - i) for i in range(n)]
    cells = truth_table + "0" * n
    size = len(cells)
    strip = _Strip(cells, weights)
    out = _Lines()
    # Phase 1: lay out the strip cells the selection walk will cross.
    _emit_strip_cells(out, strip, size)
    # Phase 2: read each input and walk its weight on a zero.  A read
    # overwrites the cell it lands on, so its guard is every value that
    # cell's class admits; the first step off it is one line, not two,
    # because the byte just read says which branch is running.  The read
    # for level ``i`` sits at ``size - 1 - i`` mod ``2**(n-i)`` --
    # exactly, for level 0.
    for i in range(n):
        _emit_linear_read(out, strip, weights, size, i)
    # Phase 3: print the selected cell the walk ends on.
    _emit_linear_output(out, strip)
    return _resolve(out.lines)


def _emit_loop(lines: list[str], strip: _Strip, level: int, size: int) -> None:
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
    lines.append(f"@{name}")
    lines.extend(f"if {v} left" for v in crossable)
    lines.extend(f"if {v} left" for v in sorted(strip.alphabet[1 - parity]))
    lines.extend(f"if {v} goto @{name}" for v in crossable)


def _balance(_table: str, default: str) -> str:
    """Return the DAG; the full and small zero-jump trees never won (n=1..8)."""
    return default


LANGUAGE = Language(
    "BrainIf",
    "brainif",
    category="tape_based",
    boolean=brainif,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    no_wrap="each line is one instruction and goto targets are line numbers",
    proof_workspace=(workspace, True, (3, 6)),
)
