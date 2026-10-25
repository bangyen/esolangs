"""Executed command bounds."""


def _divide_steps(value: int, bit: int) -> int:
    """Steps the packed divide block spends extracting ``bit`` of a chunk.

    One pass a bit up to ``bit``: pass j halves ``value >> j`` for an
    initialisation, a body of 4w + 1 + (w mod 2) at w = value >> j
    (eight steps a pair of decrements, six for an odd tail unit, one
    last test on an even finish) and a closing tail, eight a pass and
    two on the last.  The pass values telescope by the identity
    sum_j (x >> j) = 2x - popcount(x).
    """
    span = (2 * value - value.bit_count()) - (
        2 * (value >> (bit + 1)) - (value >> (bit + 1)).bit_count()
    )
    return 4 * span + (value & ((1 << (bit + 1)) - 1)).bit_count() + 11 * bit + 5


def _packed_steps(n: int, cells: list[int]) -> int | None:
    """A packed program's exact worst-row steps, or None off that route.

    The decoder's seventeen named cells sit at 3 * (2n + 9m + 45) for
    m essential inputs, followed by one target cell an instruction
    and the negated chunks.  A row's cost is its reads (eleven an
    essential input, two an ignored one), the chunk walk
    7 * idx + 5 * (idx // m) + 1 to its projected index, the seven of
    the select, the divide over its chunk and the five of the print
    and the halt; a chunk's worst row is its last, so the program's
    worst is the best chunk-end total.
    """
    for at in range(len(cells) - 16):
        if cells[at : at + 4] != [0, 1, -1, -48]:
            continue
        m = cells[at + 4]
        if (
            m >= 1
            and cells[at + 5 : at + 9] == [0, 0, 0, 0]
            and cells[at + 9] == m
            and cells[at + 10 : at + 15] == [0, 0, 0, 0, 0]
            and cells[at + 15] == 48
            and cells[at + 16] == -1
            and at == 3 * (2 * n + 9 * m + 45)
            and len(cells) - (at + 17 + at // 3) == -(-(1 << m) // m)
        ):
            break
    else:
        return None
    chunks = cells[at + 17 + at // 3 :]
    worst = 0
    for q, cell in enumerate(chunks):
        size = m if q < len(chunks) - 1 else (1 << m) - q * m
        idx = q * m + size - 1
        worst = max(worst, 7 * idx + 5 * q + _divide_steps(-cell, size - 1))
    return 2 * n + 9 * m + 13 + worst


def execution(n: int, program: str) -> int:
    """The stated execution bound, evaluated for n and the program.

    Off the packed route the worst is the tree's 3n + 2 (n reads,
    2n - 1 tests, the print and the halt; a constant takes n + 1).
    A packed program is counted exactly from its chunks instead, so
    the figure a row must meet is that program's own worst row; over
    all tables the packed worst is 8T + (7n + 5)(floor(T/n) - 1)
    + 26n - 8, reached when the last full chunk is all ones.
    """
    cells = [int(word) for word in program.split()]
    packed = _packed_steps(n, cells)
    return packed if packed is not None else 3 * n + 2
