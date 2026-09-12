r"""Boolean-function generators for tape-based languages."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import permutations

from esolangs.exceptions import GeneratorCapError

# rotfuck and six_five each own.
# per-position rotation, an.
# dimensional keeps one for its.
# here so this module stays the.
from esolangs.tools.boolean.dimensional import dimensional, dimensional_tree
from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    best_input_order,
    decision_tree_program,
    decision_tree_tokens,
    essential_inputs,
    read_at,
    stored_inputs,
)
from esolangs.tools.boolean.rotfuck import rotfuck
from esolangs.tools.boolean.six_five import six_five
from esolangs.tools.boolean.slow_acv_mammalian import slow_acv_mammalian

__all__ = [
    "basicfuck",
    "bf_tree",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "dimensional",
    "dimensional_tree",
    "factor",
    "jaune",
    "jaune_multiply",
    "painfuck",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian",
    "suffolk",
    "three_d_brainfuck",
]


@dataclass
class _Cmd:
    r"""A line emitted verbatim, apart from its ``goto`` placeholder."""

    text: str


@dataclass
class _If:
    r"""An ``if <char> goto <label>`` line, resolved once labels are known."""

    char: int
    label: int


@dataclass
class _MoveLeft:
    r"""An ``if <char> move left`` line that also *defines* ``label``."""

    char: int
    label: int


@dataclass
class _Out:
    r"""A marker defining output routine ``which``; it emits no line itself."""

    which: int


@dataclass
class _End:
    r"""The trailing blank line every program ends on."""


_Entry = _Cmd | _If | _MoveLeft | _Out | _End


def brainif(truth_table: str) -> str:
    r"""Build a BrainIf program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    entries: list[_Entry] = []
    # The answer byte goes on cell.
    # far end back down.
    # are still zero, where one.
    # cell -- no digit is around to.
    entries += [_Cmd(f"if {v} increment") for v in range(_ASCII_ZERO)]
    entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
    entries += [_Cmd("if 0 move right") for _ in range(n - 1)]

    counter = [0]

    def build(rows: list[int], k: int) -> list[_Entry]:
        r"""Emit the subtree for ``rows``, entered with the pointer on cell."""
        rest = n - (k - 1)
        if rest == 0 or len({truth_table[row] for row in rows}) == 1:
            # Consume the inputs this path.
            # the pointer the rest of the.
            # answer is a 1 and join the.
            # a program whose input count.
            # a caller feeding several.
            out: list[_Entry] = []
            for _ in range(rest):
                out.append(_Cmd("if 0 input"))
                out.append(_Cmd(f"if {_ASCII_ZERO} move left"))
                out.append(_Cmd(f"if {_ASCII_ONE} move left"))
            if int(truth_table[rows[0]]):
                out.append(_Cmd(f"if {_ASCII_ZERO} increment"))
            out.append(_Cmd(f"if {_ASCII_ZERO} goto OUT0"))
            out.append(_Cmd(f"if {_ASCII_ONE} goto OUT0"))
            return out
        # Level ``k`` reads input ``k -.
        # bit it selects is the table's.
        # the reads are in input order.
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        sub0 = build(g0, k + 1)
        sub1 = build(g1, k + 1)
        return [
            _Cmd("if 0 input"),
            _If(_ASCII_ZERO, l0),
            _If(_ASCII_ONE, l1),
            _MoveLeft(_ASCII_ZERO, l0),
            *sub0,
            _MoveLeft(_ASCII_ONE, l1),
            *sub1,
        ]

    entries += build(list(range(2**n)), 1)
    # One shared tail: the answer.
    # this is two lines rather than.
    entries.append(_Out(0))
    entries.append(_Cmd(f"if {_ASCII_ZERO} output"))
    entries.append(_Cmd(f"if {_ASCII_ONE} output"))
    entries.append(_End())

    # resolve labels from the.
    # no line, so the marker's.
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
                # keep the line's own guard: a.
                # cell holding 48 or 49, so it.
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
            # _End, the trailing blank line.
            # than a fifth ``isinstance``.
            # ``_Entry`` without a branch.
            # this to ``_End``, and a wider.
            _: _End = entry
            lines.append("")
    return "\n".join(lines)


