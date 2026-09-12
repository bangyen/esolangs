r"""Boolean-function generators for languages in the ``other`` category."""

# laserfuck, streetcode and.
# construction (a grid layout.
# category; they are.
# the package and tests already.

from itertools import pairwise

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _maybe_complement,
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
    essential_inputs,
    minterm_sum,
    read_at,
)
from esolangs.tools.boolean.laserfuck import laserfuck
from esolangs.tools.boolean.streetcode import streetcode
from esolangs.tools.boolean.ztoalc_l import ztoalc_l

__all__ = [
    "between",
    "bit_tilde",
    "clockwise",
    "container",
    "forbin",
    "function_x_y",
    "laserfuck",
    "nevermind",
    "streetcode",
    "suptiftam",
    "taglate",
    "three_x",
    "ztoalc_l",
]

# Closed-form 3x constant.
# 3 with the ``x`` op (which.
# top, with ``(c-b)//a``).
_ZERO = "333x"  # (3-3)//3 = 0.
_ONE = "3333x3x"  # (3-0)//3 = 1.
_TWO = _ONE + _ONE + "3x"  # (3-1)//1 = 2.

# From [v], ``push X # push Y.
# Y=-d/3 it maps v -> (-d/3 -.
# rationals (and the d=0 case,.
_NEG_THIRD = "3" + _ONE + _ZERO + "x"  # (0-1)//3 = -1/3.
_NEG_TWO_THIRDS = "33" + _ONE + "x"  # (1-3)//3 = -2/3.
_DIGIT = (_ZERO, _ONE, _TWO)
_NEG_DIGIT = (_ZERO, _NEG_THIRD, _NEG_TWO_THIRDS)


def _const(n: int) -> str:
    r"""3x code pushing ``n`` on a clean stack, for any integer ``n``."""
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


def function_x_y(truth_table: str, width: int | None = None) -> str:
    r"""Build a function x(y) program computing the given truth table."""
    return best_input_order(
        truth_table,
        lambda table, perm: _function_x_y_ordered(table, perm, width),
    )


def _function_x_y_ordered(
    truth_table: str, perm: tuple[int, ...], width: int | None = None
) -> str:
    r"""Emit one input order's function x(y) program; see."""
    n = _validate_truth_table(truth_table)
    named: list[str] = []
    # The prefix a named subtree's.
    # *last* index the tree could.
    # node is often named later.
    # spend several names in.
    # time leaves the line a column.
    head = len(f"var t{max(1, 2**n - 1)}: ")

    def build(i: int, combo: int) -> str:
        r"""Return the text for this subtree, naming as much as the width needs."""
        # ``combo`` has the bits above.
        # so it is the first row of the.
        run = truth_table[combo : combo + 2 ** (n - i)]
        if i == n or len(set(run)) == 1:
            return f'"{truth_table[combo]}"'
        arms = [build(i + 1, combo | (1 << (n - 1 - i))), build(i + 1, combo)]

        def compose() -> str:
            return f'(b{perm[i]} == "1")<{arms[0]}, {arms[1]}>'

        text = compose()
        while width is not None and head + len(text) > width:
            longest = max((0, 1), key=lambda j: len(arms[j]))
            name = f"t{len(named)}"
            if len(arms[longest]) <= len(name):
                # Both arms are already names.
                # left to give, and this node's.
                break
            named.append(f"var {name}: {arms[longest]}")
            arms[longest] = name
            text = compose()
        return text

    body = build(0, 0)
    reads = [f"var b{i}: [~]" for i in range(n)]
    return "\n".join(["function truthTable()", *reads, *named, f"`{body}"])


def myscript(truth_table: str) -> str:
    r"""Build a MyScript program computing the given truth table."""
    return best_input_order(truth_table, _myscript_ordered)


