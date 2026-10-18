"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return n + 2


def _diagram_cap(n: int) -> int:
    """Distinct subtables each depth can hold: the maximal state count."""
    return sum(min(1 << d, 1 << (1 << (n - d))) for d in range(n + 1))


def _primes(count: int) -> list[int]:
    """The first ``count`` primes."""
    out: list[int] = []
    p = 2
    while len(out) < count:
        if all(p % q for q in out):
            out.append(p)
        p += 1
    return out


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        bl(_primes(n + 1 + _diagram_cap(n))[-1])
        + n
        + 2
        + sum(map(bl, _primes(n + 1)[1:]))
    )
