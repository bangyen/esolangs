"""Piet's emitted codels: the strip, or the least-area packed layout.

To n = 7 every packed layout is a function of the operations' block sizes alone
(a lane takes whole blocks to its room; 5,800 random tables at n = 5..7 never
cost a clash row), and a table with n essential inputs and z zeros has the
sizes ``[1] * (T + z)`` then a tail that depends on n only.
So the shipped area is a function of (n, z): the worst is its maximum over z.
From n = 8 a colour clash can cost a row (+32 codels at n = 8, in 53 of 1,277
tables), the rows depend on the bit pattern, and only the fold's bound holds.
"""

from functools import cache
from math import isqrt


def _tail(n: int) -> list[int]:
    """Block sizes after the T + z entries: row number, select, print, halt pad."""
    return [
        *(1, 1),  # push 1, not
        *(2, 1, 1, 1) * n,  # per input: push 2, multiply, in, add
        1,  # push T, rebuilt by doubling:
        *(2, 1) * n,  # push 2, multiply
        *(2, 1, 1, 1, 1, 1, 2, 1, 1, 1),  # the roll
        1,  # print
        *(2, 1),  # push 2, pop keep the halt off the last turn
    ]


def _lanes(
    entries: int, tail: list[int], columns: int, kind: int
) -> tuple[int, list[tuple[int, int, int, int]]]:
    """Width and lanes (start x, end x, direction, blocks so far) of the greedy plan.

    Kind 0 plain, 1 shared, 2 short.
    """
    total = entries + len(tail)
    at, x, direction, widest, lanes = 0, 2, 1, 1, []
    while at < total:
        room = columns - x - 4 if direction == 1 else x - (9 if kind == 0 else 7)
        used = max(0, min(entries - at, room))
        at += used
        while entries <= at < total:
            size = tail[at - entries]
            if used + (3 if at == total - 2 else size) > room:
                break
            used += size
            at += 1
        assert used, "no room for a block"
        end = x + direction * used
        widest = max(widest, end + 3 if direction == 1 and at < total else x, end)
        lanes.append((x, end, direction, at))
        x = (end + 1 if direction == 1 else end - 2) if kind == 2 else end - direction
        direction = -direction
    return widest + 1, lanes


@cache
def _layouts(
    n: int, z: int
) -> list[tuple[int, list[tuple[int, int, int, int]], int, int]]:
    """(area, lanes, kind, rows) of the nine layouts: width * rows.

    Rows are lanes + 4 (shared, short) or 2 * lanes + 2 (plain), 3 for one lane.
    """
    tail, entries = _tail(n), (1 << n) + z
    root = isqrt(entries + sum(tail))
    found = []
    for kind, floor in ((0, 22), (1, 18), (2, 18)):
        for offset in (5, 9, 13):
            width, lanes = _lanes(entries, tail, max(floor, root + offset), kind)
            count = len(lanes)
            rows = 3 if count == 1 else count + 4 if kind else 2 * count + 2
            found.append((width * rows, lanes, kind, rows))
    return found


def _packed(n: int, z: int) -> int:
    """The least area of the nine layouts."""
    return min(found[0] for found in _layouts(n, z))


def _strip(n: int, z: int) -> int:
    """Three rows by 2T + z + 5n + 18 columns."""
    return 3 * (2 * (1 << n) + z + 5 * n + 18)


def _walk(n: int, z: int) -> int:
    """Steps of the shipped layout (the most of any area tie), n <= 7.

    Blocks entered: T + z + len(tail) operations and the halt, five per extra
    lane (the turn's four blocks and the landing); the strip's push(T) is one
    block, not a doubling, so it is 2n shorter.
    """
    blocks = (1 << n) + z + len(_tail(n))
    least = min(_strip(n, z), _packed(n, z))
    walks = [
        blocks + 5 * (len(lanes) - 1) + 2
        for area, lanes, _, _ in _layouts(n, z)
        if area == least
    ]
    if _strip(n, z) == least:
        walks.append(blocks - 2 * n)
    return max(walks)


def walk_zeros(n: int) -> int:
    """The z whose steps are the most, the last on a tie."""
    return max(range(2, (1 << n) - 1), key=lambda z: (_walk(n, z), z))


def _steps(n: int, _: str) -> int:
    """Worst steps: the most over z to n = 7, then the fold's bound."""
    if n >= 8:
        return 5 * (1 << n) + 11 * n + 31
    return _walk(n, walk_zeros(n))


@cache
def _trace(n: int, row: int) -> list[int]:
    """Stack bits after each tail operation on ``row``; entries are 1 bit each."""
    stack = [1] * (1 << n)
    reads = iter((row >> (n - 1 - i)) & 1 for i in range(n))
    steps = [("push", 1), ("not", 0)]
    steps += [("push", 2), ("mul", 0), ("in", 0), ("add", 0)] * n
    steps += [("push", 1), *[("push", 2), ("mul", 0)] * n]
    steps += [("push", 2), ("push", 1), ("roll", 0), ("push", 1), ("add", 0)]
    steps += [("push", 1), ("push", 2), ("sub", 0), ("mul", 0), ("roll", 0)]
    steps += [("out", 0), ("push", 2), ("pop", 0)]
    trace = []
    for name, value in steps:
        if name == "push":
            stack.append(value)
        elif name == "not":
            stack.append(int(stack.pop() == 0))
        elif name == "in":
            stack.append(next(reads))
        elif name in {"out", "pop"}:
            stack.pop()
        elif name == "roll":
            turns, depth = stack.pop(), stack.pop()
            if turns % depth:
                cut = len(stack) - turns % depth
                stack[-depth:] = [*stack[cut:], *stack[-depth:cut]]
        else:
            right, left = stack.pop(), stack.pop()
            stack.append(
                left + right
                if name == "add"
                else left - right
                if name == "sub"
                else left * right
            )
        trace.append(sum((abs(v).bit_length() or 1) + (v < 0) for v in stack))
    return trace


