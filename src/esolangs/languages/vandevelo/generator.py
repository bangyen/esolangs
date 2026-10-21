"""Vandevelo Boolean program generator: one hang guard per affine cube.

Reads the inputs, then hangs (``loop -> loop?`` never terminates lazily)
exactly when the table entry is 1.  Every bindable value is affine in the
inputs (``==``/``!=`` are XNOR/XOR over nil) and only ``::`` chains evaluate
conditionally, so a guard line hangs on an affine coset.  One line is
emitted per cube of an affine-cube peel cover of the 1-set (:mod:`._peel`);
single cosets and their complements (every affine table) bypass the peel.

A guard has one part per dual-space constraint (:func:`_constraints`): all
but at most ``1 + 2**((dim + 1) / 2)`` are parities of at most four inputs,
the rest come from reduced elimination at most ``dim + 1`` wide.
Single-input constraints test the input directly; wider ones live in
registers (``A ~> a?``, ``A ~> A? != b?``) that later clauses morph one
toggle at a time, strictly cheaper than a fresh register.  The bank holds
at most ``n**2`` registers (:func:`_bank_cap`), so a name is at most two
input names long; a full bank respells its least recently used free
register, and a clause scans the :data:`_SCAN` most recently used.  A test
for 0 is ``x? == Nil?``, so guards avoid it: a register's last toggle takes
the polarity the clause wants, an input mostly tested for 0 is read negated
(``~!>``) when the rows reaching those tests agree, and a test every
reaching row passes is dropped.

Size:
    O(T log n) chars (identifier length is O(log n); removing that factor
    is open).  A clause weighs at most ``4 * n + (dim + 1) * (1 + 2**((dim +
    1) / 2))`` inputs: over the peel ``4 * n + 36 * 2**n``, the second term
    at most ``4 * 2**n`` over the disjoint cubes, so register upkeep is
    under ``40 * 2**n + 4 * n`` lines and under half the emitted text.
    Parity and and are linear; n=10 parity: 259 chars, n=10 and: 179 chars,
    n=10 majority: 3,405 chars, n=10 random 1847: 8,352 chars.

Decisions:
    The reduced-echelon basis alone does not bound the weight: on a cube
    whose columns spread over ``2**dim`` values it weighs ``n * dim / 2``
    whatever the pivots, ``Theta(T log log T)`` at the ``log2(n)``
    dimensions the peel produces.  Ordering bare tests first saved 0.0% of
    characters and 8.8% of steps at n=7 and was retired.  Avoiding
    ``x? == Nil?`` (eight characters, four steps over a bare ``x?``) took
    the three-input tables from 25,922 to 23,425 characters.  Tighter bank
    caps force respelling (:func:`_bank_cap`).
"""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING, NamedTuple

from esolangs.generation.helpers import _validate_truth_table, short_name
from esolangs.generation.wrap import balance_score
from esolangs.languages.vandevelo._cover import _cover, _flips
from esolangs.languages.vandevelo._peel import _CANDIDATES, _points
from esolangs.languages.vandevelo.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}

# Registers examined when a clause looks for one to reuse or morph: the
# bank stays under this to n=13 (about 2**(n/2) live registers), so the
# cap costs nothing measured ([ablations.bank_cap]).
_SCAN = 3 * _CANDIDATES


def _bank_cap(n: int) -> int:
    """Live registers allowed for an ``n``-input table.

    Uncapped, the bank grows with the peel -- 7 registers at n=6 to 117 at
    n=13, about ``2**(n/2)`` -- and names for that many registers would put
    a factor of ``n`` on every reference.  ``n**2`` keeps a register name
    within twice an input name's length, always leaves a free register (a
    clause binds at most ``n - 1``), and never binds at measured sizes;
    ``n`` or ``2 * n`` would cost size in forced respelling
    ([ablations.bank_cap]).
    """
    return n * n


class _Held(NamedTuple):
    """What a register holds: the input set ``w`` it XORs and its polarity."""

    w: int
    polarity: int


class _Binding(NamedTuple):
    register: str
    polarity: int
    lines: list[tuple[str, ...]]