def _myscript_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's MyScript program; see :func:`myscript`."""
    n = _validate_truth_table(truth_table)
    lines = [f"var b{i} is ask" for i in range(n)]

    def build(i: int, combo: int, pad: str) -> list[str]:
        # ``combo`` has the bits above.
        # so it is the first row of the.
        if i == n or len(set(truth_table[combo : combo + 2 ** (n - i)])) == 1:
            return [f'{pad}say "{truth_table[combo]}"']
        one = build(i + 1, combo | (1 << (n - 1 - i)), pad + "    ")
        zero = build(i + 1, combo, pad + "    ")
        return [
            f"{pad}check b{perm[i]}?",
            f'{pad}  if "1",',
            *one,
            f"{pad}  else,",
            *zero,
        ]

    return "\n".join(lines + build(0, 0, ""))


def three_x(truth_table: str) -> str:
    r"""Build a 3x program computing the given truth table."""
    return best_input_order(truth_table, _three_x_ordered)


def _three_x_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's 3x program; see :func:`three_x`."""
    n = _validate_truth_table(truth_table)

    # Variable allocation: var 0 is.
    # short and emitted twice per.
    # is the single char `3`,.
    # live in the cheapest.
    # base-3 encodings are.
    # are assigned by *depth*, so.
    # tree reads it most often;.
    # ``best_input_order`` searches.
    trash = _const(0) + "#v"  # pop the stack top into.
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends.

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b].

    def guard(i: int, body: str) -> str:
        r"""If bit i is 1, run ``body``; leaves the stack balanced."""
        return read(i) + "(" + trash + body + _ZERO + ")" + trash

    def guard_not(i: int, body: str) -> str:
        r"""If bit i is 0, run ``body``; leaves the stack balanced."""
        return read(i) + not_bit() + "(" + trash + body + _ZERO + ")" + trash

    # A table that ignores some of.
    # tree does not fold it away on.
    # *differ from the default*,.
    # half of them, each carrying a.
    # essential inputs collapses.
    # stream order -- every input.
    # the interface -- and an.
    # reads.
    essential = essential_inputs(truth_table, n) or [0]
    if len(essential) < n:
        table = read_at(truth_table, essential, n)
        width = len(essential)
    else:
        table, width = truth_table, n

    # Reads run in stream order;.
    # ``i`` goes into the name the.
    # A reduced tree tests only.
    # the leftover ones; ``perm``.
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    prog = "".join("?" + store(input_vars[depth_of[i]]) for i in range(n))

    # Default the result to the.
    # need an override block.
    default = "1" if table.count("1") >= table.count("0") else "0"
    prog += (_ONE if default == "1" else _ZERO) + store(result)

    # One decision tree instead of.
    # combo: rows that share a bit.
    # amortizing the ~19-char guard.
    # leaves the stack balanced, so.
    # their parent's body, and.
    # pruned.
    def override(combo: int) -> str:
        return (_ONE if table[combo] == "1" else _ZERO) + store(result)

    # ``truth_table`` is already.
    # wrapper calls this, so.
    # entry ``s`` names the depth.
    # the bit for that depth sits.
    # back through ``depth_of``.
    # agrees only when the.
    # like ``[0, 2]`` are exactly.
    slot_var = [input_vars[s] for s in essential]

    def build(rows: list[int], depth: int) -> str:
        if not rows:
            return ""
        if depth == width:
            return override(rows[0])  # rows are pruned, so it.
        bit = width - 1 - depth
        rows1 = [r for r in rows if (r >> bit) & 1]
        rows0 = [r for r in rows if not (r >> bit) & 1]
        sub1 = build(rows1, depth + 1)
        sub0 = build(rows0, depth + 1)
        return (guard(slot_var[depth], sub1) if sub1 else "") + (
            guard_not(slot_var[depth], sub0) if sub0 else ""
        )

    differing = [c for c in range(2**width) if table[c] != default]
    prog += build(differing, 0)

    prog += read(result) + "!"
    return prog


