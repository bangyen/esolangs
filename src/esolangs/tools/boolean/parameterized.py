r"""Boolean generators that embed each input once."""

from functools import cache
from math import factorial

from esolangs.exceptions import GeneratorCapError

# Re-exported so this module.
# parameterized family; each of.
# construction (a search or a.
from esolangs.interpreters.tape_based.nocomment import _TAPE
from esolangs.tools.boolean.a_painter_ant import a_painter_ant
from esolangs.tools.boolean.cod import cod
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
    essential_inputs,
    instantiate,
    permute_truth_table,
    read_at,
)
from esolangs.tools.boolean.minifuck import minifuck
from esolangs.tools.boolean.one_two_three import one_two_three
from esolangs.tools.boolean.pct_squared_minus_one import pct_squared_minus_one
from esolangs.tools.boolean.wii2d import wii2d

__all__ = [
    "a_painter_ant",
    "arrowqueue",
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "cod",
    "eval",
    "instantiate",
    "lamfunc",
    "minifuck",
    "minsky_swap",
    "nocomment",
    "one_two_three",
    "pct_squared_minus_one",
    "ram0",
    "wii2d",
]

# A decision-tree node:.
# ("node", node_id, level,.
type _Node = tuple[str, int, int, _Node | None, _Node | None]


def bio(truth_table: str) -> str:
    r"""Build a BIO template for the given truth table."""
    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = " ".join("{X" + str(i) + "}" for i in range(n))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox;" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "};"
    init = "0oy;" if truth_table[0] == "1" else ""
    return pack + " " + init + inner + "0oy;" * _ASCII_ZERO + "1iy;"


# Eval's two stacks and the ops.
# which stack is active, ``*``.
# active stack onto the other.
# reverses them, so composing.
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1
# Longest op string worth.
# displaced input, and an.
# folds it was meant to buy;.
# reach, which is what makes.
_EVAL_MAX_OPS = 16
# The reorder words, built.
# ``~``, ``*`` and ``=``-runs,.
# ``~~`` and ``**`` are the.
# run.
# are pinned by a conservation.
# which way it moves, and a.
# everything pushed onto it.
# must sum alike -- and it must.
# only carry back what is.
# lengths) under that law, in.
# ``=``, gives the words.
# .
# The law over-approximates and.
# spellings of arrangements a.
# for the 735 arrangements the.
# discards.
# lost, only re-spelled.
# 735-entry catalog it.
# finite for *every* ``n``: a.
# riding along in rigid.
# once the stack outgrows that.
# ``n == 7..12``, then.
# replays the replaced.
_EVAL_OP_RANK = {"~": 0, "*": 1, "=": 2}


def _eval_skeletons(max_ops: int) -> list[str]:
    r"""Reorder-word skeletons, ``E`` marking an ``=``-run of unfixed."""
    out: list[str] = []

    def grow(skeleton: str, last: str, cost: int) -> None:
        if skeleton:
            out.append(skeleton)
        if cost >= max_ops:
            return
        for char in "~*E":
            if char == last and char != "E":
                continue
            if char == "E" and last == "E":
                continue
            if not skeleton and char != "~":
                continue
            grow(skeleton + char, char, cost + 1)

    grow("", "", 0)
    return out


def _eval_run_directions(skeleton: str) -> list[int]:
    r"""Which stack each ``E`` run pops from, by the ``~`` parity before it."""
    active = _EVAL_TREE_STACK
    directions: list[int] = []
    for char in skeleton:
        if char == "~":
            active = 1 - active
        elif char == "E":
            directions.append(active)
    return directions


def _eval_fill_runs(
    skeleton: str,
    directions: list[int],
    budget: int,
    words: set[str],
) -> None:
    r"""Add every word spelling ``skeleton`` whose runs balance within."""
    count = len(directions)
    last = count - 1

    def fill(index: int, spent: int, balance: int, runs: tuple[int, ...]) -> None:
        side = directions[index]
        remaining = count - index - 1
        ceiling = budget - spent - remaining
        if side == _EVAL_TREE_STACK:
            # An in-run can only carry back.
            ceiling = min(ceiling, balance)
        if index == last:
            # The last run is an in-run of.
            # shorter leaves values.
            # longer pops it empty.
            # still has to fit what the cap.
            if 1 <= balance <= ceiling:
                parts = iter((*runs, balance))
                words.add(
                    "".join(
                        "=" * next(parts) if char == "E" else char for char in skeleton
                    )
                )
            return
        for length in range(1, ceiling + 1):
            shift = length if side == _EVAL_READ_STACK else -length
            fill(index + 1, spent + length, balance + shift, (*runs, length))

    fill(0, 0, 0, ())


