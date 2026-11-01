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


def execution(n: int, p: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    if details := _constant_details(n, p):
        return len(p) + 5 * details[2]
    return 8 * (1 << (2 * n)) + 43 * (1 << n) + 15 * n - 5


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