def nevermind(truth_table: str) -> str:
    r"""Build a Nevermind program computing the given truth table."""
    return best_input_order(truth_table, _nevermind_ordered)


def _nevermind_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Nevermind program; see :func:`nevermind`."""
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def leaf(level: int, row: int) -> list[str]:
        return [f"{'  ' * level}print,{truth_table[row]}"]

    def node(level: int, zero: list[str], one: list[str], _at: int) -> list[str]:
        indent = "  " * level
        var = f"${chr(ord('a') + perm[level])}"
        return [
            f"{indent}if,{var},==,0",
            *zero,
            f"{indent}endif",
            f"{indent}if,{var},==,1",
            *one,
            f"{indent}endif",
        ]

    lines += decision_tree_tokens(truth_table, leaf, node, collapse=True)
    return "\n".join(lines)


def _reorder_tt(tt: str, n: int) -> str:
    r"""Reorder truth table entries into the slot order the reduces expect."""
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    r"""Even-reduction block: select half the value pairs, keep all inputs."""
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


# Final odd-reduce block: the.
# queue [0, v0, 0, v1, 48, 48,.
# prev/curr the two remaining.
# drops the candidate the.
# the two 48s (48 + bit), and.
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
    r"""Pad a ``2**(n_effective - 1)``-entry truth table to ``n_effective``."""
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def between(truth_table: str) -> str:
    r"""Build a Between program computing the given truth table."""
    return best_input_order(truth_table, _between_ordered)


def _between_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Between program; see :func:`between`."""
    n = _validate_truth_table(truth_table)

    def first_row(path: list[int]) -> int:
        r"""Return the lowest table row ``path`` reaches."""
        row = 0
        for bit in path:
            row = row * 2 + bit
        return row << (n - len(path))

    def leaf_value(path: list[int]) -> int:
        return int(truth_table[first_row(path)])

    def constant(path: list[int]) -> bool:
        r"""Whether every row ``path`` reaches holds the same entry."""
        row = first_row(path)
        return len(set(truth_table[row : row + 2 ** (n - len(path))])) == 1

    def size(path: list[int]) -> int:
        if len(path) == n or constant(path):
            return 2
        return 1 + size([*path, 1]) + size([*path, 0])

    lines: list[str] = []
    for bit in range(n):
        lines.append(f"'{bit}'v.")
        lines.append(f"[{bit}]i.")
        lines.append(f"[{bit}]s|[{bit}]c.|")

    def emit(path: list[int], offset: int) -> int:
        # Must stop exactly where.
        # line numbers ``size``.
        # that folds here and not there.
        if len(path) == n or constant(path):
            lines.append(f"|{leaf_value(path)}|p.")
            lines.append(".x.")
            return offset + 2
        zero_addr = offset + 1 + size([*path, 1])
        lines.append(f"|{zero_addr}|f([{perm[len(path)]}]=|0|)")
        offset += 1
        offset = emit([*path, 1], offset)
        return emit([*path, 0], offset)

    emit([], len(lines))
    return "\n".join(lines)


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    r"""Odd-reduction block: retire one input, reduce, keep the rest."""
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added.
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


def _taglate_reduced_table(truth_table: str, n: int, used: list[int]) -> str:
    r"""Rewrite the function over just the inputs in ``used``."""
    width = len(used)
    return "".join(
        truth_table[
            sum(
                1 << (n - 1 - i)
                for slot, i in enumerate(used)
                if (row >> (width - 1 - slot)) & 1
            )
        ]
        for row in range(2**width)
    )


