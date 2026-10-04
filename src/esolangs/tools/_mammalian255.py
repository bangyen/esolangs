"""Loopless Boolean decision trees using only Mammalian array zero."""

from dataclasses import dataclass, replace


@dataclass
class _State:
    head: int = 0
    rest: int = 0
    acc: int = 0
    io_modulus: int = 255

    def seed(self, count: int) -> list[str]:
        self.head = (self.head + count) % 255
        return ["SEED"] * count

    def clear(self) -> list[str]:
        self.rest += self.acc % self.io_modulus
        self.acc = 0
        return ["EXCRETE"]

    def load(self, value: int) -> list[str]:
        head = (value - self.rest) % self.io_modulus
        tokens = []
        if head == 255:
            # Adjacent sums crossing 127/128 (or 255/256) XOR to 255
            # in the low byte.  The final head is 254-2*value mod 256,
            # hence even and reachable despite the missing head 255.
            first = (127 - self.rest) % 256
            if first >= 254:
                first = (255 - self.rest) % 256
            tokens += self.seed((first - self.head) % 255)
            self.acc = self.head + self.rest
            tokens += ["DIGEST"]
            tokens += self.seed(1)
            self.acc ^= self.head + self.rest
            tokens += ["DIGEST"]
            head = ((value ^ 255) - self.rest) % 256
        tokens += self.seed((head - self.head) % 255)
        self.acc ^= self.head + self.rest
        return [*tokens, "DIGEST"]

    def append(self, value: int) -> list[str]:
        tokens = self.load(value)
        return tokens + self.clear()

    def raise_to(self, target: int) -> list[str]:
        if target < self.rest:
            raise AssertionError("target precedes the running sum")
        tokens = []
        while target - self.rest >= 254:
            # A 253 chunk skips the missing head and makes the sum even;
            # subsequent 254 chunks cannot need head 255 again.
            chunk = 253 if self.io_modulus == 256 and self.rest % 256 == 255 else 254
            tokens += self.append(chunk)
        tail = target - self.rest
        if tail:
            tokens += self.append(tail)
        return tokens

    def jump(self, target: int) -> list[str]:
        tokens = self.clear()
        tokens += self.raise_to(max(self.rest, target - 254))
        hop = target - self.rest
        if not 1 <= hop <= 254:
            raise AssertionError("jump has no positive tail")
        tokens += self.append(hop)
        self.acc = self.head + self.rest
        return [*tokens, "DIGEST", "LEAPFROG"]


def decision_tree(table: str, inputs: int, *, io_modulus: int = 255) -> str:
    """Emit a fixed-layout tree for cell modulus 255 and either I/O modulus."""
    leaf_size = 512 if io_modulus == 255 else 1024
    overhead = 2048 if io_modulus == 255 else 4096
    sizes, blocks = [leaf_size], [leaf_size]
    for _ in range(inputs):
        # Bulk chunks cost at most five tokens per 253 added to the sum;
        # 1/32 exceeds that slope.  The overhead covers the head solves.
        block = overhead + (sizes[-1] + 31) // 32
        blocks.append(block)
        sizes.append(block + 2 * sizes[-1])

    def build(rows: str, depth: int, pos: int, state: _State) -> list[str]:
        if not depth:
            tokens = state.clear()
            tokens += state.load(48 + int(rows))
            tokens += ["PRONOUNCE", "EXCRETE", "LEAPFROG"]
            # EXCRETE clears acc and leaves a nonzero last cell: the final
            # LEAPFROG has a negative target and halts on both output digits.
            return tokens + ["SEED"] * (sizes[0] - len(tokens))

        one_pos = pos + blocks[depth]
        zero_pos = one_pos + sizes[depth - 1]
        tokens = state.clear()
        tokens += state.raise_to(one_pos + 15)
        tokens += state.seed((-state.head) % 255)
        start = state.rest
        offset = (start - 16) % 64
        first_seeds = start % 2 if offset <= 14 else 64 - offset
        first = start + first_seeds
        tokens += state.seed(first_seeds)
        tokens += ["DIGEST"]
        tokens += state.seed(16)
        tokens += ["DIGEST", "ACCEPT", "DIGEST", "LEAPFROG"]
        zero = replace(state, acc=first)
        one = replace(state, rest=start + 1, acc=first + 1)
        tokens += zero.jump(zero_pos)
        if len(tokens) > blocks[depth]:  # pragma: no cover - fixed region bound
            raise AssertionError("decision node exceeds its reserved region")
        tokens += ["SEED"] * (blocks[depth] - len(tokens))
        middle = len(rows) // 2
        tokens += build(rows[middle:], depth - 1, one_pos, one)
        tokens += build(rows[:middle], depth - 1, zero_pos, zero)
        return tokens

    return " ".join(build(table, inputs, 0, _State(io_modulus=io_modulus)))
