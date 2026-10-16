"""Fixed small-counter FRACTRAN bit decoder and the linear stream template."""

from collections.abc import Callable
from functools import cache

from esolangs.generation.helpers import TEMPLATE_CHAR


class _Assembler:
    def __init__(self) -> None:
        self.code: list[tuple] = []
        self.labels: dict[str, int] = {}
        self.serial = 0

    def fresh(self) -> str:
        self.serial += 1
        return f"L{self.serial}"

    def mark(self, label: str) -> None:
        self.labels[label] = len(self.code)

    def inc(self, r: str) -> None:
        self.code.append(("inc", r))

    def sub(self, r: str) -> None:
        self.code.append(("dec", r, None))

    def jump(self, label: str) -> None:
        self.code.append(("jump", label))

    def clear(self, r: str) -> None:
        loop, end = self.fresh(), self.fresh()
        self.mark(loop)
        self.code.append(("dec", r, end))
        self.jump(loop)
        self.mark(end)

    def move(self, src: str, dst: str) -> None:
        loop, end = self.fresh(), self.fresh()
        self.mark(loop)
        self.code.append(("dec", src, end))
        self.inc(dst)
        self.jump(loop)
        self.mark(end)

    def copy(self, src: str, dst: str, tmp: str = "tmp") -> None:
        self.clear(dst)
        self.clear(tmp)
        loop, end = self.fresh(), self.fresh()
        self.mark(loop)
        self.code.append(("dec", src, end))
        self.inc(dst)
        self.inc(tmp)
        self.jump(loop)
        self.mark(end)
        self.move(tmp, src)

    def loop(self, r: str, body: Callable[[], None]) -> None:
        start, end = self.fresh(), self.fresh()
        self.mark(start)
        self.code.append(("dec", r, end))
        self.inc(r)
        body()
        self.jump(start)
        self.mark(end)

    def zero(self, r: str, body: Callable[[], None]) -> None:
        yes, end = self.fresh(), self.fresh()
        self.code.append(("dec", r, yes))
        self.inc(r)
        self.jump(end)
        self.mark(yes)
        body()
        self.mark(end)

    def divide(self, r: str, base: str, digit: str) -> None:
        self.clear("Q")
        self.clear(digit)
        self.copy(base, "C")

        def step() -> None:
            self.sub(r)
            self.inc(digit)
            self.sub("C")

            def wrap() -> None:
                self.inc("Q")
                self.clear(digit)
                self.copy(base, "C")

            self.zero("C", wrap)

        self.loop(r, step)
        self.move("Q", r)

    def fractions(self, registers: dict[str, int]) -> list[str]:
        # Descending thresholds identify the active state. A separate bridge
        # prime prevents self-targets from cancelling their own guards.
        main, bridges = [], []
        for i, instruction in reversed(list(enumerate(self.code))):
            state = i + 1
            op, *args = instruction
            if op == "halt":
                main.append(f"1/109^{state}")
                continue
            if op == "inc":
                transitions = [(1, f"*{registers[args[0]]}", "", i + 1)]
            elif op == "jump":
                transitions = [(1, "", "", self.labels[args[0]])]
            else:
                fallback = i + 1 if args[1] is None else self.labels[args[1]]
                transitions = [
                    (1, "", f"*{registers[args[0]]}", i + 1),
                    (2, "", "", fallback),
                ]
            for branch, numerator, denominator, target in transitions:
                bridge = 2 * i + branch
                main.append(f"113^{bridge}{numerator}/109^{state}{denominator}")
                bridges.append((bridge, f"109^{target + 1}/113^{bridge}"))
        bridges.sort(reverse=True)
        return (
            main
            + [rule for _bridge, rule in bridges]
            + [f"1/{prime}" for name, prime in registers.items() if name != "answer"]
        )


_REGISTERS = dict(
    zip(
        (
            "E",
            "B",
            "Q",
            "D",
            "C",
            "tmp",
            "t",
            "F",
            "U",
            "R",
            "X",
            "L",
            "Z",
            "power",
            "M",
            "tmp2",
            "two",
            "row",
            "answer",
        ),
        (7, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 2),
        strict=True,
    )
)
_REGISTERS["ones"] = 149


