"""Assemble the Minifuck boolean generator around a joint simulator.

Every emitted fragment is executed against all 2**n rows as it is emitted, so
the layout bookkeeping (which is affine but fiddly) is never hand-tracked --
the emitter reads the simulated truth and asserts it.

Pipeline:
  embed      each {Xi} once with `[<`/`xx`; `[x` derives the companion
  minterms   for each row in the ON-set: clamp, walk to a fresh station,
             chain v==0 literals against whichever cell currently holds the
             needed polarity, deposit with `[x`
  relay      `[<` turns acc into a pointer offset; a constant walk lands
             ptr = 6 + acc; `[x.` prints (acc=0 -> '1', acc=1 -> '0')
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from minifuck_joint_sim import Sim  # noqa: E402

TAPE = 4096


class Joint:
    """The 2**n instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n):
        self.n = n
        self.rows = [
            [(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)
        ]
        self.ms = []
        for _ in self.rows:
            m = Sim()
            m.tape = [0] * TAPE
            self.ms.append(m)
        self.parts = []

    def emit(self, code):
        self.parts.append(code)
        for m in self.ms:
            for ch in code:
                m.exec(ch)

    def emit_setter(self, i):
        """Emit the {Xi} placeholder; simulate each row with its own bit."""
        self.parts.append("{X" + str(i) + "}")
        for bits, m in zip(self.rows, self.ms):
            for ch in ("[<" if bits[i] else "xx"):
                m.exec(ch)

    def col(self, cell):
        return tuple(m.tape[cell] for m in self.ms)

    def ptrs(self):
        return tuple(m.ptr for m in self.ms)

    def template(self):
        return "".join(self.parts)


def _walk_to(j, target):
    """Walk right to `target` with `[x` (position-safe over any junk)."""
    ptrs = set(j.ptrs())
    assert len(ptrs) == 1, f"walk needs a converged pointer, got {ptrs}"
    cur = ptrs.pop()
    assert target >= cur, f"cannot walk left with [x ({cur} -> {target})"
    j.emit("[x" * (target - cur))


def _clamp(j):
    """Clamp every row's pointer to 0 (`<` never writes)."""
    hi = max(j.ptrs())
    j.emit("<" * (hi + 1))
    assert set(j.ptrs()) == {0}


def _pool_fix(j, walk_out):
    """Leave the pool so that the walk out to `walk_out` lands on 0011000.

    The pool is input-independent here, so this is pure bookkeeping: try
    short clamped walks and keep the pair that works.  A walk of length k
    complements cells 1..k (prefix-XOR) and clamping costs nothing.
    """
    target = [0, 0, 1, 1, 0, 0, 0]
    for a in range(9):
        for b in range(9):
            probe = Joint(j.n)
            probe.parts = list(j.parts)
            probe.ms = [m.copy() for m in j.ms]
            for k in (a, b):
                probe.emit("[x" * k)
                _clamp(probe)
            _walk_to(probe, walk_out)
            if [probe.col(c)[0] for c in range(7)] == target:
                for k in (a, b):
                    j.emit("[x" * k)
                    _clamp(j)
                return
    raise ValueError("could not set the pool pattern")


def build(truth_table, bit_stride=4):
    n = (len(truth_table) - 1).bit_length()
    if len(truth_table) != 2**n or set(truth_table) - set("01"):
        raise ValueError("truth_table must be a binary string of length 2**n")

    j = Joint(n)
    # --- embed: bit i at BASE + i*stride, companion derived by the crossing
    base = 16
    _walk_to(j, base - 1)
    cells = []
    for i in range(n):
        j.emit_setter(i)  # writes at ptr+1, no net move
        cells.append(j.ptrs()[0] + 1)
        j.emit("[x")  # cross: leaves the complement, carries the value on
        if i + 1 < n:
            j.emit("[x" * (bit_stride - 1))

    # --- relay.  Several things interact here that are easy to get wrong by
    # hand: the pool fix and the walk out both re-cross every candidate cell
    # (the prefix-XOR law), and cell 7's value at print time decides whether
    # the endgame prints the answer or its complement.  So don't model any of
    # it -- run the whole endgame in a copy per candidate and accept the cell
    # only if the copy actually prints the table.
    frontier = max(j.ptrs()) + 2
    _clamp(j)

    acc = None
    for cell in range(base - 4, frontier):
        probe = Joint(n)
        probe.parts = list(j.parts)
        probe.ms = [m.copy() for m in j.ms]
        try:
            _endgame(probe, cell)
        except (ValueError, AssertionError):
            continue
        if ["".join(m.out) for m in probe.ms] == list(truth_table):
            acc = cell
            break
    if acc is None:
        raise ValueError(
            f"no cell prints {truth_table!r} directly; this table needs "
            "the minterm loop, which is not built yet (see the notes)"
        )

    _endgame(j, acc)
    return j, cells, acc


def _endgame(j, acc):
    """Pool fix, relay the acc cell into the pointer, and print.

    `[<` leaves the pointer at (acc-1) + the cell's value, a constant walk
    lands it on 6 or 7, and `[x.` prints one ASCII digit.  Which digit each
    position yields depends on cell 7, so the caller checks the output rather
    than assuming an orientation.
    """
    _pool_fix(j, acc - 1)
    _walk_to(j, acc - 1)
    live = j.col(acc)
    j.emit("[<")
    assert j.ptrs() == tuple(acc - 1 + v for v in live), (j.ptrs(), live)
    j.emit("<" * (acc - 7))
    assert j.ptrs() == tuple(6 + v for v in live), j.ptrs()
    for cell in range(8):
        col = j.col(cell)
        assert len(set(col)) == 1, f"pool cell {cell} is input-dependent: {col}"
    j.emit("[x.")


def emit_program(truth_table):
    j, _cells, _acc = build(truth_table)
    outs = ["".join(m.out) for m in j.ms]
    expect = list(truth_table)
    if outs != expect:
        raise AssertionError(f"generator self-check failed: {outs} != {expect}")
    return j.template()


if __name__ == "__main__":
    for table in ("0001", "0110", "1110", "1000", "1001", "0111"):
        try:
            t = emit_program(table)
            print(f"{table}: OK  len={len(t)}  {t[:60]}...")
        except (ValueError, AssertionError) as exc:
            print(f"{table}: {exc}")