def _position(lanes: list[tuple[int, int, int, int]], kind: int) -> int:
    """Peak bl(x) + bl(y) of the packed layout's block entries.

    A right lane peaks on its turn column (end + 3) down to the next lane's
    row; a left lane at its start; the last at its start or end.
    """
    count = len(lanes)
    rows = [1]
    for i in range(1, count):
        rows.append(rows[-1] + (3 if i == count - 1 else 1 + (kind == 0)))
    peak = 0
    for i, (start, end, direction, _) in enumerate(lanes):
        if i == count - 1:
            peak = max(peak, max(start, end).bit_length() + rows[i].bit_length())
        elif direction == 1:
            peak = max(peak, (end + 3).bit_length() + rows[i + 1].bit_length())
        else:
            peak = max(peak, start.bit_length() + rows[i].bit_length())
    return peak


def _bits(n: int, z: int, row: int) -> int:
    """Written bits on ``row`` of the shipped layout (the most of an area tie).

    The sum of the components' peaks: position, dp (2 once a turn exists), the
    stack (the entry bits and operands, plus a turn's push operands, 2 bits
    to the right and 4 to the left), input progress bl(2n-1), halted 1 and the
    read count bl(n).
    """
    trace, entries = _trace(n, row), (1 << n) + z
    least = min(_strip(n, z), _packed(n, z))
    fixed = (2 * n - 1).bit_length() + 1 + n.bit_length()
    found = []
    candidates = [(area, lanes, kind) for area, lanes, kind, _ in _layouts(n, z)]
    candidates.append((_strip(n, z), [], 0))
    for area, lanes, kind in candidates:
        if area != least:
            continue
        stack = max(trace)
        for k, (_, _, _, at) in enumerate(lanes[:-1]):
            below = trace[at - 1 - entries] if at > entries else min(at, 1 << n)
            stack = max(stack, below + (4 if k % 2 else 2))
        if len(lanes) > 1:
            found.append(_position(lanes, kind) + 2 + stack + fixed)
        else:
            found.append((area // 3 - 1).bit_length() + 1 + stack + fixed)
    return max(found)


@cache
def bit_zeros(n: int) -> int:
    """The z whose written bits are the most on the last row, the last on a tie.

    The last row's stack trace dominates every row's at each operation (checked
    for every row to n = 10), so it is the worst row.
    """
    return max(range(2, (1 << n) - 1), key=lambda z: (_bits(n, z, (1 << n) - 1), z))


def _written(n: int, _: str) -> int:
    """Worst written bits: the most over z and rows to n = 7, then the stack bound."""
    if n >= 8:
        return (
            (1 << n)
            + 2 * n
            + 12
            + 2 * (3 * (1 << n) + 5 * n + 15).bit_length()
            + (2 * n - 1).bit_length()
            + n.bit_length()
        )
    return _written_at(n)


@cache
def _written_at(n: int) -> int:
    return _bits(n, bit_zeros(n), (1 << n) - 1)


def zeros(n: int) -> int:
    """The last z whose shipped area is the worst."""
    shipped = {z: min(_strip(n, z), _packed(n, z)) for z in range(2, (1 << n) - 1)}
    return max(shipped, key=lambda z: (shipped[z], z))


def _fold(blocks: int) -> int:
    """The fold plan's area bound for ``blocks`` codels of bounded operations.

    Columns c = max(13, isqrt(2C - 1) + 9).  A row packs at least c - 9
    codels (room is c - 7 or less, a block wastes one), so R <= 1 +
    (C - 1) // (c - 9) rows; a right/left row pair is five rows tall, the
    last bend two more, plus the border: height <= 5R/2 + 3, width <= c.
    """
    columns = max(13, isqrt(2 * blocks - 1) + 9)
    rows = 1 + (blocks - 1) // (columns - 9)
    return columns * (5 * rows // 2 + 3 + 1)


def _codels(n: int, _: str) -> int:
    """F: max over z in [2, T - 2] of min(strip, least packed layout) to n = 7.

    Fewer essential inputs store fewer entries (the family
    scan never reached the plain family).  From n = 8 the result is also at
    most the fold, drawn in the race, at the most blocks C = 2T + 8n + 17.
    """
    if n >= 8:
        return min(
            3 * (3 * (1 << n) + 5 * n + 16),
            max(_fold(c) for c in range(2, 2 * (1 << n) + 8 * n + 18)),
        )
    z = zeros(n)
    return min(_strip(n, z), _packed(n, z))


FORMULAS = {
    "scaling": (_codels, frozenset(range(3, 8)), (3, 4, 5, 6, 7, 8)),
    "execution": (_steps, frozenset(range(3, 8)), (3, 4, 5, 6, 7, 8)),
    "workspace": (_written, frozenset(range(3, 8)), (3, 4, 5, 6, 7, 8)),
}
