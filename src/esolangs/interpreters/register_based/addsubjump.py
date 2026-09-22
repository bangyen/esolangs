"""Interpreter for AddSubJump (ASJ).

An OISC: ``ASJ a b c d`` is ``if (*d > 0) {*a -= *b} else {*a += *b};
goto c`` over a self-modifying integer memory, ``ip`` from 0. Source may
be raw integers or assembly with labels, macros, directives, and comments.
Special addresses: ``-1`` I/O (read a byte / print ``*b``),
``-2``..``-5`` Carry/Zero/Negative/Overflow, ``-6``/``-7``/``-8`` the
constants 1/0/-1, ``-9`` the flag update mode (starts 0).  Jumping to a
special address or off the end halts.  Cells are unbounded (Carry and
Overflow stay 0); reading ``-1`` raises :class:`EOFError` when input runs
out; malformed source raises :class:`ValueError`; no instruction cap
(``esolangs.run``'s ``timeout``); a write to an address too large to
allocate halts with :class:`HaltError`.
"""

import re
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

# The largest memory a run will grow.  Cell values are unbounded, but the
# list backing them is not: past this the allocation is one no machine
# would satisfy, so the run halts instead of raising OverflowError (or
# spending the box's memory finding out).
_MAX_MEMORY = 1 << 24

_IO = -1
_CF, _ZF, _NF, _VF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))

_BUILTINS = {
    "IO": _IO,
    "CF": _CF,
    "ZF": _ZF,
    "NF": _NF,
    "VF": _VF,
    "@1": _ONE,
    "@0": _ZERO,
    "@n1": _NEG,
    "FUM": _FUM,
}
_LABEL = re.compile(r"(?:@[A-Za-z0-9]+|[A-Za-z][A-Za-z0-9]*)(?:[+-]\d+)?$")


@dataclass(frozen=True)
class _Macro:
    """One assembly macro: formal names and its source lines."""

    params: tuple[str, ...]
    body: tuple[tuple[str, ...], ...]


def _source_lines(code: str) -> list[list[str]]:
    """Return comment-free assembly tokens grouped by source line."""
    code = re.sub(
        r"/\*.*?\*/",
        lambda match: "\n" * match.group().count("\n"),
        code,
        flags=re.S,
    )
    lines = []
    for raw in code.splitlines():
        raw = raw.split("//", 1)[0].split("#", 1)[0]
        tokens = re.findall(r"\{|\}|[^\s{}]+", raw)
        if tokens:
            lines.append(tokens)
    return lines


def _macros(lines: list[list[str]]) -> tuple[dict[str, _Macro], list[list[str]]]:
    """Remove and return ``def`` blocks."""
    macros: dict[str, _Macro] = {}
    program: list[list[str]] = []
    at = 0
    while at < len(lines):
        line = lines[at]
        if line[0] != "def":
            program.append(line)
            at += 1
            continue
        if len(line) < 3 or "{" not in line:
            raise ValueError("malformed AddSubJump macro definition")
        brace = line.index("{")
        if brace != len(line) - 1 or brace < 2:
            raise ValueError("malformed AddSubJump macro definition")
        name = line[1]
        body: list[tuple[str, ...]] = []
        at += 1
        while at < len(lines) and lines[at] != ["}"]:
            if "{" in lines[at] or "}" in lines[at]:
                raise ValueError("nested AddSubJump macro definition")
            body.append(tuple(lines[at]))
            at += 1
        if at == len(lines):
            raise ValueError(f"macro {name!r} is missing '}}'")
        if name in macros:
            raise ValueError(f"duplicate macro {name!r}")
        macros[name] = _Macro(tuple(line[2:brace]), tuple(body))
        at += 1
    return macros, program


def _defined_labels(lines: tuple[tuple[str, ...], ...]) -> set[str]:
    """Return labels defined by ``lines``."""
    out = set()
    for line in lines:
        for token in line:
            if ":" in token:
                name, _value = token.split(":", 1)
                if name:
                    out.add(name)
    return out


