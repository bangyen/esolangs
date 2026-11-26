"""Parse GridScript source into commands and program bodies."""

import re
from typing import Any, NamedTuple

from esolangs.exceptions import ProgramError
from esolangs.languages.gridscript._values import (
    _FLOAT,
    _INT,
    NULL,
    _f32,
    _Float,
    _int,
    _Value,
)
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

_NODE = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)\s*:(.*)")
_TOKEN = re.compile(r"\s*('[^']*'|\"[^\"]*\"|\S+)")
_NAME = re.compile(r"[a-z_][a-z0-9_]*")
_TYPES = frozenset({"INT", "FLOAT", "STRING", "BOOL"})
_HEADINGS = {"EAST": 0, "SOUTH": 90, "WEST": 180, "NORTH": 270}
_META = frozenset(
    {"width", "height", "datawidth", "dataheight", "radius", "steps", "debug"}
)
_DEFAULTS = {"datawidth": 64, "dataheight": 64, "radius": 1}


class _Var(NamedTuple):
    """A variable reference inside a parsed command."""

    name: str


class _Named(NamedTuple):
    """An expression supplying a variable name at execution time."""

    source: "_Arg"


type _Arg = _Value | _Var | _Named | None
_NAMED = "THE VARIABLE NAMED "


class _Cmd(NamedTuple):
    """A parsed command: its verb and operands."""

    verb: str
    args: tuple[object, ...] = ()


class _Body(NamedTuple):
    """One program or subroutine: its nodes, metadata and lookup tables."""

    name: str
    nodes: tuple[tuple[int, int, _Cmd], ...]  # in file order
    meta: tuple[tuple[str, int], ...]
    start: tuple[int, int]
    cells: dict[tuple[int, int], tuple[int, ...]]  # centre -> node indices
    checkpoints: tuple[tuple[int, int, int], ...]  # id, x, y
    mutable: bool


def _bad(text: str, hint: str) -> ValueError:
    return syntax_error(f"cannot parse {text!r}", hint, error_type=ProgramError)


def _bad_node(x: int, y: int, hint: str) -> ValueError:
    return _bad(f"({format_integer(x)},{format_integer(y)})", hint)


def _unsupported(what: str) -> ValueError:
    return syntax_error(
        f"{what} is not implemented",
        "the page names it but no example exercises or defines it",
        error_type=ProgramError,
    )


# --- values and casts -------------------------------------------------------


def _literal(tok: str) -> _Arg:
    if tok.startswith(_NAMED):
        return _Named(_literal(tok[len(_NAMED) :]))
    if tok[:1] in ("'", '"') and len(tok) >= 2 and tok[-1] == tok[0]:
        return tok[1:-1]
    if _INT.fullmatch(tok):
        return _int(parse_integer(tok))
    if _FLOAT.fullmatch(tok):
        return _Float(_f32(float(tok)))
    if tok in ("TRUE", "FALSE"):
        return tok == "TRUE"
    if tok == "NULL":
        return NULL
    if _NAME.fullmatch(tok):
        return _Var(tok)
    raise _bad(
        tok, "a value is a number, a quoted string, TRUE, FALSE, NULL or a variable"
    )


# --- parsing ----------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    out, pos, end = [], 0, len(text.rstrip())
    while pos < end:
        m = _TOKEN.match(text, pos)
        assert m is not None
        out.append(m.group(1))
        pos = m.end()
    return out


def _named_tokens(toks: list[str]) -> list[str]:
    """Group a dynamic name as one operand, retaining any type or switch."""
    for i in range(len(toks) - 4, -1, -1):
        if i + 3 >= len(toks):
            continue
        start, kind, named, source = toks[i : i + 4]
        lead = start.removesuffix("THE")
        if (
            start != lead + "THE"
            or lead not in ("", "!", "=", "!=")
            or named != "NAMED"
            or (kind != "VARIABLE" and kind not in _TYPES)
        ):
            continue
        operand = lead + _NAMED + source
        toks[i : i + 4] = [operand] if kind == "VARIABLE" else [kind, operand]
    return toks


def _var(tok: str, text: str) -> str | _Named:
    if tok.startswith(_NAMED):
        return _Named(_literal(tok[len(_NAMED) :]))
    if not _NAME.fullmatch(tok):
        raise _bad(text, "a variable is lowercase letters, digits and _")
    return tok


def _go(rest: list[str], _text: str) -> _Cmd | None:
    relative = rest[:2] == ["RELATIVE", "TO"]
    rest = rest[2:] if relative else rest
    if len(rest) == 1 and rest[0] in _HEADINGS and not relative:
        return _Cmd("GO", (False, _HEADINGS[rest[0]]))
    if rest == ["THIS", "DIRECTION"]:
        return _Cmd("GO", (relative, None))
    return _Cmd("GO", (relative, _literal(rest[0]))) if len(rest) == 1 else None


def _goto(rest: list[str], _text: str) -> _Cmd | None:
    if rest == ["THIS", "CHECKPOINT"]:
        return _Cmd("GOTO", (None,))
    return _Cmd("GOTO", (_literal(rest[0]),)) if len(rest) == 1 else None