@cache
def _eval_reorders(max_ops: int = _EVAL_MAX_OPS) -> tuple[str, ...]:
    r"""Every reorder word the cap admits, shortest first then ``~*=``."""
    words: set[str] = set()
    for skeleton in _eval_skeletons(max_ops):
        directions = _eval_run_directions(skeleton)
        if not directions:
            # No transfers: the only word.
            # reversal of the read stack;.
            # discarded by the fold anyway.
            if skeleton == "~*~":
                words.add(skeleton)
            continue
        if directions[-1] == _EVAL_READ_STACK:
            # A skeleton ending in an.
            # in-run is capped at.
            # negative; a final out-run.
            # strictly positive, meaning.
            # stack when the word ends.
            # are this shape, and filling.
            continue
        _eval_fill_runs(
            skeleton, directions, max_ops - (len(skeleton) - len(directions)), words
        )
    ordered = sorted(
        words, key=lambda word: (len(word), [_EVAL_OP_RANK[c] for c in word])
    )
    return ("", *ordered)


@cache
def _eval_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    r"""Shortest ops rearranging the staged bits into each arrangement."""
    reached: dict[tuple[int, ...], str] = {}
    # A word only shuttles and.
    # arrangement it can leave is a.
    # of them are claimed there is.
    # and first-claim-wins means.
    # so stopping is not a.
    # catalog collapses onto all.
    # reach is short of ``n!`` (119.
    everything = factorial(n)
    for ops in _eval_reorders():
        stacks: tuple[list[int], list[int]] = ([], list(range(n)))
        active = _EVAL_TREE_STACK
        for op in ops:
            if op == "~":
                active = 1 - active
            elif op == "*":
                stacks[active].reverse()
            elif stacks[active]:
                stacks[1 - active].append(stacks[active].pop())
            else:
                break
        else:
            arrangement = tuple(stacks[_EVAL_READ_STACK])
            if (
                active == _EVAL_TREE_STACK
                and not stacks[_EVAL_TREE_STACK]
                and arrangement not in reached
            ):
                reached[arrangement] = ops
                if len(reached) == everything:
                    break
    return reached


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    r"""Build an Eval template for the given truth table."""
    n = _validate_truth_table(truth_table)
    # The staging leaves the input.
    # else, so the tree can be.
    # reachable arrangement is a.
    # already produces, which costs.
    # .
    # The tree pops the input stack.
    # bottom-to-top tests its.
    # the arrangement reversed.
    # arrangement is ``(0, ...,.
    # -- which is why the no-ops.
    best: tuple[int, str, str] | None = None
    for arrangement, ops in sorted(
        _eval_stack_programs(n).items(), key=lambda item: len(item[1])
    ):
        perm = tuple(reversed(arrangement))
        table = permute_truth_table(truth_table, perm)
        candidate = (_eval_cost(table, ops), table, ops)
        # Sorted by op cost with the.
        # comparison is strict, so a.
        # what it emitted before.
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:  # pragma: no cover - the free arrangement is always reachable
        raise RuntimeError("Eval's free stack arrangement is missing")
    _, table, ops = best
    return _eval_ordered(table, ops)


def _eval_cost(truth_table: str, ops: str) -> int:
    r"""Return :func:`_eval_ordered`'s exact rendered length without."""
    n = _validate_truth_table(truth_table)
    slots = 2 ** (n + 1) - 1

    def tree_cost(index: int, first: int, width: int) -> int:
        values = truth_table[first : first + width]
        if width == 1 or len(set(values)) == 1:
            return 3 if values[0] == "1" else 2
        half = width // 2
        return (
            index
            + 6
            + tree_cost(2 * index + 1, first, half)
            + tree_cost(2 * index + 2, first + half, half)
        )

    bits = sum(len(str(i)) + 3 for i in range(n))
    # Every positional heap slot.
    # folded node, whose empty.
    return int(bits + len(ops) + 2 * slots + tree_cost(0, 0, 2**n) + 2)