class _Bank:
    """The live registers, least recently used first; each binds an input parity.

    A register holds its parity XOR its own polarity, and a clause that
    (re)binds it sets that polarity -- a ``==`` toggle in place of ``!=``
    -- so the test it makes is a bare ``r?``.
    """

    def __init__(self, n: int, ref: Callable[[int], str]) -> None:
        self.held: dict[str, _Held] = {}
        self.cap = _bank_cap(n)
        self.next_register = n
        self.ref = ref

    def bind(self, w: int, value: int, used: set[str]) -> _Binding:
        """Return the register, polarity and binding lines testing parity ``w``.

        Reuses a register already holding ``w``, else morphs the nearest
        free recent one, else binds a fresh or respelled register.
        """
        held = self.held
        recent = list(islice(reversed(held.items()), _SCAN))
        exact = next((r for r, h in recent if h.w == w and r not in used), None)
        if exact is not None:
            polarity = held.pop(exact).polarity
            held[exact] = _Held(w, polarity)  # most recently used
            return _Binding(exact, polarity, [])
        lines: list[tuple[str, ...]] = []
        nearest: str | None = None
        distance = w.bit_count()
        for r, h in recent:
            if r in used:
                continue
            d = (h.w ^ w).bit_count()
            if d < distance:
                nearest, distance = r, d
        if nearest is not None:
            register = nearest
            old = held.pop(register)
            polarity = old.polarity
            toggles = _points(old.w ^ w)
        else:
            if len(held) < self.cap:
                register = short_name(self.next_register, _ALPHABET)
                self.next_register += 1
            else:
                # Bank full: respell the least recently used free register.
                register = next(r for r in held if r not in used)
                del held[register]
            first, *toggles = _points(w)
            polarity = 0
            lines.append((register, "~>", f"{self.ref(first)}?"))
        # Every rebinding toggles at least once; the last toggle
        # sets the polarity that makes this test pass on a 1.
        for i, b in enumerate(toggles):
            op = "!="
            if i == len(toggles) - 1 and polarity == value:
                op, polarity = "==", polarity ^ 1
            lines.append((register, "~>", f"{register}?", op, f"{self.ref(b)}?"))
        held[register] = _Held(w, polarity)
        return _Binding(register, polarity, lines)


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [short_name(index, _ALPHABET) for index in range(n)]
    cover = _cover(truth_table, n)
    flips = _flips(cover, n)
    lines = []
    joiner = "" if compact else " "
    glue = "::" if compact else " :: "

    def spaced(*tokens: str) -> str:
        """Join tokens with no separator (compact) or spaces (readable)."""
        return joiner.join(tokens)

    for index in range(n):
        # A flipped input is read negated, so its ``== Nil`` tests go.
        arrow = "~!>" if (flips >> (n - 1 - index)) & 1 else "~>"
        lines.append(spaced(names[index], arrow, "Inp?"))
    loop = "l?" if compact else "loop?"
    lines.append(spaced("l" if compact else "loop", "->", loop))

    def ref(bit: int) -> str:
        # Index bit ``bit`` is the (n-1-bit)th input read: rows are spelled
        # most-significant-first, and the first read is the top bit.
        return names[n - 1 - bit]

    bank = _Bank(n, ref)
    for clause in cover:
        parts = []
        used: set[str] = set()
        for w, value in clause.tests:
            # The constraint over the reads as spelled, flipped inputs and all.
            value ^= (w & flips).bit_count() & 1
            if w.bit_count() == 1:
                part, polarity = ref(w.bit_length() - 1), 0
            else:
                part, polarity, binding = bank.bind(w, value, used)
                lines.extend(spaced(*tokens) for tokens in binding)
                used.add(part)
            # The test passes when the variable equals ``value ^ polarity``.
            if value ^ polarity:
                parts.append(f"{part}?")
            else:
                parts.append(spaced(f"{part}?", "==", "Nil?"))
        lines.append(glue.join([*parts, loop]))
    return "\n".join(lines)


def _balance(table: str, default: str) -> str:
    """Compare the default with the compact spelling."""
    return min(default, vandevelo(table, 1), key=balance_score)


LANGUAGE = Language(
    "Vandevelo",
    "vandevelo",
    category="variable_based",
    boolean=vandevelo,
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Vandevelo answers by terminating: nil halts and not nil loops",
    ),
    balance=_balance,
    example=Example(expected="", slow_build=True),
    proof_execution=(execution, False, (3, 5)),
)
