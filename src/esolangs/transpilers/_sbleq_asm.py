"""The S*bleq assembler that :func:`decleq_to_sbleq` emits through.

Extracted from ``transpilers.py`` because it is the one large piece of
machinery there: a symbolic assembler with labels, sentinels and address
resolution, at 178 lines against 127 for the other three transpilers put
together.  ``_bf_streetcode`` was split out on the same reasoning.

It stays private and lives beside its only caller rather than in the
package ``__init__``, which would put it out of the mutation harness's
reach -- ``_modules`` skips ``__init__`` as a non-target.
"""

from typing import Any

_SEQ = object()  # sentinel ``c``: fall through to the next instruction

_HALT = "__halt__"  # a jump cell holding -1; S*bleq halts on a negative target


class _SbleqAsm:
    """Tiny S*bleq assembler used by :func:`decleq_to_sbleq`.

    Emits into three regions -- ``[code | scratch | image]`` -- and resolves
    symbolic operands at :meth:`build` time.  An operand is an ``int`` (a
    literal address, including the ``-1``/``-2``/``-3`` specials), a
    ``("scratch", i)`` pair, or a ``("field", label, off)`` reference to
    operand ``off`` of the instruction at ``label`` -- the last is how the
    emulator patches its own operands to reach an address it computed at
    runtime, which is S*bleq's only form of indirect load and store.

    S*bleq branches when the difference is at most zero and otherwise falls
    through, so a ``c`` of ``_SEQ`` still has to name the next instruction:
    :meth:`build` allocates a cell holding that address.
    """

    def __init__(self) -> None:
        self.code: list[list[Any]] = []
        self.syms: dict[str, int] = {}
        self.names: dict[str, int] = {}
        self.scratch: list[int] = []
        self.jumps: dict[str, int] = {}
        self.image: list[int] = []
        self._serial = 0

    # -- allocation ---------------------------------------------------

    def cell(self, name: str, value: int = 0) -> tuple[str, int]:
        """Return the named scratch cell, creating it with ``value``."""
        if name not in self.names:
            self.names[name] = len(self.scratch)
            self.scratch.append(value)
        return ("scratch", self.names[name])

    def const(self, value: int) -> tuple[str, int]:
        """Return a scratch cell holding the constant ``value``."""
        return self.cell(f"_k{value}", value)

    def jcell(self, label: str) -> tuple[str, int]:
        """Return a scratch cell holding the address of ``label``.

        S*bleq's ``c`` operand is indirect (``ip = mem[c]``), so a jump
        needs a cell holding the target rather than the target itself.
        """
        key = "@" + label
        if key not in self.names:
            self.names[key] = len(self.scratch)
            self.scratch.append(0)
            self.jumps[label] = self.names[key]
        return ("scratch", self.names[key])

    def field(self, label: str, off: int) -> tuple[str, str, int]:
        """Return the address of operand ``off`` of instruction ``label``."""
        return ("field", label, off)

    def fresh(self, stem: str) -> str:
        """Return a label unique to this assembler."""
        self._serial += 1
        return f"{stem}.{self._serial}"

    # -- emission -----------------------------------------------------

    def emit(self, a: Any, b: Any, c: Any = _SEQ, label: str | None = None) -> None:
        """Emit ``a b c``; ``c`` defaults to falling through."""
        if label is not None:
            self.mark(label)
        self.code.append([a, b, c])

    def mark(self, label: str) -> None:
        """Attach ``label`` to the next instruction emitted."""
        if label in self.syms:
            raise ValueError(f"duplicate label {label}")
        self.syms[label] = len(self.code)

    # -- macros -------------------------------------------------------

    def goto(self, label: str) -> None:
        """Jump to ``label`` unconditionally (zeroing a cell always branches)."""
        z = self.cell("_zero")
        self.emit(z, z, self.jcell(label))

    def clear(self, dst: Any) -> None:
        """``dst = 0``."""
        self.emit(dst, dst)

    def sub(self, dst: Any, src: Any) -> None:
        """``dst -= src``, falling through whatever the sign."""
        self.emit(dst, src)

    def add(self, dst: Any, src: Any) -> None:
        """``dst += src``, via a negated temporary."""
        neg = self.cell("_neg")
        self.emit(neg, neg)
        self.emit(neg, src)
        self.emit(dst, neg)

    def move(self, dst: Any, src: Any) -> None:
        """``dst = src``, preserving ``src``."""
        self.clear(dst)
        self.add(dst, src)

    def branch_neg(self, value: Any, label: str) -> None:
        """Branch to ``label`` when ``value`` is negative, preserving it.

        ``value < 0`` is ``value + 1 <= 0``, which is the branch S*bleq
        actually offers.
        """
        t = self.cell("_bt")
        self.move(t, value)
        self.emit(t, self.const(-1), self.jcell(label))

    def branch_le(self, value: Any, other: Any, label: str) -> None:
        """Branch to ``label`` when ``value <= other``, preserving both."""
        t = self.cell("_bt")
        self.move(t, value)
        self.emit(t, other, self.jcell(label))

    def load_indirect(self, dst: Any, addr: Any) -> None:
        """``dst = mem[addr]`` for a runtime address held in ``addr``."""
        site = self.fresh("ld")
        f = self.field(site, 1)
        self.clear(f)
        self.add(f, addr)
        self.clear(dst)
        neg = self.cell("_neg")
        self.emit(neg, neg)
        self.emit(neg, 0, label=site)  # neg -= mem[addr]; b is patched above
        self.emit(dst, neg)  # dst = -neg

    def store_indirect(self, addr: Any, value: Any) -> None:
        """``mem[addr] = value`` for a runtime address held in ``addr``."""
        zap, put = self.fresh("stz"), self.fresh("stp")
        for site, off in ((zap, 0), (zap, 1), (put, 0)):
            f = self.field(site, off)
            self.clear(f)
            self.add(f, addr)
        neg = self.cell("_neg2")
        self.clear(neg)
        self.sub(neg, value)  # neg = -value
        self.emit(0, 0, label=zap)  # mem[addr] -= mem[addr]
        self.emit(0, neg, label=put)  # mem[addr] -= -value

    # -- build --------------------------------------------------------

    def build(self) -> list[int]:
        """Resolve every symbolic operand and lay the three regions out."""
        base_scratch = 3 * len(self.code)

        seq: dict[int, int] = {}
        for i, (_a, _b, c) in enumerate(self.code):
            if c is _SEQ and 3 * (i + 1) not in seq:
                self.scratch.append(3 * (i + 1))
                seq[3 * (i + 1)] = len(self.scratch) - 1

        base_image = base_scratch + len(self.scratch)
        # ``base`` holds the image's own address, which only becomes known
        # here; the emulator adds a Decleq index to it to reach a cell.
        self.scratch[self.names["base"]] = base_image
        for label, idx in self.jumps.items():
            self.scratch[idx] = -1 if label == _HALT else 3 * self.syms[label]

        def resolve(v: Any) -> int:
            if isinstance(v, tuple):
                if v[0] == "scratch":
                    return base_scratch + int(v[1])
                return 3 * self.syms[str(v[1])] + int(v[2])
            return int(v)

        mem: list[int] = []
        for i, (a, b, c) in enumerate(self.code):
            target = base_scratch + seq[3 * (i + 1)] if c is _SEQ else resolve(c)
            mem += [resolve(a), resolve(b), target]
        return mem + self.scratch + self.image
