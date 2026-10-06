r"""Interpreter for INTERCAL-72 with the C-INTERCAL extensions.

Implements the C-INTERCAL manual's single-threaded language: onespot ``.`` and
twospot ``:`` scalars, tail ``,`` and hybrid ``;`` arrays (``BY`` dimensions,
``SUB`` subscripts), mingle ``$`` (also the currency signs), select ``~``, the
unary ``&``/``V``/``?`` (infix, and prefix as in C-INTERCAL 0.26+), sparks and
rabbit-ears with the wow ``!``; ``NEXT``/``RESUME``/``FORGET``, ``STASH``/
``RETRIEVE``, ``IGNORE``/``REMEMBER``, ``ABSTAIN``/``REINSTATE`` by label, by
gerund and computed, ``DO NOT`` and ``%n`` chances, ``ONCE``/``AGAIN``,
``COME FROM`` and ``NEXT FROM`` by label, expression and gerund, ``TRY AGAIN``,
``GIVE UP``, numeric I/O and Turing Tape array I/O. Not implemented: the system
library, threads, backtracking, ``CREATE``, operand overloading, ``PIN``,
CLC-INTERCAL I/O and wimpmode.

Unparsable statements are E000 syntax errors raised only when executed. Errors
raise ``HaltError`` naming their E-number; program-wide checks (labels,
politeness, NEXT/ABSTAIN/COME FROM targets) raise at load. Numeric ``WRITE IN``
at EOF raises ``EOFError``; Turing Tape input stores 256 at EOF. A ``%n`` draws
from the ``rng`` hook (:mod:`esolangs.interpreters.randomness`).

Judgment calls where the manual or C-INTERCAL leave a gap:

* A statement starts at ``DO``/``PLEASE`` even inside a word (``DOUBLE``), as
  C-INTERCAL lexes; a label starts one only before an identifier. A line with
  no identifier that is a complete core command stays its own statement.
* Politeness keeps the stricter one-fifth to one-third rule for any length;
  running off the end halts quietly instead of E633.
* Zero prints a lone overbar over an empty line, as the manual says; a value
  below 4000 prints one line, where C-INTERCAL prints an empty overbar line first.
* Whitespace may split a number from its sigil and its own digits, as
  C-INTERCAL's lexer allows, though the manual says it cannot.
* Digit words read in any case, split at any whitespace; C-INTERCAL wants
  upper case split at spaces.  Of two errors in one statement, the
  right-hand side's is raised before the target subscript's.
* ``READ OUT`` takes any expression; a subscript list holds bare operands, and
  a subscripted element may be the left operand of a binary operator.
* Array elements start at 0, where C-INTERCAL leaves them uninitialised;
  ``RETRIEVE`` restores an array even if it is undimensioned.
* Turing Tape characters are code points; the tape differences are taken
  modulo 256 and output bytes are written as code points 0-255.
* ``ONCE``/``AGAIN`` take effect when the statement is reached (for ``COME
  FROM`` when it fires); a computed ``COME FROM`` is checked at every labelled
  statement, a gerund one after every statement of that kind.
"""

from __future__ import annotations

import copy
from collections.abc import Hashable
from typing import Any

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other._intercal_parse import (
    _SELF_ABSTAIN,
    _SELF_REINSTATE,
    _fail,
    _Key,
    _load,
    _Node,
    _parse_expression,
    _Statement,
    _statements,
    _unary,
)
from esolangs.interpreters.randomness import Randomness, draw

type _Value = tuple[int, int]
type _Array = tuple[tuple[int, ...], dict[int, int]]

