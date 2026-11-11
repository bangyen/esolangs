"""Piet bounds: triple strips, or packed lookups below four essential inputs.

To n = 7 every packed layout is a function of the operations' block sizes alone
(a lane takes whole blocks to its room; 5,800 random tables at n = 5..7 never
cost a clash row), and a table with n essential inputs and z zeros has the
sizes ``[1] * (T + z)`` then a tail that depends on n only.
So the shipped area is a function of (n, z): the worst is its maximum over z.
Past half zeros the complement is stored instead, T - z zeros and a ``not`` on
the selected entry, so the worst z is the middle one.
Majority and its complement count their inputs in O(n) operations instead.
They stay below these bounds; unchanged generic witnesses attain the maxima.
For old full lookups from n = 8 a colour clash can cost a row (+32 codels
at n = 8, in 53 of 1,277 tables). Rows depend on the bit pattern; only the
fold's bound holds.
"""

from functools import cache
from itertools import combinations
from math import isqrt


def _flipped(n: int, z: int) -> bool:
    """Whether the complement is stored: it has fewer codels, ``not`` included."""
    return (1 << n) + 1 < 2 * z


def _stored(n: int, z: int) -> int:
    """Zeros among the stored entries."""
    return (1 << n) - z if _flipped(n, z) else z


