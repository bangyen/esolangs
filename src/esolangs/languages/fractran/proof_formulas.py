"""Executed command and snapshot-bit bounds."""


def _constant_answer(p: str) -> int | None:
    """Native constants have no state factor before their input powers."""
    tokens = p.split()
    if not tokens:
        return None
    head = tokens[0].split("*")[0]
    if "^" in head:
        return 0
    return 1 if head == "2" else None


def execution(n: int, _p: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return n + 1


def _diagram_cap(n: int) -> int:
    """The maximal internal-state count: each depth's unequal-halves cap."""
    return sum(
        min(1 << d, (1 << (1 << (n - d))) - (1 << (1 << (n - d - 1)))) for d in range(n)
    )


def _primes(count: int) -> list[int]:
    """The first ``count`` primes."""
    out: list[int] = []
    p = 2
    while len(out) < count:
        if all(p % q for q in out):
            out.append(p)
        p += 1
    return out


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    if (bit := _constant_answer(p)) is not None:
        return sum(map(bl, _primes(n + bit)[bit:])) + n + 1 + 3 * bit
    return (
        bl(_primes(n + 1 + _diagram_cap(n))[-1])
        + n
        + 2
        + sum(map(bl, _primes(n + 1)[1:]))
    )