def _switch(rest: list[str], _text: str) -> _Cmd | None:
    if len(rest) != 1:
        return None
    tok = rest[0]
    for mode in ("!=", "!", "="):
        if tok.startswith(mode) and len(tok) > len(mode):
            return _Cmd("SWITCH", (mode, _literal(tok[len(mode) :])))
    return _Cmd("SWITCH", ("", _literal(tok)))


def _store(rest: list[str], text: str) -> _Cmd | None:
    target = None
    if len(rest) >= 2 and rest[-2] == "TO":
        target, rest = _var(rest[-1], text), rest[:-2]
    if len(rest) > 1:
        return None
    return _Cmd("STORE", (_literal(rest[0]) if rest else None, target))


def _input(rest: list[str], text: str) -> _Cmd | None:
    prompt = None
    if "WITH" in rest:
        at = rest.index("WITH")
        tail, rest = rest[at + 1 :], rest[:at]
        if len(tail) != 2 or tail[0] != "PROMPT":
            raise _bad(text, "INPUT WITH PROMPT needs one value")
        prompt = _literal(tail[1])
    typ = rest.pop(0) if rest and rest[0] in _TYPES else None
    if rest and rest[0] == "TO":
        rest = rest[1:]
    if len(rest) > 1:
        return None
    return _Cmd("INPUT", (typ, _var(rest[0], text) if rest else None, prompt))


def _print(rest: list[str], _text: str) -> _Cmd | None:
    if rest[:1] in (["IMAGE"], ["FILE"]):
        raise _unsupported(f"PRINT {rest[0]}")
    if rest == ["NEWLINE"]:
        return _Cmd("PRINT NEWLINE")
    return _optional("PRINT", rest)


def _optional(verb: str, rest: list[str]) -> _Cmd | None:
    """A verb with one optional value."""
    if len(rest) > 1:
        return None
    return _Cmd(verb, (_literal(rest[0]) if rest else None,))


def _split(rest: list[str], _text: str) -> _Cmd | None:
    if len(rest) not in (1, 3) or rest[1:2] not in ([], ["OVER"]):
        return None
    return _Cmd("SPLIT", (_literal(rest[0]), _literal(rest[2]) if rest[2:] else None))


def _move_last(rest: list[str], _text: str) -> _Cmd | None:
    if len(rest) == 5 and rest[:2] == ["LAST", "NODE"] and rest[2] in ("TO", "BY"):
        return _Cmd("MOVE", (rest[2] == "BY", _literal(rest[3]), _literal(rest[4])))
    return None


def _checkpoint(rest: list[str], _text: str) -> _Cmd | None:
    if len(rest) == 1 and rest[0].isdigit():
        return _Cmd("CHECKPOINT", (parse_integer(rest[0]),))
    return None


def _command(text: str) -> _Cmd:
    """Parse one node's command."""
    toks = _tokens(text)
    if not toks:
        raise _bad(text, "a node needs a command")
    if "RANDOM" in toks or toks[0] == "SHUFFLE":
        raise _unsupported("randomness")
    if "NAMED" in toks:
        toks = _named_tokens(toks)
    verb, rest = toks[0], toks[1:]
    if verb in ("LOAD", "THROW"):
        raise _unsupported(verb)
    cmd: _Cmd | None = None
    if verb in ("START", "PEEK", "HOME") and not rest:
        cmd = _Cmd(verb)
    elif verb in ("NEXT", "PREVIOUS") and rest in (["VALUE"], ["ROW"]):
        cmd = _Cmd(f"{verb} {rest[0]}")
    elif verb in ("INCREMENT", "DECREMENT", "MULTIPLY", "DIVIDE"):
        cmd = _arith_command(verb, rest, text)
    elif verb in ("PUSH", "RETURN"):
        cmd = _optional(verb, rest)
    elif verb == "WARN":
        cmd = _Cmd(verb)
    elif verb == "CALL" and rest:
        cmd = _call(rest, text)
    elif verb in _PARSERS:
        cmd = _PARSERS[verb](rest, text)
    if cmd is None:
        raise _bad(text, "see the command list in the module docstring")
    return cmd


def _remove(rest: list[str], text: str) -> _Cmd:
    typ = target = None
    if "TO" in rest:
        at = rest.index("TO")
        tail, rest = rest[at + 1 :], rest[:at]
        typ = tail.pop(0) if tail and tail[0] in _TYPES else None
        if len(tail) != 1:
            raise _bad(text, "REMOVE ... TO [type] variable")
        target = _var(tail[0], text)
    if rest == ["ANY", "POSITION"]:
        raise _unsupported("randomness")
    if rest == ["THIS", "POSITION"]:
        where: object = "this"
    elif rest == ["TOP"]:
        where = "top"
    elif not rest:
        where = 0
    elif len(rest) == 1:
        where = _literal(rest[0])
    else:
        raise _bad(text, "REMOVE [position|THIS POSITION|TOP] [TO [type] variable]")
    return _Cmd("REMOVE", (where, typ, target))