def _expand(lines: list[list[str]], macros: dict[str, _Macro]) -> list[list[str]]:
    """Expand macro calls, giving each expansion private labels."""
    serial = 0

    def rewrite(token: str, mapping: dict[str, str]) -> str:
        """Replace a symbol in ``token``, retaining a label offset."""
        match = re.fullmatch(r"(.+?)([+-]\d+)?", token)
        if match is None:
            return token
        name, offset = match.groups()
        return mapping.get(name, name) + (offset or "")

    def one(line: list[str], active: tuple[str, ...]) -> list[list[str]]:
        nonlocal serial
        prefix: list[str] = []
        while line and line[0].endswith(":"):
            prefix.append(line.pop(0))
        if not line or line[0] not in macros:
            return [prefix + line]
        name = line[0]
        if name in active:
            raise ValueError(f"recursive macro {name!r}")
        macro = macros[name]
        args = line[1:]
        if len(args) != len(macro.params):
            raise ValueError(
                f"macro {name!r} takes {len(macro.params)} arguments, got {len(args)}"
            )
        values = dict(zip(macro.params, args, strict=True))
        local = _defined_labels(macro.body) - set(macro.params)
        serial += 1
        renamed = {label: f"@M{serial}{label.lstrip('@')}" for label in local}
        expanded: list[list[str]] = []
        for raw in macro.body:
            replaced = []
            for token in raw:
                label, colon, value = token.partition(":")
                mapping = {**values, **renamed}
                label = rewrite(label, mapping)
                value = rewrite(value, mapping) if colon else value
                replaced.append(label + colon + value)
            expanded += one(replaced, (*active, name))
        if prefix:
            if not expanded:
                expanded = [prefix]
            else:
                expanded[0] = prefix + expanded[0]
        return expanded

    out: list[list[str]] = []
    for line in lines:
        out += one(list(line), ())
    return out


def _split_labels(line: list[str]) -> tuple[list[str], list[str]]:
    """Return leading/attached label definitions and remaining tokens."""
    labels: list[str] = []
    rest: list[str] = []
    defining = True
    for token in line:
        if defining and ":" in token:
            name, value = token.split(":", 1)
            if not name:
                raise ValueError("empty AddSubJump label")
            labels.append(name)
            if value:
                rest.append(value)
                defining = False
        else:
            rest.append(token)
            defining = False
    return labels, rest


def _assembly(code: str) -> list[int]:
    """Assemble documented AddSubJump source into integer memory."""
    macros, source = _macros(_source_lines(code))
    lines = _expand(source, macros)
    parsed: list[tuple[int, bool, list[str]]] = []
    labels = dict(_BUILTINS)
    address = 0
    for line in lines:
        definitions, tokens = _split_labels(line)
        for name in definitions:
            if name in labels:
                raise ValueError(f"duplicate label {name!r}")
            labels[name] = address
        if not tokens:
            continue
        data = tokens[0] == ".data"
        if data:
            operands = []
            for token in tokens[1:]:
                if ":" not in token:
                    operands.append(token)
                    continue
                name, item = token.split(":", 1)
                if not name:
                    raise ValueError("empty AddSubJump label")
                if name in labels:
                    raise ValueError(f"duplicate label {name!r}")
                labels[name] = address + len(operands)
                if item:
                    operands.append(item)
        else:
            operands = tokens[1:] if tokens[0].upper() == "ASJ" else tokens
            if len(operands) not in (2, 3, 4):
                raise ValueError(
                    f"AddSubJump instruction needs 2 to 4 operands, got {len(operands)}"
                )
        parsed.append((address, data, operands))
        address += len(operands) if data else 4

    def value(token: str, next_ip: int) -> int:
        if token == "?":  # nosec B105 - assembly punctuation, not a password
            return next_ip
        try:
            return int(token)
        except ValueError:
            pass
        if not _LABEL.fullmatch(token):
            raise ValueError(f"invalid AddSubJump operand {token!r}")
        match = re.fullmatch(r"(.+?)([+-]\d+)?", token)
        if match is None:  # pragma: no cover - _LABEL accepted the same grammar
            raise AssertionError("label grammar disagrees with its parser")
        name, offset = match.groups()
        if name not in labels:
            raise ValueError(f"undefined label {name!r}")
        return labels[name] + (int(offset) if offset else 0)

    memory: list[int] = []
    for at, data, operands in parsed:
        next_ip = at + (len(operands) if data else 4)
        values = [value(token, next_ip) for token in operands]
        if not data:
            if len(values) == 2:
                values += [next_ip, _ZERO]
            elif len(values) == 3:
                values.append(_ZERO)
        memory += values
    return memory