# Digit words 0-9: English and, as the manual says C-INTERCAL accepts
# (src/numerals.c), Sanskrit, Basque, Tagalog, Classical Nahuatl, Georgian,
# Kwakiutl, Volapuk and Latin.
_DIGIT_WORDS = (
    "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE",
    "SUTYA EKA DVI TRI CHATUR PANCHAN SHASH SAPTAM ASHTAN NAVAN",
    "ZEROA BAT BI HIRO LAU BORTZ SEI ZAZPI ZORTZI BEDERATZI",
    "WALA ISA DALAWA TATLO APAT LIMA ANIM PITO WALO SIYAM",
    "AHTLE CE OME IEI NAUI NACUILI CHIQUACE CHICOME CHICUE CHICUNAUI",
    "NULI ERTI ORI SAMI OTXI XUTI EKSVI SHVIDI RVA CXRA",
    "KE'YOS 'NEM MAL'H YUDEXW MU SEK'A Q'ETL'A ETLEBU MALHGWENALH 'NA'NE'MA",
    "NOS BAL TEL KIL FOL LUL MÄL VEL JÖL ZÜL",
    "NIL UNUS DUO TRES QUATTUOR QUINQUE SEX SEPTEM OCTO NOVEM",
)
_DIGITS = {
    word: digit for line in _DIGIT_WORDS for digit, word in enumerate(line.split())
} | {
    "OH": 0, "NINER": 9, "SHUTYA": 0, 'M\\"AL': 6, 'J\\"OL': 8, 'Z\\"UL': 9,
    "NIHIL": 0, "UNA": 1, "UNUM": 1, "DUAE": 2, "QUATUOR": 4,
}  # fmt: skip

_WIDTH = {".": 16, ":": 32, ",": 16, ";": 32}
_ONESPOT_MAX = 0xFFFF
_TWOSPOT_MAX = 0xFFFFFFFF
_NEXT_LIMIT = 80

# Bit reversal of a byte, for Turing Tape output (C-INTERCAL's binout).
_REVERSED = tuple(int(f"{byte:08b}"[::-1], 2) for byte in range(256))


def _spread(value: int) -> int:
    """Move bit ``k`` of a 16-bit value to bit ``2k``."""
    value = (value | (value << 8)) & 0x00FF00FF
    value = (value | (value << 4)) & 0x0F0F0F0F
    value = (value | (value << 2)) & 0x33333333
    return (value | (value << 1)) & 0x55555555


def _select(value: int, mask: int) -> int:
    result = place = 0
    while mask:
        low = mask & -mask
        if value & low:
            result |= 1 << place
        place += 1
        mask ^= low
    return result


def _evaluate(
    node: _Node, scalars: dict[_Key, int], arrays: dict[_Key, _Array]
) -> _Value:
    """Return ``(value, width)``; C-INTERCAL types every result statically."""
    tag = node[0]
    if tag == "#":
        return node[1], 16
    if tag == "." or tag == ":":
        return scalars.get((tag, node[1]), 0), _WIDTH[tag]
    if tag == "u":
        value, width = _evaluate(node[2], scalars, arrays)
        return _unary(value, width, node[1]), width
    if tag == "$":
        left, _ = _evaluate(node[1], scalars, arrays)
        right, _ = _evaluate(node[2], scalars, arrays)
        if left > _ONESPOT_MAX or right > _ONESPOT_MAX:
            raise _fail(
                "E533",
                "INTERCAL mingle needs two onespot values",
                hint="use two 16-bit onespot values as mingle operands",
            )
        return (_spread(left) << 1) | _spread(right), 32
    if tag == "~":
        left, _ = _evaluate(node[1], scalars, arrays)
        right, width = _evaluate(node[2], scalars, arrays)
        return _select(left, right), width
    data, index = _element(node, scalars, arrays)
    return data.get(index, 0), _WIDTH[node[1]]


def _element(
    node: _Node, scalars: dict[_Key, int], arrays: dict[_Key, _Array]
) -> tuple[dict[int, int], int]:
    """Locate a subscripted element: its array's store and flat index."""
    _tag, sigil, number, subscripts = node
    dimensions, data = arrays.get((sigil, number), ((), {}))
    if len(subscripts) != len(dimensions):
        raise _fail(
            "E241",
            "INTERCAL subscripts do not match the array's dimensions",
            hint="dimension the array first and give one subscript per dimension",
        )
    index = 0
    for subscript, size in zip(subscripts, dimensions, strict=True):
        value, _ = _evaluate(subscript, scalars, arrays)
        if not 1 <= value <= size:
            raise _fail("E241", "INTERCAL subscript out of range")
        index = index * size + value - 1
    return data, index


