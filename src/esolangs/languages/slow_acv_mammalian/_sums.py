"""Build-time machine-state model for the SLOW ACV MAMMALIAN generator.

:class:`_Sums` tracks the heads of all 23 arrays, the two big non-head sums
(arrays 0 and 16), the accumulator, the pointer, and the cells of the small
arrays the machine indexes into.  :func:`_replay` and :func:`_apply` evolve
it token by token as the interpreter would.  Every build step emits its
tokens against this model and asserts it agrees with the token-level
arithmetic, so a finished build is correct by construction.
"""

from collections.abc import Sequence

from esolangs.languages.slow_acv_mammalian.interpreter import _ARRAYS, MammalianModuli

#: The weight array, tracked as head plus non-head sum (like array 0)
#: because the construction only ever reads it through ``DIGEST``.
_W = 16

#: Cell arithmetic modulus: ``SEED`` steps array ``k``'s head by ``k + 1``.
_MODULUS = 256

#: Default I/O modulus: ``EXCRETE`` appends ``acc`` mod this.
_IO_MODULUS = 256


# The read node's second seed run.  The aim class fixes ``first & 48 == 16``,
# and XORing bits 4-5 from ``01`` to ``10`` is ``+16``, so this run is what
# lands the accumulator on the clean digit 48 -- it is not a free knob.
_J2 = 16


def _aim(start: int) -> int:
    """Return the seed count putting ``start + j1`` on the aim class.

    Even values whose bits 4-5 are ``01``: 16 residues per 256, at most 49
    apart, so the head stays far under the 255 a mid-run wrap needs.
    """
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd ``start`` steps to the next even.
        return start % 2
    return 64 - offset


class _Sums:
    """Build-time machine state: heads, the two big sums, the small cells.

    Arrays 0 and 16 are only ever read through ``DIGEST`` and through
    ``SPRINT``'s ``curr[0]``, so a head and a non-head sum say everything
    about them.  The pool and print arrays *are* indexed, by ``CONSUME``
    and by ``SPRINT``'s ``curr[acc]``, so those carry their cells.
    """

    __slots__ = ("acc", "cells", "heads", "io_modulus", "n0", "nw", "ptr")

    def __init__(self, *, io_modulus: int = _IO_MODULUS) -> None:
        self.io_modulus = MammalianModuli(io_modulus=io_modulus).io_modulus
        self.heads = [0] * _ARRAYS
        self.cells: dict[int, list[int]] = {}
        self.n0 = self.nw = self.acc = self.ptr = 0

    def clone(self) -> "_Sums":
        out = _Sums.__new__(_Sums)
        out.io_modulus = self.io_modulus
        out.heads = list(self.heads)
        out.cells = {key: list(val) for key, val in self.cells.items()}
        out.n0, out.nw, out.acc, out.ptr = self.n0, self.nw, self.acc, self.ptr
        return out

    @property
    def h0(self) -> int:
        """Return array 0's head."""
        return self.heads[0]

    @property
    def hw(self) -> int:
        """Return array 16's head."""
        return self.heads[_W]

    @hw.setter
    def hw(self, value: int) -> None:
        self.heads[_W] = value

    def arr0(self) -> list[int]:
        """Array 0 as the two-cell stand-in the sum arithmetic works on."""
        return [self.heads[0], self.n0]

    def rest(self, arr: int) -> int:
        """Return the non-head sum of array ``arr``."""
        if arr == 0:
            return self.n0
        if arr == _W:
            return self.nw
        return sum(self.cells.get(arr, ()))

    def append(self, arr: int, byte: int) -> None:
        """Append ``byte`` to array ``arr``, as ``EXCRETE`` does."""
        if arr == 0:
            self.n0 += byte
        elif arr == _W:
            self.nw += byte
        else:
            self.cells.setdefault(arr, []).append(byte)

    def full(self, arr: int) -> list[int]:
        """Return array ``arr`` cell by cell; only small arrays have cells."""
        return [self.heads[arr], *self.cells.get(arr, ())]


def _advance_heads(st: _Sums, seeds: int) -> None:
    """Step every head by ``seeds`` ``SEED`` runs: array ``k`` gains ``k + 1`` each."""
    for arr in range(_ARRAYS):
        st.heads[arr] = (st.heads[arr] + (arr + 1) * seeds) % _MODULUS


def _replay(st: _Sums, tokens: Sequence[str], bit: int = 0) -> None:
    """Apply a token run to ``st``.  ``LEAPFROG`` moves only the cursor."""
    seeds = 0
    for tok in tokens:
        if tok == "SEED":
            seeds += 1
            continue
        if seeds:
            _advance_heads(st, seeds)
            seeds = 0
        _apply(st, tok, bit)
    _advance_heads(st, seeds)


def _apply(st: _Sums, tok: str, bit: int) -> None:
    """Apply one non-``SEED`` token to ``st``."""
    if tok == "DIGEST":
        st.acc ^= st.heads[st.ptr] + st.rest(st.ptr)
    elif tok == "EXCRETE":
        st.append(st.ptr, st.acc % st.io_modulus)
        st.acc = 0
    elif tok == "ACCEPT":
        if st.acc % _MODULUS != 48:
            raise AssertionError(
                f"ACCEPT entered with acc % {_MODULUS} == {st.acc % _MODULUS}"
            )
        st.n0 += bit
    elif tok == "CONSUME":
        cells = st.cells[st.ptr]
        mid = len(cells) // 2
        if mid < 1:  # pragma: no cover - the pools are built long enough
            raise AssertionError("CONSUME would take the head")
        st.acc = cells.pop(mid - 1)
    elif tok == "SPRINT":
        cells = st.full(st.ptr)
        if not 0 <= st.acc < len(cells):
            raise AssertionError(f"SPRINT index {st.acc} outside array {st.ptr}")
        st.ptr = (st.ptr + cells[st.acc]) % _ARRAYS


def _leaf(digit: int, *, unit: int) -> list[str]:
    """Return the tokens run ``digit`` executes, padded to one slot.

    ``EXCRETE`` clears the accumulator the dispatch left, ``SPRINT`` rides
    array 16's head to a print array, ``CONSUME`` lifts its middle cell
    (``'0'`` or ``'1'``) and ``PRONOUNCE`` writes it.  The closing
    ``EXCRETE`` leaves a nonzero cell so ``LEAPFROG`` fires; with a zero
    accumulator it can only aim before the program, which halts the run.
    One SEED separates the two print arrays (``generator._dispatch_head``),
    so the digit is the step count, and nothing reads array 16's sum: every
    leaf has the same length whatever row reached it.
    """
    body = [
        "EXCRETE",
        *["SEED"] * digit,
        "SPRINT",
        "CONSUME",
        "PRONOUNCE",
        "EXCRETE",
        "LEAPFROG",
    ]
    return [*body, *["SEED"] * (unit - len(body))]


def _crossing_head(rest: int) -> int:
    """Return a head whose sum and successor's sum XOR to 255 in the low byte.

    No SEED makes head 255 in 255-cell arithmetic, so the I/O byte 255 is
    synthesized from adjacent sums crossing 127/128 (or 255/256).
    """
    first = (127 - rest) % 256
    return (255 - rest) % 256 if first >= 254 else first
