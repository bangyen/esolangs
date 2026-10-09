"""Boolean-function generator for Dig."""

from itertools import pairwise
from typing import cast

from esolangs.registry._language import Language
from esolangs.tools.dig_layout import _DIG_ALT_BRANCH, _DIG_DIRECTIONS
from esolangs.tools.dig_layout import _dig_alt_clear as _dig_alt_clear
from esolangs.tools.dig_layout import _dig_layout as _dig_layout
from esolangs.tools.dig_layout import _dig_leaf_inputs as _dig_leaf_inputs
from esolangs.tools.dig_leaf import (
    _DIG_DIGITS,
    _DIG_OPAQUE,
    _DIG_PRINT,
    _DIG_SPAN,
    _dig_constant_leaf,
    _Reads,
    _render,
)
from esolangs.tools.dig_leaf import (
    _dig_adder as _dig_adder,
)
from esolangs.tools.dig_leaf import (
    _dig_flat_leaf as _dig_flat_leaf,
)
from esolangs.tools.dig_shared import _dig_indexed_shared
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    read_at,
)
from esolangs.tools.wrap import balance_score

# Dig blocks for one level of the decision tree.  ``$`` takes its count
# from the digit beside it and looks up, right, down, left for one, so the
# count sits to the *right* of the ``$`` and the whole block is entered
# from the left: the count digit is itself the first of the commands it
# arms, which is why three covers a read and a store.
_DIG_BRANCH = "$3~;#"  # arm three, read a bit, store it, then turn on it


# Columns one level owns.  A block is five cells and its ``#`` is the last,
# so the child's ``>`` sits under that ``#`` -- which is the cell before the
# child's own block, and the stride is what puts it there.
_DIG_STRIDE = len(_DIG_BRANCH)


# A banded level leaves one column spare.  Six is what makes the two bands
# able to share columns at all: see :func:`_dig_columns`.
_DIG_BAND = _DIG_STRIDE + 1


# Offset of a block's ``#``, the cell its children attach under.
_DIG_LAST = _DIG_STRIDE - 1


def _dig_leaf(reads: int, value: int, *, aligned: bool) -> str:
    """Build a leaf that consumes ``reads`` inputs, then prints ``value``.

    ``$`` arms the cells after it as commands, up to nine per window; windows
    chain, a spent count arming the next ``$``.  ``aligned`` (banded layout)
    makes windows exactly ``_DIG_BAND`` long and pads the value to an odd
    offset from the ``$``, where the other band's ``$`` and ``#`` never look.
    """
    out = ""
    if not aligned:
        return _dig_constant_leaf(reads, value)
    while reads > _DIG_BAND - 1:
        take = _DIG_BAND - 2
        out += f"${take + 1}" + "~" * take
        reads -= take
    pad = 1 - reads % 2
    tail = "~" * reads + " " * pad + _DIG_PRINT.format(value)
    return out + f"${reads + pad + 3}" + tail


def _dig_columns(strides: list[int], split: int | None) -> list[int]:
    """Return the ``$`` column of every level, the leaf's last, from the strides.

    A banded tree turns round once and the west band runs over the east
    band's columns, mirrored.  A ``$`` or ``#`` sits at block offset 0 or 4
    and confusable digits at 1 and 3, so with stride six a collision needs
    the bands' column difference ``d`` to be 0, 1, 2, 3 or 5 mod six; four is
    not, so ``d = 4 mod six`` clears all of them.  A second turn would put two
    bands the same way, differing by 0 mod six -- the case ``d`` must avoid.
    The west band is anchored at the leaf, whose ``$`` sits at column seven:
    one stride further back from the east band's last ``#`` makes ``d`` four.
    A level's skipped reads lengthen its stride, so only the one-band tree
    has any.
    """
    east = [1]
    for stride in strides:
        east.append(east[-1] + stride)
    if split is None:
        return east
    west = [7]
    for stride in reversed(strides[split:]):
        west.append(west[-1] + stride)
    return east[:split] + west[::-1]