class _Available:
    """Select and delete symbols by their ranks among remaining symbols."""

    def __init__(self, size: int) -> None:
        self.tree = [0, *(i & -i for i in range(1, size + 1))]
        self.size = size

    def pop(self, rank: int) -> int:
        index = 0
        bit = 1 << (self.size.bit_length() - 1)
        while bit:
            candidate = index + bit
            if candidate <= self.size and self.tree[candidate] <= rank:
                rank -= self.tree[candidate]
                index = candidate
            bit >>= 1
        position = index + 1
        while position <= self.size:
            self.tree[position] -= 1
            position += position & -position
        return index


def capacity(k: int) -> int:
    """Return the independently encodable Lehmer bits, sum floor(log2 m)."""
    width = k.bit_length() - 1
    return width * k - (1 << (width + 1)) + width + 2


def digit_order(table: str, k: int) -> tuple[int, ...]:
    """Encode separate power-of-two Lehmer digits with rank selection."""
    if capacity(k) < len(table):
        raise ValueError("not enough independent Lehmer bits")
    available = _Available(k)
    result = []
    offset = 0
    for remaining in range(k, 0, -1):
        width = remaining.bit_length() - 1
        chunk = table[offset : offset + width]
        rank = int(chunk[::-1] or "0", 2)
        result.append(available.pop(rank))
        offset += width
    return tuple(result)


@cache
def bit_decoder() -> tuple[_Assembler, tuple[str, ...]]:
    """Return the fixed small-counter bit extractor; no factorial rank."""
    assembly = _Assembler()

    def shift() -> None:
        assembly.sub("row")
        assembly.divide("R", "two", "Z")

    assembly.loop("row", shift)
    assembly.divide("R", "two", "Z")
    assembly.move("Z", "answer")
    assembly.code.append(("halt",))
    registers = {
        name: _REGISTERS[name]
        for name in ("Q", "C", "tmp", "two", "row", "Z", "answer")
    }
    registers["R"] = 7
    return assembly, tuple(assembly.fractions(registers))


def _linear_primes(count: int) -> list[int]:
    """Return primes with Euler's sieve and an explicit O(count log count) bound."""
    assert count >= 6
    # Rosser-Schoenfeld (1962), (3.13), bounds the count-th prime below this.
    bound = 4 * count * count.bit_length()
    least = [0] * (bound + 1)
    primes = []
    for candidate in range(2, bound + 1):
        if not least[candidate]:
            least[candidate] = candidate
            primes.append(candidate)
            if len(primes) == count:
                return primes
        for prime in primes:
            if prime > least[candidate]:
                break
            product = prime * candidate
            if product > bound:
                break
            least[product] = prime
    raise AssertionError("explicit prime bound failed")


def stream_template(table: str, k: int) -> str:
    """Decode one independent Lehmer digit in O(k+n) fraction firings."""
    n = len(table).bit_length() - 1
    assert len(table) == 1 << n
    order = digit_order(table, k)
    primes = [prime for prime in _linear_primes(40 + n + k) if prime > 149]
    inputs, features = primes[:n], primes[n : n + k]
    start = "*".join(
        [
            "29",
            "103^2",
            *(f"{prime}^{TEMPLATE_CHAR}" for prime in inputs),
            *map(str, features),
        ]
    )
    loaders = [f"107^{1 << (n - 1 - i)}/{prime}" for i, prime in enumerate(inputs)]
    mappings = []
    offset = 0
    for position, remaining in enumerate(range(k, 1, -1)):
        mappings.append(f"3*23*11^{position}/29*107^{offset}")
        offset += remaining.bit_length() - 1
    selectors = []
    for i in order:
        selectors.extend((f"17/3*{features[i]}*11", f"13*5^{i}/3*{features[i]}"))
    scans = []
    bridges = []
    for i in reversed(range(k)):
        scans.extend(
            (
                f"19^{i + 1}*7/13^{i + 1}*{features[i]}*5",
                f"19^{i + 1}/13^{i + 1}*5",
            )
        )
        bridges.append(f"13^{i + 2}/19^{i + 1}")
    _assembly, decoder_rules = bit_decoder()
    return " ".join(
        [
            start,
            *loaders,
            *reversed(mappings),
            *selectors,
            "3/17",
            *scans,
            *bridges,
            "1/13",
            "109/23",
            *decoder_rules,
            *(f"1/{prime}" for prime in features),
        ]
    )
