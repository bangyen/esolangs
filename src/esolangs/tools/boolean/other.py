"""Boolean-function generators for languages in the ``other`` category."""

# streetcode and ztoalc_l_boolean each own a file because their construction
# (a grid layout or a program search) dwarfs the rest of the category; they
# are re-exported here so this module stays the import site the package and
# tests already use.
from esolangs.tools import laserfuck_layout
from esolangs.tools.boolean.helpers import _maybe_complement, _validate_truth_table
from esolangs.tools.boolean.streetcode import streetcode
from esolangs.tools.boolean.ztoalc_l import ztoalc_l_boolean

__all__ = [
    "between",
    "bit_tilde",
    "clockwise",
    "container",
    "forbin_boolean",
    "laserfuck",
    "nevermind",
    "streetcode",
    "suptiftam",
    "taglate",
    "three_x",
    "ztoalc_l_boolean",
]

# Closed-form 3x constant encodings.  Every integer is built from the literal
# 3 with the ``x`` op (which replaces the top three items ``a, b, c``, c on
# top, with ``(c-b)//a``).  The three base-3 digits are:
_ZERO = "333x"  # (3-3)//3 = 0
_ONE = "3333x3x"  # (3-0)//3 = 1
_TWO = _ONE + _ONE + "3x"  # (3-1)//1 = 2

# From [v], ``push X # push Y x`` leaves [(Y-v)//X], so with X=-1/3 and
# Y=-d/3 it maps v -> (-d/3 - v)/(-1/3) = 3v + d.  These are the two fixed
# rationals (and the d=0 case, which is just 0):
_NEG_THIRD = "3" + _ONE + _ZERO + "x"  # (0-1)//3 = -1/3
_NEG_TWO_THIRDS = "33" + _ONE + "x"  # (1-3)//3 = -2/3
_DIGIT = (_ZERO, _ONE, _TWO)
_NEG_DIGIT = (_ZERO, _NEG_THIRD, _NEG_TWO_THIRDS)


def _const(n: int) -> str:
    """3x code pushing ``n`` on a clean stack, for any integer ``n``.

    ``n`` is written in base 3 and its digits are processed most significant
    first: ``v`` starts as the leading digit and each following digit ``d``
    applies the affine map ``v -> 3v + d`` via one ``x`` (see ``_NEG_THIRD``).
    The result is a closed-form program of ``O(log_3 n)`` length that leaves
    exactly ``[n]`` on the stack.
    """
    if n <= 2:
        return _DIGIT[n]
    digits = []
    while n:
        digits.append(n % 3)
        n //= 3
    prog = _DIGIT[digits[-1]]
    for d in reversed(digits[:-1]):
        prog += _NEG_THIRD + "#" + _NEG_DIGIT[d] + "x"
    return prog