def _tail(n: int, *, flip: bool = False) -> list[int]:
    """Block sizes after the T + z entries: row number, select, print, halt pad."""
    return [
        *(1, 1),  # push 1, not
        *(2, 1, 1, 1) * n,  # per input: push 2, multiply, in, add
        1,  # push T, rebuilt by doubling:
        *(2, 1) * n,  # push 2, multiply
        *(2, 1, 1, 1, 1, 1, 2, 1, 1, 1),  # the roll
        *((1,) if flip else ()),  # not on the entry of a complemented table
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
    tail, entries = _tail(n, flip=_flipped(n, z)), (1 << n) + _stored(n, z)
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
    """Three rows by 2T + z + 5n + 18 columns, one more for a ``not``."""
    return 3 * (2 * (1 << n) + _stored(n, z) + 5 * n + 18 + _flipped(n, z))


def _walk(n: int, z: int) -> int:
    """Steps of the shipped layout (the most of any area tie), n <= 7.

    Blocks entered: T + z + len(tail) operations and the halt, five per extra
    lane (the turn's four blocks and the landing); the strip's push(T) is one
    block, not a doubling, so it is 2n shorter.
    """
    blocks = (1 << n) + _stored(n, z) + len(_tail(n, flip=_flipped(n, z)))
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


@cache
def _trace(n: int, row: int, *, flip: bool = False) -> list[int]:
    """Stack bits after each tail operation on ``row``; entries are 1 bit each."""
    stack = [1] * (1 << n)
    reads = iter((row >> (n - 1 - i)) & 1 for i in range(n))
    steps = [("push", 1), ("not", 0)]
    steps += [("push", 2), ("mul", 0), ("in", 0), ("add", 0)] * n
    steps += [("push", 1), *[("push", 2), ("mul", 0)] * n]
    steps += [("push", 2), ("push", 1), ("roll", 0), ("push", 1), ("add", 0)]
    steps += [("push", 1), ("push", 2), ("sub", 0), ("mul", 0), ("roll", 0)]
    steps += [*([("not", 0)] if flip else []), ("out", 0), ("push", 2), ("pop", 0)]
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
    trace = _trace(n, row, flip=_flipped(n, z))
    entries = (1 << n) + _stored(n, z)
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


@cache
def _written_at(n: int) -> int:
    return _bits(n, bit_zeros(n), (1 << n) - 1)


def zeros(n: int) -> int:
    """The last z whose shipped area is the worst."""
    shipped = {z: min(_strip(n, z), _packed(n, z)) for z in range(2, (1 << n) - 1)}
    return max(shipped, key=lambda z: (shipped[z], z))


@cache
def _projected_steps(inputs: int) -> int:
    """Old layouts with at most three essential bits; retain physical read order."""
    found: list[int] = []
    for n in range(2, min(inputs, 3) + 1):
        for essential in combinations(range(inputs), n):
            prefix = [1, 1]
            for cell in range(inputs):
                prefix += [2, 1, 1, 1] if cell in essential else [1, 1]
            for z in range(2, (1 << n) - 1):
                flip = _flipped(n, z)
                tail = prefix + _tail(n, flip=flip)[2 + 4 * n :]
                entries = (1 << n) + _stored(n, z)
                root = isqrt(entries + sum(tail))
                layouts: list[tuple[int, int]] = []
                for kind, floor in ((0, 22), (1, 18), (2, 18)):
                    for offset in (5, 9, 13):
                        width, lanes = _lanes(
                            entries, tail, max(floor, root + offset), kind
                        )
                        count = len(lanes)
                        rows = 3 if count == 1 else count + 4 if kind else 2 * count + 2
                        layouts.append(
                            (width * rows, entries + len(tail) + 5 * (count - 1) + 2)
                        )
                layouts.append(
                    (_strip(n, z) + 6 * (inputs - n), entries + len(tail) - 2 * n)
                )
                least = min(area for area, _ in layouts)
                found.extend(steps for area, steps in layouts if area == least)
    return max(found)


def _chunk_count(n: int) -> int:
    return ((1 << n) + 2) // 3


def execution_terms(n: int, _: object) -> dict[str, int]:
    """Price the selected packed walk below four inputs."""
    return {"P": _walk(n, walk_zeros(n))}


def workspace_terms(n: int, _: object) -> dict[str, int]:
    """Price the packed stack and cursor below four inputs."""
    return {"B": _written_at(n)}


def scaling_terms(n: int, _: object) -> dict[str, int]:
    """Price the worst selected packed layout below four inputs."""
    z = zeros(n)
    return {"A": min(_strip(n, z), _packed(n, z))}


def _chunk_table(values: list[int], n: int) -> str:
    return "".join(str((value >> j) & 1) for value in values for j in range(3))[
        : 1 << n
    ]


def source_witness(n: int) -> str:
    """Balanced endpoint chunks attain the source maximum from four inputs."""
    count = _chunk_count(n)
    ones = (count - 1) // 2 if n % 2 else count // 2
    return _chunk_table([7] * ones + [0] * (count - 1 - ones) + [3 if n % 2 else 1], n)


def execution_witness(n: int) -> str:
    """Three zero rows force the complemented sparse triple lookup."""
    return "000" + "1" * ((1 << n) - 3)


def workspace_witness(n: int) -> str:
    """Chunks 4/2 saturate the source-choice bit inequality."""
    count = _chunk_count(n)
    twos = (count + 1) // 4 if n % 2 else (count - 2) // 4
    return _chunk_table([4] * (count - 1 - twos) + [2] * twos + [2 if n % 2 else 1], n)


def resource_witness(n: int, kind: str) -> str:
    """Triple-strip attainers from four; original packed cases below."""
    if n >= 4:
        return {
            "area": source_witness,
            "steps": execution_witness,
            "bits": workspace_witness,
        }[kind](n)

    width = 1 << n
    middle = [r for r in range(width) if 2 <= r.bit_count() <= n - 2]
    rest = [r for r in range(1, width - 1) if r not in middle]
    z = {"area": zeros, "steps": walk_zeros, "bits": bit_zeros}[kind](n)
    ones = {0, width - 1, *[*middle, *rest][: width - z - 2]}
    return "".join("1" if r in ones else "0" for r in range(width))


def resource_tables(n: int) -> tuple[str, ...]:
    """Return distinct witnesses for native area, command and workspace bounds."""
    if n < 2:
        return ()
    kinds = ("area", "steps", "bits") if n <= 7 else ("area",)
    return tuple(dict.fromkeys(resource_witness(n, kind) for kind in kinds))