def taglate(truth_table: str) -> str:
    r"""Build a Taglate program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of.
    # taglate's cost is almost all.
    # -- the seed alone is.
    # drops a whole tier.
    # ignored inputs anyway,.
    # which leaves the queue.
    # arithmetic is undisturbed.
    # .
    used = essential_inputs(truth_table, n)
    # A constant table depends on.
    # valid table there is -- a.
    # table, which is not a valid.
    if not used and n > 1:
        used = [0]
    # An odd-sized dependency set.
    # ghost-pad itself and expect.
    # widen it by one adjacent.
    if len(used) % 2 == 1 and len(used) > 1:
        if used[-1] + 1 < n:
            used = [*used, used[-1] + 1]
        elif used[0] > 0:
            used = [used[0] - 1, *used]
    if 0 < len(used) < n and (len(used) % 2 == 0 or len(used) == 1):
        reduced = _taglate_reduced_table(truth_table, n, used)
        seed, commands = taglate(reduced).split("\n", 1)
        discard = "h" + "e" * len(seed) + "f"
        # Odd ``n`` above 1 is called.
        # one more input to read and.
        ghost = 1 if n % 2 == 1 and n > 1 else 0
        leading = used[0] + ghost
        reads = commands.split("h")
        parts = [reads[0] + "h"]
        for read, (before, after) in enumerate(pairwise(used), start=1):
            between = "h" + "e" * (len(seed) + read) + "f"
            parts.append(between * (after - before - 1))
            parts.append(reads[read] + "h")
        parts.append(reads[-1])
        trailing = n - used[-1] - 1
        return seed + "\n" + discard * leading + "".join(parts) + "h" * trailing

    if n == 1:
        base = _ASCII_ZERO + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    # For odd n, prepend a fake.
    # on a separator.
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
        # Drop the first n_eff-2.
        # remaining two inputs so the.
        # w1, 48, 48, prev, curr].
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


# Cells in a Clockwise leaf:.
# with the '+' that set their.
# in this height -- '0' pads.
# node always end on the same.
_CLOCKWISE_LEAF = 14

# Rows one level of the tree.
_CLOCKWISE_LEVEL = 9


def clockwise(truth_table: str, width: int | None = None) -> str:
    r"""Build a Clockwise program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    def constant(bit: int, combo: int) -> bool:
        r"""Whether every row this subtree covers agrees."""
        span = 2 ** (n - bit)
        start = combo << (n - bit)
        return len(set(truth_table[start : start + span])) == 1

    def leafy(bit: int, combo: int) -> bool:
        r"""Whether this subtree stops here, either at ``n`` or on a fold."""
        return bit == n or (bit > 0 and constant(bit, combo))

    shapes: dict[tuple[int, int, int], tuple[int, int]] = {}

    def shape(bit: int, combo: int, stacked: int) -> tuple[int, int]:
        r"""Report the columns and rows this subtree needs, spine on the right."""
        key = (bit, combo, stacked)
        if key not in shapes:
            if leafy(bit, combo):
                shapes[key] = (1, _CLOCKWISE_LEVEL * (n - bit) + _CLOCKWISE_LEAF)
            else:
                one = shape(bit + 1, (combo << 1) | 1, stacked)
                zero = shape(bit + 1, combo << 1, stacked)
                if bit < stacked:
                    shapes[key] = (
                        max(3, one[0] + 1, zero[0]),
                        _CLOCKWISE_LEVEL + one[1] + zero[1],
                    )
                else:
                    step = max(2, zero[0])
                    shapes[key] = (
                        step + max(1, one[0] - 1) + 1,
                        _CLOCKWISE_LEVEL + max(one[1], zero[1]),
                    )
        return shapes[key]

    def spine(stacked: int) -> int:
        r"""Return the root's column with ``stacked`` levels stacked."""
        root = shape(0, 0, stacked)[0]
        if 2 ** (n + 1) >= 8 and (width is None or width >= 9):
            root = max(root, 8)
        return root

    # The shallow levels are the.
    # displaces ``2 ** (n - bit)``.
    # root and takes as few levels.
    # floor stacks everything,.
    stacked = 0
    if width is not None:
        for count in range(n + 1):
            stacked = count
            if spine(count) + 1 <= width:
                break

    root = spine(stacked)
    # What the hoist's floor added.
    # relative, so the tree's.
    # are trimmed, so a cell.
    # slack on the root's own.
    # against the left edge and.
    # where the zero-branch's.
    slack = root - shape(0, 0, stacked)[0]
    hoist = root >= 8
    # Hoisting the root's reads.
    # the tree starts that much.
    shift = 7 if hoist else 0

    cells: dict[tuple[int, int], str] = {}
    exits: list[tuple[int, int]] = []

    def place(node: tuple[int, int], ch: str) -> None:
        r"""Write ``ch`` at ``node``, refusing to land on an occupied cell."""
        if node in cells:
            raise AssertionError(f"two cells at {node}: {cells[node]!r} and {ch!r}")
        cells[node] = ch

    def leaf(x: int, y: int, combo: int) -> None:
        r"""Print the answer at ``(x, y)`` and leave by the row it ends on."""
        # Emit the answer as the ASCII.
        # Seven ';' print one bit each,.
        # prints acc % 2 -- so a '+'.
        # into the bit that position.
        # 0110001, which differ only in.
        # the same shape apart from one.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(_ASCII_ZERO + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # A '?' turns by acc.
        # left onto its exit row.
        # depending on the digit, so.
        # tracking it: 'S+' is uniform.
        # extra 'S' pads the shorter.
        # which is what keeps the two.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)
        exits.append((x, y + _CLOCKWISE_LEAF - 1))

    def build(bit: int, x: int, y: int, combo: int) -> None:
        r"""Lay the subtree for ``combo`` at ``bit``, spine head at ``(x, y)``."""
        if leafy(bit, combo):
            # Every row below here agrees,.
            # change the answer and this.
            # The reads are not optional,.
            # count depended on its table.
            # several from one stream, and.
            # clockwise reads *inside* the.
            # still spend their ``S`` and.
            # the ``?`` that would have.
            # is padded with an ``S`` -- a.
            # reads leave at 0 or 1 -- so.
            # unfolded one would, and a.
            for level in range(n - bit):
                place((x, y + _CLOCKWISE_LEVEL * level), "S")
                for i in range(7):
                    place((x, y + _CLOCKWISE_LEVEL * level + 1 + i), ".")
                place((x, y + _CLOCKWISE_LEVEL * level + 8), "S")
            leaf(x, y + _CLOCKWISE_LEVEL * (n - bit), combo << (n - bit))
            return
        if bit == 0 and hoist:
            # The seven reads sit on row 0,.
            # node's ``?`` is all that is.
            for i in range(7):
                place((x - 7 + i, 0), ".")
        else:
            place((x, y), "S")
            for i in range(7):
                place((x, y + 1 + i), ".")
        place((x, y + 8), "?")
        one = shape(bit + 1, (combo << 1) | 1, stacked)
        zero = shape(bit + 1, combo << 1, stacked)
        # A stacked node displaces a.
        # zero-branch below the.
        # past the zero-branch's span.
        step = 1 if bit < stacked else max(2, zero[0])
        xn = x - step - (slack if bit == 0 else 0)
        # b=1: '?' turns the pointer.
        place((xn, y + 8), " ")
        place((xn - 1, y + 8), "R")
        place((xn - 1, y + 7), "R")
        place((xn, y + 7), "R")
        build(bit + 1, xn, y + 9, (combo << 1) | 1)
        below = one[1] if bit < stacked else 0
        # b=0: fall down this column,.
        build(bit + 1, x, y + 9 + below, combo << 1)

    build(0, root, 1 - shift, 0)

    for x, y in exits:
        # Drop a passing path back to.
        # of a leaf further left along.
        place((x - 1, y), "S")
    for y in sorted({y for _, y in exits}):
        # The ring closes up column 0:.
        # zero accumulator, and the '+'.
        # so the climb passes every.
        place((0, y), "!")
        place((0, y - 1), "+")
    place((root, 0), "R")

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), ch in cells.items():
        # ``span`` and ``height`` are.
        # test holds for every one of.
        # a future caller's stray.
        if 0 <= x < span and 0 <= y < height:  # pragma: no branch - see above
            grid[y][x] = ch
    # The grid is a fixed-size.
    # into, so a row's trailing.
    # short rows itself, so.
    return "\n".join("".join(row).rstrip() for row in grid)