def myscript(truth_table: str) -> str:
    """Build a MyScript program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program reads all ``n`` input lines up front into ``b0..b(n-1)``,
    then walks a ``check`` decision tree: at level ``i`` it branches on
    ``b_i`` and the leaves ``say`` the table value for the combination.
    """
    n = _validate_truth_table(truth_table)
    lines = [f"var b{i} is ask" for i in range(n)]

    def build(i: int, combo: int, pad: str) -> list[str]:
        if i == n:
            return [f'{pad}say "{truth_table[combo]}"']
        one = build(i + 1, combo | (1 << (n - 1 - i)), pad + "    ")
        zero = build(i + 1, combo, pad + "    ")
        return [
            f"{pad}check b{i}?",
            f'{pad}  if "1",',
            *one,
            f"{pad}  else,",
            *zero,
        ]

    return "\n".join(lines + build(0, 0, ""))


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    3x reads an integer with ``?`` and has no direct boolean literals or
    conditionals, so the generator builds a decision tree with variables:

    - each ``?`` reads one input bit and stores it in a variable (the
      cheapest names after 0 and 3);
    - a ``( ... )`` loop runs while its guard is nonzero: the guard value is
      popped into a trash variable (0), the body stores the table entry into
      the result variable (3), and a sentinel zero exits the loop.

    The result variable defaults to the majority table value (so the
    ``( ... )`` loop emits no override at all when every row matches), and
    only the input combinations whose table entry differs from the default
    get an override block.  Each override's ``( ... )`` guard leaves the
    stack balanced via the trash pop, so arbitrary ``n`` works.
    """
    n = _validate_truth_table(truth_table)

    # Variable allocation: var 0 is the loop-trash (its constant, 333x, is
    # short and emitted twice per guard), var 3 is the result (its constant
    # is the single char `3`, emitted once per table entry), and the inputs
    # live in the cheapest remaining names by actual constant length (the
    # base-3 encodings are non-monotonic: 15 is cheaper than 13).  Every
    # input is read once per override block, so any assignment of the n
    # cheapest names to the inputs costs the same.
    trash = _const(0) + "#v"  # pop the stack top into variable 0
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends empty

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b]

    def guard(i: int, body: str) -> str:
        """If bit i is 1, run ``body``; leaves the stack balanced."""
        return read(i) + "(" + trash + body + _ZERO + ")" + trash

    def guard_not(i: int, body: str) -> str:
        """If bit i is 0, run ``body``; leaves the stack balanced."""
        return read(i) + not_bit() + "(" + trash + body + _ZERO + ")" + trash

    prog = "".join("?" + store(v) for v in input_vars)

    # Default the result to the majority value so only the minority rows
    # need an override block (combos matching the default are skipped).
    default = "1" if truth_table.count("1") >= truth_table.count("0") else "0"
    prog += (_ONE if default == "1" else _ZERO) + store(result)

    # One decision tree instead of an independent guard chain per differing
    # combo: rows that share a bit prefix share the guards for that prefix,
    # amortizing the ~19-char guard scaffolding across them.  Each guard
    # leaves the stack balanced, so both branches concatenate safely inside
    # their parent's body, and whole subtrees that match the default are
    # pruned.
    def override(combo: int) -> str:
        return (_ONE if truth_table[combo] == "1" else _ZERO) + store(result)

    def build(rows: list[int], depth: int) -> str:
        if not rows:
            return ""
        if depth == n:
            return override(rows[0])  # rows are pruned, so it differs from default
        bit = n - 1 - depth
        rows1 = [r for r in rows if (r >> bit) & 1]
        rows0 = [r for r in rows if not (r >> bit) & 1]
        sub1 = build(rows1, depth + 1)
        sub0 = build(rows0, depth + 1)
        return (guard(input_vars[depth], sub1) if sub1 else "") + (
            guard_not(input_vars[depth], sub0) if sub0 else ""
        )

    differing = [c for c in range(2**n) if truth_table[c] != default]
    prog += build(differing, 0)

    prog += read(result) + "!"
    return prog


def nevermind(truth_table: str) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def build(k: int, row: int) -> None:
        indent = "  " * k
        if k == n:
            lines.append(f"{indent}print,{truth_table[row]}")
            return
        for bit in (0, 1):
            lines.append(f"{indent}if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append(f"{indent}endif")

    build(0, 0)
    return "\n".join(lines)


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries into the slot order the reduces expect.

    Each entry sits in a value slot ``[0, s_i, 0, s_j, ...]``; an even
    reduce must be able to drop an entire contiguous run of slots without
    splitting a pair.  Sorting the input index ``i`` by ``(-(i >> 1),
    i & 1)`` puts the 1-group of the current input first, then the 0-group,
    with the two sub-cases of the next input adjacent inside each group.
    Odd-reduce levels (which branch the other way) then re-apply the same
    ordering, so the sort key serves both.
    """
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two 48s, then the ``n`` input chars.  The ``rot`` rotation brings the
    next input to the front; ``gy ... gz`` branches on it so the ``e^pairs``
    strides past the half of the value slots the input rejects; ``e^ahead``
    skips the untouched half and ``f^pairs`` drops it.  Every input stays on
    the queue, so the level that follows still sees all ``n`` of them.
    """
    processed = level
    ahead = n - level
    total = n
    rot = 2 * pairs + 2 + processed
    return (
        "e" * rot
        + "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )


# Final odd-reduce block: the committed n==2 pattern.  Given the 8-cell
# queue [0, v0, 0, v1, 48, 48, prev, curr] (v0/v1 the two candidate values,
# prev/curr the two remaining inputs), it rotates curr and prev to the front,
# drops the candidate the inputs reject, adds the surviving value to one of
# the two 48s (48 + bit), and prints it with ``i``.
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _build_padded_tt(truth_table: str, n_effective: int) -> str:
    """Pad a ``2**(n_effective - 1)``-entry truth table to ``n_effective`` bits.

    Odd ``n`` is computed with ``n_effective = n + 1`` inputs whose leading
    (ghost) digit is always 0.  The real table covers the ghost=0 half; the
    entries the ghost=1 would select are padded with 0 so the never-taken
    rows stay harmless.
    """
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def between(truth_table: str) -> str:
    """Build a Between program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program reads each input bit as a line, converts it to an integer
    with ``c``, then walks a decision tree laid out linearly: every node
    tests bit ``i`` and, when the bit is zero, jumps over the ``1`` subtree
    to the ``0`` subtree; each leaf prints ``|0|``/``|1|`` and exits.  The
    branch addresses are 0-indexed line numbers, so the size of each subtree
    is computed ahead of the linear layout.
    """
    n = _validate_truth_table(truth_table)

    def leaf_value(path: list[int]) -> int:
        row = 0
        for bit in path:
            row = row * 2 + bit
        return int(truth_table[row])

    def size(path: list[int]) -> int:
        if len(path) == n:
            return 2
        return 1 + size([*path, 1]) + size([*path, 0])

    lines: list[str] = []
    for bit in range(n):
        lines.append(f"'{bit}'v.")
        lines.append(f"[{bit}]i.")
        lines.append(f"[{bit}]s|[{bit}]c.|")

    def emit(path: list[int], offset: int) -> int:
        if len(path) == n:
            lines.append(f"|{leaf_value(path)}|p.")
            lines.append(".x.")
            return offset + 2
        zero_addr = offset + 1 + size([*path, 1])
        lines.append(f"|{zero_addr}|f([{len(path)}]=|0|)")
        offset += 1
        offset = emit([*path, 1], offset)
        return emit([*path, 0], offset)

    emit([], len(lines))
    return "\n".join(lines)


# The two loops that normalize the input cells.  ``,`` reads a character, so
# ``'0'``/``'1'`` arrive as 48/49 and every input needs 48 subtracted.
# Writing that straight costs 48 columns per input; running it as a loop
# costs a counter instead, and the counter itself is built by a second loop
# rather than by 48 ``+`` -- ``_LASER_OUTER * _LASER_INNER`` is 48.
_LASER_OUTER = 8
_LASER_INNER = 6


def _laserfuck_ring_reader(n: int) -> tuple[list[str], int]:
    r"""Build the looping input reader, and say how wide it is.

    Returns the reader's rows and the column the beam leaves them on, moving
    right, with the pointer on cell 0.

    The tape is laid out as *cell 0 = counter and answer*, cells 1..n =
    inputs.  Cell 0 earns that double duty: the counter ends the reader at
    zero and *touched*, which is exactly the state a ``0`` answer needs to
    print, so a leaf writes nothing for a zero and a single ``+`` for a one.

    Two loops run left to right, each a ring: a ``}`` faces the beam right
    along the body, ``#`` skips the deflector so ``)`` can test the cell
    under the pointer, and a nonzero cell turns the beam back to the ``/``,
    which drops it onto the return row where ``{`` sends it left to the
    ``^`` under the ring's own ``}``.  A zero cell lets the beam through the
    ``)`` and on to whatever follows on the row.

    The first ring multiplies: cell 1 is preloaded with ``_LASER_OUTER`` and
    each pass adds ``_LASER_INNER`` to cell 0, leaving the 48 the inputs
    need.  The reads then happen -- cell 1's preload is spent by now, so the
    inputs may use it -- and the second ring subtracts one from cell 0 and
    from every input per pass, running until the counter is spent.

    A ring body cannot be folded: the return leg re-enters at the ``}`` and
    re-runs the *whole* body, so a body split across rows would re-execute
    only its tail.  Both bodies therefore live on one row -- and when a
    width cannot hold that row, :func:`_laserfuck_rotate` stands the whole
    block on end rather than breaking it.
    """
    preload = ">" + "+" * _LASER_OUTER
    multiply = "<" + "+" * _LASER_INNER + ">" + "-#/)"
    reads = ""
    for i in range(n):
        reads += ","
        if i < n - 1:
            reads += ">"
    reads += "<" * n  # back to the counter
    # one '-' for the counter and one for each input, then home again
    retire = "".join("->" for _ in range(n)) + "-" + "<" * n + "#/)"

    body = "}" + preload + "}" + multiply + reads + "}" + retire
    top = [" "] * (len(body) + 2)
    ret = [" "] * (len(body) + 2)
    for i, char in enumerate(body):
        top[i] = char
    # each ring's return leg: '^' under its own '}', '{' under its '/'
    first = 1 + len(preload)
    ret[first] = "^"
    ret[first + 1 + multiply.index("/")] = "{"
    second = len(body) - len(retire) - 1
    ret[second] = "^"
    ret[second + 1 + retire.index("/")] = "{"
    return ["".join(top).rstrip(), "".join(ret).rstrip()], len(body)


# Rotating or mirroring a LaserFuck block is a character substitution: the
# ops are direction-agnostic and only the mirrors and heading-setters carry
# an orientation.  Rotating a quarter turn clockwise turns a rightward beam
# into a downward one, which is how a block too wide for a width is made
# tall instead.
_LASER_ROTATE = str.maketrans(
    {
        "/": "\\",
        "\\": "/",
        "_": "|",
        "|": "_",
        "(": ")",
        ")": "(",
        "{": "^",
        "}": "v",
        "^": "}",
        "v": "{",
    }
)


def _laserfuck_rotate(rows: list[str]) -> list[str]:
    r"""Turn ``rows`` a quarter turn, so a rightward block becomes downward.

    The cells move as any rotation moves them -- the last row becomes the
    first column -- and each one is then substituted, since a mirror or a
    heading-setter means something different once the beam runs the other
    way.  ``,``, ``+``, ``-``, ``<``, ``>``, ``#`` and ``x`` are unchanged:
    they act on the tape, not on the beam.

    A reader is forty-odd columns and two rows laid flat; rotated it is two
    columns and forty-odd rows, which is what lets a narrow width still be
    met.
    """
    height = len(rows)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    return [
        "".join(padded[height - 1 - row][col] for row in range(height)).translate(
            _LASER_ROTATE
        )
        for col in range(width)
    ]


_LASER_FLIP_H = str.maketrans({"/": "\\", "\\": "/", "{": "}", "}": "{"})


def _laserfuck_flip(rows: list[str]) -> list[str]:
    r"""Mirror ``rows`` left to right, so a rightward block runs leftward.

    Like the rotation, this is a substitution: only the mirrors and the two
    horizontal heading-setters mean something different once the beam runs
    the other way, and the tape ops do not.  The rows are padded to a
    rectangle first, for the same reason -- a short row would mirror to a
    block whose cells no longer line up with the ones they pair with.
    """
    width = max(len(line) for line in rows)
    return [line.ljust(width)[::-1].translate(_LASER_FLIP_H) for line in rows]


def _laserfuck_reader_blocks(n: int) -> list[list[str]]:
    """Cut the flat reader into rectangles, padded so a rotation is exact."""
    rows, _ = _laserfuck_ring_reader(n)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    starts = [col for col, char in enumerate(padded[0]) if char == "}"]
    return [
        [
            line[start : starts[index + 1] if index + 1 < len(starts) else width]
            for line in padded
        ]
        for index, start in enumerate(starts)
    ]


def _laserfuck_assemble_reader(n: int, orientation: str) -> tuple[list[str], int, int]:
    """Chain the reader's blocks, each flat (``F``) or on end (``R``)."""
    cells: dict[tuple[int, int], str] = {}

    def put(row: int, col: int, char: str) -> None:
        if char != " ":
            cells[(row, col)] = char

    row = col = 0
    for block, upright in zip(_laserfuck_reader_blocks(n), orientation, strict=True):
        if upright == "F":
            for offset, line in enumerate(block):
                for index, char in enumerate(line):
                    put(row + offset, col + index, char)
            col += len(block[0])
        else:
            turned = _laserfuck_rotate(block)
            entry = turned[0].index("v")
            put(row, col + entry, "v")
            for offset, line in enumerate(turned):
                for index, char in enumerate(line):
                    put(row + 1 + offset, col + index, char)
            row += 1 + len(turned)
            col += entry
            put(row, col, "\\")
            col += 1

    height = max(r for r, _ in cells) + 1
    span = max(c for _, c in cells) + 1
    lines = [
        "".join(cells.get((r, c), " ") for c in range(span)).rstrip()
        for r in range(height)
    ]
    return lines, row, col


