"""Mammalian chains with coprime array assignments."""

from dataclasses import dataclass, field, replace
from math import gcd

from esolangs._mammalian import MammalianModuli


@dataclass
class _State:
    head: int = 0
    rest: list[int] = field(default_factory=lambda: [0] * 23)
    acc: int = 0
    ptr: int = 0

    def clone(self) -> "_State":
        return replace(self, rest=self.rest.copy())


class _Chain:
    def __init__(self, modulus: int, *, io_modulus: int | None = None) -> None:
        moduli = MammalianModuli(modulus, modulus if io_modulus is None else io_modulus)
        self.modulus, self.io_modulus = moduli.cell_modulus, moduli.io_modulus
        units = [array for array in range(23) if gcd(array + 1, modulus) == 1]
        self.weight = units[1]
        self.step = self.weight + 1
        for seeds in range(1, 23):
            for first in units:
                if first in (0, self.weight):
                    continue
                head = (first - self.weight) % 23
                second = (first + seeds * self.step) % 23
                if second in units and second not in (
                    0,
                    self.weight,
                    first,
                ):
                    self.prints = (first, second)
                    self.digit_seeds = seeds
                    self.dispatch_head = head
                    return
        raise AssertionError(
            "no coprime print pair"
        )  # pragma: no cover - supported moduli

    def seed(self, state: _State, count: int) -> list[str]:
        state.head = (state.head + count) % self.modulus
        return ["SEED"] * count

    def head(self, state: _State) -> int:
        return ((state.ptr + 1) * state.head) % self.modulus

    def clear(self, state: _State) -> list[str]:
        state.rest[state.ptr] += state.acc % self.io_modulus
        state.acc = 0
        return ["EXCRETE"]

    def append(self, state: _State, value: int) -> list[str]:
        rest = state.rest[state.ptr]
        head = (value - rest) % self.io_modulus
        tokens = []
        if head >= self.modulus:
            # For 255-cell/256-I/O arithmetic, synthesize low byte 255
            # before the final DIGEST; no SEED can make head 255.
            first = (127 - rest) % 256
            if first >= 254:
                first = (255 - rest) % 256
            tokens += self.set_head(state, first)
            state.acc = self.head(state) + rest
            tokens += ["DIGEST"]
            tokens += self.set_head(state, first + 1)
            state.acc ^= self.head(state) + rest
            tokens += ["DIGEST"]
            head = ((value ^ 255) - rest) % 256
        tokens += self.set_head(state, head)
        state.acc ^= self.head(state) + rest
        return [*tokens, "DIGEST", *self.clear(state)]

    def set_head(self, state: _State, head: int) -> list[str]:
        count = (head - self.head(state)) * pow(state.ptr + 1, -1, self.modulus)
        return self.seed(state, count % self.modulus)

    def route(self, state: _State, dest: int) -> list[str]:
        tokens = self.clear(state) if state.acc else []
        want = (dest - state.ptr) % 23
        count = (want - self.head(state)) * pow(state.ptr + 1, -1, self.modulus)
        tokens += self.seed(state, count % self.modulus)
        state.ptr = dest
        return [*tokens, "SPRINT"]

    def raise_to(self, state: _State, target: int) -> list[str]:
        remaining = target - state.rest[state.ptr]
        if remaining < 0:
            raise ValueError("target precedes the running sum")
        tokens = []
        maximum = self.io_modulus - 1
        if state.ptr == self.weight:
            while remaining > 2 * maximum:
                tokens += self.seed(state, self.greedy_seeds(state))
                state.acc = self.head(state) + state.rest[state.ptr]
                added = state.acc % self.io_modulus
                tokens += ["DIGEST", *self.clear(state)]
                remaining -= added
        while remaining:
            chunk = min(remaining, maximum)
            tokens += self.append(state, chunk)
            remaining -= chunk
        return tokens

    def greedy_seeds(self, state: _State) -> int:
        if self.io_modulus == self.modulus:
            residue = (self.head(state) + state.rest[state.ptr]) % self.modulus
            return max(0, -(-(self.modulus - self.step - residue) // self.step))
        counts = []
        for value in range(self.io_modulus - self.step, self.io_modulus):
            head = (value - state.rest[state.ptr]) % self.io_modulus
            # Head 255 duplicates head zero with 256 cells and 255 I/O;
            # include both representatives, or the short continuation fails.
            for reachable in range(head, self.modulus, self.io_modulus):
                count = (reachable - self.head(state)) * pow(
                    self.step, -1, self.modulus
                )
                counts.append(count % self.modulus)
        return min(counts)

    def jump(self, state: _State, target: int) -> tuple[list[str], int]:
        tokens = self.clear(state)
        if target <= state.rest[0]:
            raise ValueError("jump precedes the running sum")
        tokens += self.raise_to(state, max(state.rest[0], target - self.io_modulus + 1))
        hop = target - state.rest[0]
        tokens += self.append(state, hop)
        state.acc = state.head + state.rest[0]
        return [*tokens, "DIGEST", "LEAPFROG"], hop

    def level(self, state: _State, weight: int, pos: int) -> tuple[list[str], _State]:
        # Greedy banking costs at most four tokens per 252 added. These
        # slopes also cover jump chunks; the constants cover head solves.
        mixed = self.io_modulus != self.modulus
        arm_size = (6144 if mixed else 4096) + (weight + 15) // 16
        prefix_size = (4096 if mixed else 2048) + (arm_size + 31) // 32
        landing = pos + prefix_size
        cont = landing + arm_size
        tokens = self.clear(state)
        tokens += self.raise_to(state, landing + 15)
        tokens += self.seed(state, (-state.head) % self.modulus)
        start = state.rest[0]
        offset = (start - 16) % 64
        seeds = start % 2 if offset <= 14 else 64 - offset
        first = start + seeds
        tokens += self.seed(state, seeds)
        tokens += ["DIGEST"]
        tokens += self.seed(state, 16)
        tokens += ["DIGEST", "ACCEPT", "DIGEST", "LEAPFROG"]
        zero, one = state.clone(), state.clone()
        zero.acc, one.acc = first, first + 1
        one.rest[0] += 1
        jump, hop = self.jump(zero, cont)
        tokens += jump

        arm = self.clear(one)
        arm += self.route(one, self.weight)
        arm += self.raise_to(one, one.rest[self.weight] + weight)
        arm += self.route(one, 0)
        gap = cont - one.rest[0] - hop
        if gap < 0:  # pragma: no cover - arm region includes all head solves
            raise AssertionError("merge precedes the one-branch sum")
        # Equal tails leave equal pre-append sums, so even the missing-head
        # XOR construction closes with the same head on both paths.
        arm += self.append(one, gap % (self.io_modulus - 1))
        closing, _ = self.jump(one, cont)
        arm += closing
        expected = zero.clone()
        expected.rest[self.weight] += weight
        if one != expected:  # pragma: no cover - exact merge invariant
            raise AssertionError("branch states did not merge")
        if len(tokens) > prefix_size or len(arm) > arm_size:  # pragma: no cover
            raise AssertionError("chain node exceeds its reserved regions")
        tokens += ["SEED"] * (prefix_size - len(tokens))
        tokens += arm + ["SEED"] * (arm_size - len(arm))
        return tokens, zero

    def emit(self, inputs: int, base: int) -> list[str]:
        state = _State()
        tokens = []
        for digit, array in enumerate(self.prints):
            tokens += self.route(state, array)
            tokens += self.append(state, 48 + digit)
            tokens += self.clear(state)
            tokens += self.route(state, 0)
        tokens += self.route(state, self.weight)
        tokens += self.raise_to(state, base)
        tokens += self.route(state, 0)
        for bit in range(inputs):
            weight = self.io_modulus * (1 << (inputs - bit - 1))
            level, state = self.level(state, weight, len(tokens))
            tokens += level
        tokens += self.route(state, self.weight)
        count = (self.dispatch_head - self.head(state)) * pow(
            self.step, -1, self.modulus
        )
        tokens += self.seed(state, count % self.modulus)
        tokens += ["DIGEST", "LEAPFROG"]
        return tokens + ["SEED"] * max(0, base - len(tokens))

    def build(self, table: str, inputs: int) -> str:
        base = 0
        for _ in range(16):
            tokens = self.emit(inputs, base)
            if len(tokens) == base:
                break
            base = len(tokens)
        else:  # pragma: no cover - base padding exceeds the emission slope
            raise AssertionError("leaf base did not settle")
        for digit in table:
            leaf = [
                "EXCRETE",
                *["SEED"] * (int(digit) * self.digit_seeds),
                "SPRINT",
                "CONSUME",
                "PRONOUNCE",
                "EXCRETE",
                "LEAPFROG",
            ]
            tokens += leaf + ["SEED"] * (self.io_modulus - len(leaf))
        return " ".join(tokens)


def compact_chain(
    table: str, inputs: int, *, modulus: int, io_modulus: int | None = None
) -> str:
    """Emit a coprime-step chain whose weights vanish under I/O reduction."""
    return _Chain(modulus, io_modulus=io_modulus).build(table, inputs)
