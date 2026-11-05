"""NOR machine Boolean program generator: the table as one integer, muxed.

The machine has no literals: an input and its complement make 0, then -2.
Horner builds the table integer V, and essential inputs form P, first input
lowest. The accumulator starts as ``(V << m) | P``. Each input selects a
half of V with a mask above the remaining input field; shifting the whole
accumulator right drops the consumed bit. Only one persistent value rides
large smear passes: rebuilding -2 costs 15 commands, so halves of at least
16 consume it. The final V prints the selected low bit. Code runs once.

Size:
    6T + 8r + O(n^2) chars for r runs of true rows, every input essential;
    n=4 parity: 545 chars; n=8 constant zero: 12 chars

Decisions:
    Horner holds ``~V`` through each run of 1s ([ablations.complement_runs]),
    the smear shares its rotations with the half-shift
    ([ablations.shared_rotations]), and with every input essential the
    constants wait until after Horner ([ablations.late_constants]).

    An ignored input is absorbed as ``1 = nor(nor(x, 1), 0)``: ``x`` is 0
    or 1, so ``nor(x, 1)`` is -2 for both.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.nor_machine.proof_formulas import execution, workspace
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._language import Language, Shape
from esolangs.runtime._definition import RuntimeSpec


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
        self.shift_all({a: (op, k)})

    def shift_all(self, jobs: dict[str, tuple[str, int]]) -> None:
        """Shift several values on shared passes: one rotation serves all."""
        left = {a: k for a, (_, k) in jobs.items() if k}
        while left:
            a = self.names[0]
            if a in left:
                self.out.append(jobs[a][0])
                left[a] -= 1
                if not left[a]:
                    del left[a]
            else:
                self.out.append("I")
            self.names = [*self.names[1:], a]


def nor_machine(truth_table: str) -> str:
    """Build a NOR machine program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    m = len(essential)
    table = read_at(truth_table, essential, n)
    if not essential:
        # [ablations.constant_table_audit_20261101]: NOR all inputs, then x NOR ~x.
        return "V" * (n - 1) + "AAVV" + ("V" if table == "0" else "AVLAVV")
    q = _Queue(n)
    # 0 = nor(~x, x) from the first input.
    c = q.dup("x0")
    c_b = q.dup(c)
    zero = q.nor(q.dup(c), q.nor(c, c_b))
    # With every input essential no 1 is needed until the mux, so none rides
    # the queue through the T Horner shifts and the smear passes.
    lean = len(essential) == n
    one = ""
    if not lean:
        # 1 = nor(-1 << 1, 0).
        ones = q.nor(q.dup(zero), q.dup(zero))
        q.unary("L", ones, ones)
        one = q.nor(ones, q.dup(zero))
        for i in range(n):
            if i not in essential:
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
    if lean:
        # -2 from packed: nor(p, ~p) is 0, ~0 is -1, and one shift gives -2.
        p0 = q.dup(packed)
        minus_one = q.inv(q.nor(p0, q.inv(q.dup(p0))))
        q.unary("L", minus_one, minus_one)
        low = minus_one
    else:
        low = q.inv(one)  # -2: NOR with it keeps bit 0 of the complement
    # [ablations.single_accumulator_20261102]: retain P below the table;
    # each right shift consumes one input bit and shrinks that field.
    q.shift("L", v, m)
    v = q.or_(v, packed)
    for remaining in range(m, 0, -1):
        h = 1 << (remaining - 1)
        refresh_low = h >= 16  # one-value rematerialization costs exactly 15
        mask = q.nor(q.inv(q.dup(v)), low if refresh_low else q.dup(low))
        upper = q.dup(v)
        width = 1
        while width < h:
            wide = q.dup(mask)
            q.shift_all({wide: ("L", width), upper: ("R", width)})
            mask = q.or_(mask, wide)
            width *= 2
        q.shift("R", upper, h - width + 1)
        q.shift("L", mask, remaining)
        # [ablations.nor_mux_20261102]: complementary negative arms select
        # with four NORs, without keeping three copies of the aligned mask.
        keep_lower = q.nor(v, q.dup(mask))
        keep_upper = q.nor(upper, q.inv(mask))
        v = q.nor(keep_lower, keep_upper)
        q.unary("R", v, v)
        if refresh_low:
            low = _low_from_singleton(q, v)
    result = q.nor(q.inv(v), low)
    assert q.names == [result], q.names
    return "".join(q.out) + "V"


def _low_from_singleton(q: _Queue, value: str) -> str:
    """Keep the accumulator and append -2 in exactly 15 commands."""
    assert q.names == [value], q.names
    inverse = q.inv(q.dup(value))
    zero = q.nor(q.dup(value), inverse)
    low = q.inv(zero)
    q.unary("L", low, low)
    return low


LANGUAGE = Language(
    "NOR machine",
    RuntimeSpec(
        "nor_machine",
        category="queue_based",
        eof="every input is enqueued first, so a short input is a shorter queue",
        empty_program="a program with no command loops forever",
    ),
    boolean=nor_machine,
    certification=CertificationSpec(
        proof_execution=(execution, False, (1, 2, 3, 5)),
        proof_workspace=(workspace, False, (1, 2, 3, 5)),
    ),
    # Not a tree: Horner's rule packs every row of the essential-input table.
    shape=Shape.LOOKUP,
    wrap=wrap_chars,
)