def laserfuck(truth_table: str, width: int | None = None) -> str:
    r"""Build a LaserFuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading
    to the top row moving right.  There it meets the reader, then the tree.

    **The reader.**  ``,`` reads a character, so ``'0'``/``'1'`` arrive as
    48/49 and each input needs 48 subtracted.  Written straight that is 49
    columns per input; instead two rings do it as a loop
    (:func:`_laserfuck_ring_reader`).  The first multiplies 8 by 6 to build
    the 48, the second spends that counter one unit at a time across the
    counter and every input.  Each ring is a ``}`` facing the beam along
    its body, ``#`` skipping the deflector so ``)`` can test the cell under
    the pointer, and a return leg beneath.  The reader is two rows and a
    few dozen columns whatever ``n`` is.

    **The tape.**  The ring counter is cell 0 and the inputs are cells
    1..n.  That is not an accident of layout: the counter ends *touched at
    zero*, which is exactly what a zero answer must be for the dump to
    print it, so cell 0 doubles as the answer cell.

    **The tree.**  Each node writes ``>#v)``: the ``#`` skips the ``v`` on
    the way in, so ``)`` tests the cell under the pointer.  A zero passes
    straight through and the next node carries on *along the same row*;
    only a one turns the beam back onto the ``v``, which drops it to a
    ``\\`` that faces it right again on a fresh row.  Rows therefore scale
    with the number of *one* edges rather than with the node count, and the
    all-zeros path is a single straight line.  A leaf retires each input
    (one ``-`` more than its value, driving the cell negative so the dump
    skips it), walks down to cell 0, and adds a ``+`` only if the answer is
    one -- a zero answer needs no code at all.

    LaserFuck has no output instruction: it prints the tape when the last
    laser dies, in decimal, skipping negative cells.  Cell (0, 0) is left
    blank deliberately -- a ``\\xff`` there would select byte mode.

    ``width`` bounds the columns.  The tree adds only a column or two past
    the reader, so the reader is what a width has to bargain with: laid
    flat it is one row and forty-odd columns, and when that will not fit
    :func:`_laserfuck_rotate` stands it on end instead -- two columns and
    forty-odd rows.  A ring body cannot simply be broken across rows, since
    the return leg re-enters at the ``}`` and re-runs the whole body, which
    is why the block is rotated rather than folded.  Below the width the
    *tree* needs there is nothing left to give, and the grid comes out as
    wide as the tree.
    """
    n = _validate_truth_table(truth_table)
    # The tree adds only a column or two past the reader, so the reader is
    # what a width has to bargain with: side by side the rings are one row
    # and forty-odd columns, stacked they are seven rows and under twenty.
    count = len(_laserfuck_reader_blocks(n))
    candidates = []
    for choice in range(2**count):
        orientation = "".join("R" if choice >> b & 1 else "F" for b in range(count))
        rows_of, exit_row, exit_col = _laserfuck_assemble_reader(n, orientation)
        span = max(len(line) for line in rows_of)
        candidates.append(
            (len(rows_of), span, rows_of, exit_row, exit_col, orientation)
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    fitting = [
        item
        for item in candidates
        if width is None or laserfuck_layout.MARGIN + item[1] + 2 <= width
    ]
    chosen = fitting[0] if fitting else min(candidates, key=lambda item: item[1])
    _, _, reader_rows, reader_exit_row, reader_exit_col, orientation_of = chosen

    margin = laserfuck_layout.MARGIN
    grid: list[list[str]] = []

    def put(row: int, col: int, char: str) -> None:
        while len(grid) <= row:
            grid.append([])
        line = grid[row]
        while len(line) <= col:
            line.append(" ")
        line[col] = char

    # The funnel: every start heading ends up on row 0 moving right.  Cell
    # (0, 0) stays blank so the tape dumps in decimal rather than byte mode.
    put(0, 1, "}")
    put(0, 2, "}")
    put(1, 0, "|")
    put(1, 1, "o")
    put(1, 2, "^")
    put(2, 1, "_")

    # The rings go on rows 0 and 1; the beam leaves them still moving right
    # with the pointer on cell 0.
    for offset, text in enumerate(reader_rows):
        for index, char in enumerate(text):
            if char != " ":
                put(offset, margin + index, char)
    # The beam leaves the reader moving right, and turns down onto a row of
    # its own for the tree.  How far it has to fall depends on what the last
    # block left beneath it: a block laid flat keeps its ring's return leg
    # on the row below, which the beam must clear, while a rotated one ends
    # at its own foot with nothing under it.
    # The tree is built as a block of its own, then mirrored and hung under
    # the reader.  Laid out rightward it would have to be *reached*: the
    # beam leaves the reader at its far right, and a leftward return leg
    # would be needed to carry it back to the margin before the tree could
    # start.  Mirrored, the tree runs leftward from where the beam already
    # is, so that whole row disappears -- the beam simply turns down at the
    # reader's end and a '/' faces it into the tree.
    #
    # Within the tree a node writes ``>#v)``: the '#' skips the 'v' on the
    # way in, so ')' tests the cell under the pointer.  A zero passes
    # straight through and the next node continues on the same row; only a
    # one turns the beam back onto the 'v' and drops it, to a '\' that
    # faces it right again on a fresh row.  Rows therefore scale with the
    # number of *one* edges rather than with the node count, and the
    # all-zeros path is a single straight line.
    tree: dict[tuple[int, int], str] = {}
    used = [0]

    def lay(row: int, col: int, char: str) -> None:
        if char != " ":
            tree[(row, col)] = char

    def emit(path: list[int], row: int, col: int) -> None:
        """Lay the subtree for ``path``, entered at ``(row, col)`` going right."""
        if len(path) == n:
            index = int("".join(map(str, path)), 2) if path else 0
            # The rings leave the inputs in cells 1..n and cell 0 already
            # touched at zero, so the sweep walks down to it and a zero
            # answer needs no code at all.
            run = ""
            for level in range(n, 0, -1):
                run += "-" * (path[level - 1] + 1) + "<"
            run += "+" if truth_table[index] == "1" else ""
            for offset, char in enumerate(run):
                lay(row, col + offset, char)
            lay(row, col + len(run), "x")
            return
        for offset, char in enumerate(">#v)"):
            lay(row, col + offset, char)
        emit([*path, 0], row, col + 4)  # a zero carries on along this row
        used[0] += 1
        drop = used[0]
        lay(drop, col + 2, "\\")  # a one comes down the 'v' column
        emit([*path, 1], drop, col + 3)

    emit([], 0, 0)
    height = max(row for row, _ in tree) + 1
    span = max(col for _, col in tree) + 1
    upright = [
        "".join(tree.get((row, col), " ") for col in range(span))
        for row in range(height)
    ]

    # Where the tree goes depends on whether the width can afford it.
    #
    # The beam leaves the reader still moving right, so the cheapest thing
    # is to carry straight on: the tree starts in the next column along, on
    # the reader's own rows, and costs no rows at all beyond the ones the
    # tree itself needs.  That only works if the grid may be as wide as the
    # reader and the tree laid end to end.
    #
    # Otherwise the tree is mirrored and hung underneath.  The beam turns
    # down at the reader's end and a '/' on the tree's first row faces it
    # left into a tree that runs backwards -- which needs no row to be
    # *reached*, unlike a rightward tree below, which would need one to
    # carry the beam back to the margin first.
    straight = margin + reader_exit_col + max(len(line) for line in upright)
    if width is None or straight + 1 <= width:
        for offset, line in enumerate(upright):
            for index, char in enumerate(line):
                put(reader_exit_row + offset, margin + reader_exit_col + index, char)
    else:
        flipped = _laserfuck_flip(upright)
        entry = len(flipped[0].rstrip()) - 1
        # A narrow reader can leave the beam further left than the tree is
        # wide, and the tree would run off the western edge.  Turning down
        # further to the right costs nothing but the blank cells it crosses,
        # so the fall column is pushed out to wherever the tree needs it.
        fall = max(margin + reader_exit_col, margin + entry + 1)
        top = reader_exit_row + (2 if orientation_of[-1] == "F" else 1)
        put(reader_exit_row, fall, "v")
        for offset, line in enumerate(flipped):
            for index, char in enumerate(line):
                put(top + offset, fall - 1 - entry + index, char)
        put(top, fall, "/")

    lines = ["".join(line).rstrip() for line in grid]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction block: retire one input, reduce, keep the rest.

    ``level`` is the 0-based reduce level (odd here: 1, 3, ...).  The queue
    holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then two 48s,
    then the ``n`` input chars.  Unlike the even reduce, the odd level
    branches on a *retired* (previous) input whose bit has already been
    used, so ``e^rot`` brings that input to the front and the block runs
    ``zero`` (``gy j e^(qlen-1) gz``) to fold it away, ``swap`` (``e gy j
    e^(qlen-2) j gz``) to encode the current input as the ghost cell the
    even-reduce branches on, and ``bring`` (``e^(qlen-1)``) to put the
    value slots back at the front before ``er`` runs the even-reduce body.

    The ZS adds an extra ghost cell at the front, so the even-reduce body
    uses ``ahead = n - level + 1`` instead of ``n - level``.  No input is
    popped; the final ``f^pairs`` in ``er`` drops only the rejected value
    slots.
    """
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added by the swap
    total = n
    qlen = 2 * pairs + 2 + total
    rot = 2 * pairs + 2 + (processed - 1) if processed > 0 else 0
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )
    return "e" * rot + zero + swap + bring + er


def taglate(truth_table: str) -> str:
    r"""Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ``n == 1`` reads the single input with ``h`` and computes the affine
    combination ``base + bit * coeff`` with the ``b``/``c``/``a`` queue
    arithmetic, then prints it.

    For ``n >= 2`` the program is ``seed\\n<commands>``.  The seed holds
    ``n_effective`` literal ``'1'``s (``n_effective - 1`` leading, one
    trailing) around a run of ``'0'``s; the prefix of ``h``/``e``/``b``/
    ``d``/``j`` commands reads ``n_effective`` inputs and interleaves the
    (reordered) truth-table bits into ``[0, s0, 0, s1, 0, s2, ...]`` value
    slots, followed by two 48s and the inputs.  Odd ``n`` prepends a fake
    zero input (ghost digit) so the slot stride lands on a separator, and
    pads the table to ``n_effective = n + 1`` inputs.

    The command list alternates even-reduce blocks (select half the
    value slots on an input bit, keep all inputs) and odd-reduce blocks
    (retire the previous input, swap the current one in, even-reduce).
    Neither reduce pops inputs; ``e^6 f^(n_effective - 2) e^2`` reshapes
    the queue into the 8-cell ``[0, v0, 0, v1, 48, 48, prev, curr]``
    layout, and ``_SEL1_N2`` selects between the last two candidate
    values on the two remaining inputs and prints ``48 + bit``.
    """
    n = _validate_truth_table(truth_table)
    if n == 1:
        base = 48 + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    # For odd n, prepend a fake zero-input (ghost) to make the stride land
    # on a separator.  n_effective is the number of h-reads and levels.
    if n % 2 == 1 and n > 1:
        n_eff = n + 1
        full_tt = _build_padded_tt(truth_table, n_eff)
    else:
        n_eff = n
        full_tt = truth_table

    seed = "1" * (n_eff - 1) + "0" * (2 ** (n_eff + 2) + 2) + "1"

    ordered = _reorder_tt(full_tt, n_eff)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    prefix = (
        "he" * (n_eff - 1)
        + "h"
        + selectors
        + "ee"
        + "b" * n_eff
        + "e" * (2 ** (n_eff + 1) + 2)
        + "j" * n_eff
    )

    select_parts: list[str] = []
    for level in range(n_eff - 1):
        pairs = 2 ** (n_eff - level)
        if level % 2 == 0:
            select_parts.append(_even_reduce(pairs, level, n_eff))
        else:
            select_parts.append(_odd_reduce(pairs, level, n_eff))

    if n_eff > 2:
        # Drop the first n_eff-2 already-used inputs, then rotate the
        # remaining two inputs so the queue matches the 8-cell [0, w0, 0,
        # w1, 48, 48, prev, curr] layout that the committed n=2 odd
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


# Cells in a Clockwise leaf: 'S', the seven ';' that print the answer digit
# with the '+' that set their parity, and the 'S+?' exit.  Both digits fit
# in this height -- '0' pads with one extra 'S' -- so every leaf's exit '?'
# lands on the same row, which is what the ring's bottom row assumes.
_CLOCKWISE_LEAF = 14


def clockwise(truth_table: str) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints the result as the ASCII digit ``'0'`` or ``'1'``.

    The program is a decision tree in a closed ring.  ``S`` zeroes the
    accumulator and seven ``.`` reads consume a ``0``/``1`` input char's seven
    bits, leaving its value bit in the accumulator.  At each node a ``?``
    turns the pointer by ``acc`` quarter-turns, so a zero bit continues down
    the spine while a one bit turns right (cw) into a column; three ``R`` in
    an L pattern turn it back down into the next column, at a ``2**(n-k)``
    displacement so each input combination reaches a unique leaf column.

    A leaf prints the answer's seven bits with ``;``, which emits ``acc % 2``,
    so a ``+`` before a ``;`` flips the parity into the bit that position
    needs.  Printing the ASCII digit rather than the bare bit costs almost
    nothing here: ``'0'`` is ``0110000`` and ``'1'`` is ``0110001``, so the
    two leaves differ by a single ``+``.  The leaf then resets and counts up
    to one (``S+``) so the exit ``?`` sees ``acc == 1`` whatever it printed,
    and turns left onto a shared bottom row; an ``S`` after each exit keeps
    passing paths at acc=0 so they do not turn on another leaf's exit.  Both
    leaves are padded to the same height, so every exit lands on that row.
    The row funnels left to the corner ``R`` and up column 0 to halt.

    The root node needs no spine of its own.  The pointer starts at ``(0, 0)``
    heading right and walks the whole top row into the corner ``R``, so seven
    ``.`` laid just left of that corner are the first instructions executed,
    and the accumulator is already zero when they run -- so the root's ``S``
    is a no-op too.  Hoisting those eight cells onto row 0 retires seven rows
    of grid, roughly a fifth of the blanks in a small table.  It needs seven
    free columns left of the root, i.e. ``2 ** (n + 1) >= 7``, so ``n == 1``
    (four columns) keeps the spine; widening that ring would cost more than
    the rows save.
    """
    n = _validate_truth_table(truth_table)
    cells: dict[tuple[int, int], str] = {}
    # Seven free columns left of the root are what the hoist needs; see above.
    hoist = 2 ** (n + 1) >= 7
    shift = 7 if hoist else 0
    # The spine starts far enough right that the tree's leftward branches
    # clear column 0, which holds the closing corner.  A node at ``bit``
    # displaces its one-branch ``2**(n - bit)`` to the left and puts two
    # ``R`` one column further, so the whole tree spans
    # ``sum(2**(n - bit)) + 1 == 2**(n + 1) - 1`` columns left of the spine
    # and ``2**(n + 1)`` leaves exactly one free column at the left edge.
    # Anything wider is dead space: the turns are relative, so the tree's
    # absolute column never matters.
    root = 2 ** (n + 1)

    def place(node: tuple[int, int], ch: str) -> None:
        cells[node] = ch

    def build(bit: int, x: int, y: int, combo: int) -> None:
        if bit == n:
            leaf(x, y, combo)
            return
        if bit == 0 and hoist:
            # The seven reads sit on row 0, left of the corner ``R``; the
            # node's ``?`` is all that is left of its spine.
            for i in range(7):
                place((x - 7 + i, 0), ".")
        else:
            place((x, y), "S")
            for i in range(7):
                place((x, y + 1 + i), ".")
        place((x, y + 8), "?")
        build(bit + 1, x, y + 9, combo << 1)  # b=0: continue down
        # b=1: '?' turns right (cw from down) then three R's turn left->down
        xn = x - 2 ** (n - bit)
        place((xn, y + 8), " ")
        place((xn - 1, y + 8), "R")
        place((xn - 1, y + 7), "R")
        place((xn, y + 7), "R")
        build(bit + 1, xn, y + 9, (combo << 1) | 1)

    def leaf(x: int, y: int, combo: int) -> None:
        # Emit the answer as the ASCII digit rather than as the raw bit.
        # Seven ';' print one bit each, most significant first, and each
        # prints acc % 2 -- so a '+' before a ';' is what flips the parity
        # into the bit that position needs.  '0' is 0110000 and '1' is
        # 0110001, which differ only in the last bit, so the two leaves are
        # the same shape apart from one '+'.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(48 + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # A '?' turns by acc quarter-turns and must see exactly 1 to turn
        # left onto the bottom row.  The accumulator is 2 or 3 by now
        # depending on the digit, so reset and count up to 1 rather than
        # tracking it: 'S+' is uniform where a bare '+' would not be.  The
        # extra 'S' pads the shorter leaf so both are _LEAF_HEIGHT cells and
        # every leaf's exit lands on the same row, which the ring's geometry
        # depends on; 'S' on an already-zero accumulator is a no-op.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)

    # Hoisting the root's reads onto row 0 retires seven rows of spine, so the
    # tree starts that much higher and every row below rides up with it.
    build(0, root, 1 - shift, 0)

    bottom = 1 + 9 * n + _CLOCKWISE_LEAF - 1 - shift
    for (x, y), ch in list(cells.items()):
        if ch == "?" and y == bottom:
            place((x - 1, bottom), "S")
    place((0, bottom), "R")
    place((root, 0), "R")

    height = bottom + 1
    width = max(x for (x, y) in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), ch in cells.items():
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = ch
    # The grid is a fixed-size rectangle of blanks that the cells are painted
    # into, so a row's trailing filler is never reached; the interpreter pads
    # short rows itself, so trimming it changes nothing but the file.
    return "\n".join("".join(row).rstrip() for row in grid)


def container(truth_table: str) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``+1 T>=2k``,
      ``-2 T>=2k+1``, ``+1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, an armed gate ``A_k`` (65, dipping to 49) and
      ``B_k`` (47, dipping to 48) make ``IN>=A_k`` and ``IN<=B_k`` hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A survivor per row (initial 1) is killed by ``-1 IN>=A_k`` or
      ``-1 IN<=B_k`` when the corresponding bit mismatches, so exactly the
      matching row's survivor stays 1.
    * At tick ``2n`` a gate ``Gout`` dips to 1, so ``+1 S_r>=Gout`` adds the
      table entry of the surviving row to ``OUT``; ``PRINT`` fires and
      ``EXIT`` halts.
    """
    n = _validate_truth_table(truth_table)

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches
    for k in range(n):
        lines.append(f"A{k}=65:")
        lines.append(f"-16 T>={2 * k}")
        lines.append(f"+32 T>={2 * k + 1}")
        lines.append(f"-16 T>={2 * k + 2}")
        lines.append(f"B{k}=47:")
        lines.append(f"+1 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"+1 T>={2 * k + 2}")
    for row in range(2**n):
        lines.append(f"S{row}=1:")
        for k in range(n):
            if (row >> (n - 1 - k)) & 1:
                lines.append(f"-1 IN<=B{k}")
            else:
                lines.append(f"-1 IN>=A{k}")
    lines.append("Gout=2:")
    lines.append(f"-1 T>={2 * n - 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("OUT:")
    lines.append(f"+48 T>={2 * n}")
    lines.append(f"-48 T>={2 * n + 1}")
    for row in range(2**n):
        if truth_table[row] == "1":
            lines.append(f"+1 S{row}>=Gout")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def bit_tilde(truth_table: str) -> str:
    """Build a bit~ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    bit~ is a bit pool with ``{``/``}`` while-nonzero loops.  Each ``)``
    reads an input byte into eight bits (MSB first), so the input bit lands
    at cell ``8i+7`` and cells ``8i+2``/``8i+3`` hold the ``00110000`` byte
    pattern a ``0`` output needs.  Every (input, one-row) pair each minterm
    tests is pre-copied unconditionally into a fresh cell (chained two-dest
    copies so the source survives), complemented when the minterm needs the
    bit zero; the first input-0 copy also consumes the input bit out of cell
    7 so the output window holds a clean 48.  Each ``1`` row of the table is
    then a nested ``{ bit ... }`` test whose innermost body forces the result
    cell to 1, and the result is copied into cell 7 so ``(`` prints ``48 +
    result``.  Dense tables evaluate the complement instead (fewer minterms)
    and flip the output bit once.
    """
    n = _validate_truth_table(truth_table)

    table, use_complement = _maybe_complement(truth_table)

    prog: list[str] = []
    pos = 0

    def move(dst: int) -> None:
        nonlocal pos
        while pos < dst:
            prog.append(">")
            pos += 1
        while pos > dst:
            prog.append("<")
            pos -= 1

    def copy2(src: int, d1: int, d2: int) -> None:
        """Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
        nonlocal pos
        move(src)
        prog.append("{")
        move(d1)
        prog.append("~")
        move(d2)
        prog.append("~")
        move(src)
        prog.append("~")
        prog.append("}")

    for i in range(n):
        if i:
            move(8 * i)
        prog.append(")")
        pos = 8 * i

    scratch = 8 * n
    uses: dict[tuple[int, int], int] = {}
    for i in range(n):
        src = 8 * i + 7
        for k in range(2**n):
            # only one-rows' indicators are used; the first input-0 copy must
            # still run to consume the input bit out of cell 7
            if table[k] != "1" and not (i == 0 and k == 0):
                continue
            c = (k >> (n - 1 - i)) & 1
            use = scratch
            keep = scratch + 1
            scratch += 2
            copy2(src, use, keep)
            src = keep
            if c == 0:
                move(use)
                prog.append("~")
                pos = use
            uses[(k, i)] = use

    result = scratch
    scratch += 1

    def set_result() -> None:
        nonlocal pos
        move(result)
        prog.append("{ ~ } ~")
        pos = result

    def node(level: int, k: int) -> None:
        nonlocal pos
        if level == n:
            set_result()
            return
        use = uses[(k, level)]
        move(use)
        prog.append("{")
        pos = use
        node(level + 1, k)
        move(use)
        prog.append("~")
        pos = use
        prog.append("}")

    for k in range(2**n):
        if table[k] == "1":
            node(0, k)

    move(result)
    prog.append("{")
    move(7)
    prog.append("~")
    move(result)
    prog.append("~")
    prog.append("}")
    pos = result
    if use_complement:
        move(7)
        prog.append("~")
        pos = 7
    move(0)
    prog.append("(")
    return "".join(prog)


def forbin_boolean(truth_table: str) -> str:
    """Build a Forbin program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Forbin's ``in`` reads one bit (most significant first), so each input
    byte contributes 8 reads and only the last bit (the LSB, which is what
    distinguishes ``'0'`` from ``'1'``) is used.  A decision tree over those
    bits is laid out with the range-loop if-trick: ``for _:!b..b`` runs its
    body once when ``b`` is 1 (the ``return`` cuts the second iteration)
    and falls through when ``b`` is 0, so each node emits the 1-subtree then
    the 0-subtree and every leaf prints the result byte and returns.
    """
    n = _validate_truth_table(truth_table)

    lines: list[str] = ["main {"]
    bits: list[str] = []
    for i in range(n):
        reads = [f"i{i}_{j}" for j in range(8)]
        lines.append(f"  {','.join(reads)} = (in 0);")
        bits.append(reads[7])

    def emit(level: int, row: int, depth: int) -> None:
        indent = "  " * depth
        if level == n:
            byte = 49 if truth_table[row] == "1" else 48
            lines.append(f"{indent}out {','.join(format(byte, '08b'))};")
            lines.append(f"{indent}return 0;")
            return
        lines.append(f"{indent}for _:!{bits[level]}..{bits[level]} {{")
        emit(level + 1, row + 2 ** (n - 1 - level), depth + 1)
        lines.append(f"{indent}}}")
        emit(level + 1, row, depth)

    emit(0, 0, 1)
    lines.append("}")
    return "\n".join(lines)


def _suptiftam_bit(i: int) -> str:
    """Variable name for input bit ``i`` (identifiers must be alphabetical)."""
    if i < 25:
        return chr(ord("b") + i)
    return "b" + _suptiftam_bit(i - 25)


def suptiftam(truth_table: str) -> str:
    """Build a Suptiftam program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Suptiftam has only ``+``/``-``/``/`` and no equality test, so the table
    is evaluated as a sum of minterms: each bit is read from its own input
    row and normalized to 0/1 with ``%-[read]22%`` (the literal ``22``
    parses in base 23 to 48), each minterm multiplies its bits (AND, via a
    recursive add-until-zero ``mulStep`` guarded by ``if``), and the sum is
    written to ``term``.  Exactly one minterm is 1 for any input, so the
    sum is the table entry.
    """
    n = _validate_truth_table(truth_table)
    names = [_suptiftam_bit(i) for i in range(n)]
    lines = [
        "sum=0",
        "p=1",
        "fd mulStep :x",
        "prod=%+[prod]a%",
        "x=%-[x]1%",
        "mulStep(:x:)if(x)",
        "fi",
    ]
    for name in names:
        lines.append(f"{name}=%-[read]22%")
        lines.append("down(:read:)")
    for row in range(2**n):
        if truth_table[row] != "1":
            continue
        lines.append("p=1")
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            factor = names[i] if bit else f"%-[1]{names[i]}%"
            lines += ["prod=0", f"a={factor}", "mulStep(:p:)if(p)", "p=prod"]
        lines.append("sum=%+[sum]p%")
    lines.append("term=sum")
    return "\n".join(lines)


# A leaf is exactly as wide as the ``(( ))`` it ends on, so consecutive
# leaves abut and the tree needs no gutter between them at all.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves are placed first, on a fixed pitch, and the switches are then
    collapsed upwards: each pair of entry columns yields a ``< >`` centred
    between them with rails drawn out to both.  Positioning everything from
    the leaf pitch is what keeps the drawing tight -- an earlier recursive
    version assembled each subtree into its own padded block and separated
    the blocks by a gutter, which cost a column of blanks for every leaf at
    every level even though two ``(( ))`` boxes may sit flush against each
    other.

    Rows run ``( )``, its rail, then four rows per level (``/ /``, a rail,
    ``< >``, a rail), then the five-row leaf block.
    """
    cells: dict[tuple[int, int], str] = {}

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    # Leaf ``k`` spans columns ``5k`` to ``5k + 4``, so its middle -- the
    # column every rail in that leaf's band lands on -- is ``5k + 2``.
    mids = [_FLOWCHART_PITCH * k + 2 for k in range(len(truth_table))]

    leaf_top = 2 + 4 * n
    for k, bit in enumerate(truth_table):
        middle = mids[k]
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        put(middle - 1, leaf_top + 2, "\\ \\")
        cells[(middle, leaf_top + 3)] = "│"
        put(middle - 2, leaf_top + 4, "(( ))")

    for depth in range(n - 1, -1, -1):
        switch_row = 4 + 4 * depth
        parents = []
        for j in range(0, len(mids), 2):
            west, east = mids[j], mids[j + 1]
            middle = (west + east) // 2
            put(middle - 1, switch_row - 2, "/ /")
            cells[(middle, switch_row - 1)] = "│"
            put(middle - 1, switch_row, "< >")
            for x in range(west + 1, middle - 1):
                cells[(x, switch_row)] = "─"
            for x in range(middle + 2, east):
                cells[(x, switch_row)] = "─"
            cells[(west, switch_row)] = "┌"
            cells[(east, switch_row)] = "┐"
            cells[(west, switch_row + 1)] = "│"
            cells[(east, switch_row + 1)] = "│"
            parents.append(middle)
        mids = parents

    root = mids[0]
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def flowchart(truth_table: str) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is a binary decision tree drawn on the grid: every level
    reads one input bit with ``/ /`` and hands it to a ``< >`` switch whose
    two sides are the halves of the table, and each of the ``2**n`` leaves
    sets the register to its own digit, prints it, and halts.

    Unlike the repo's other 2D boolean generators there is no geometry to
    build for the branch itself -- Flowchart has a real conditional node --
    and each input arrives as a bare bit, so no per-input decoding loop is
    needed either.  What the layout has to get right instead is routing:
    every switch is centred over the two subtree entries it feeds, with
    rails drawn out to each.

    The leaves are laid down first, on a pitch of exactly one ``(( ))``
    width, and the switches are collapsed upwards from them.  Nothing
    separates one leaf from the next: two ``(( ))`` boxes may sit flush
    against each other, since a rail only has to clear a node when it needs
    to pass *through* that node's row.  Sibling subtrees never do -- they
    descend in their own column bands -- so the gutter an earlier version
    kept between them was never load-bearing, and dropping it takes the
    ``n = 4`` drawing from 2444 characters to 1557.

    **The tree holds many ``/ /`` nodes but reads each input once.**  A
    depth-``n`` tree draws ``2**n - 1`` read nodes, one per internal node,
    yet any single run walks one root-to-leaf path and so executes exactly
    ``n`` of them -- the duplication is spatial, the way an unrolled
    brainfuck branch repeats ``,`` in each arm of a nested ``[ ]`` without
    any one execution reading twice.  This is deliberately *not* the
    once-only embedding rule that ``tools.boolean.parameterized`` documents:
    that rule exists so a language with no input mechanism cannot, through
    repeated ``{Xi}`` substitution, consult a bit more often than an
    input-capable language would.  Flowchart has a real input command, so
    it is an input-reading generator like :func:`streetcode` (whose ``I``
    commands likewise repeat across tree branches), not a parameterized one.

    An alternative construction reads all ``n`` bits up front into a deque
    and pops one per level instead, which exercises the deques -- the
    language's defining feature, untouched here.  It was built and verified
    over the same tables, and is worth revisiting if Flowchart ever gets a
    cross-check that would benefit from the wider coverage; it costs a
    ``4n``-row prologue and depends on push-top/pop-bottom being FIFO, a
    silent wrong-answer trap if the pop is ever changed to pop-top.
    """
    _validate_truth_table(truth_table)
    return _flowchart_render(_flowchart_cells(truth_table))
