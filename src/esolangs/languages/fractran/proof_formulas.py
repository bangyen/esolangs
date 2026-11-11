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


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure the prime-factor storage for the constant or state layout."""
    bl = int.bit_length
    if (value := _constant_answer(program)) is not None:
        return {
            "C": 1,
            "V": value,
            "B": sum(map(bl, _primes(n + value)[value:])),
            "P": 0,
        }
    return {
        "C": 0,
        "V": 0,
        "B": sum(map(bl, _primes(n + 1)[1:])),
        "P": bl(_primes(n + 1 + _diagram_cap(n))[-1]),
    }
