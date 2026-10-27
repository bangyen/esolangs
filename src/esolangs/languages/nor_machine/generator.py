"""NOR machine Boolean program generator: the table as one integer, muxed.

The machine has no literals, so the first input is copied and NORed with
its own complement into 0, and 1 is grown from that.  ``V`` is built by
Horner's rule so bit ``k`` holds row ``k``, and the essential inputs are
packed into one integer ``P``, first input lowest.  Each input then keeps
the half of ``V`` it selects: its bit smeared over a half-width mask
chooses ``V`` or ``V >> h``.  The low bit of what is left is printed by the
lone final ``V``.  Straight-line code, run once: it never loops.

Size:
    13T + 12r + 10n^2 + 96n - 29 chars for r runs of true rows, every
    input essential, n >= 2; n=4 parity: 783 chars

Decisions:
    Horner holds ``~V`` through each run of 1s ([ablations.complement_runs]).

    An ignored input is absorbed as ``1 = nor(nor(x, 1), 0)``: ``x`` is 0
    or 1, so ``nor(x, 1)`` is -2 for both.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._language import Language, Shape


class _Queue:
    """The queue's names, front first, and the commands emitted so far."""

    def __init__(self, n: int) -> None:
        self.names = [f"x{i}" for i in range(n)]
        self.out: list[str] = []
        self.count = 0

    def new(self) -> str:
        self.count += 1
        return f"t{self.count}"

    def front(self, a: str) -> None:
        """Rotate ``a`` to the front."""
        i = self.names.index(a)
        self.out.append("I" * i)
        self.names = self.names[i:] + self.names[:i]

    def unary(self, op: str, a: str, result: str) -> None:
        self.front(a)
        self.out.append(op)
        self.names = [*self.names[1:], result]

    def dup(self, a: str) -> str:
        """Keep ``a`` and return the name of a copy."""
        copy = self.new()
        self.front(a)
        self.out.append("A")
        self.names = [*self.names[1:], a, copy]
        return copy

    def nor(self, a: str, b: str) -> str:
        # Swap pairs until a and b are adjacent, then dequeue them together.
        while True:
            size = len(self.names)
            ia, ib = self.names.index(a), self.names.index(b)
            if ib == (ia + 1) % size:
                self.front(a)
                break
            if ia == (ib + 1) % size:
                self.front(b)
                break
            self.front(a)
            self.out.append("X")
            self.names = [*self.names[2:], self.names[1], self.names[0]]
        result = self.new()
        self.out.append("V")
        self.names = [*self.names[2:], result]
        return result

    def inv(self, a: str) -> str:
        return self.nor(a, self.dup(a))

    def or_(self, a: str, b: str) -> str:
        return self.inv(self.nor(a, b))

    def shift(self, op: str, a: str, k: int) -> None:
        for _ in range(k):
            self.unary(op, a, a)


def nor_machine(truth_table: str) -> str:
    """Build a NOR machine program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    q = _Queue(n)
    # 0 = nor(~x, x) and 1 = nor(-1 << 1, 0) from the first input.
    c = q.dup("x0")
    c_b = q.dup(c)
    zero = q.nor(q.dup(c), q.nor(c, c_b))
    ones = q.nor(q.dup(zero), q.dup(zero))
    q.unary("L", ones, ones)
    one = q.nor(ones, q.dup(zero))
    for i in range(n):
        if i not in essential:
            # nor(x, 1) is -2 for x in {0, 1}, and nor(-2, 0) is 1.
            one = q.nor(q.nor(f"x{i}", one), q.dup(zero))
    packed = f"x{essential[-1]}" if essential else ""
    for i in reversed(essential[:-1]):
        q.shift("L", packed, 1)
        packed = q.or_(packed, f"x{i}")
    # ~V << 1 is ~((V << 1) | 1), so a 1 shifts the complement in free:
    # hold ~V through each run of 1s and pay one ``inv`` per change.
    v, inverted = zero, False
    for bit in reversed(table):
        if inverted != (bit == "1"):
            v, inverted = q.inv(v), not inverted
        q.unary("L", v, v)
    if inverted:
        v = q.inv(v)
    low = q.inv(one)  # -2: NOR with it keeps bit 0 of the complement
    for level in range(1, len(essential) + 1):
        h = len(table) >> level
        bit = q.dup(packed) if level < len(essential) else packed
        mask = q.nor(q.inv(bit), q.dup(low))
        if level < len(essential):
            q.unary("R", packed, packed)
        width = 1
        while width < h:
            wide = q.dup(mask)
            q.shift("L", wide, width)
            mask = q.or_(mask, wide)
            width *= 2
        upper = q.dup(v)
        q.shift("R", upper, h)
        # mask ? upper : v, as nor(nor(~mask, ~upper), nor(mask, ~v)).
        keep_upper = q.nor(q.inv(q.dup(mask)), q.inv(upper))
        keep_lower = q.nor(mask, q.inv(v))
        v = q.inv(q.nor(keep_upper, keep_lower))
    result = q.nor(q.inv(v), low)
    assert q.names == [result], q.names
    return "".join(q.out) + "V"


LANGUAGE = Language(
    "NOR machine",
    "nor_machine",
    category="queue_based",
    boolean=nor_machine,
    # Not a tree: Horner's rule packs every row of the essential-input table.
    shape=Shape.LOOKUP,
    wrap=wrap_chars,
    eof="every input is enqueued first, so a short input is a shorter queue",
    empty_program="a program with no command loops forever",
)
