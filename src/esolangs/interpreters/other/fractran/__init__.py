"""Interpreter for FRACTRAN.

John Conway's 1987 language: a program is an ordered list of positive
fractions and a starting value.  A step multiplies the value by the first
fraction that leaves an integer, and the run ends when none does.  The
value is the whole machine -- there are no registers, no instruction
pointer and no I/O -- so data lives in the exponents of its prime
factorization.

The source is whitespace- or comma-separated tokens: the first is the
starting value, the rest are the fractions in priority order.  Any of them
may be written as a product of prime powers (``2^3*5`` is 40), which is
notation only -- the machine still starts from one integer -- and is how a
generated program spells a value with thousands of digits without spelling
the digits.  Because FRACTRAN has no output vocabulary either, the final
value *is* the result, and this interpreter prints it. Small-base sources
retain exact prime exponents and indexed guards; other sources use the literal
integer scan. Debug values are materialized on request.

An empty source, a token that is not a fraction or a product of powers, a
zero or negative value, and a zero denominator raise :class:`ValueError`.
No operation can be invalid once a program parses -- every step is a
multiplication that was already checked to divide -- so no
:class:`~esolangs.exceptions.HaltError` arises and a value no fraction
divides is the normal end.  Nothing is read, so no ``EOFError`` can come
from here: a program's inputs are in its starting value.
"""

from __future__ import annotations

import re
from typing import cast

from esolangs._drive import drive
from esolangs.interpreters.io import IO
from esolangs.interpreters.other.fractran.index import (
    Factors,
    Index,
    advance,
    compile_index,
    integer,
)
from esolangs.interpreters.source_hints import syntax_error

#: A fraction, as the numerator and denominator it was written with.
type _Fraction = tuple[int, int]
#: The whole run as a value: the current number, and whether the value the
#: run stopped on has been printed.  The fractions are fixed for the run, so
#: they are not part of the state.
type _State = tuple[int, bool]

_POWER = re.compile(r"^(\d+)(?:\^(\d+))?$")


def _product(text: str) -> int:
    """Return the value of a product of powers such as ``2^3*5``."""
    total = 1
    for factor in text.split("*"):
        found = _POWER.match(factor)
        if found is None:
            raise syntax_error(
                f"{factor!r} is not a FRACTRAN number or power",
                ("write a decimal integer or a power such as 2^3; join factors with *"),
            )
        base, exponent = found.group(1), found.group(2)
        total *= int(base) ** (1 if exponent is None else int(exponent))
    return total


def _parse(code: str) -> tuple[int, tuple[_Fraction, ...], tuple[int, ...]]:
    """Return the starting value, the fractions, and each token's offset."""
    tokens = [(found.start(), found.group()) for found in re.finditer(r"[^\s,]+", code)]
    if not tokens:
        raise syntax_error(
            "a FRACTRAN program needs a starting value",
            ("put a positive starting integer before the fractions, for example 2 3/2"),
        )
    start = _product(tokens[0][1])
    if start <= 0:
        raise syntax_error(
            "a FRACTRAN starting value must be positive",
            "use a starting integer greater than zero",
        )
    fractions = []
    for _offset, token in tokens[1:]:
        head, slash, tail = token.partition("/")
        numerator = _product(head)
        denominator = _product(tail) if slash else 1
        if denominator == 0:
            raise syntax_error(
                f"FRACTRAN fraction {token!r} divides by zero",
                "use a nonzero denominator, for example 3/2",
            )
        if numerator <= 0:
            raise syntax_error(
                f"FRACTRAN fraction {token!r} is not positive",
                "use positive numerators and denominators",
            )
        fractions.append((numerator, denominator))
    return start, tuple(fractions), tuple(offset for offset, _token in tokens)


def _choose(value: int, fractions: tuple[_Fraction, ...]) -> int | None:
    """Return the index of the first fraction that keeps the value whole."""
    for index, (numerator, denominator) in enumerate(fractions):
        if value * numerator % denominator == 0:
            return index
    return None


def _advance(
    state: _State, fractions: tuple[_Fraction, ...], index: int | None
) -> tuple[_State, int | None]:
    """Return the state after one step, and the value to print.

    Pure.  ``index`` is ``None`` when no fraction divides, which is the step
    that prints the result rather than one that multiplies.
    """
    value, printed = state
    if index is None:
        return (value, True), None if printed else value
    numerator, denominator = fractions[index]
    return (value * numerator // denominator, printed), None


class _Machine:
    """The run state: one integer, against a fixed list of fractions."""

    def __init__(self, code: str, io: IO) -> None:
        self._index = compile_index(code)
        self._factors: Factors = ()
        self._fractions: tuple[_Fraction, ...] | None = None
        self._integer = 1
        if self._index is None:
            self._integer, self._fractions, self.offsets = _parse(code)
        else:
            self._factors = self._index.initial
            self.offsets = self._index.offsets
        self.inspections = 0
        self._selected_for: int | Factors | None = None
        self._selected: int | None = None
        self.io = io
        self.printed = False

    @property
    def value(self) -> int:
        """The exact integer; materialized only when a caller requests it."""
        return self._integer if self._index is None else integer(self._factors)

    @property
    def fractions(self) -> tuple[_Fraction, ...]:
        """The exact fractions, retaining the literal machine's debug interface."""
        if self._fractions is None:
            self._fractions = tuple(
                (integer(numerator), integer(denominator))
                for numerator, denominator in cast(Index, self._index).literal
            )
        return self._fractions

    def _next(self) -> int | None:
        state = self._integer if self._index is None else self._factors
        if state != self._selected_for:
            if self._index is None:
                self._selected = _choose(self._integer, self.fractions)
            else:
                self._selected, probes = self._index.choose(self._factors)
                self.inspections += probes
            self._selected_for = state
        return self._selected

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.value, self.printed)

    @_state.setter
    def _state(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self._integer, self.printed = state

    @property
    def halted(self) -> bool:
        """Whether no fraction divides the value any more."""
        return self.printed and self._next() is None

    #: The position is the offset of the fraction about to fire, on the
    #: source the caller handed in.
    ip_shape = "offset"

    @property
    def ip(self) -> int | None:
        index = self._next()
        return None if index is None else self.offsets[index + 1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self._integer if self._index is None else self._factors,
            self.printed,
            self.io.position(),
        )

    def step(self) -> None:
        """Fire one fraction, or print the final value and stop.

        The print is a step of its own, so that ``halted`` is false until it
        has happened: a stepping caller that stopped at the last
        multiplication would otherwise see no result at all.
        """
        if self.halted:
            return
        index = self._next()
        if self._index is None:
            self._state, out = _advance(self._state, self.fractions, index)
        elif index is None:
            out = None if self.printed else self.value
            self.printed = True
        else:
            self._factors = advance(self._factors, self._index.rules[index][1])
            out = None
        if out is not None:
            self.io.print_num(out)


def run(code: str, io: IO) -> None:
    """Run a FRACTRAN program, printing the value it ends on."""
    machine = _Machine(code, io)
    drive(machine)