def _program(code: str) -> list[int]:
    """Parse raw integer memory, or assemble source using symbolic syntax."""
    try:
        return list(_parse(code))
    except ValueError:
        return _assembly(code)


#: One instant of a run: ``(memory, ip, cf, zf, nf, vf, fum)`` -- the
#: self-modifying store, the instruction pointer, the four flags, and the
#: flag-update mode.  A value, not a record: every transition below returns
#: a new one rather than editing one in place, and the memory is copied on
#: write for the same reason.
#:
#: The memory is in the state rather than beside it because this language
#: rewrites it as it runs *and* can extend it: a write past the end grows
#: the store, and ``halted`` compares the pointer against the current
#: length.
#:
#: It is *sparse* -- ``(non-zero cells, allocated length)`` -- because the
#: addresses a program uses are unrelated to how many cells it fills: one
#: writing cell 999999 allocates a million and leaves all but a handful
#: zero.  The length is carried explicitly because it stays semantic (it is
#: what ``halted`` and the allocation cap test) and can no longer be read
#: off the container.  A ``dict`` is unhashable, so :meth:`_Machine.snapshot`
#: is what freezes it for the cycle detector.
type _Cells = tuple[dict[int, int], int]
type _State = tuple[_Cells, int, int, int, int, int, int]


def _pack(values: list[int]) -> _Cells:
    """Return ``values`` as the sparse store: non-zero cells, and the length.

    Zeros are dropped, as :func:`_store` does, so parsed and written zeros match.
    """
    return ({i: v for i, v in enumerate(values) if v}, len(values))


def _operands(state: _State) -> tuple[int, int, int, int]:
    """Return the four cells of the instruction under the pointer.

    Missing operands read as zero.
    """
    (cells, length), ip = state[0], state[1]
    return (
        cells.get(ip, 0),
        cells.get(ip + 1, 0) if ip + 1 < length else 0,
        cells.get(ip + 2, 0) if ip + 2 < length else 0,
        cells.get(ip + 3, 0) if ip + 3 < length else 0,
    )


def _load(state: _State, addr: int, byte: int | None = None) -> int:
    """Return the value at ``addr``, which may be a special register.

    ``byte`` is what the shell read from the port; out of range reads zero.
    """
    (cells, length), _ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return byte if byte is not None else 0
    if addr == _CF:
        return cf
    if addr == _ZF:
        return zf
    if addr == _NF:
        return nf
    if addr == _VF:
        return vf
    if addr == _ONE:
        return 1
    if addr == _ZERO:
        return 0
    if addr == _NEG:
        return -1
    if addr == _FUM:
        return fum
    return cells.get(addr, 0) if 0 <= addr < length else 0


def _too_large(state: _State, addr: int) -> bool:
    """Whether writing ``addr`` would grow the store past what is allowed.

    Values are unbounded; the list of cells is not: halt, not ``OverflowError``.
    """
    _cells, length = state[0]
    return (
        addr != _IO
        and addr not in _SPECIAL
        and addr >= length
        and addr + 1 > _MAX_MEMORY
    )


