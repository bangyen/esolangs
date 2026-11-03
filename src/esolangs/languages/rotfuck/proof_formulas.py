"""Executed command and snapshot-bit bounds."""

from esolangs.languages.rotfuck.interpreter import ROTFUCK_CYCLES


def _constant_details(n: int, p: str) -> tuple[str, int, int] | None:
    """Native constants start with a read; lookups start by planting their strip."""
    if not p.lstrip().startswith(","):
        return None
    positions = [i for i, c in enumerate(p) if c in ROTFUCK_CYCLES["backward"]]
    source = "".join(p[i] for i in positions)
    if not source.startswith(",") or len(source) not in (n + 26, n + 27):
        return None
    second = "," if n > 1 else ">"
    for rotation, cycle in ROTFUCK_CYCLES.items():
        if source[1] == cycle[(cycle.index(second) - 1) % 8]:
            # Six trips execute the body/closing bracket span five extra times.
            return rotation, len(source), positions[n + 23] - positions[n + 7]
    return None


def _forward(program: str) -> bool:
    """A positive0/1 strip begins >> or +>>, whose second glyph names the cycle."""
    chars = "".join(c for c in program if c in ROTFUCK_CYCLES["backward"])
    return len(chars) >= 2 and chars[1] == "-"


def _raw_execution(n: int, *, forward: bool) -> int:
    """All-one digits maximize the bounded-byte Horner/walk cost."""
    widths = ([n % 5] if n % 5 else []) + [5] * (n // 5)
    steps, shift = 3 * (1 << n) - 2 + 50, 0
    for width in widths:
        steps += 1
        for j in range(1, width):
            partial = 49 * ((1 << j) - 1) % 256
            steps += 7 + (16 if forward else 8) * partial + 16 * (2 * partial % 256)
        bias = -48 * ((1 << width) - 1) % 256
        steps += min(bias, 256 - bias)
        stride, count = 2 << shift, (1 << width) - 1
        even = (stride.bit_length() - 1) % 2 == 0
        inner = 4 * stride + (16 if forward else 8)
        other = (4 * stride + 16 * (1 + even)) // 3
        other += 8 * (not even) if forward else 0
        steps += 1 + count * other + count * (count + 1) // 2 * inner
        shift += width
    return steps


def execution(n: int, p: str) -> int:
    """Default exact finite rungs; raw digits use the same derived loop costs."""
    if details := _constant_details(n, p):
        return len(p) + 5 * details[2]
    forward = _forward(p)
    if n >= 7:
        bound = _raw_execution(n, forward=forward)
    elif forward:
        bound = 199 if n == 1 else 12 * (1 << (2 * n)) + 55 * (1 << n) + 7 * n - 21
    else:
        bound = 183 if n == 1 else 8 * (1 << (2 * n)) + 43 * (1 << n) + 15 * n - 5
    # Comment cells execute without rotating; a retained count walk can visit
    # its body255*256/2 times. Default finite-rung formulas are unchanged.
    return bound + 32768 * sum(c not in ROTFUCK_CYCLES["backward"] for c in p)


def workspace(n: int, program: str) -> int:
    """Written-state peaks: tape, pointer, cursor, rotation count, input count.

    The tape peaks at 2T + 2 cells (the strip, the Horner scratch pair) with a
    count of 2^n - 1 (n bits) and one decrement-wrapped 255 (8) on it;
    pointer at most 2T + 6, cursor L, rotation the execution bound.  Past
    n = 6 the earlier bound V (the tape measured 2T + 2 at n = 7, 8 on
    lone-zero, one-hot and random tables).
    """
    t = 1 << n
    bl = int.bit_length
    if details := _constant_details(n, program):
        rotation, size, _ = details
        # Four neutral body commands repeat; forward padding wraps one extra bit.
        return (
            (16 if rotation == "backward" else 17)
            + bl(len(program))
            + bl(size + 80)
            + bl(n)
        )
    if n > 6:
        size = len(program)
        return 2 * t + 5 * n + 35 + bl(2080 * size) + bl(2 * t + 6) + bl(size) + bl(n)
    return (
        2 * t
        + n
        + 8
        + bl(2 * t + 6)
        + bl(len(program))
        + bl(execution(n, program))
        + bl(n)
    )
