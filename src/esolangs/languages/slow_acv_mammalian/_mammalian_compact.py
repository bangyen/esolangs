"""Mammalian chains with coprime array assignments."""

from dataclasses import dataclass, field, replace
from math import gcd, lcm

from esolangs.generation.helpers import essential_inputs, read_at
from esolangs.languages.slow_acv_mammalian._sums import (
    _aim,
    _crossing_pair,
    _leaf,
    _read_seeds,
    _seeds_onto,
)
from esolangs.languages.slow_acv_mammalian.interpreter import _ARRAYS, MammalianModuli


@dataclass
class _State:
    head: int = 0
    rest: list[int] = field(default_factory=lambda: [0] * _ARRAYS)
    acc: int = 0
    ptr: int = 0

    def clone(self) -> "_State":
        return replace(self, rest=self.rest.copy())


def _routing_seeds(head: int, step: int, want: int, modulus: int) -> int:
    """Return the earliest SEED count reaching a head congruent to want modulo 23."""
    return _seeds_onto(head, step, range(want, modulus, _ARRAYS), modulus)


#: The print pair by cell modulus: two unit arrays (a SEED run reaches any
#: head there) past 0 and the weight array, ``digit`` of its SEEDs apart so
#: a leaf's digit is its SEED count.  Under 256 the units are the even
#: arrays and the weight array 2 steps by 3: one SEED from any even array
#: lands on an odd one or wraps onto 0 or 2, two take 4 to 10.  Under 255
#: the weight array 1 steps by 2, and 10 to 12 is the first step from a
#: unit (``a + 1`` coprime to 3, 5 and 17) onto one.
_PRINTS = {256: (4, 10, 2), 255: (10, 12, 1)}


