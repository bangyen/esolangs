"""Assemble AddSubJump source into an initial memory image."""

import re
from dataclasses import dataclass

from esolangs.languages.addsubjump._addresses import (
    _CF,
    _FUM,
    _IO,
    _NEG,
    _NF,
    _ONE,
    _VF,
    _ZERO,
    _ZF,
)
from esolangs.runtime.memory import parse_integer as _integer
from esolangs.runtime.source_hints import syntax_error

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
        flags=re.DOTALL,
    )
    lines = []
    for raw_line in code.splitlines():
        raw = raw_line.split("//", 1)[0].split("#", 1)[0]
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
            raise syntax_error(
                "malformed AddSubJump macro definition",
                "write def <name> <parameters> { with the body on following lines",
            )
        brace = line.index("{")
        if brace != len(line) - 1 or brace < 2:
            raise syntax_error(
                "malformed AddSubJump macro definition",
                "put { last on the macro header line",
            )
        name = line[1]
        body: list[tuple[str, ...]] = []
        at += 1
        while at < len(lines) and lines[at] != ["}"]:
            if "{" in lines[at] or "}" in lines[at]:
                raise syntax_error(
                    "nested AddSubJump macro definition",
                    "put macro definitions at the top level instead of nesting them",
                )
            body.append(tuple(lines[at]))
            at += 1
        if at == len(lines):
            raise syntax_error(
                f"macro {name!r} is missing '}}'",
                "close the macro body with } on its own line",
            )
        if name in macros:
            raise syntax_error(
                f"duplicate macro {name!r}", "give each macro a unique name"
            )
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


def _rewrite_token(token: str, mapping: dict[str, str]) -> str:
    """Replace a symbol in ``token``, retaining a label offset."""
    match = re.fullmatch(r"(.+?)([+-]\d+)?", token)
    if match is None:
        return token
    name, offset = match.groups()
    return mapping.get(name, name) + (offset or "")


def _substitute_token(token: str, mapping: dict[str, str]) -> str:
    """Rewrite a macro body token's label and value parts through ``mapping``."""
    label, colon, value = token.partition(":")
    label = _rewrite_token(label, mapping)
    value = _rewrite_token(value, mapping) if colon else value
    return label + colon + value


class _LabelRenamer:
    """Hands out the per-expansion names that make macro labels private.

    The serial is mutable allocator state shared by every expansion of one
    source, so no two expansions of a macro ever reuse a label name.
    """

    def __init__(self) -> None:
        self._serial = 0

    def rename(self, local: set[str]) -> dict[str, str]:
        """Return a fresh private name for each of one expansion's labels."""
        self._serial += 1
        return {label: f"@M{self._serial}{label.lstrip('@')}" for label in local}


def _expand_line(
    line: list[str],
    macros: dict[str, _Macro],
    renamer: _LabelRenamer,
    active: tuple[str, ...],
) -> list[list[str]]:
    """Expand one line's macro call, recursing into the substituted body.

    Leading label definitions are peeled off first and re-attached to the
    first expanded line (or kept alone when the body expands to nothing).
    A line that does not call a macro passes through unchanged.
    """
    prefix: list[str] = []
    while line and line[0].endswith(":"):
        prefix.append(line.pop(0))
    if not line or line[0] not in macros:
        return [prefix + line]
    name = line[0]
    if name in active:
        raise syntax_error(
            f"recursive macro {name!r}",
            "remove recursive macro calls; expansion must terminate",
        )
    macro = macros[name]
    args = line[1:]
    if len(args) != len(macro.params):
        raise syntax_error(
            f"macro {name!r} takes {len(macro.params)} arguments, got {len(args)}",
            "pass the number of operands declared by the macro parameters",
        )
    values = dict(zip(macro.params, args, strict=True))
    local = _defined_labels(macro.body) - set(macro.params)
    mapping = {**values, **renamer.rename(local)}
    expanded: list[list[str]] = []
    for raw in macro.body:
        replaced = [_substitute_token(token, mapping) for token in raw]
        expanded += _expand_line(replaced, macros, renamer, (*active, name))
    if prefix:
        if not expanded:
            expanded = [prefix]
        else:
            expanded[0] = prefix + expanded[0]
    return expanded