def _dig_levels(essential: list[int], n: int) -> list[int]:
    """Return the inputs a tree branches on.

    The essential ones, and an ignored one only where a block's count digit
    cannot hold more skips.
    """
    if not essential:
        return list(range(n))
    levels: list[int] = []
    pending = 0
    for i in range(essential[-1] + 1):
        if i in essential or pending == _DIG_SPAN - 3:
            levels.append(i)
            pending = 0
        else:
            pending += 1
    return levels


def _dig_grid(
    truth_table: str, n: int, split: int | None, *, reduce: bool = True
) -> str:
    """Lay the decision tree out, in one band east or two that turn round.

    The one-band tree branches only on the essential inputs; an ignored one
    is read by the next block (``$5~~;#`` after one skipped read), or by the
    leaf.  The banded tree branches on every input: with a skip or a long
    leaf it left blocks the clearance check does not see (mole deaths at
    n=5, essential inputs (0, 2, 3, 4) and (0, 1, 2)).  ``reduce=False``
    branches on every input in either.
    """
    levels = list(range(n))
    if reduce and split is None:
        levels = _dig_levels(essential_inputs(truth_table, n), n)
    return _dig_lay(truth_table, n, split, levels)


def _dig_lay(truth_table: str, n: int, split: int | None, used: list[int]) -> str:
    """Lay the tree out branching on the inputs ``used``, reading the rest."""
    truth_table = read_at(truth_table, used, n)
    m = len(used)
    # Inputs read before level ``l``'s own block, its skips being the gap.
    consumed = [0, *(i + 1 for i in used)]
    skips = [used[level] - consumed[level] for level in range(m)]
    columns = _dig_columns(
        [(_DIG_STRIDE if split is None else _DIG_BAND) + skip for skip in skips],
        split,
    )
    total = 2 ** (m + 1) - 1
    constant = constant_span_test(truth_table)
    cells: dict[tuple[int, int], str] = {}
    corridors: list[tuple[int, int, int]] = []

    def leftward(level: int) -> bool:
        """Whether this level's block is entered facing west."""
        return split is not None and level >= split

    def dollar(level: int) -> int:
        """Return the column of this level's ``$``, the cell the mole meets first."""
        return columns[level]

    def place(row: int, col: int, text: str) -> None:
        """Write ``text`` along ``row`` from ``col``, refusing an occupied cell.

        An overwrite is one of the two ways a bad layout fails; :func:`_dig_clear`
        checks the other.
        """
        for i, char in enumerate(text):
            if col + i < 0:
                raise AssertionError(f"cell off the left edge at row {row}")
            if (row, col + i) in cells:
                raise AssertionError(f"two cells at {(row, col + i)}")
            cells[row, col + i] = char

    def block(row: int, level: int, text: str) -> None:
        """Write a block so the mole meets its first cell first."""
        col = dollar(level)
        if leftward(level):
            place(row, col - len(text) + 1, text[::-1])
        else:
            place(row, col, text)

    def walk(row: int, level: int, lo: int, hi: int) -> None:
        """Lay the subtree for ``truth_table[lo:hi]`` at ``row``."""
        if level == m or constant(lo, hi):
            # A constant slice cannot be told apart by more branching, so
            # this is a leaf and every row below it goes unwritten.  It
            # still reads what it did not branch on: a program whose input
            # count depended on its table would desync a caller feeding
            # several programs from one stream.
            reads = n - consumed[level]
            block(
                row,
                level,
                _dig_leaf(reads, int(truth_table[lo]), aligned=split is not None),
            )
            return
        skip = skips[level]
        block(row, level, f"${3 + skip}{'~' * skip}~;#")
        col = dollar(level)
        last = _DIG_LAST + skip
        hop = col - last if leftward(level) else col + last
        step = 2 ** (m - level - 1)
        half = (hi - lo) // 2
        # ``#`` rotates one way on a 0 and the other on a 1, so which child
        # is up and which is down follows the mole's heading: a bit that
        # sends an eastbound mole down sends a westbound one up.
        one, zero = (
            (row - step, row + step) if leftward(level) else (row + step, row - step)
        )
        for child, bounds in (
            (one, (lo + half, hi)),
            (zero, (lo, lo + half)),
        ):
            # the mole arrives here vertically from the parent's "#", which
            # is the cell right before the child's own block -- so the turn
            # goes in that column, pointing the way the child is entered
            place(child, hop, "<" if leftward(level + 1) else ">")
            corridors.append((hop, row, child))
            walk(child, level + 1, *bounds)

    # The mole starts at (0, 0) facing right, so the ``'`` below turns it
    # down column 0 and this is the cell that turns it back out of it.
    place(total // 2, columns[0] - 1, ">")
    walk(total // 2, 0, 0, 2**m)
    _dig_clear(cells, corridors)

    if (0, 0) in cells:
        raise AssertionError("the start marker's cell is taken")
    cells[0, 0] = "'"
    return _render(cells, dense=False)


def _dig_clear(
    cells: dict[tuple[int, int], str],
    corridors: list[tuple[int, int, int]],
) -> None:
    """Refuse a grid whose moles would be stopped on their way.

    A mole falling from ``#`` to its child meets every row between (only
    :data:`_DIG_OPAQUE` is scenery), and a ``$`` or ``#`` takes the first
    digit of up, right, down, left.  Checked against the grid, since the
    column rule is what places the cells.
    """
    for col, start, end in corridors:
        low, high = sorted((start, end))
        for row in range(low + 1, high):
            char = cells.get((row, col))
            if char is not None and char in _DIG_OPAQUE:
                raise AssertionError(
                    f"mole from row {start} meets {char!r} at {(row, col)}"
                )
    for (row, col), char in cells.items():
        if char not in "$#":
            continue
        for step in (-1, 1):
            above = cells.get((row + step, col))
            if above is not None and above in _DIG_DIGITS:
                raise AssertionError(f"{char!r} at {(row, col)} reads {above!r} first")


def _dig_alternating(truth_table: str, n: int) -> str:
    """Return the total unshared alternating layout."""
    return cast("str", _dig_layout(truth_table, n))


def _dig_lane_shared(truth_table: str, n: int) -> str | None:
    """Join aligned repeated leaves along spare rows or columns.

    Reject crossings and paths above the execution ledger. A six-bit leaf's
    worst walk is the sum of its adder, painter, selector and output legs.
    """
    return _dig_layout(truth_table, n, sharing=True) if n > 6 else None


def _dig_parallel_shared(truth_table: str, n: int) -> str | None:
    """Join interleaved leaf classes on two lanes separated by a gutter.

    Stretch branch counters around gutters, preserve rigid leaf stamps,
    and reject collisions or paths past the existing execution ledger.
    """
    return _dig_layout(truth_table, n, sharing=True, parallel=True) if n > 6 else None


def _dig_center_shared(truth_table: str, n: int) -> str | None:
    """Bridge offset leaves to the entry nearest their callers' box center.

    Heading-separated doglegs must clear retained stamps and fit the
    ledger. Ignored-prefix parity shrinks 2,627/2,698 cells to 1,960;
    eight seeded n=12 sparse/disjoint pairs shrink 77,816 to 62,272 (20.0%).
    Full-input routes may refuse.
    """
    return _dig_layout(truth_table, n, sharing=True, offset=True) if n > 8 else None


def _dig_size(program: str) -> tuple[int, int]:
    """Rank grid area first, then text length for ties."""
    return len(program.splitlines()) * grid_width(program), len(program)


def _dig_center_choice(table: str, n: int, current: str, width: int | None) -> str:
    """Shrink area while fitting width or lowering its existing floor."""
    candidates = tuple(
        filter(None, (_dig_center_shared(table, n), _dig_indexed_shared(table, n)))
    )
    if width is not None:
        candidates = tuple(
            p
            for p in candidates
            if grid_width(p) <= width
            or (grid_width(current) > width and grid_width(p) <= grid_width(current))
        )
    if not candidates:
        return current
    candidate = min(candidates, key=_dig_size)

    return candidate if _dig_size(candidate)[0] < _dig_size(current)[0] else current


def _dig_shared_pair(truth_table: str, n: int) -> str | None:
    """Share two distinct 64-entry leaves behind an eight-input prefix.

    The two 24-row leaves overlap one empty corner row. East and west
    prefix branches select the same leaves in opposite orders; their rays
    merge before either entry. Worst path: 60 prefix + 158 leaf commands.
    """
    if n != 8:
        return None
    blocks = [truth_table[i : i + 64] for i in range(0, 256, 64)]
    upper, lower = blocks[:2], blocks[2:]
    if upper[0] != upper[1]:
        a, b = upper
    elif lower[0] != lower[1]:
        b, a = lower
    else:
        return None  # only the first prefix bit matters
    if any(block not in (a, b) for block in blocks):
        return None
    if upper == lower:
        return None  # only the second prefix bit matters
    cells: dict[tuple[int, int], str] = {}
    reads: _Reads = []
    corridors: list[tuple[tuple[int, int], int, int]] = []

    def place(point: tuple[int, int], char: str) -> None:
        if point in cells:
            raise AssertionError(f"two cells at {point}")
        cells[point] = char

    for row, table in ((11, a), (34, b)):
        chars, spins, wants, _exit, _box = _dig_flat_leaf(table, [4, 2, 1], [4, 2, 1])

        def onto(point: tuple[int, int], row: int = row) -> tuple[int, int]:
            return point[0] + row, point[1] + 11

        for point, char in chars.items():
            place(onto(point), char)
        for point, heading in spins.items():
            place(onto(point), ">'<^"[heading])
        reads.extend(
            (onto(point), onto(want), frozenset(onto(p) for p in pending))
            for point, want, pending in wants
        )
    rays: list[tuple[tuple[int, int], int, int]] = []
    junctions: set[tuple[int, int]] = set()
    for row, col, heading, words in (
        (17, 1, 1, None),
        (14, 5, 1, upper),
        (24, 9, 3, lower),
    ):
        constant = words is not None and words[0] == words[1]
        code = "$~" if constant else _DIG_ALT_BRANCH
        d_col = _DIG_DIRECTIONS[heading][1]
        for offset, char in enumerate(code):
            place((row, col + d_col * offset), char)
        place((row - 1, col), "1" if constant else "2")
        reads.append(((row, col), (row - 1, col), frozenset()))
        if not constant:
            reads.append(((row, col + 3 * d_col), (row, col + 2 * d_col), frozenset()))
        if words is None:
            continue
        ray_col = col + len(code) * d_col if constant else col + 3 * d_col
        targets = (11 if words[0] == a else 34,) if constant else (11, 34)
        if constant:
            place((row, ray_col), "^" if targets[0] < row else "'")
        for target in targets:
            rays.append(((row, ray_col), 0 if target < row else 2, abs(target - row)))
            junctions.add((target, ray_col))
    # The lower branch enters from the east: its zero steers south to B.
    for point, char in (
        ((0, 0), "'"),
        ((17, 0), ">"),
        ((14, 4), ">"),
        ((26, 4), ">"),
        ((26, 10), "^"),
        ((24, 10), "<"),
    ):
        place(point, char)
    for point in junctions:
        place(point, ">")
    for row in (11, 34):
        cols = [*sorted(col for y, col in junctions if y == row), 11]
        corridors.extend(
            ((row, left), 1, right - left) for left, right in pairwise(cols)
        )
    corridors.extend(rays)
    corridors.extend(
        (
            ((0, 0), 2, 17),
            ((17, 0), 1, 1),
            ((17, 4), 0, 3),
            ((17, 4), 2, 9),
            ((14, 4), 1, 1),
            ((26, 4), 1, 6),
            ((26, 10), 0, 2),
            ((24, 10), 3, 1),
        )
    )
    _dig_alt_clear(cells, reads, corridors)
    return _render(cells, dense=True)


def _dig_quarter_turn(program: str) -> str:
    """Turn a grid clockwise with an external entry above its original origin."""
    rows = program.splitlines()
    height = len(rows)
    span = max(map(len, rows))
    arrows = str.maketrans("^>'<", ">'<^")
    grid = [[" "] * (height + 1) for _ in range(span + 1)]
    grid[0][height] = "'"
    for row, line in enumerate(rows):
        for col, char in enumerate(line):
            grid[col + 1][height - row] = char.translate(arrows)
    return "\n".join("".join(row).rstrip() for row in grid)


def _dig_xor_pair() -> str:
    """Compute a+b-2ab in four operand-sharing passes, with two input reads."""
    # Down the first column: read/store a and b. Up the second: copy b
    # into three cells, add a, store their sum. Down the third: copy the
    # sum twice, subtract b, multiply by b, and store ab three times.
    # The final climb starts with ab, subtracts its three stored copies,
    # adds the saved sum, and prints. Separating stores from readers
    # prevents the up/right/down/left operand priority selecting a copy.
    columns = (
        "'$~;  ~;   >",
        ">9;+ ;;;  $^",
        "'$;; -*;;;8>",
        "@8:+   ---$^",
    )
    return "\n".join(
        "".join(column[row] for column in columns).rstrip() for row in range(12)
    )


def _dig_discards(count: int, tail: str = "0") -> str:
    """Return a column reading and dropping ``count`` inputs, then ``tail``.

    Its ``'`` on the start cell turns the mole down it, and windows of eight
    reads chain below; the last window also arms ``tail``.  The default, an
    armed ``0``, clears the mole: the program below then meets it on its
    ``'`` facing down, carrying 0, nothing armed -- the state it has one
    step into a run of its own.
    """
    cells = "'"
    while count > _DIG_SPAN - 1 - len(tail):
        take = min(_DIG_SPAN - 1, count)
        cells += f"${take + 1}" + "~" * take
        count -= take
    cells += f"${count + 1 + len(tail)}" + "~" * count + tail
    return "\n".join(cells)


def dig(truth_table: str, width: int | None = None, *, share: bool = True) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Past
    four inputs the default stops branching six inputs short and gives each
    leaf their whole table as one rectangle of digits, indexed by two ``$``
    counts (:func:`_dig_flat_leaf`), keeping the area O(T).  ``width`` admits
    the unshared alternating layout when it fits, alongside the one- or
    two-band layouts (:func:`_dig_columns`); widths below the floor return
    the narrowest candidate; two-input XOR below width eight uses a
    four-column polynomial stencil.

    A constant span at any level is a row of reads and a print, its box sized
    alone (seeded n=7/8/9 area, one half constant: -14.7% / -20.0% / -25.4%;
    constant 64-entry blocks -12.3% / -34.2% / -24.3%; random unchanged).
    Aligned repeated leaves join along spare rows or columns, retaining the
    last copy and compacting unused external space. Paths must fit the execution
    ledger (n=8 A B B A: 1,155 cells, 208 commands). Narrow width paths can
    use the fixed two-leaf stencil (26 columns, at most 218 commands).
    Two parallel lanes admit interleaved classes (n=10: 5,175 cells,
    292 commands), stretching branch counters around their gutter.
    A prefix lookup can instead index up to seven shared leaf classes at
    n=8..12, adding eight rows per class to one six-input body. Full-input
    parity uses 720 cells and 227 commands at n=9; four-class n=10 controls
    use 1,152 cells and 291 commands. Candidates must fit the same ledger.
    Groups whose corridors collide or exceed the bound remain unshared.
    """
    n = _validate_truth_table(truth_table)
    built = _dig_build(truth_table, n, width, share=share)
    essential = essential_inputs(truth_table, n)
    if width is None and not essential:
        # The n=8 column uses 16 cells against the row's 51, despite more text.
        column = _dig_discards(n, truth_table[0] + ":") + "\n@"
        return min(built, column, key=_dig_size)
    if width is None and essential and 0 < essential[0] == n - len(essential):
        # Inputs before the first essential one can be read and dropped above
        # the smaller table's program, when that uses less area.
        inner = dig(read_at(truth_table, essential, n), share=share)
        # Grids are measured by area: the n=10 parity-prefix wrapper used
        # 2,736 cells against the integrated reader's 2,627, despite less text.
        return min(
            built,
            _dig_discards(essential[0]) + "\n" + inner,
            key=_dig_size,
        )
    return built


def _dig_build(
    truth_table: str, n: int, width: int | None, *, share: bool = True
) -> str:
    """Return :func:`dig`'s layout for every table, ignored inputs included."""
    if width is not None and 0 < width < 8 and truth_table == "0110":
        return _dig_xor_pair()
    pair = _dig_shared_pair(truth_table, n) if share else None
    lane = _dig_lane_shared(truth_table, n) if share else None
    parallel = _dig_parallel_shared(truth_table, n) if share else None
    if width is None and n > 4:
        current = min(
            filter(None, (pair, lane, parallel, _dig_alternating(truth_table, n))),
            key=len,
        )
        return _dig_center_choice(truth_table, n, current, width) if share else current
    flat = _dig_grid(truth_table, n, None)
    if n < 2:
        return flat
    # The turn has to leave the westbound band room to finish left of where
    # the eastbound one starts its last block, which is what fixes the
    # split rather than any search: the halves are as even as that allows.
    banded = _dig_grid(truth_table, n, -(-(n + 2) // 2))
    if width is None:
        return min((flat, banded), key=len)
    if n <= 4:
        if grid_width(flat) <= width:
            return flat
        if grid_width(banded) <= width:
            return banded
    candidates = tuple(filter(None, (flat, banded, pair, lane, parallel)))
    fitting = [p for p in candidates if grid_width(p) <= width]
    if n > 4:
        # Width 40 used 11,250 banded cells on the n=8 repeated-leaf case;
        # the 35-column unshared layout needs 1,925.
        alternating = _dig_alternating(truth_table, n)
        if grid_width(alternating) <= width:
            fitting.append(alternating)
    if fitting:
        current = min(fitting, key=len)
        return _dig_center_choice(truth_table, n, current, width) if share else current
    # A bounded flat width keeps the rotated entry padding O(T).
    if n <= 4:
        candidates += (_dig_quarter_turn(flat),)
    # Equal-width narrow fallbacks still prefer the shorter route: the n=9
    # parity prefix otherwise kept 27,036 banded cells over 2,556 shared cells.
    current = min(candidates, key=lambda program: (grid_width(program), len(program)))
    return _dig_center_choice(truth_table, n, current, width) if share else current


def _balance(table: str, default: str) -> str:
    """Compare alternating, flat, banded and reachable narrow/affine routes."""
    n = _validate_truth_table(table)
    flat = _dig_grid(table, n, None)
    # The full tree stays: a reduced one can be less square.
    candidates = [
        default,
        dig(table, share=False),
        flat,
        _dig_grid(table, n, None, reduce=False),
        dig(table, 1),
        dig(table, 8),
    ]
    essential = essential_inputs(table, n)
    if essential and 0 < essential[0] == n - len(essential):
        # A discard column can be more square even when its area is larger.
        inner = dig(read_at(table, essential, n))
        wrapped = _dig_discards(essential[0]) + "\n" + inner
        legacy = min(_dig_build(table, n, None, share=True), wrapped, key=len)
        candidates.append(legacy)
    if n >= 2:
        banded = _dig_grid(table, n, (n + 3) // 2)
        if grid_width(banded) < grid_width(flat):
            candidates.append(banded)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Dig",
    "grid_based.dig",
    boolean=dig,
    split=True,
    balance=_balance,
    empty_program="Dig program cannot be empty",
)