class _Chain:
    def __init__(self, modulus: int, *, io_modulus: int | None = None) -> None:
        moduli = MammalianModuli(modulus, modulus if io_modulus is None else io_modulus)
        self.modulus, self.io_modulus = moduli.cell_modulus, moduli.io_modulus
        units = [array for array in range(_ARRAYS) if gcd(array + 1, modulus) == 1]
        self.weight = units[1]
        self.step = self.weight + 1
        first, second, self.digit_seeds = _PRINTS[self.modulus]
        self.prints = (first, second)
        self.dispatch_head = (first - self.weight) % _ARRAYS
        self.pools = tuple(
            array for array in units if array not in (0, self.weight, first, second)
        )[:4]

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
            first, head = _crossing_pair(rest, value)
            tokens += self.set_head(state, first)
            state.acc = self.head(state) + rest
            tokens += ["DIGEST"]
            tokens += self.set_head(state, first + 1)
            state.acc ^= self.head(state) + rest
            tokens += ["DIGEST"]
        tokens += self.set_head(state, head)
        state.acc ^= self.head(state) + rest
        return [*tokens, "DIGEST", *self.clear(state)]

    def set_head(self, state: _State, head: int) -> list[str]:
        count = (head - self.head(state)) * pow(state.ptr + 1, -1, self.modulus)
        return self.seed(state, count % self.modulus)

    def route(self, state: _State, dest: int, *, short: bool = False) -> list[str]:
        tokens = self.clear(state) if state.acc else []
        want = (dest - state.ptr) % _ARRAYS
        if short:
            count = _routing_seeds(self.head(state), state.ptr + 1, want, self.modulus)
        else:
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
            # A non-final 254 write avoids synthesizing unreachable head 255.
            if (
                remaining > maximum
                and self.modulus < self.io_modulus
                and (chunk - state.rest[state.ptr]) % self.io_modulus >= self.modulus
            ):
                chunk -= 1
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

    def costs(self) -> tuple[int, int, int]:
        """Bound one append, a raise's two end chunks, and each full chunk between."""
        missing = self.modulus < self.io_modulus
        append = 2 * self.modulus + 3 if missing else self.modulus + 1
        # Two arbitrary end chunks; full middle chunks cost 3/4 tokens.
        # Missing head 255 adds at most 257 once per 256 full chunks.
        raise_base = 2 * append + (self.modulus + 2 if missing else 0)
        slope = 5 if missing else 3 + int(self.modulus != self.io_modulus)
        return append, raise_base, slope

    def reserve(self, fixed: int) -> int:
        """Bound a region of ``fixed`` tokens plus a raise across itself."""
        maximum = self.io_modulus - 1
        slope = self.costs()[2]
        # x = fixed + slope*q <= maximum*q, so ceil(x/maximum) <= q.
        return fixed + slope * (-(-fixed // (maximum - slope)))

    def regions(
        self, state: _State, weight: int, pos: int, pool: int | None
    ) -> tuple[int, int]:
        """Bound node regions, including residue wraps and missing-head XORs."""
        maximum = self.io_modulus - 1
        missing = self.modulus < self.io_modulus
        append, raise_base, slope = self.costs()
        reserve = self.reserve
        bank = 3
        if pool is None:
            minimum = self.io_modulus - self.step
            tail_append = append
            if missing:
                tail_append += pow(self.step, -1, self.modulus) - 1
            # One initial greedy solve, four-token continuations, two tails.
            bank = self.modulus + 1 + 4 * (-(-weight // minimum)) + 2 * tail_append
        arm = reserve(4 + 2 * self.modulus + bank + 2 * append + raise_base)
        distance = max(0, pos + 15 - state.rest[0] - state.acc % self.io_modulus)
        # Reset/read overhead is modulus+84; the closing jump adds three.
        prefix = reserve(
            self.modulus
            + 87
            + 2 * raise_base
            + append
            + slope * (-(-arm // maximum) + -(-distance // maximum))
        )
        return prefix, arm

    def read_node(
        self, state: _State, landing: int
    ) -> tuple[list[str], _State, _State]:
        """Emit one read node up to its branch split: tokens, 0-exit, 1-exit."""
        tokens = self.clear(state)
        tokens += self.raise_to(state, landing + 15)
        start = state.rest[0]
        if self.modulus == 255:
            seeds = _read_seeds(state.head, start, self.modulus)
        else:
            tokens += self.seed(state, (-state.head) % self.modulus)
            seeds = _aim(start)
        tokens += self.seed(state, seeds)
        first = start + state.head
        tokens += ["DIGEST"]
        tokens += self.seed(state, 16)
        tokens += ["DIGEST", "ACCEPT", "DIGEST", "LEAPFROG"]
        zero, one = state.clone(), state.clone()
        zero.acc, one.acc = first, first + 1
        one.rest[0] += 1
        return tokens, zero, one

    def bank_arm(
        self,
        one: _State,
        zero: _State,
        weight: int,
        pool: int | None,
        cont: int,
        hop: int,
    ) -> list[str]:
        """Emit the 1-branch: bank ``weight``, then close the jump to ``cont``."""
        arm = self.clear(one)
        if pool is None:
            arm += self.route(one, self.weight, short=True)
            arm += self.raise_to(one, one.rest[self.weight] + weight)
        else:
            arm += self.route(one, pool, short=True)
            one.rest[pool] -= weight
            one.acc, one.ptr = weight, self.weight
            arm += ["CONSUME", "SPRINT", *self.clear(one)]
        arm += self.route(one, 0, short=True)
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
        if pool is not None:
            # Spent pools are never read again; the remaining live state merges.
            expected.rest[pool] -= weight
        if one != expected:  # pragma: no cover - exact merge invariant
            raise AssertionError("branch states did not merge")
        return arm

    def level(
        self, state: _State, weight: int, pos: int, pool: int | None
    ) -> tuple[list[str], _State]:
        prefix_size, arm_size = self.regions(state, weight, pos, pool)
        landing = pos + prefix_size
        cont = landing + arm_size
        tokens, zero, one = self.read_node(state, landing)
        jump, hop = self.jump(zero, cont)
        tokens += jump
        arm = self.bank_arm(one, zero, weight, pool, cont, hop)
        if len(tokens) > prefix_size or len(arm) > arm_size:  # pragma: no cover
            raise AssertionError("chain node exceeds its reserved regions")
        tokens += ["SEED"] * (prefix_size - len(tokens))
        tokens += arm + ["SEED"] * (arm_size - len(arm))
        return tokens, zero

    def plan(self, inputs: int) -> tuple[list[tuple[int, int | None]], int, int, int]:
        free = min(inputs, len(self.pools) + 1)
        fixed = inputs - free
        unit = 8
        stride = lcm(self.io_modulus, unit)
        if self.io_modulus == 255 and inputs > free:
            unit = 6 + self.digit_seeds
            free = min(free, (self.io_modulus // unit).bit_length() - 1)
            fixed = inputs - free
            stride = self.io_modulus
        weights = [stride * (1 << (fixed - bit - 1)) for bit in range(fixed)]
        weights += [unit * (1 << bit) for bit in range(free)]
        pools: list[int | None] = [None] * (fixed + 1) + list(self.pools[: free - 1])
        return list(zip(weights, pools, strict=True)), free, stride, unit

    def plant_pool(
        self, state: _State, weight: int, pool: int, *, compact: bool = True
    ) -> list[str]:
        tokens = self.route(state, pool, short=True)
        hop = (self.weight - pool) % _ARRAYS
        if compact and self.modulus == self.io_modulus:
            inverse = pow(pool + 1, -1, self.modulus)
            head, rest = self.head(state), state.rest[pool]

            def seeds(first: int, second: int) -> int:
                a = (first - rest) % self.modulus
                b = (second - rest - first) % self.modulus
                end = (-pool) % _ARRAYS
                return (
                    ((a - head) * inverse) % self.modulus
                    + ((b - a) * inverse) % self.modulus
                    + _routing_seeds(b, pool + 1, end, self.modulus)
                )

            # Reversing the writes can add a whole seed cycle; avoid paying
            # more seeds than the compact layout saves in filler cells.
            compact = seeds(weight, hop) - seeds(hop, weight) <= weight + 1
        # Minimal layout shifts the last cell to index weight after CONSUME.
        count = weight + 1 if compact else 2 * weight + 2
        middle = (weight - 1) // 2 if compact else weight
        ride = weight if compact else weight - 1
        for cell in range(count):
            if cell == middle:
                tokens += self.append(state, weight)
            elif cell == ride:
                tokens += self.append(state, hop)
            else:
                tokens += self.clear(state)
        return tokens + self.route(state, 0, short=True)

    def plant_tables(
        self, state: _State, plan: list[tuple[int, int | None]], base: int
    ) -> list[str]:
        """Plant the print arrays and pools, then raise the weight array to ``base``."""
        tokens: list[str] = []
        for digit, array in enumerate(self.prints):
            tokens += self.route(state, array, short=True)
            tokens += self.append(state, 48 + digit)
            tokens += self.clear(state)
            tokens += self.route(state, 0, short=True)
        for weight, pool in plan:
            if pool is not None:
                tokens += self.plant_pool(state, weight, pool)
        tokens += self.route(state, self.weight, short=True)
        tokens += self.raise_to(state, base)
        tokens += self.route(state, 0, short=True)
        return tokens

    def emit(
        self, plan: list[tuple[int, int | None]], table: int
    ) -> tuple[list[str], int]:
        """Return everything but the leaf bodies, and where the leaf table starts.

        The table comes first, behind a jump from the empty machine sized by
        :meth:`reserve`, so its base is known before array 16 is raised to it.
        """
        state = _State()
        append, raise_base, slope = self.costs()
        maximum = self.io_modulus - 1
        # A jump is a clear, a raise, the hop's append and DIGEST LEAPFROG.
        base = self.reserve(3 + raise_base + append + slope * -(-table // maximum))
        tokens, _ = self.jump(state, base + table)
        if len(tokens) > base:  # pragma: no cover - reserve bounds the jump
            raise AssertionError(f"the table jump overran its {base} tokens")
        tokens += ["SEED"] * (base + table - len(tokens))
        tokens += self.plant_tables(state, plan, base)
        for weight, pool in plan:
            level, state = self.level(state, weight, len(tokens), pool)
            tokens += level
        tokens += self.route(state, self.weight)
        tokens += self.set_head(state, self.dispatch_head)
        return [*tokens, "DIGEST", "LEAPFROG"], base

    def build(self, table: str, inputs: int, *, project_inputs: bool = False) -> str:
        original_inputs = inputs
        used = (
            essential_inputs(table, inputs) if project_inputs else list(range(inputs))
        )
        if not used:
            used = list(range(inputs))
        inputs = len(used)
        plan, free, stride, unit = self.plan(inputs)
        if inputs < original_inputs:
            kept = dict(zip(used, plan, strict=True))
            # Keep every read in place; zero weights merge both digit paths
            # without allocating another leaf coordinate.
            plan = [kept.get(i, (0, None)) for i in range(original_inputs)]
            table = read_at(table, used, original_inputs)
        groups = 1 << (inputs - free)
        tokens, base = self.emit(plan, (groups - 1) * stride + (unit << free))
        # Leaf offsets need no shared alignment: LEAPFROG addresses tokens.
        for group in range(groups):
            for offset in range(1 << free):
                suffix = int(f"{offset:0{free}b}"[::-1], 2)
                digit = table[(group << free) | suffix]
                start = base + group * stride + offset * unit
                tokens[start : start + unit] = _leaf(
                    int(digit) * self.digit_seeds, unit=unit, guard=False
                )
        return " ".join(tokens)


def compact_chain(
    table: str,
    inputs: int,
    *,
    modulus: int,
    io_modulus: int | None = None,
    project_inputs: bool = False,
) -> str:
    """Emit pooled-weight chains with leaves in I/O-aligned blocks."""
    return _Chain(modulus, io_modulus=io_modulus).build(
        table, inputs, project_inputs=project_inputs
    )