def _eval_ordered(truth_table: str, ops: str) -> str:
    r"""Emit one input order's Eval template; see :func:`eval`."""
    n = _validate_truth_table(truth_table)

    def combo(leaf: int) -> tuple[int, ...]:
        r"""Input bits (most significant first) reaching the heap ``leaf``."""
        path: list[int] = []
        while leaf > 0:
            path.append(0 if leaf % 2 else 1)  # odd = left child = 0 branch.
            leaf = (leaf - 1) // 2
        return tuple(reversed(path))

    def rows_under(i: int) -> list[int]:
        r"""Table rows reachable from heap node ``i``."""
        if i >= 2**n - 1:
            return [sum(b << (n - 1 - k) for k, b in enumerate(combo(i)))]
        return rows_under(2 * i + 1) + rows_under(2 * i + 2)

    # A node whose rows all agree.
    # it would have reached.
    # are pinned at 2i+1/2i+2 and.
    # so a folded subtree cannot be.
    # can, or every later index.
    # keeps that arithmetic.
    # because the only node that.
    dead: set[int] = set()
    tree: list[str] = []
    for i in range(2 ** (n + 1) - 1):
        if i in dead:
            tree.append("")
            continue
        rows = rows_under(i)
        values = {truth_table[row] for row in rows}
        if i < 2**n - 1 and len(values) == 1:
            tree.append("0+." if values.pop() == "1" else "0.")
            below = [2 * i + 1, 2 * i + 2]
            while below:  # the whole subtree, not just.
                child = below.pop()
                dead.add(child)
                if child < 2**n - 1:
                    below += [2 * child + 1, 2 * child + 2]
        elif i < 2**n - 1:  # internal node: test the next.
            tree.append("~=~?" + ";" * (i + 1) + "!")
        else:  # leaf: print the table entry.
            tree.append("0+." if truth_table[rows[0]] == "1" else "0.")

    # Staged forward, like every.
    # is a free choice rather than.
    # arrangement costs no ops, and.
    # arrangement's cost are.
    # involution -- staging one way.
    bits = "".join("{X" + str(i) + "}" for i in range(n))
    return bits + ops + "".join(f'"{t}"' for t in tree) + "*!"


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table."""
    return best_input_order(truth_table, _back_ordered)


def _back_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Build one Back template, loading its inputs in ``perm`` order."""
    n = _validate_truth_table(truth_table)

    # The load: fill the input.
    # and walk the pointer back to.
    # units because a '{Xi}' is one.
    # .
    # The load runs the ``{Xi}`` in.
    # cell each one belongs in.
    # has to test input.
    # ``perm.index(i)`` -- the.
    # .
    # Filling in cell order instead.
    # no walk at all and is what.
    # and delivers the full 12.0%.
    # kept, because it puts the.
    # and every other generator in.
    # sequence.
    # the docstring for the trade.
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level

    def walk(frm: int, to: int) -> list[str]:
        r"""Move the pointer from cell ``frm`` to cell ``to``, one per row."""
        return [">" if to >= frm else "<"] * abs(to - frm)

    # Emitted in *reverse* name.
    # into column 0 (the beam runs.
    # units backwards.
    # first in the emitted.
    # in this module reads in.
    # over input orders prices it.
    units: list[str] = []
    at = 0
    for cell in range(n - 1, -1, -1):
        # Two units per input, so.
        # the beam reads one cell per.
        # command needs a row of its.
        # Where the tree is the taller.
        # .
        # The first row is a constant.
        # bits alike, and the *second*.
        # it: '-' again to flip a zero.
        # Putting the bit on the.
        # what makes every load row.
        # '{Xi}' + '+' order skipped a.
        # .
        # The walk that puts this input.
        # never between the two halves.
        # equal-width embedding, since.
        # stay two rows for either bit.
        units.extend(walk(at, cells[cell]))
        units.append("-")
        units.append("{X" + str(cell) + "}")
        at = cells[cell]
    # Open the answer cell at n,.
    # test.
    # this is the single '>' the.
    units.extend(walk(at, n))
    units.extend("<" * n)

    # The load occupies column 0.
    # tree carries no indent for it.
    # A single '/' at the origin.
    # heading right; the '/' turns.
    # row, where it runs the load.
    # again, now heading up, and.
    # written bottom-to-top, and an.
    # beam off the load's end, one.
    # with the row and the indent.
    # .
    # Riding off the top edge makes.
    # ``_Machine.step`` advances.
    # on the last row.
    # the edges at all, and no.
    # one place the generator leans.
    # repo's own interpreter.
    grid: dict[tuple[int, int], str] = {}
    next_row = [1]

    def leaf(level: int, value: str, row: int, col: int) -> None:
        # walk to the single answer.
        # value is 1 (it starts 0), and.
        delta = n - level
        move = (">" if delta >= 0 else "<") * abs(delta)
        code = move + ("-" if value == "1" else "") + "*"
        for k, ch in enumerate(code):
            grid[(row, col + k)] = ch

    def emit(level: int, lo: int, hi: int, row: int, col: int) -> None:
        vals = {truth_table[r] for r in range(lo, hi)}
        if level == n or len(vals) == 1:
            leaf(level, vals.pop() if level < n else truth_table[lo], row, col)
            return
        mid = lo + (hi - lo) // 2
        grid[(row, col)] = "+"
        grid[(row, col + 1)] = "\\"
        grid[(row, col + 2)] = ">"
        emit(level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight.
        nrow = next_row[0]
        next_row[0] += 1
        grid[(nrow, col + 1)] = "\\"
        grid[(nrow, col + 2)] = ">"
        emit(level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child.

    emit(0, 0, 2**n, 0, 1)  # tree root at column 1, the.

    # The grid is as tall as.
    # wants 2**n and the load wants.
    # n = 3 the tree is the taller,.
    # rows -- safe for the same.
    # only thing on its row that.
    # exactly three (every.
    # and it sits left of the tree,.
    # to the columns they were.
    # on the bit would break that.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    width = max(c for _, c in grid) + 1
    rows = [[" "] * width for _ in range(height)]
    for (r, c), ch in grid.items():
        rows[r][c] = ch
    rows[0][0] = "/"
    for k, unit in enumerate(units):
        rows[height - 1 - k][0] = unit
    # Every row is built at the.
    # each one carries past its.
    # both bits embed as a single.
    # zero once used, so no.
    # the strip cannot change a.
    return "\n".join("".join(row).rstrip() for row in rows)


# The largest value a NoComment.
# single ``s``/``b`` jump can.
# and everything on that stack.
_NOCOMMENT_SKIP_MAX = 255

# Past this arity the *index*.
# decode below stops working.
# the largest ``n`` with ``2**n.
_NOCOMMENT_NARROW_MAX = (_NOCOMMENT_SKIP_MAX + 1).bit_length() - 1


def _nocomment_summand_plan(n: int, room: int) -> list[list[tuple[int, int]]]:
    r"""Split the index's bit weights into cells that cannot overflow a."""
    parts: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    total = 0
    for i in range(n):
        remaining = 2 ** (n - 1 - i)
        while remaining:
            if total == _NOCOMMENT_SKIP_MAX:
                parts.append(current)
                current, total = [], 0
            take = min(remaining, _NOCOMMENT_SKIP_MAX - total, room)
            current.append((i, take))
            total += take
            remaining -= take
    # Each pass appends to.
    # way to arrive here empty is a.
    # ``_validate_truth_table``.
    if current:  # pragma: no branch - n == 0 never reaches the planner
        parts.append(current)
    return parts


def _nocomment_wide(truth_table: str, n: int, tape: int) -> str:
    r"""Build a NoComment template for a table too wide for one byte-sized."""
    cap = _NOCOMMENT_SKIP_MAX
    k = 2**n
    comp_base = n  # comp_i = 1 - bit_i.
    sbase = 2 * n  # the summand cells.

    # The furthest summand cell.
    # move-add-return block is,.
    # in a single skip.
    # emitted skip within a byte.
    plan = _nocomment_summand_plan(n, 1)
    span = len(plan) + 1
    room = cap - 2 * (sbase + span - 1 - comp_base)
    if room > 0:
        plan = _nocomment_summand_plan(n, room)
    q = len(plan) + 1  # the input-driven summands.
    scratch = sbase + q
    base = scratch + 1
    apron = base + k
    # Each stage pre-walks a full.
    # testing, so the guard apron.
    # and the walk itself reaches.
    top = apron + 2 * cap + 1
    if top >= tape:
        raise GeneratorCapError(
            f"the NoComment boolean generator needs cell {top} for n == {n}, "
            f"past the interpreter's {tape}-cell tape"
        )

    out: list[str] = []
    ptr = [0]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            out.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            out.append("l")
            ptr[0] -= 1

    def guarded(guard: int, chunks: list[list[str]]) -> None:
        r"""Emit a region that runs iff ``guard`` is zero, chunked to fit skips."""
        for chunk in chunks:
            move(scratch)
            out.append("c")
            out.extend(["i"] * len(chunk))
            out.append("n")
            move(guard)
            out.append("s")
            out.extend(chunk)
            ptr[0] = guard

    for i in range(n):
        out.append("{X" + str(i) + "}")
        out.append("r")
    ptr[0] = n

    # comp_i = 1 - bit_i: the block.
    for i in range(n):
        dist = comp_base + i - i
        guarded(i, [["r"] * dist + ["i"] + ["l"] * dist])

    for j in range(q):
        move(sbase + j)
        out.append("c")

    # The output table, then an.
    # pre-walk lands on a truthy.
    # through one sorted diff.
    # single push/pop plus the.
    cells: list[tuple[int, int]] = [
        (base + j, _ASCII_ZERO + int(truth_table[j])) for j in range(k)
    ]
    cells += [(apron + t, _ASCII_ZERO) for t in range(2 * cap + 1)]
    cells.sort(key=lambda cv: cv[1])
    first_addr, first_value = cells[0]
    move(first_addr)
    out.extend(["i"] * first_value)
    prev_value = first_value
    for addr, value in cells[1:]:
        out.append("n")
        move(addr)
        out.append("f")
        diff = value - prev_value
        out.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
        prev_value = value

    # Bit i adds its share to each.
    # complement, so the block runs.
    for j, part in enumerate(plan):
        cell = sbase + j
        for i, amount in part:
            guard = comp_base + i
            dist = cell - guard
            chunks = []
            remaining = amount
            while remaining:
                take = min(remaining, cap - 2 * dist)
                chunks.append(["r"] * dist + ["i"] * take + ["l"] * dist)
                remaining -= take
            guarded(guard, chunks)

    move(sbase + q - 1)
    out.append("c")
    out.append("i")  # the constant trailing summand.

    # Push the summands so the.
    for j in reversed(range(q)):
        move(sbase + j)
        out.append("n")

    # The trailing summand.
    # one cell left of the table.
    move(base - 1)
    for j in range(q):
        if j:
            # Advance the stack top.
            # the cell under the pointer,.
            # least one staircase left of.
            out.append("f")
        out.extend(["r"] * cap)
        out.append("s")
        out.extend(["l"] * cap)
    out.append("o")
    return "".join(out)


def nocomment(truth_table: str, tape: int = _TAPE) -> str:
    r"""Build a NoComment template for the given truth table."""
    n = _validate_truth_table(truth_table)
    if n > _NOCOMMENT_NARROW_MAX:
        return _nocomment_wide(truth_table, n, tape)

    # A table that ignores some of.
    # everything here is sized by.
    # ``l`` per row, and one output.
    # through in the setup's sorted.
    # inputs alone shrinks the.
    # .
    # Every input keeps its.
    # harness has a bit for each.
    # guarded increment's *run.
    # ``["i"] * (2**w)``, a run.
    # contributes an empty run.
    # pointer on its complement.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    # Slot ``s`` carries original.
    # ``2**(width - 1 - s)``; an.
    weights = {i: 2 ** (width - 1 - slot) for slot, i in enumerate(used)}

    k = 2**width
    index = 2 * n
    skip_base = index + 1  # one skip cell per input bit.
    tbase = skip_base + n  # the output cells.
    sentinel = tbase + k  # non-zero cell the final ``s``.
    scratch = sentinel + 1  # reused per bit to push each.

    # Emit the index computation.
    # guarded increment ends with.
    # so the emitted moves stay.
    commands: list[str] = []
    ptr = [index]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            commands.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            commands.append("l")
            ptr[0] -= 1

    skip_vals: dict[int, int] = {}
    for i in range(n):
        comp = n + i
        d = skip_base + i
        move(d)
        commands.append("n")
        move(comp)
        commands.append("s")
        block = len(commands)
        move(index)
        commands.extend(["i"] * weights.get(i, 0))
        move(comp)
        skip_vals[d] = len(commands) - block
    move(index)
    commands.append("n")  # push the index.
    ptr[0] = index
    move(sentinel)
    commands.append("s")  # skip by the index into the.
    commands.extend(["l"] * k)
    commands.append("o")

    # Setup: bits, complements,.
    # scratch.
    # by the NOT-gate prologue.
    setup: list[str] = []
    setup_ptr = [0]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    for i in range(n):
        setup.append("{X" + str(i) + "}")
        setup.append("r")
    setup_ptr[0] = n

    # NOT-gate prologue: for each.
    # bit cell skips a fixed-length.
    # exactly when the bit is.
    # the complement cell -- only.
    # fall-through paths leave the.
    # next bit's prologue starts.
    for i in range(n):
        comp = n + i
        # comp is always to the right.
        # is a straight-line.
        dist = comp - i
        gate = ["r"] * dist + ["i"] + ["l"] * dist
        gate_len = len(gate)

        setup_move(scratch)
        setup.append("c")
        setup.extend(["i"] * gate_len)
        setup.append("n")  # push gate_len.
        setup_move(i)
        setup.append("s")
        setup.extend(gate)

    setup_move(index)
    setup.append("c")  # index starts at zero.
    cells: list[tuple[int, int]] = list(skip_vals.items())
    cells.append((sentinel, _ASCII_ZERO))
    for j in range(k):
        cells.append((tbase + j, _ASCII_ZERO + int(table[j])))
    cells.sort(key=lambda cv: cv[1])
    # The sentinel is appended.
    # least one cell to walk here.
    if cells:  # pragma: no branch - the sentinel keeps this non-empty
        first_addr, first_value = cells[0]
        setup_move(first_addr)
        setup.extend(["i"] * first_value)
        prev_value = first_value
        for addr, value in cells[1:]:
            setup.append("n")
            setup_move(addr)
            setup.append("f")
            diff = value - prev_value
            setup.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
            prev_value = value
    setup_move(index)

    return "".join(setup + commands)


def bfpda(truth_table: str) -> str:
    r"""Build a BF-PDA template for the given truth table."""
    n = _validate_truth_table(truth_table)

    # Load: push a constant-1.
    # of the stack is the *last*.
    # .
    # The load used to run reversed.
    # could test input ``i``.
    # and testing the inputs.
    # LIFO either way, every level.
    # marker, and the tree is the.
    # order keeps the emitted.
    head = "".join("<@{X" + str(i) + "}" for i in range(n))

    def leaf(level: int, value: str) -> str:
        drain_preloaded_bits = ">" * (2 * (n - level))
        print_answer = ("<@" if value == "1" else "<") + ".>"
        return drain_preloaded_bits + print_answer

    # Not routed through.
    # string with no index to.
    # to be one-element lists.
    # the four lines it saves.
    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if i == n or len(results) == 1:
            return leaf(i, results.pop() if i < n else truth_table[rows[0]])
        # The load pushes in name.
        # input first: level ``i``.
        # is at position ``i``.
        zero = [r for r in rows if ((r >> i) & 1) == 0]
        one = [r for r in rows if ((r >> i) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # one-branch pops ~bi first.
        # by the node's own loop.
        return "[>" + ">" + sub1 + "<]>[>" + sub0 + "<]>"

    return head + node(0, list(range(2**n)))


def lamfunc(truth_table: str) -> str:
    r"""Build a Lamfunc template for the given truth table."""
    return best_input_order(truth_table, _lamfunc_ordered)


def _lamfunc_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Lamfunc template; see :func:`lamfunc`."""
    n = _validate_truth_table(truth_table)

    def node(level: int, lo: int, hi: int) -> str:
        results = {truth_table[k] for k in range(lo, hi)}
        if level == n or len(results) == 1:
            return f"p {results.pop()}"
        mid = (lo + hi) // 2
        # i x y z returns y when x is.
        return (
            f"i vg v{perm[level]} {node(level + 1, mid, hi)} {node(level + 1, lo, mid)}"
        )

    head = " ".join(f"vs v{i} {{X{i}}}" for i in range(n))
    return head + " " + node(0, 0, 2**n)


def bitdeque(truth_table: str) -> str:
    r"""Build a Bitdeque template for the given truth table."""
    return best_input_order(truth_table, _bitdeque_ordered)


def _bitdeque_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's Bitdeque template; see :func:`bitdeque`."""
    n = _validate_truth_table(truth_table)

    def leaf(answer: str) -> list[str]:
        out = ["POP"] * (n + 1)
        if answer == "1":
            out.append("INVERT")
        out.append("PUSH")
        if answer == "0":
            out.append("INVERT")
        out.append("GOTO@END")
        return out

    # Simulate the deque to find.
    # inputs in name order, so the.
    # ``n - 1`` and the head is.
    # .
    # Pushing in name order rather.
    # made the first ``POP`` the.
    # which input a root-level test.
    # already brings any bit to.
    # of orders at the same cost.
    # 4, the rotation-length.
    # better default: it keeps the.
    # sequence.
    deque = list(range(n))
    rotations: list[list[str]] = []
    for level in range(n):
        want = perm[level]
        index = deque.index(want)
        from_tail = len(deque) - 1 - index
        if from_tail <= index:
            # Nearer the tail: rotate the.
            rotations.append(["POP", "INJECT"] * from_tail + ["POP"])
            for _ in range(from_tail):
                deque.insert(0, deque.pop())
            deque.pop()
        else:
            # Nearer the head: rotate the.
            rotations.append(["EJECT", "PUSH"] * index + ["EJECT"])
            for _ in range(index):
                deque.append(deque.pop(0))
            deque.pop(0)

    def width(level: int) -> int:
        # the rotation, its consuming.
        return len(rotations[level]) + 1

    # Each placeholder expands to.
    # counts; see the docstring for.
    load_block_in_name_order = ["{X" + str(i) + "}" for i in range(n)]

    # A node spends its rotation,.
    # subtree, so the walker's.
    # width(level)`` on the zero.
    # commands ahead of the tree,.
    # ``GOTO`` operands are right.
    def leaf_tokens(_level: int, row: int) -> list[str]:
        return leaf(truth_table[row])

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        return [
            *rotations[level],
            f"GOTO {at + width(level) + len(zero)}",
            *zero,
            *one,
        ]

    tree = decision_tree_tokens(
        truth_table,
        leaf_tokens,
        node,
        parent_width=width,
        start=2 * n,
        collapse=True,
    )
    end = 2 * n + len(tree)
    return " ".join(
        load_block_in_name_order
        + ["GOTO " + str(end) if t == "GOTO@END" else t for t in tree]
    )


def _ram0_width(address: int) -> int:
    r"""Commands a RAM0 tree node spends before its subtrees."""
    return address + 4


def ram0(truth_table: str) -> str:
    r"""Build a RAM0 template for the given truth table."""
    return best_input_order(truth_table, _ram0_ordered)


def _ram0_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's RAM0 template; see :func:`ram0`."""
    n = _validate_truth_table(truth_table)

    def width(level: int) -> int:
        return _ram0_width(perm[level])

    tokens: list[str] = []
    pos = 0  # instantiated command index of.

    # load phase: ram[i] = bit i,.
    for i in range(n):
        tokens.append("Z")
        tokens.extend("A" for _ in range(i))
        tokens.append("N")
        pos += 1 + i + 1
        tokens.append("{X" + str(i) + "}")  # expands to "Z A" / "Z Z".
        pos += 2
        tokens.append("S")
        pos += 1

    def leaf_tokens(_level: int, row: int) -> list[str]:
        return ["Z", "A" if truth_table[row] == "1" else "Z", "END@"]

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        # ``Z``, the level's ``A`` run,.
        # precede the subtrees, which.
        # therefore starts a further.
        return [
            "Z",
            *("A" for _ in range(perm[level])),
            "L",
            "C",
            f"ONE@{at + width(level) + len(zero) + 1}",
            *zero,
            *one,
        ]

    # Every tree token is one.
    # expands to two), so the.
    tree = decision_tree_tokens(
        truth_table,
        leaf_tokens,
        node,
        parent_width=width,
        start=pos,
        collapse=True,
    )
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just.
    return " ".join(
        str(end) if t == "END@" else str(int(t[4:])) if t.startswith("ONE@") else t
        for t in tokens
    )


def minsky_swap(truth_table: str) -> str:
    r"""Build a Minsky Swap template for the given truth table."""
    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    targets: list[int] = []
    pos = 0  # instantiated command index of.

    # load: bits MSB first; every.
    # LSB a length-4 block.
    for i in range(n - 1):
        tokens.append("{X" + str(i) + "}")
        pos += 2**n
    tokens.append("{X" + str(n - 1) + "}")
    pos += 4

    for _ in range(2**n):  # cascade: route the assembled.
        tokens.append("~")
        targets.append(0)
        pos += 1
    for v in range(2**n):  # leaves: reg[1] holds the LSB;.
        targets[v] = pos + 1
        tokens.append("*")  # pointer onto reg[1].
        pos += 1
        lsb = v & 1
        if lsb == 1 and truth_table[v] == "0":
            tokens.append("~")  # reg[1] is 1 here, so it.
            targets.append(0)
            pos += 1
        elif lsb == 0 and truth_table[v] == "1":
            tokens.append("+")
            pos += 1
        tokens.append("*")  # pointer back onto reg[0].
        pos += 1
        tokens.append("~")  # reg[0] is 0, so this always.
        targets.append(0)
        pos += 1

    end = pos + 1  # 1-based target just past the.
    return (
        " ".join(tokens) + "\n" + " ".join(str(end if t == 0 else t) for t in targets)
    )


# --- ArrowQueue (no-input grid.
# .
# Boolean generator for.
# .
# ArrowQueue is a 2D grid.
# clockwise, ``~`` pushes the.
# pops the queue and points the.
# an empty pop).
# the parameterized convention.
# termination convention (like.
# ``{Xi}`` placeholders for the.
# fills each with the.
# from whether the instantiated.
# *loops forever* (a ``1``.
# halt-vs-hang ring (see.
# .
# The template is a grid:.
# .
# - the first rows embed each.
# (the queue stores bits as.
# - the next rows queue the.
# leaf pops them all and then.
# sustains on them);.
# - the decision tree then pops.
# pointer right for a 0 bit or.
# so the pointer runs off the.
# pushes on every edge and pops.
# .
# The tree is a full binary.
# (``" + "``) pops the next.
# for 1; a 1-branch (``"*.
# the right; and each leaf is a.
# places a 0-branch at the.
# the second at the 1-branch's.
# left (one row below the first.
# The pointer enters the whole.
# section, which pops the.

_TREE_1 = ["+~+", "~ ~", "+~+"]  # the ``1`` leaf: a.
_TREE_0 = ["   ", "   ", "   "]  # the ``0`` leaf: empty, runs.
_TREE_BRANCH_0 = [" + ", "   ", "   "]  # pops a bit; 0 goes right, 1.
_TREE_BRANCH_1 = ["*  ", "** ", "   "]  # reflects the down-route back.

# Input-embedding blocks.
# right (0).
# heading right from the.
# the ``~``, while every later.
# previous block's exit (each.
# column 3, one row below.
# The one blocks carry **inert.
# number of characters as the.
# emitted program's length.
# A wall is only inert where.
# block's row 0 is left exactly.
# ``docs/generators/arrowqueue_g.
# wall per row suffices.
_FIRST_ONE = ["   *", "   ~*", "  *", "  *", "  *"]
_FIRST_ZERO = ["   *", "*~* ", "*  *", "*  *", "* * "]
_NEXT_ONE = ["   ~*", "  *", "  *", "  *"]
_NEXT_ZERO = ["*~* ", "*  *", "*  *", "* * "]

# The loop-component section:.
# embedding block, it queues.
# the queue holds ``[bits...,.
# pointer down column 1 into.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


def _header_rows(bits: list[int]) -> list[str]:
    r"""Build the input-embedding rows for ``bits`` (most significant."""
    rows = list(_FIRST_ONE if bits[0] else _FIRST_ZERO)
    for bit in bits[1:]:
        rows.extend(_NEXT_ONE if bit else _NEXT_ZERO)
    return rows


def _connect(t0: list[str], t1: list[str]) -> list[str]:
    r"""Connect two decision subtrees into one."""
    yb = len(t0)  # the 1-branch's top row: one.
    width = max(3 + len(t0[0]), 3 + len(t1[0]))
    height = max(3, yb + 3, yb + len(t1))
    grid = [[" "] * width for _ in range(height)]
    for r, line in enumerate(_TREE_BRANCH_0):
        for c, ch in enumerate(line):
            grid[r][c] = ch
    for r, line in enumerate(_TREE_BRANCH_1):
        for c, ch in enumerate(line):
            grid[yb + r][c] = ch
    for r, line in enumerate(t0):
        for c, ch in enumerate(line):
            grid[r][3 + c] = ch
    for r, line in enumerate(t1):
        for c, ch in enumerate(line):
            grid[yb + r][3 + c] = ch
    return ["".join(row) for row in grid]


def _drained_leaf(value: str, skipped: int) -> list[str]:
    r"""Build a folded leaf that drains the ``skipped`` bits it never."""
    # A ``0`` leaf halts by running.
    # prevent, so it needs no drain.
    # characters: the staircase.
    # replaced, leaving.
    if value != "1":
        return list(_TREE_0)
    # The leaf is 3x3 placed at.
    # ``skipped + 3`` rows and one.
    grid = [[" "] * (skipped + 4) for _ in range(skipped + 3)]
    for i in range(skipped):
        grid[i][i + 1] = "+"
        grid[i][i + 2] = "*"
        grid[i + 1][i] = "*"
        grid[i + 2][i] = "*"
        grid[i + 2][i + 1] = "*"
    leaf = _TREE_1 if value == "1" else _TREE_0
    for r, line in enumerate(leaf):
        for c, char in enumerate(line):
            if char != " ":
                grid[skipped + r][skipped + 1 + c] = char
    return ["".join(row) for row in grid]


def _tree(values: list[str]) -> list[str]:
    r"""Build the decision tree for the ``2**n`` table values."""
    if len(set(values)) == 1:
        skipped = len(values).bit_length() - 1
        return _drained_leaf(values[0], skipped)
    if len(values) == 2:
        return _connect(
            _TREE_1 if values[0] == "1" else _TREE_0,
            _TREE_1 if values[1] == "1" else _TREE_0,
        )
    half = len(values) // 2
    return _connect(_tree(values[:half]), _tree(values[half:]))


def arrowqueue(truth_table: str) -> str:
    r"""Build an ArrowQueue template for an ``n``-input Boolean function."""
    n = _validate_truth_table(truth_table)
    header = ["{X0}"]
    header.extend(["    "] * 4)
    for i in range(1, n):
        header.append("{X" + str(i) + "}")
        header.extend(["    "] * 3)
    rows = header + _MIDDLE + _tree(list(truth_table))
    return "\n".join(row.rstrip() for row in rows)


def _instantiate_arrowqueue(template: str, bits: list[int]) -> str:
    r"""Fill an ArrowQueue template's ``{Xi}`` placeholders with the bits."""
    n = len(bits)
    rows = template.split("\n")
    # The header rows are built to.
    # travels past the last glyph.
    # trim them so the emitted.
    joined = _header_rows(bits) + rows[4 * n + 1 :]
    return _compact(joined)


def _compact(rows: list[str]) -> str:
    r"""Drop the wholly blank rows and columns from an instantiated program."""
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:
        return ""  # pragma: no cover - every table lays a cell
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return "\n".join("".join(row[x] for x in columns).rstrip() for row in kept)


def home_row(truth_table: str) -> str:
    r"""Build a Home Row template for the given truth table."""
    n = _validate_truth_table(truth_table)
    # A table that ignores some of.
    # leaf chain -- the whole cost.
    # the table says, so dropping.
    # stay: every input keeps its.
    # an ignored one carries binary.
    # consumes its guard exactly as.
    # accumulator.
    # keeps the slot-order and.
    used = essential_inputs(truth_table, n)
    # A constant table depends on.
    # never to the length-1 table,.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        "{X" + str(i) + "}lsffff" + "a" * weights.get(i, 0) + "fl" for i in range(n)
    ]
    leaves = [
        "afffflsfsfflflf" + ("a" if bit == "1" else "") + "k;lff" for bit in table[:-1]
    ]
    leaves.append("f" + ("a" if table[-1] == "1" else "") + "k;")
    return setup + "".join(bit_lines) + "".join(leaves)