def _store(state: _State, addr: int, value: int) -> _State:
    """Return ``state`` with ``addr`` set to ``value``.

    Writing the port is the shell's; other special registers are discarded.
    The store is a dict of non-zero cells plus the length: a write to cell
    999999 rebuilt a million-cell tuple at 4.6ms a step.  A zero deletes its
    key so written and never-written zeros hash alike.
    """
    (cells, length), ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return state
    if addr in _SPECIAL:
        return (state[0], ip, cf, zf, nf, vf, value) if addr == _FUM else state
    if addr >= length:
        length = addr + 1
    new = dict(cells)
    if value:
        new[addr] = value
    else:
        new.pop(addr, None)
    return ((new, length), ip, cf, zf, nf, vf, fum)


def _advance(state: _State, reads: tuple[int, ...]) -> tuple[int, _State]:
    """Return the value the instruction computed, and the state after it.

    ``reads`` holds the bytes the shell took from the port, in operand order.
    The value comes back because writing the port is the shell's effect.
    """
    pending = list(reads)

    def take(addr: int) -> int:
        return _load(state, addr, pending.pop(0) if addr == _IO else None)

    a, b, c, d = _operands(state)
    vd = take(d)
    vb = take(b)
    if a == _IO:
        value = vb
    else:
        va = take(a)
        value = va - vb if vd > 0 else va + vb

    after = _store(state, a, value)
    memory, _ip, cf, zf, nf, vf, fum = after
    if fum:
        zf = 1 if value == 0 else 0
        nf = 1 if value < 0 else 0
        cf = vf = 0
    after = (memory, _ip, cf, zf, nf, vf, fum)
    return value, (memory, _load(after, c), cf, zf, nf, vf, fum)


class _Machine:
    """Per-run ASJ state: the self-modifying memory, ip, and flags."""

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer and flags."""
        self.io = io
        self.state: _State = (_pack(_program(code)), 0, 0, 0, 0, 0, 0)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def memory(self) -> list[int]:
        """The self-modifying store, densified (a test view)."""
        cells, length = self.state[0]
        return [cells.get(i, 0) for i in range(length)]

    @property
    def ip(self) -> int:
        """The instruction pointer."""
        return self.state[1]

    @property
    def cf(self) -> int:
        return self.state[2]

    @property
    def zf(self) -> int:
        return self.state[3]

    @property
    def nf(self) -> int:
        return self.state[4]

    @property
    def vf(self) -> int:
        """The Overflow flag (``VF``, address -5)."""
        return self.state[5]

    @property
    def fum(self) -> int:
        """Whether the flags follow each instruction's result."""
        return self.state[6]

    @property
    def halted(self) -> bool:
        """Whether the pointer is off the end of memory or a special address."""
        (_cells, length), ip = self.state[0], self.state[1]
        return ip < 0 or ip >= length

    # The VM's language-shaped view: self-modifying memory + instruction
    # pointer.  ``ip`` and ``memory`` above already *are* the view, so only
    # the empty stack needs saying.

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands plus the input cursor: a repeat that
        # ignores consumed input is not a real cycle.
        #
        # The sparse store's dict is unhashable and its iteration order
        # follows insertion, so equal memories reached by different write
        # orders would freeze differently.  Sorting the items is what makes
        # the key depend on the contents alone -- and sorted items rather
        # than a frozenset because a frozenset's repr is unstable across
        # processes, which the mutation baselines compare.
        (cells, length) = self.state[0]
        return (
            tuple(sorted(cells.items())),
            length,
            *self.state[1:],
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one instruction, advancing the pointer.

        Up to three operands may name the input port, so the shell reads them
        in the transition's order (``d``, ``b``, then ``a`` unless written).
        """
        if self.halted:
            return
        a, b, _c, d = _operands(self.state)
        if _too_large(self.state, a):
            raise HaltError(f"memory address {a} is too large")
        reads = tuple(
            self.io.input_char()
            for addr in ((d, b) if a == _IO else (d, b, a))
            if addr == _IO
        )
        value, self.state = _advance(self.state, reads)
        if a == _IO:
            self.io.print_char(chr(value & 0xFF))


def run(code: str, io: IO) -> None:
    """Run an AddSubJump program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