def _expression(
    text: str, variables: dict[int, int], at: int = 0
) -> tuple[_Value, int]:
    """Parse and evaluate one expression over onespot ``variables``."""
    node, end = _parse_expression(text, at)
    scalars = {(".", number): value for number, value in variables.items()}
    return _evaluate(node, scalars, {}), end


def _roman(value: int) -> str:
    """Return Roman output; emit a separate overbar line when needed."""
    if not 0 <= value <= _TWOSPOT_MAX:
        raise HaltError("INTERCAL output out of range")
    chunks: list[tuple[str, str]] = []
    place = 0
    while value:
        value, digit = divmod(value, 10)
        group, column = divmod(place, 3)
        one, five, ten = ("IVX", "XLC", "CDM")[column]
        if column == 0 and group and digit <= 3:
            text = "M" * digit
            group -= 1
        elif digit <= 3:
            text = one * digit
        elif digit == 4:
            text = one + five
        elif digit <= 8:
            text = five + one * (digit - 5)
        else:
            text = one + ten
        if group >= 2:
            text = text.lower()
        chunks.append((text, ("_" if group % 2 else " ") * len(text)))
        place += 1
    body = "".join(text for text, _bars in reversed(chunks))
    bars = "".join(bars for _text, bars in reversed(chunks)) or "_"
    # "Zero is indicated by an overline with no character underneath."
    return bars + "\n" + body if "_" in bars else body


class _Draws:
    """Scripted draws for one branch: the prefix, then the first outcome."""

    def __init__(self, prefix: tuple[int, ...]) -> None:
        self.prefix = prefix
        self.drawn: list[int] = []

    def randbelow(self, upper: int) -> int:
        index = len(self.drawn)
        value = self.prefix[index] if index < len(self.prefix) else 0
        self.drawn.append(value)
        return value % upper