def circlefuck(truth_table: str) -> str:
    r"""Build a Circlefuck program computing the given truth table."""
    # Validated here rather than.
    # a *byte* table, where a.
    # carry the boolean generators'.
    _validate_truth_table(truth_table)
    return circlefuck_byte([_ASCII_ZERO + int(bit) for bit in truth_table])


def circlefuck_byte(truth_table: Sequence[int]) -> str:
    r"""Build a Circlefuck program computing a byte-valued function."""
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    return _best_byte_order(truth_table, n)


def _permute_byte_table(truth_table: Sequence[int], perm: tuple[int, ...]) -> list[int]:
    r"""Return ``truth_table`` re-indexed so input ``perm[i]`` sits at."""
    n = len(perm)
    out = [0] * len(truth_table)
    for row in range(len(truth_table)):
        source = 0
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            source |= bit << (n - 1 - perm[i])
        out[row] = truth_table[source]
    return out


def _best_byte_order(truth_table: Sequence[int], n: int) -> str:
    r"""Return the shortest program over every input order."""
    best = _circlefuck_ordered(list(truth_table), tuple(range(n)))
    if n < 2:
        return best
    if n > _ORDER_SEARCH_MAX:
        return min(best, _circlefuck_greedy(truth_table, n), key=len)
    for perm in permutations(range(n)):
        if perm == tuple(range(n)):
            continue
        candidate = _circlefuck_ordered(_permute_byte_table(truth_table, perm), perm)
        if len(candidate) < len(best):
            best = candidate
    return best


def _circlefuck_greedy(truth_table: Sequence[int], n: int) -> str:
    r"""Pick an order level by level above the exhaustive cap."""
    remaining = list(range(n))
    order: list[int] = []
    while remaining:
        best_input = max(
            remaining,
            key=lambda i: _constant_subtree_count(truth_table, n, [*order, i]),
        )
        order.append(best_input)
        remaining.remove(best_input)
    perm = tuple(order)
    return _circlefuck_ordered(_permute_byte_table(truth_table, perm), perm)


def _constant_subtree_count(
    truth_table: Sequence[int], n: int, prefix: list[int]
) -> int:
    r"""Count the subtrees that come out constant after splitting on."""
    buckets: dict[int, set[int]] = {}
    for row in range(len(truth_table)):
        key = 0
        for i in prefix:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        buckets.setdefault(key, set()).add(truth_table[row])
    return sum(1 for values in buckets.values() if len(values) == 1)