def container(truth_table: str) -> str:
    r"""Build a Container program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container.
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches.
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
    # OUT is 48 plus one ``+1`` per.
    # table pays for nearly every.
    # line each and starts from 49,.
    # complement, and since ``S``.
    # the container's clamp at zero.
    # smaller wins; ties keep the.
    ones = truth_table.count("1")
    invert = ones > 2**n - ones
    lines.append("OUT:")
    lines.append(f"+{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n}")
    lines.append(f"-{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n + 1}")
    wanted = "0" if invert else "1"
    delta = "-1" if invert else "+1"
    for row in range(2**n):
        if truth_table[row] == wanted:
            lines.append(f"{delta} S{row}>=Gout")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def bit_tilde(truth_table: str) -> str:
    r"""Build a bit~ program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of.
    # cost here is per *one-row*.
    # pre-copies one cell per input.
    # dropping an input removes.
    # reads stay -- one ``)`` per.
    # ignored inputs are read into.
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)

    table, use_complement = _maybe_complement(reduced)
    # Reads keep their original.
    # minterm's ``level`` indexes.
    width = len(used)

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
        r"""Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
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

    # A fixed window: three cells.
    # through and one indicator the.
    # The whole scratch area is ``3.
    # table holds, because a row is.
    # reuses the cells.
    base = 8 * n
    chain = [(base + 3 * slot, base + 3 * slot + 1) for slot in range(width)]
    indicator = [base + 3 * slot + 2 for slot in range(width)]
    result = base + 3 * width

    if 0 not in used:
        # ``(`` prints cell 7's window,.
        # has to be consumed whether or.
        # input 0 is essential the.
        # effect; when it is *ignored*.
        # output comes out as the input.
        # the 16 tables at ``n <= 3``.
        move(7)
        prog.append("{ ~ }")
        pos = 7

    def set_result() -> None:
        nonlocal pos
        move(result)
        prog.append("{ ~ } ~")
        pos = result

    def node(level: int) -> None:
        nonlocal pos
        if level == width:
            set_result()
            return
        cell = indicator[level]
        move(cell)
        prog.append("{")
        pos = cell
        node(level + 1)
        move(cell)
        prog.append("~")
        pos = cell
        prog.append("}")

    # Each slot threads its input.
    # are independent and advance.
    source = [8 * i + 7 for i in used]
    turn = [0] * width
    for k in range(2**width):
        one_row = table[k] == "1"
        for slot, i in enumerate(used):
            # only one-rows' indicators are.
            # still run to consume the.
            if not one_row and not (slot == 0 and i == 0 and k == 0):
                continue
            # The indicator is reused, and.
            # never entered the body that.
            # unconditionally rather than.
            # previous row consumed.
            # so a stale 1 here would.
            # without the spaces the other.
            # emitted once per (one-row,.
            # and the interpreter ignores.
            cell = indicator[slot]
            move(cell)
            prog.append("{~}")
            pos = cell
            nxt = chain[slot][turn[slot]]
            copy2(source[slot], cell, nxt)
            source[slot] = nxt
            turn[slot] ^= 1
            if not (k >> (width - 1 - slot)) & 1:
                move(cell)
                prog.append("~")
                pos = cell
        if one_row:
            node(0)

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


def forbin(truth_table: str) -> str:
    r"""Build a Forbin program computing the given truth table."""
    return best_input_order(truth_table, _forbin_ordered)


def _forbin_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Forbin program; see :func:`forbin`."""
    n = _validate_truth_table(truth_table)

    lines: list[str] = ["main {"]
    bits: list[str] = []
    for i in range(n):
        reads = [f"i{i}_{j}" for j in range(8)]
        lines.append(f"  {','.join(reads)} = (in 0);")
        bits.append(reads[7])

    def emit(level: int, row: int, depth: int) -> None:
        indent = "  " * depth
        if level == n or len(set(truth_table[row : row + 2 ** (n - level)])) == 1:
            byte = _ASCII_ZERO + int(truth_table[row])
            lines.append(f"{indent}out {','.join(format(byte, '08b'))};")
            lines.append(f"{indent}return 0;")
            return
        bit = bits[perm[level]]
        lines.append(f"{indent}for _:!{bit}..{bit} {{")
        emit(level + 1, row + 2 ** (n - 1 - level), depth + 1)
        lines.append(f"{indent}}}")
        emit(level + 1, row, depth)

    emit(0, 0, 1)
    lines.append("}")
    return "\n".join(lines)