class _Machine:
    """Parsed INTERCAL statements and the mutable C-INTERCAL run state."""

    reproducible_seed = 0

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.io = io
        self._rng = rng
        self.lines = _statements(code)
        self._program = [_load(line) for line in self.lines]
        polite = sum(statement.polite for statement in self._program)
        if (
            not self.lines
            or polite * 5 < len(self.lines)
            or polite * 3 > len(self.lines)
        ):
            raise _fail(
                "E079" if polite * 5 < len(self.lines) else "E099",
                "INTERCAL program is insufficiently or excessively polite",
                hint="use PLEASE on one fifth to one third of the statements",
            )
        self.labels: dict[int, int] = {}
        for i, statement in enumerate(self._program):
            if statement.label is not None:
                if statement.label in self.labels:
                    raise _fail("E182", f"duplicate INTERCAL label: {statement.label}")
                self.labels[statement.label] = i
        self._link()
        self.ind = 0
        self._scalars: dict[_Key, int] = {}
        self._arrays: dict[_Key, _Array] = {}
        self._ignored: set[_Key] = set()
        self._stashes: dict[_Key, list[int | _Array]] = {}
        self._abstained = [int(statement.abstained) for statement in self._program]
        self._next: list[tuple[int, int]] = []
        self._last_in = self._last_out = 0

    def _link(self) -> None:
        """Check every constant label target and index the COME FROMs."""
        self._by_kind: dict[str, list[int]] = {}
        self._come_label: dict[int, list[int]] = {}
        self._come_kind: dict[str, list[int]] = {}
        self._come_computed: list[int] = []
        codes = {"next": "E129", "abstain": "E139", "reinstate": "E139"}
        for i, statement in enumerate(self._program):
            command, kind = statement.command, statement.kind
            if kind is not None:
                self._by_kind.setdefault(kind, []).append(i)
            target = command[1] if len(command) > 1 else None
            if kind in codes and isinstance(target, int) and target not in self.labels:
                raise _fail(codes[kind], f"unknown INTERCAL label: {target}")
            if kind not in ("come from", "next from"):
                continue
            if isinstance(target, int):
                if target not in self.labels:
                    raise _fail("E444", f"unknown INTERCAL label: {target}")
                self._come_label.setdefault(target, []).append(i)
                if len(self._come_label[target]) > 1:
                    raise _fail("E555", f"two COME FROMs aim at label {target}")
            elif isinstance(target, frozenset):
                for name in target:
                    self._come_kind.setdefault(str(name), []).append(i)
            else:
                self._come_computed.append(i)
        self._sucks = [
            (statement.label is not None and bool(self._come_computed))
            or statement.label in self._come_label
            or statement.kind in self._come_kind
            for statement in self._program
        ]
        last = len(self._program) - 1
        for i in self._by_kind.get("try again", ()):
            if i != last:
                raise _fail("E993", "TRY AGAIN must be the last statement")

    @property
    def halted(self) -> bool:
        return self.ind >= len(self._program)

    @property
    def ip(self) -> int:
        return self.ind

    @property
    def memory(self) -> list[int]:
        return [value for _key, value in sorted(self._scalars.items())]

    @property
    def stack(self) -> list[object]:
        return [resume for resume, _origin in self._next]

    def snapshot(self) -> tuple[Any, ...]:
        arrays = tuple(
            (key, dimensions, tuple(sorted(data.items())))
            for key, (dimensions, data) in sorted(self._arrays.items())
        )
        stashes = tuple(
            (key, tuple(map(_freeze, values)))
            for key, values in sorted(self._stashes.items())
        )
        return (
            self.ind,
            tuple(sorted(self._scalars.items())),
            arrays,
            tuple(sorted(self._ignored)),
            stashes,
            tuple(self._abstained),
            tuple(self._next),
            self._last_in,
            self._last_out,
            self.io.position(),
        )

    def branching_snapshot(self) -> tuple[Any, ...]:
        """Return immutable state for exhaustive ``%`` branch search."""
        return self.snapshot()

    def branching_halted(self, state: Any) -> bool:
        """Report whether an immutable state has run past its last statement."""
        return bool(state[0] >= len(self._program))

    def _restore(self, state: tuple[Any, ...]) -> None:
        ind, scalars, arrays, ignored, stashes, abstained, nexts, last_in, last_out = (
            state[:9]
        )
        self.ind = ind
        self._scalars = dict(scalars)
        self._arrays = {
            key: (dimensions, dict(data)) for key, dimensions, data in arrays
        }
        self._ignored = set(ignored)
        self._stashes = {
            key: [_thaw(value) for value in values] for key, values in stashes
        }
        self._abstained = list(abstained)
        self._next = list(nexts)
        self._last_in, self._last_out = last_in, last_out

    def branching_successors(
        self, state: Any, _limit: int
    ) -> tuple[tuple[Any, ...], ...] | None:
        """Return every outcome of the step's draws, or ``None`` at input."""
        current: tuple[Any, ...] = state
        if self.branching_halted(current):
            return (current,)
        ind: int = current[0]
        if self._program[ind].command[0] == "write" and not current[5][ind]:
            return None
        successors = []
        pending: list[tuple[int, ...]] = [()]
        while pending:
            prefix = pending.pop()
            branch = copy.copy(self)
            branch._restore(current)  # noqa: SLF001 - same-class state fork
            branch.io = ScriptedIO("")
            draws = branch._rng = _Draws(prefix)  # noqa: SLF001
            branch.step()
            pending.extend(
                (*draws.drawn[:at], 99) for at in range(len(prefix), len(draws.drawn))
            )
            successors.append((*branch.snapshot()[:-1], current[-1]))
        return tuple(successors)

    def _runs(self, chance: int) -> bool:
        """Roll a ``%chance`` qualifier; 0 never runs and 100 always does."""
        if chance >= 100:
            return True
        return chance > 0 and draw(self._rng, 100) < chance

    def _reach(self, i: int) -> bool:
        """Apply ONCE/AGAIN at statement ``i``; report if it was reinstated."""
        before = self._abstained[i]
        after = self._program[i].after
        if after == _SELF_ABSTAIN:
            self._abstained[i] = before or 1
        elif after == _SELF_REINSTATE:
            self._abstained[i] = 0
        return not before

    def step(self) -> None:
        if self.halted:
            return
        i = self.ind
        statement = self._program[i]
        if statement.kind in ("come from", "next from"):
            self._leave(i)
        elif self._reach(i) and self._runs(statement.chance):
            self._execute(i, statement)
        else:
            self._leave(i)

    def _leave(self, i: int) -> None:
        """Continue past statement ``i``, unless a COME FROM takes control."""
        self.ind = i + 1
        if not self._sucks[i]:
            return
        statement = self._program[i]
        candidates = [
            *self._come_label.get(statement.label or 0, ()),
            *self._come_kind.get(statement.kind or "", ()),
        ]
        if statement.label is not None:
            candidates.extend(
                c
                for c in self._come_computed
                if not self._abstained[c]
                and self._value(self._program[c].command[1]) == statement.label
            )
        taken = [
            c
            for c in candidates
            if self._reach(c) and self._runs(self._program[c].chance)
        ]
        if len(taken) > 1:
            raise _fail(
                "E555", "two COME FROMs take control at once in a one-thread program"
            )
        if taken:
            if self._program[taken[0]].kind == "next from":
                self._push(i + 1, -1)
            # Control passes to the COME FROM, which then finishes in turn:
            # the manual's DO COME FROM COMING FROM is an infinite loop.
            self.ind = taken[0]

    def _push(self, resume: int, origin: int) -> None:
        if len(self._next) >= _NEXT_LIMIT:
            raise _fail("E123", "INTERCAL NEXT stack overflow")
        self._next.append((resume, origin))

    def _value(self, node: _Node) -> int:
        return _evaluate(node, self._scalars, self._arrays)[0]

    def _store(self, target: _Node, value: int) -> None:
        if target[0] == "sub":
            sigil = str(target[1])
            data, index = _element(target, self._scalars, self._arrays)
        else:
            sigil = str(target[0])
        if sigil in ".," and value > _ONESPOT_MAX:
            raise _fail("E275", "INTERCAL onespot assignment overflow")
        if (sigil, target[2] if target[0] == "sub" else target[1]) in self._ignored:
            return
        if target[0] == "sub":
            data[index] = value
        else:
            self._scalars[(sigil, target[1])] = value

    def _targets(self, target: int | frozenset[str]) -> list[int]:
        if isinstance(target, int):
            return [self.labels[target]]
        return [i for kind in target for i in self._by_kind.get(kind, ())]

    def _array(self, key: _Key) -> _Array:
        array = self._arrays.get(key, ((), {}))
        if len(array[0]) != 1:
            raise _fail(
                "E241",
                "INTERCAL array I/O needs a one-dimensional array",
                hint="dimension the array with a single size first",
            )
        return array

    def _execute(self, i: int, statement: _Statement) -> None:
        command = statement.command
        action = command[0]
        if action == "calculate":
            self._store(command[1], self._value(command[2]))
        elif action == "dimension":
            sizes = tuple(self._value(size) for size in command[2])
            if 0 in sizes:
                raise _fail("E240", "an INTERCAL array dimension must be positive")
            if command[1] not in self._ignored:
                self._arrays[command[1]] = (sizes, {})
        elif action == "next":
            self._push(i + 1, i)
            self.ind = self.labels[command[1]]
            return
        elif action in ("forget", "resume"):
            count = self._value(command[1])
            if action == "resume":
                self._resume(count)
                return
            del self._next[max(0, len(self._next) - count) :]
        elif action in ("stash", "retrieve", "ignore", "remember"):
            for key in command[1]:
                self._variable(action, key)
        elif action == "abstain":
            amount = None if command[2] is None else self._value(command[2])
            for t in self._targets(command[1]):
                if amount is not None:
                    self._abstained[t] += amount
                elif not self._abstained[t]:
                    self._abstained[t] = 1
        elif action == "reinstate":
            for t in self._targets(command[1]):
                if self._program[t].kind is not None and self._abstained[t]:
                    self._abstained[t] -= 1
        elif action == "read":
            for item in command[1]:
                self._read_out(item)
        elif action == "write":
            for item in command[1]:
                self._write_in(item)
        elif action == "give up":
            self.ind = len(self._program)
            return
        elif action == "try again":
            self.ind = 0
            return
        else:
            raise HaltError(
                f"INTERCAL syntax error (E000) in {statement.text!r}: {command[1]}",
                hint="use statements supported by esolangs describe --spec INTERCAL",
            )
        self._leave(i)

    def _resume(self, count: int) -> None:
        if count == 0:
            raise _fail(
                "E621",
                "invalid INTERCAL stack count: RESUME #0",
                hint="use a positive stack count",
            )
        if count > len(self._next):
            raise _fail(
                "E632",
                "INTERCAL NEXT stack underflow",
                hint="leave enough stack entries for the operation to consume",
            )
        resume, origin = self._next[-count]
        del self._next[-count:]
        if origin < 0:
            self.ind = resume
        else:
            # The NEXT finishes only now, so a COME FROM aimed at it fires.
            self._leave(origin)

    def _variable(self, action: str, key: _Key) -> None:
        if action == "ignore":
            self._ignored.add(key)
        elif action == "remember":
            self._ignored.discard(key)
        elif action == "stash":
            value: int | _Array
            if key[0] in ",;":
                dimensions, data = self._arrays.get(key, ((), {}))
                value = (dimensions, dict(data))
            else:
                value = self._scalars.get(key, 0)
            self._stashes.setdefault(key, []).append(value)
        else:
            stash = self._stashes.get(key)
            if not stash:
                raise _fail("E436", f"INTERCAL RETRIEVE of an unstashed {key[0]}")
            value = stash.pop()
            if key in self._ignored:
                return
            if isinstance(value, int):
                self._scalars[key] = value
            else:
                self._arrays[key] = value

    def _read_out(self, item: _Node) -> None:
        if item[0] != "array":
            self.io.print_str(_roman(self._value(item)) + "\n")
            return
        (size,), data = self._array((str(item[1]), int(item[2])))
        characters = []
        for index in range(size):
            self._last_out = (self._last_out - data.get(index, 0)) % 256
            characters.append(chr(_REVERSED[self._last_out]))
        self.io.print_str("".join(characters))

    def _write_in(self, item: _Node) -> None:
        if item[0] == "array":
            key = (str(item[1]), int(item[2]))
            (size,), data = self._array(key)
            for index in range(size):
                try:
                    character = self.io.input_char()
                except EOFError:
                    value, self._last_in = 256, -1
                else:
                    value = (character - self._last_in) % 256
                    self._last_in = character
                if key not in self._ignored:
                    data[index] = value
            return
        words = self.io.input_str().upper().split()
        if not words or any(word not in _DIGITS for word in words):
            raise _fail(
                "E579" if words else "E562",
                "invalid INTERCAL numeric input",
                hint="spell each decimal digit as a word, for example ONE TWO",
            )
        value = 0
        for word in words:
            value = value * 10 + _DIGITS[word]
            if value > _TWOSPOT_MAX:
                raise _fail("E533", "INTERCAL twospot input overflow")
        sigil = item[1] if item[0] == "sub" else item[0]
        if sigil in ".," and value > _ONESPOT_MAX:
            raise _fail("E275", "INTERCAL onespot input overflow")
        self._store(item, value)


def _freeze(value: int | _Array) -> Hashable:
    if isinstance(value, int):
        return value
    return value[0], tuple(sorted(value[1].items()))


def _thaw(value: Any) -> int | _Array:
    if isinstance(value, int):
        return value
    dimensions, data = value
    return dimensions, dict(data)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Execute an INTERCAL program."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
