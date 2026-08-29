r"""Prototype of a parameterized 123 boolean generator.

Groundwork already established (see ``docs/walls.md`` and the sibling
scripts):

* every byte 0-255 is printable by a ``1``/``2`` program (``bfs.py``), with
  ``'0'`` at length 14 and ``'1'`` at length 28 (``witness.py``);
* substitution selects between two outputs (``verify_sel.py``), via pointer
  phase divergence and the TRUE-backward re-run rather than a forward skip
  (``trace_sel.py``).

The construction here follows the Minifuck playbook: emit a template while
simulating all ``2**n`` instantiations in lockstep, and accept only a
program actually seen to print the table.

The bit setter must be same-width so no instantiation leaks its inputs
through ``len()``.  ``1`` flips the bit under the pointer and moves left;
the natural same-width partner is ``2``, which at a non-IO position simply
moves right -- so ``{Xi}`` becomes ``1`` for a one and ``2`` for a zero,
and the two differ in both tape effect and pointer displacement.
"""

_READ = -3
_WRITE = -2


class _Sim:
    """A 123 machine simulated without a program string.

    Mirrors ``_Machine`` in the interpreter, but exposes one-command steps so
    a generator can advance every row as it emits.  Only ``1`` and ``2`` are
    executed here; ``3`` is control flow and is handled by the caller, which
    knows the code layout.
    """

    def __init__(self) -> None:
        """Start on a blank tape at location 0."""
        self.bits: dict[int, bool] = {}
        self.pos = 0
        self.out: list[str] = []
        self.dead = False

    def copy(self) -> "_Sim":
        """Return an independent copy."""
        clone = _Sim.__new__(_Sim)
        clone.bits = dict(self.bits)
        clone.pos = self.pos
        clone.out = list(self.out)
        clone.dead = self.dead
        return clone

    def byte(self) -> int:
        """Read locations 0-7 as an MSB-first byte."""
        return sum(1 << (7 - i) for i in range(8) if self.bits.get(i, False))

    def exec(self, char: str) -> None:
        """Execute one ``1`` or ``2`` command.

        A ``2`` at the read position would consume stdin, which a
        parameterized program must never do; that row is marked ``dead``
        rather than raising, so a search can reject the branch and continue.
        """
        if self.dead:
            return
        if char == "1":
            self.bits[self.pos] = not self.bits.get(self.pos, False)
            self.pos -= 1
            if self.pos == -4:
                self.pos = 0
        elif char == "2":
            if self.pos == _READ:
                self.dead = True
            elif self.pos == _WRITE:
                self.out.append(chr(self.byte()))
                self.pos = 0
            else:
                self.pos += 1


class _Joint:
    """The ``2**n`` instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n: int) -> None:
        """Start one machine per row of the truth table."""
        self.n = n
        self.rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)]
                     for r in range(2**n)]
        self.ms = [_Sim() for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        """Append code and run it on every row, keeping them in lockstep."""
        self.parts.append(code)
        for m in self.ms:
            for ch in code:
                m.exec(ch)

    def emit_setter(self, i: int) -> None:
        """Emit ``{Xi}``: ``1`` when the row's bit is one, ``2`` when zero.

        This one-character setter displaces the pointer by -1 for a one and
        +1 for a zero, so rows drift apart in position by bit *count*.  See
        :meth:`emit_pair` for the displacement-neutral alternative.
        """
        self.parts.append("{X" + str(i) + "}")
        for bits, m in zip(self.rows, self.ms, strict=True):
            m.exec("1" if bits[i] else "2")

    def emit_pair(self, i: int) -> None:
        """Emit ``{Xi}`` as ``12`` for a one and ``21`` for a zero.

        Both are two characters and both return the pointer to where they
        started, so every row stays in position lockstep and no
        instantiation leaks its inputs through ``len()``.  They differ only
        in which cell is flipped: ``12`` flips the current cell, ``21``
        flips the one to its right.
        """
        self.parts.append("{X" + str(i) + "}")
        for bits, m in zip(self.rows, self.ms, strict=True):
            for ch in ("12" if bits[i] else "21"):
                m.exec(ch)

    def fork(self) -> "_Joint":
        """Return a copy, for trying a continuation without committing."""
        clone = _Joint.__new__(_Joint)
        clone.n = self.n
        clone.rows = self.rows
        clone.ms = [m.copy() for m in self.ms]
        clone.parts = list(self.parts)
        return clone

    def template(self) -> str:
        """Return the template built so far."""
        return "".join(self.parts)