def _expand(lines: list[list[str]], macros: dict[str, _Macro]) -> list[list[str]]:
    """Expand macro calls, giving each expansion private labels."""
    renamer = _LabelRenamer()
    out: list[list[str]] = []
    for line in lines:
        out += _expand_line(list(line), macros, renamer, ())
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
                raise syntax_error(
                    "empty AddSubJump label", "put a name before : to define a label"
                )
            labels.append(name)
            if value:
                rest.append(value)
                defining = False
        else:
            rest.append(token)
            defining = False
    return labels, rest


def _define(labels: dict[str, int], name: str, address: int, hint: str) -> None:
    """Bind ``name`` to ``address``, refusing a second definition."""
    if name in labels:
        raise syntax_error(f"duplicate label {name!r}", hint)
    labels[name] = address


def _data_operands(
    tokens: list[str], labels: dict[str, int], address: int
) -> list[str]:
    """Return a ``.data`` line's items, binding each ``name:item`` label."""
    operands: list[str] = []
    for token in tokens:
        name, sep, item = token.partition(":")
        if not sep:
            operands.append(token)
            continue
        if not name:
            raise syntax_error(
                "empty AddSubJump label",
                "put a name before : in the data declaration",
            )
        _define(
            labels, name, address + len(operands), "give each data label a unique name"
        )
        if item:
            operands.append(item)
    return operands


def _resolve(token: str, next_ip: int, labels: dict[str, int]) -> int:
    """Return an operand: an integer, ``?`` (the next instruction), or a label."""
    if token == "?":  # assembly punctuation, not a password
        return next_ip
    try:
        return _integer(token)
    except ValueError:
        pass
    if not _LABEL.fullmatch(token):
        raise syntax_error(
            f"invalid AddSubJump operand {token!r}",
            ("use an integer, ?, or a label with an optional signed decimal offset"),
        )
    match = re.fullmatch(r"(.+?)([+-]\d+)?", token)
    if match is None:  # pragma: no cover - _LABEL accepted the same grammar
        raise AssertionError("label grammar disagrees with its parser")
    name, offset = match.groups()
    if name not in labels:
        raise syntax_error(
            f"undefined label {name!r}", "define the label before using its address"
        )
    return labels[name] + (_integer(offset) if offset else 0)


def _assembly(code: str) -> list[int]:
    """Assemble documented AddSubJump source into integer memory."""
    macros, source = _macros(_source_lines(code))
    # Each line's operands, whether it is data, and the address after it.
    parsed: list[tuple[list[str], bool, int]] = []
    labels = dict(_BUILTINS)
    address = 0
    for line in _expand(source, macros):
        definitions, tokens = _split_labels(line)
        for name in definitions:
            _define(
                labels,
                name,
                address,
                "give each label a unique name distinct from built-in labels",
            )
        if not tokens:
            continue
        data = tokens[0] == ".data"
        if data:
            operands = _data_operands(tokens[1:], labels, address)
        else:
            operands = tokens[1:] if tokens[0].upper() == "ASJ" else tokens
            if len(operands) not in (2, 3, 4):
                raise syntax_error(
                    "AddSubJump instruction needs 2 to 4 operands, "
                    f"got {len(operands)}",
                    ("write ASJ with 2 to 4 address operands"),
                )
        address += len(operands) if data else 4
        parsed.append((operands, data, address))

    memory: list[int] = []
    for operands, data, next_ip in parsed:
        values = [_resolve(token, next_ip, labels) for token in operands]
        if not data:
            # An omitted ``c`` falls through; an omitted ``d`` reads the
            # constant 0, so the instruction adds.
            if len(values) == 2:
                values += [next_ip, _ZERO]
            elif len(values) == 3:
                values.append(_ZERO)
        memory += values
    return memory


def _program(code: str) -> list[int]:
    """Parse raw integer memory, or assemble source using symbolic syntax."""
    try:
        return [
            _integer(token)
            for line in code.splitlines()
            for token in line.split("#", 1)[0].split()
        ]
    except ValueError:
        return _assembly(code)