def _circlefuck_ordered(truth_table: list[int], perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Circlefuck program; see."""
    n = len(perm)
    prog: list[str] = []

    def emit(c: str) -> None:
        prog.append(c)

    for _ in range(n):
        emit(",")
        prog.extend("-" * _ASCII_ZERO)
        emit(">")
    prog.pop()  # the trailing ">" would leave.

    def move(source: int, target: int) -> None:
        r"""Walk the pointer from cell ``source`` to cell ``target``."""
        step = ">" if target > source else "<"
        prog.extend(step * abs(target - source))

    def span(k: int, row: int) -> range:
        r"""Return the table rows the subtree at ``(k, row)`` stands for."""
        step = 2 ** (n - 1 - k)
        return range(row, len(truth_table), step)

    def build(k: int, row: int, cell: int) -> None:
        r"""Emit the subtree at level ``k`` with the pointer over ``cell``."""
        if k < 0:
            value = truth_table[row]
            if value:
                prog.extend("+" * value)
            emit(".")
            emit("@")
            return
        if len({truth_table[r] for r in span(k, row)}) == 1:
            # Every row this subtree could.
            # would branch on cannot change.
            # unconditional, above the.
            # consumes its input the same.
            # .
            # The ``[-]`` is what a.
            # emitted inside each ``[`` on.
            # its value on a cleared cell.
            # levels and so must clear the.
            # pointer still holds an input.
            # prints one too high.
            emit("[-]")
            build(-1, row, cell)
            return
        target = perm[k]
        move(cell, target)
        emit("[")
        emit("[-]")
        # Both arms leave the pointer.
        # each arm re-aims from.
        # the tested cell, so the loop.
        # reached with the pointer back.
        # returns it.
        # before the branch is what.
        build(k - 1, row + 2 ** (n - 1 - k), target)
        emit("]")
        build(k - 1, row, target)

    build(n - 1, 0, n - 1)
    return "".join(prog)


def brainfuck(truth_table: str) -> str:
    r"""Build a brainfuck program computing the given truth table."""
    return bf_tree(truth_table)


# : Digits :func:`factor`.
# : measured worst case at ten.
# : printing once below itself,.
# : cut by 4.3x together: n=10.
# : n=10 dense to 77278 (was.
# : construction with room and.
# : Past it the caller passes.
# :.
# : The budget is deliberately.
# : worst case: n=11 parity now.
# : 952366 and was refused.
# : is what an arity lift would.
# : question for the contract.
# :.
# : Sized to the construction's.
# : boolean suite currently.
# : a five-input suite and.
# : n=6, so the budget had to.
# : one does not.
# : case, and an n=6 program.
#: all 64 rows.
_DEFAULT_MAX_DIGITS = 500_000

_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}


def _factor_encode(code: str) -> int:
    r"""Encode a brainfuck program as the Factor integer for it."""
    from sympy import isprime

    number = 1
    candidate = 2
    i = 0
    while i < len(code):
        residue = _BF_RESIDUE[code[i]]
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        prime = candidate
        while not (prime % 11 == residue and isprime(prime)):
            prime += 1
        number *= prime ** (j - i)
        candidate = prime + 1
        i = j
    return number


def factor(truth_table: str, *, max_digits: int = _DEFAULT_MAX_DIGITS) -> str:
    r"""Build a Factor program computing the given truth table."""
    number = _factor_encode(brainfuck(truth_table))
    # Estimated from the bit length.
    # up, so it never.
    # integer without paying for.
    digits = int(number.bit_length() * 0.30103) + 1
    if digits > max_digits:
        raise GeneratorCapError(
            f"the Factor boolean generator's encoded integer needs about "
            f"{digits} digits, over the {max_digits}-digit limit this call "
            "allows -- try a sparser table, or fewer inputs",
        )
    limit = sys.get_int_max_str_digits()
    if digits <= limit:
        return str(number)
    # Process-global, so it is.
    sys.set_int_max_str_digits(digits + 1)
    try:
        return str(number)
    finally:
        sys.set_int_max_str_digits(limit)


def three_d_brainfuck(truth_table: str) -> str:
    r"""Build a 3D Brainfuck program computing the given truth table."""
    return brainfuck(truth_table).translate(str.maketrans("><", "ew"))


# The interpreter's two.
# scans them: Painfuck source.
# the intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str) -> str:
    r"""Build a Painfuck program computing the given truth table."""
    code = (
        brainfuck(truth_table)
        .replace(">", "rl")
        .replace("<", "l")
        .replace("+", "ps")
        .replace("-", "s")
        .replace("[", "a")
        .replace("]", "b")
        .replace(",", "j")
        .replace(".", "u")
    )
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                out.append(cycle[(p - k) % len(cycle)])
                k += 1
                break
        else:
            # every command the brainfuck.
            # in _CYCLES, so this branch is.
            raise ValueError(
                f"Painfuck command {char!r} is not in a cycle"
            )  # pragma: no cover
    return "".join(out)


def bf_tree(truth_table: str) -> str:
    r"""Build a decision-tree brainfuck program for the given truth table."""
    return decision_tree_program(truth_table, ">", "<")


def basicfuck(truth_table: str) -> str:
    r"""Build a Basicfuck program computing the given truth table."""
    return best_input_order(truth_table, _basicfuck_ordered)


def _basicfuck_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Basicfuck program; see :func:`basicfuck`."""
    n = _validate_truth_table(truth_table)

    lines = ["#basicfuck t=unbounded r=0~255 o=wrap"]
    lines.append("#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out")
    for i in range(1, n + 1):
        lines.append(f"read -> a{i} ;")
        lines.append(f"a{i} -= 48 ;")

    def leaf(level: int, row: int) -> list[str]:
        indent = "  " * level
        value = int(truth_table[row])
        return [f"{indent}out += {_ASCII_ZERO + value} ;\n{indent}write <- out ;\n"]

    def node(level: int, zero: list[str], one: list[str], _at: int) -> list[str]:
        # The one-side is emitted.
        # neighbour, so the two arms.
        indent = "  " * level
        var = f"a{perm[level] + 1}"
        return [
            f"{indent}if ({var}) {{\n",
            *one,
            f"{indent}}}\n",
            f"{indent}if !({var}) {{\n",
            *zero,
            f"{indent}}}\n",
        ]

    tree = decision_tree_tokens(truth_table, leaf, node, collapse=True)
    lines.append("".join(tree).rstrip("\n"))
    return "\n".join(lines)


def sbleq(truth_table: str) -> str:
    r"""Build an S*bleq program computing the given truth table."""
    _validate_truth_table(truth_table)
    return best_input_order(truth_table, _sbleq_hoisted)


def _sbleq_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's hoisted S*bleq program; see :func:`sbleq`."""
    n = _validate_truth_table(truth_table)
    neg49, d48 = 0, 1
    vbase = 4
    nxtbase = vbase + n
    del d48

    # (a operand, b operand, kind,.
    # offsets made absolute below,.
    reads: list[tuple[int, int, str, int]] = [
        (vbase + i, -2, "nxt", i) for i in range(n)
    ]

    def leaf(_level: int, row: int) -> list[tuple[int, int, str, int]]:
        return [(-3, 1 + int(truth_table[row]), "out", 0), (0, 0, "halt", 0)]

    def node(
        level: int,
        zero: list[tuple[int, int, str, int]],
        one: list[tuple[int, int, str, int]],
        at: int,
    ) -> list[tuple[int, int, str, int]]:
        # A branch spends one.
        # one-side starts just past.
        # The walker hands that index.
        # reserved a slot and.
        target = 3 * (at + 1 + len(zero))
        return [(vbase + perm[level], neg49, "one", target), *zero, *one]

    instructions = reads + decision_tree_tokens(
        truth_table,
        leaf,
        node,
        parent_width=1,
        start=len(reads),
        collapse=True,
    )

    onebase = nxtbase + n
    data_base = 3 * len(instructions)

    # ``one`` instructions carry.
    # holds those targets in the.
    ones: list[int] = []

    cells: list[int] = []
    for a, b, kind, arg in instructions:
        if kind == "out":
            cells += [-3, data_base + b, 0]
        elif kind == "halt":
            cells += [0, 0, data_base + 3]
        elif kind == "nxt":
            cells += [data_base + a, -2, data_base + nxtbase + arg]
        else:
            slot = len(ones)
            ones.append(arg)
            cells += [data_base + a, data_base + b, data_base + onebase + slot]

    data = (
        [-_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, -1]
        + [0] * n
        + [3 * (i + 1) for i in range(n)]
        + ones
    )
    cells += data
    return " ".join(map(str, cells))


# ROTfuck rotates the whole.
# decision tree does not.
# the *rotated* program, at a.
# The construction below is the.
# interpreter: each ``[`` body.
# brackets), and the closing.
# encoded so that the.
# .
# A block is ``[ body ]`` at.
# satisfies ``len(body) + 1 ≡ 0.
# .
# - skip path (cell == 0): the.
# ``]`` at depth 1, and lands.
# - body path (cell != 0): the.
# ends on the tested cell,.
# shows ``rot^len(body)(']')``.
# does not fire on the nonzero.
#   ``q + 1 ≡ p + 1 (mod 8)``.
# .
# Both paths therefore.
# so the rest of the program.
# relative offset ``j`` must.
# the ``[``-fire seek (at state.
# .
# The generator is a.
# indirection: each input bit.
# (cell ``n + i``, set to 1).
# ``mc_k``; one block per.
# ``2n + 1 + 2**n + k``) iff.
# input is ``k``; and blocks.
# result cell, which is printed.


def jaune(truth_table: str) -> str:
    r"""Build a Jaune program computing the given truth table."""
    return best_input_order(truth_table, _jaune_ordered)


def _jaune_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Jaune program; see :func:`jaune`."""
    n = _validate_truth_table(truth_table)
    label = [1]

    def fresh() -> int:
        label[0] += 1
        return label[0]

    def move(frm: int, to: int) -> str:
        return ">" * (to - frm) if to >= frm else "<" * (frm - to)

    stored = stored_inputs(truth_table, perm)
    # Reads run in input order;.
    # the kept bits occupy a.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    for i in range(n):
        reads += "v"
        if i in stored:
            cell_of[i] = slot
            slot += 1
            reads += ">"
    # A clobbered read leaves its.
    # reads finish on is blank only.
    # whole-table constant prints.
    # more when the final read.
    scratch = slot
    if n and (n - 1) not in stored:
        reads += ">"
        scratch = slot + 1

    def leaf(value: str, held: int | None, end: int) -> str:
        want = int(value)
        have = 0 if held is None else held
        adjust = "+" * (want - have) if want >= have else "-" * (have - want)
        return adjust + "^" + f"+{end}?"

    def node(
        level: int, lo: int, hi: int, entry: int, held: int | None, end: int
    ) -> str:
        if level == n or len(set(truth_table[lo:hi])) == 1:
            return leaf(truth_table[lo], held, end)
        # A clobbered input has no cell.
        # answer, so the two halves of.
        # descending into either one is.
        # half, which keeps the row.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held, end)
        cell = cell_of[perm[level]]
        then_lbl = fresh()
        mid = (lo + hi) // 2
        then = node(level + 1, mid, hi, cell, 1, end)
        else_ = node(level + 1, lo, mid, cell, 0, end)
        return move(entry, cell) + f"{then_lbl}?{else_}{then_lbl}:{then}"

    end = fresh()
    return reads + node(0, 0, 2**n, scratch, None, end) + f"{end}:."


def jaune_multiply() -> str:
    r"""Build a Jaune program reading two decimal numbers and printing."""
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional.
    # read the first operand until.
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6;.
    cmd("2!")  # a zero (the sentinel) exits.
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1.
    cmd("2:")  # first operand done; the '*'.
    pos = 1
    move(4)
    # read the second operand until.
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13;.
    cmd("3!")  # a zero (the sentinel) exits.
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4.
    cmd("3:")  # second operand done; the '#'.
    pos = 1
    move(2)
    # multiply: while cell 2 != 0:.
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)


def _suffolk_candidate_cost(truth_table: str, wanted: str, *, invert: bool) -> int:
    r"""Return the rendered length of one non-constant Suffolk polarity."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    # ``const(gap, value)`` is.
    cost = 2 * _ASCII_ONE
    for i in range(n):
        gap = 2 + i
        cost += (gap + 1) * _ASCII_ZERO + gap + 2
    for i in range(n):
        gap = 2 + i
        raw_gap = 2 + n + i
        cost += gap + raw_gap + 2

    cells: list[int] = []
    next_cell = 2 + 2 * n
    for row in range(2**width):
        if reduced[row] != wanted:
            continue
        for slot in range(width):
            bit = (row >> (width - 1 - slot)) & 1
            literal = 2 + used[slot] if bit else 2 + n + used[slot]
            cost += literal + 1
        cost += next_cell + 1
        cells.append(next_cell)
        next_cell += 1

    cost += sum(cell + 1 for cell in cells)
    return cost + (5 if invert else 3)


def suffolk(truth_table: str) -> str:
    r"""Build a Suffolk program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    def const(gap: int, value: int) -> str:
        r"""``(gap '>'s then '!') * value`` builds ``value`` at that cell."""
        return (">" * gap + "!") * value

    if len({*truth_table}) == 1:
        # A constant table needs no.
        # interface: skipping them.
        # stream.
        reads = "".join(
            const(2 + i, _ASCII_ZERO) + ">" * (2 + i) + "," + "!" for i in range(n)
        )
        return const(1, _ASCII_ONE + int(truth_table[0])) + reads + ">" + "<" + "."

    # A table that ignores some of.
    # minterm costs one literal.
    # selected row -- so dropping.
    # rows that remain.
    # is read into its own scratch.
    # is exactly what the constant.
    # input.
    # "the ones that matter".
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    def evaluate(wanted: str, *, invert: bool) -> str:
        r"""Sum the minterms of the rows equal to ``wanted``, then print."""
        # Cell 1 holds the print.
        # re-walks the gap once per.
        # cheapest cell there is: 49.
        # where the same constant out.
        # several hundred and swamp.
        body = const(1, _ASCII_ONE)
        # cells 2..2+n-1: complement of.
        for i in range(n):
            gap = 2 + i
            body += const(gap, _ASCII_ZERO) + ">" * gap + "," + "!"
        # cells 2+n..2+2n-1: the raw.
        for i in range(n):
            gap = 2 + i
            raw_gap = 2 + n + i
            body += ">" * gap + "<" + ">" * raw_gap + "!"

        cells: list[int] = []
        next_cell = 2 + 2 * n
        for row in range(2**width):
            if reduced[row] != wanted:
                continue
            # Slot ``s`` carries original.
            # and raw cells were laid down.
            bits = [(row >> (width - 1 - s)) & 1 for s in range(width)]
            literals = [
                (2 + used[s]) if v else (2 + n + used[s]) for s, v in enumerate(bits)
            ]
            body += "".join(">" * c + "<" for c in literals)
            body += ">" * next_cell + "!"
            cells.append(next_cell)
            next_cell += 1

        if not invert:
            body += "".join(">" * c + "<" for c in cells)
            body += ">" + "<"  # add the constant cell.
            return body + "."
        # ``S`` is 1 exactly when the.
        # ``0``, so the answer is ``1 -.
        # and ``!`` computes ``max(0,.
        # with 49 and hit with ``acc =.
        # makes ``acc = 50 - S`` and.
        # clamp never bites, since.
        # ``S`` is 1 exactly when the.
        # to ``0``, so the answer is.
        # ``max(0, cell + 1 - acc)``,.
        # reading it back makes ``acc =.
        # ``chr(acc - 1)``) prints.
        # ``'0'`` for S == 1.
        # Preloading 48 instead is the.
        # print's ``- 1`` and ``!``'s.
        body += "".join(">" * c + "<" for c in cells)
        body += ">" + "!"
        body += ">" + "<"
        return body + "."

    plain_cost = _suffolk_candidate_cost(truth_table, "1", invert=False)
    flipped_cost = _suffolk_candidate_cost(truth_table, "0", invert=True)
    # ``min((plain, flipped),.
    return (
        evaluate("1", invert=False)
        if plain_cost <= flipped_cost
        else evaluate("0", invert=True)
    )