def _suptiftam_bit(i: int) -> str:
    r"""Variable name for input bit ``i`` (identifiers must be."""
    if i < 25:
        return chr(ord("b") + i)
    return "b" + _suptiftam_bit(i - 25)


def suptiftam(truth_table: str) -> str:
    r"""Build a Suptiftam program computing the given truth table."""
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

    # One minterm per row selected,.
    # zeros and the sum inverted --.
    # minterms it saves.
    # A table that ignores some of.
    # minterm costs four lines *per.
    # row, dropping an input.
    # Every input keeps its read.
    # interface); an ignored one is.
    def literal(i: int, negated: bool) -> str:  # noqa: FBT001 - a literal's sign
        return f"%-[1]{names[i]}%" if negated else names[i]

    def product(factors: list[str]) -> str:
        # ``p=1`` seeds the row, then.
        # seed can sit here rather than.
        # literal only names a factor.
        lines.append("p=1")
        for factor in factors:
            lines.extend(["prod=0", f"a={factor}", "mulStep(:p:)if(p)", "p=prod"])
        return "p"

    def accumulate(row: str) -> None:
        lines.append(f"sum=%+[sum]{row}%")

    _used, _width, invert = minterm_sum(truth_table, literal, product, accumulate)
    lines.append("term=%-[1]sum%" if invert else "term=sum")
    return "\n".join(lines)


