"""Loopless Boolean decision trees using only Mammalian array zero."""

from dataclasses import dataclass, replace


@dataclass
class _State:
    head: int = 0
    rest: int = 0
    acc: int = 0

    def seed(self, count: int) -> list[str]:
        self.head = (self.head + count) % 255
        return ["SEED"] * count

    def clear(self) -> list[str]:
        self.rest += self.acc % 255
        self.acc = 0
        return ["EXCRETE"]

    def append(self, value: int) -> list[str]:
        tokens = self.seed(((value - self.rest) % 255 - self.head) % 255)
        self.rest += value
        return [*tokens, "DIGEST", "EXCRETE"]

    def raise_to(self, target: int) -> list[str]:
        if target < self.rest:
            raise AssertionError("target precedes the running sum")
        chunks, tail = divmod(target - self.rest, 254)
        tokens = []
        for _ in range(chunks):
            tokens += self.append(254)
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


def decision_tree(table: str, inputs: int) -> str:
    """Emit a fixed-layout tree for cell and I/O modulus 255."""
    sizes, blocks = [512], [512]
    for _ in range(inputs):
        # A jump costs at most four tokens per 254 added to the sum,
        # plus two head solves.  1/32 reserves more than twice that slope.
        block = 2048 + (sizes[-1] + 31) // 32
        blocks.append(block)
        sizes.append(block + 2 * sizes[-1])

    def build(rows: str, depth: int, pos: int, state: _State) -> list[str]:
        if not depth:
            tokens = state.clear()
            tokens += state.seed(
                ((48 + int(rows) - state.rest) % 255 - state.head) % 255
            )
            tokens += ["DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]
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

    return " ".join(build(table, inputs, 0, _State()))