def _arith_command(verb: str, rest: list[str], text: str) -> _Cmd:
    source = None
    if rest and rest[0] not in ("BY", "GIVING"):
        source = _var(rest.pop(0), text)
    by: _Arg = 1
    if rest[:1] == ["BY"] and len(rest) >= 2:
        by, rest = _literal(rest[1]), rest[2:]
    elif verb in ("MULTIPLY", "DIVIDE"):
        raise _bad(text, f"{verb} needs BY a value")
    giving = None
    if rest[:1] == ["GIVING"] and len(rest) == 2:
        giving, rest = _var(rest[1], text), []
    if rest:
        raise _bad(text, f"{verb} [variable] BY value [GIVING variable]")
    return _Cmd(verb, (source, by, giving))


def _call(rest: list[str], text: str) -> _Cmd:
    name, rest = rest[0], rest[1:]
    giving = None
    if len(rest) >= 2 and rest[-2] == "GIVING":
        giving, rest = _var(rest[-1], text), rest[:-2]
    args: tuple[_Arg, ...] = ()
    if rest[:2] == ["WITH", "ARGUMENTS"]:
        args, rest = tuple(map(_literal, rest[2:])), []
    if rest:
        raise _bad(text, "CALL NAME [WITH ARGUMENTS values] [GIVING variable]")
    return _Cmd("CALL", (name, args, giving))


_PARSERS: dict[str, Any] = {
    "GO": _go,
    "GOTO": _goto,
    "SWITCH": _switch,
    "STORE": _store,
    "INPUT": _input,
    "MOVE": _move_last,
    "PRINT": _print,
    "SPLIT": _split,
    "CHECKPOINT": _checkpoint,
    "REMOVE": _remove,
}


def _sections(code: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    for raw in code.replace("\r\n", "\n").split("\n"):
        line = raw.split("!!", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            depth = 2 if line.startswith("##") else 1
            if (depth == 1) != (not sections) or not line.endswith("."):
                raise _bad(line, "#TITLE. first, then ##SUBROUTINE. sections")
            sections.append((line[depth:-1].strip(), []))
        elif not sections:
            raise _bad(line, "a program starts with #TITLE.")
        else:
            sections[-1][1].append(line)
    if not sections:
        raise _bad(code, "a program starts with #TITLE.")
    return sections


def _metadata(line: str, meta: dict[str, int]) -> None:
    parts = line[1:].split()
    if len(parts) != 2 or parts[0] not in _META:
        raise _bad(line, f"metadata is @key value, key one of {sorted(_META)}")
    key, value = parts
    if key == "debug":
        if value not in ("true", "false", "auto"):
            raise _bad(line, "@debug is true, false or auto")
        return
    number = parse_integer(value) if _INT.fullmatch(value) else 0
    if number < 1:
        raise _bad(line, f"@{key} needs a positive integer")
    meta[key] = number


def _parse(code: str) -> tuple[_Body, ...]:
    sections = _sections(code)
    bodies: list[_Body] = []
    main_meta: dict[str, int] = {}
    for index, (name, lines) in enumerate(sections):
        meta = dict(_DEFAULTS) | main_meta
        own: dict[str, int] = {}
        nodes: list[tuple[int, int, _Cmd]] = []
        for line in lines:
            if line.startswith("@"):
                _metadata(line, own)
            elif m := _NODE.fullmatch(line):
                nodes.append(
                    (parse_integer(m[1]), parse_integer(m[2]), _command(m[3].strip()))
                )
            else:
                raise _bad(line, "a line is @key value or (x,y):COMMAND")
        meta |= own
        if index == 0:
            main_meta = dict(meta)
        for key in ("width", "height"):
            if key not in meta:
                raise _bad(f"#{name}.", f"@{key} is required")
        width, height = meta["width"], meta["height"]
        starts = [(x, y) for x, y, cmd in nodes if cmd.verb == "START"]
        if len(starts) != 1:
            raise _bad(f"#{name}.", "each program needs exactly one START node")
        cells: dict[tuple[int, int], list[int]] = {}
        for i, (x, y, cmd) in enumerate(nodes):
            if not (1 <= x <= width and 1 <= y <= height):
                raise _bad_node(x, y, "a node lies outside the program space")
            if cmd.verb == "RETURN" and index == 0:
                raise _bad_node(x, y, "RETURN is only supported in subroutines")
            cells.setdefault((x, y), []).append(i)
        checkpoints = tuple(
            (int(cmd.args[0]), x, y)  # type: ignore[call-overload]
            for x, y, cmd in nodes
            if cmd.verb == "CHECKPOINT"
        )
        bodies.append(
            _Body(
                name,
                tuple(nodes),
                tuple(sorted(meta.items())),
                starts[0],
                {k: tuple(v) for k, v in cells.items()},
                checkpoints,
                any(cmd.verb == "MOVE" for _, _, cmd in nodes),
            )
        )
    names = {body.name for body in bodies[1:]}
    for body in bodies:
        for x, y, cmd in body.nodes:
            if cmd.verb == "CALL" and cmd.args[0] not in names:
                raise _bad_node(x, y, f"no subroutine named {cmd.args[0]}")
    return tuple(bodies)