# A leaf is exactly as wide as.
# leaves abut and the tree.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    r"""Paint the decision tree onto a sparse ``(x, y) -> character`` grid."""
    cells: dict[tuple[int, int], str] = {}

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    leaf_top = 2 + 4 * n

    def leaf(slot: int, bit: str) -> int:
        r"""Draw the leaf for ``bit`` in column slot ``slot``; return its."""
        middle = _FLOWCHART_PITCH * slot + 2
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        put(middle - 1, leaf_top + 2, "\\ \\")
        cells[(middle, leaf_top + 3)] = "│"
        put(middle - 2, leaf_top + 4, "(( ))")
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        r"""Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = 4 + 4 * depth
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
        return middle

    # Slots are handed out left to.
    # folded subtree takes one.
    # would have filled -- the.
    slots = [0]

    def walk(lo: int, hi: int, depth: int) -> int:
        r"""Draw the subtree for ``truth_table[lo:hi]``; return its column."""
        if len(set(truth_table[lo:hi])) == 1:
            # Constant: no branch below.
            # is a leaf.
            # depth, so the rail from the.
            # fold skipped: the rows are a.
            # goes away.
            # .
            # The *reads* those levels.
            # program must consume its.
            # -- the reads are the.
            # them left the caller's.
            # skipped level puts its ``/.
            # runs straight through it into.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(4 * depth + 2, leaf_top):
                cells.setdefault((middle, y), "│")
            for skipped in range(depth, n):
                put(middle - 1, 4 * skipped + 2, "/ /")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    r"""Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _flowchart_stacked(truth_table: str) -> dict[tuple[int, int], str]:
    r"""Paint the tree with its subtrees stacked rather than side by side."""
    n = (len(truth_table) - 1).bit_length()
    # Columns 0..n-1 are the.
    # on ``spine``, far enough east.
    # them.
    spine = n + 2
    cells: dict[tuple[int, int], str] = {}

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    def reads(y: int, count: int) -> int:
        r"""Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            put(spine - 1, y, "/ /")
            cells[(spine, y + 1)] = "│"
            y += 2
        return y

    def leaf(y: int, depth: int, bit: str) -> int:
        r"""Draw the leaf for ``bit``, entered at ``(spine, y)``."""
        y = reads(y, n - depth)
        put(spine - 1, y, "[ }" if bit == "1" else "{ ]")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "\\ \\")
        cells[(spine, y + 3)] = "│"
        put(spine - 2, y + 4, "(( ))")
        return y + 5

    def walk(lo: int, hi: int, depth: int, y: int) -> int:
        r"""Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        if len(set(truth_table[lo:hi])) == 1:
            return leaf(y, depth, truth_table[lo])
        put(spine - 1, y, "/ /")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "< >")
        # b=1: east out of the switch,.
        cells[(spine + 2, y + 2)] = "┐"
        cells[(spine + 2, y + 3)] = "┘"
        cells[(spine + 1, y + 3)] = "─"
        cells[(spine, y + 3)] = "┌"
        half = (hi - lo) // 2
        below = walk(lo + half, hi, depth + 1, y + 4)
        # b=0: west to this depth's own.
        # one-branch drew, then east.
        for x in range(depth + 1, spine - 1):
            cells[(x, y + 2)] = "─"
        cells[(depth, y + 2)] = "┌"
        for row in range(y + 3, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        for x in range(depth + 1, spine):
            cells[(x, below)] = "─"
        cells[(spine, below)] = "┐"
        return walk(lo, lo + half, depth + 1, below + 1)

    walk(0, len(truth_table), 0, 2)
    put(spine - 1, 0, "( )")
    cells[(spine, 1)] = "│"
    return cells


def flowchart(truth_table: str, width: int | None = None) -> str:
    r"""Build a Flowchart program computing the given truth table."""
    _validate_truth_table(truth_table)
    flat = _flowchart_render(_flowchart_cells(truth_table))
    if width is None or max(len(line) for line in flat.split("\n")) <= width:
        return flat
    stacked = _flowchart_render(_flowchart_stacked(truth_table))
    if max(len(line) for line in stacked.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return stacked
    return flat


def _dinac_name(i: int) -> str:
    r"""Return the variable holding input ``i``, per the spec's name regex."""
    return f"c{i}"


def _dinac_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit the tree that splits on ``perm[k]`` at level ``k``."""
    n = _validate_truth_table(truth_table)

    def leaf(_level: int, row: int) -> list[str]:
        return [f"OUT '{truth_table[row]}"]

    def node(level: int, zero: list[str], one: list[str], _at: int) -> list[str]:
        # An IF needs its ELSE (the.
        # each branch needs a non-empty.
        # emitted -- there is no.
        head = f"IF {_dinac_name(perm[level])} = '1"
        body = [f"    {line}" for line in one]
        body += ["ELSE"]
        body += [f"    {line}" for line in zero]
        return [head, *body]

    # Every input is read whatever.
    # interface, and a folded tree.
    # bit on the input stream.
    reads = [f"SET {_dinac_name(i)}:\\0\nIN {_dinac_name(i)}" for i in range(n)]
    tree = decision_tree_tokens(truth_table, leaf, node, collapse=True)
    return "\n".join([*reads, *tree])


def dinac(truth_table: str) -> str:
    r"""Build a DINAC program computing the given truth table."""
    return best_input_order(truth_table, _dinac_ordered)
