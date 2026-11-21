r"""Interpreter for GridScript: commands at points, run by a tracer moving through them.

A program is a ``#TITLE.`` line, ``@key value`` metadata and node lines
``(x,y):COMMAND``, then optional subroutines, each a ``##NAME.`` line with
its own metadata and nodes.  Nodes are circles of the metadata radius
around integral points.  The program tracer starts at the START node facing
east (0 degrees, clockwise, y growing south); each move adds the cosine and
sine of its direction to its 16-bit-float position.  Leaving
``[1,width] x [1,height]`` halts the program (or ends a subroutine with no
return value).  Every node the tracer is inside after a move, and was not
inside before it, runs in file order, one command per step.

Commands (``value`` is a literal ``12``, ``1.5``, ``'text'``, ``"text"``,
``TRUE``, ``FALSE``, ``NULL`` or a lowercase variable; "D" is the dataspace
cell under the data tracer):
    ``GO NORTH|SOUTH|EAST|WEST|[RELATIVE TO] THIS DIRECTION|[RELATIVE TO] v``
    ``CHECKPOINT id`` / ``GOTO id|THIS CHECKPOINT``  teleport to the nearest
    ``SWITCH v|!v|=v|!=v``      turn 90 degrees clockwise if v is true, false,
                                equal to D or unequal to D
    ``STORE [v] [TO x]``        v (or D) into x (or D)
    ``INPUT [type] [TO] [x]``   a line of stdin, or the next call argument
    ``NEXT|PREVIOUS VALUE|ROW``, ``HOME``  move the data tracer, wrapping
    ``PRINT [v|NEWLINE]``       print v (or D) as a string
    ``PUSH [v]``, ``REMOVE [i|THIS POSITION|TOP] [TO [type] x]``, ``PEEK``
    ``INCREMENT|DECREMENT [x] [BY v] [GIVING y]``, ``MULTIPLY|DIVIDE [x] BY v
    [GIVING y]``                arithmetic on x (or D), into y (or in place)
    ``SPLIT v [OVER s]``        push v's pieces, split on s or whitespace
    ``CALL NAME [WITH ARGUMENTS v...] [GIVING x]``, ``RETURN [v]``, ``WARN m``

Input/output:
    Each main-program INPUT reads one line; EOF gives NULL.  PRINT writes no
    separator.  A subroutine has its own variables, dataspace and buffer; its
    INPUTs take the call's arguments in order.

Errors:
    ProgramError: malformed source or metadata, a missing or repeated START,
    a node outside the program space, RETURN in the main program, an unknown
    subroutine, or a construct no example exercises (see Decisions); raised
    as ValueError.
    HaltError: a value that cannot be cast for arithmetic or a direction,
    division by zero, a 32-bit INT overflow, a subroutine INPUT past its
    arguments, equidistant GOTO targets, or more moves than ``@steps``.

Decisions:
    * A node holds the tracer only strictly inside its radius: under
      "distance <= radius" the 99 Bottles example's tracer, turned north at
      x=6, re-enters the DECREMENT column and prints the wrong song.
    * INPUT's ``TO`` is optional: the page writes ``INPUT STRING s`` and
      ``INPUT INT TO n``.  ``STORE TO a`` stores D (Fibonacci example).
    * PREVIOUS VALUE moves left; the page's "one position right" contradicts
      its own wrapping "to the end of previous row".
    * INT arithmetic stays INT, DIVIDE truncating toward zero as when a FLOAT
      becomes an INT; anything involving a FLOAT is rounded to 32 bits.  An
      INT result outside 32 bits raises rather than wrapping.
    * ``=v`` compares v, cast to a number, with D; an uncastable v is unequal.
    * A string casts to a number when it is a decimal numeral; to an INT it
      truncates.  A value stored in the dataspace that cannot be cast stores
      0, as REMOVE specifies.
    * SPLIT pushes its pieces first to last, so the first lands nearest the
      bottom; an all-whitespace string pushes one empty piece ("one or
      more substrings").
    * Warnings go to the debug console, which this headless interpreter
      never shows: WARN and failed casts are silent.
    * A FLOAT prints as the shortest decimal that rounds back to it, with a
      ``.0`` when whole; BOOLs print TRUE or FALSE; NULL prints nothing.
    * Raised as never exercised or not defined: RANDOM in any command,
      SHUFFLE, REMOVE ANY POSITION, files and images, INPUT WITH PROMPT,
      MOVE LAST NODE, THE VARIABLE NAMED, and THROW, which the page lists
      without a description.
"""

import math
import re
import struct
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.gridscript.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

_NODE = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)\s*:(.*)")
_TOKEN = re.compile(r"\s*('[^']*'|\"[^\"]*\"|\S+)")
_NAME = re.compile(r"[a-z_][a-z0-9_]*")
_INT = re.compile(r"[+-]?\d+")
_FLOAT = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")
_TYPES = frozenset({"INT", "FLOAT", "STRING", "BOOL"})
_HEADINGS = {"EAST": 0, "SOUTH": 90, "WEST": 180, "NORTH": 270}
_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
_META = frozenset(
    {"width", "height", "datawidth", "dataheight", "radius", "steps", "debug"}
)
_DEFAULTS = {"datawidth": 64, "dataheight": 64, "radius": 1}


class _Null:
    """GridScript's NULL: unassigned, end of input, a failed cast."""

    def __repr__(self) -> str:
        return "NULL"


NULL = _Null()


class _Float(NamedTuple):
    """A 32-bit FLOAT, kept apart from INT."""

    value: float


type _Value = int | _Float | str | bool | _Null


class _Var(NamedTuple):
    """A variable reference inside a parsed command."""

    name: str


type _Arg = _Value | _Var | None


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


def _f16(value: float) -> float:
    return float(struct.unpack("e", struct.pack("e", value))[0])


def _f32(value: float) -> float:
    try:
        return float(struct.unpack("f", struct.pack("f", value))[0])
    except OverflowError:
        return math.copysign(math.inf, value)


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


def _int(value: int) -> int:
    if not _INT_MIN <= value <= _INT_MAX:
        raise HaltError(f"{format_integer(value)} overflows a 32-bit INT")
    return value


def _number(value: _Value) -> int | _Float | None:
    """Cast to INT or FLOAT, or None when the value cannot be cast."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, _Float)):
        return value
    if isinstance(value, _Null):
        return 0
    text = value.strip()
    if not text:
        return 0
    if _INT.fullmatch(text):
        number = parse_integer(text)
        return number if _INT_MIN <= number <= _INT_MAX else None
    if _FLOAT.fullmatch(text):
        return _Float(_f32(float(text)))
    return None


def _to_int(value: _Value) -> int | None:
    number = _number(value)
    if number is None:
        return None
    if isinstance(number, _Float):
        if not math.isfinite(number.value):
            return None
        number = math.trunc(number.value)
        return number if _INT_MIN <= number <= _INT_MAX else None
    return number


def _to_bool(value: _Value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, _Null):
        return False
    if isinstance(value, str):
        return value not in ("", "0")
    if isinstance(value, _Float):
        return value.value != 0
    return value != 0


def _show_float(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    for digits in range(1, 10):
        text = f"{value:.{digits}g}"
        if _f32(float(text)) == value:
            break
    if "e" not in text and "." not in text:
        text += ".0"
    return text


def _to_str(value: _Value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, _Null):
        return ""
    if isinstance(value, _Float):
        return _show_float(value.value)
    return str(value)


def _cast(value: _Value, typ: str) -> _Value:
    """Cast to a named type; NULL when it cannot be (a silent warning)."""
    if typ == "STRING":
        return _to_str(value)
    if typ == "BOOL":
        return _to_bool(value)
    if typ == "INT":
        got = _to_int(value)
        return NULL if got is None else got
    number = _number(value)
    if number is None:
        return NULL
    return number if isinstance(number, _Float) else _Float(_f32(float(number)))


def _arith(verb: str, a: _Value, b: _Value) -> int | _Float:
    x, y = _number(a), _number(b)
    if x is None or y is None:
        raise HaltError(f"{verb} needs numbers, got {a!r} and {b!r}")
    if isinstance(x, int) and isinstance(y, int):
        if verb == "INCREMENT":
            return _int(x + y)
        if verb == "DECREMENT":
            return _int(x - y)
        if verb == "MULTIPLY":
            return _int(x * y)
        if y == 0:
            raise HaltError("DIVIDE by zero")
        q = abs(x) // abs(y)
        return _int(q if (x < 0) == (y < 0) else -q)
    fx = x.value if isinstance(x, _Float) else float(x)
    fy = y.value if isinstance(y, _Float) else float(y)
    if verb == "INCREMENT":
        return _Float(_f32(fx + fy))
    if verb == "DECREMENT":
        return _Float(_f32(fx - fy))
    if verb == "MULTIPLY":
        return _Float(_f32(fx * fy))
    if fy == 0:
        raise HaltError("DIVIDE by zero")
    return _Float(_f32(fx / fy))


# --- parsing ----------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    out, pos, end = [], 0, len(text.rstrip())
    while pos < end:
        m = _TOKEN.match(text, pos)
        assert m is not None
        out.append(m.group(1))
        pos = m.end()
    return out


def _var(tok: str, text: str) -> str:
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
    if "WITH" in rest:
        raise _unsupported("INPUT WITH PROMPT")
    typ = rest.pop(0) if rest and rest[0] in _TYPES else None
    if rest and rest[0] == "TO":
        rest = rest[1:]
    if len(rest) > 1:
        return None
    return _Cmd("INPUT", (typ, _var(rest[0], text) if rest else None))


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
        raise _unsupported("dynamic variable naming")
    verb, rest = toks[0], toks[1:]
    if verb in ("LOAD", "MOVE", "THROW"):
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
            )
        )
    names = {body.name for body in bodies[1:]}
    for body in bodies:
        for x, y, cmd in body.nodes:
            if cmd.verb == "CALL" and cmd.args[0] not in names:
                raise _bad_node(x, y, f"no subroutine named {cmd.args[0]}")
    return tuple(bodies)


# --- the transition -----------------------------------------------------------


@dataclass
class _Frame:
    """One running program or subroutine instance."""

    body: int
    x: float
    y: float
    heading: int
    width: int
    height: int
    datawidth: int
    dataheight: int
    radius: int
    inside: frozenset[int] = frozenset()
    moved: bool = False
    pending: deque[int] = field(default_factory=deque)
    variables: dict[str, _Value] = field(default_factory=dict)
    data: dict[tuple[int, int], int] = field(default_factory=dict)
    cursor: tuple[int, int] = (0, 0)
    buffer: deque[_Value] = field(default_factory=deque)
    args: deque[_Value] | None = None
    giving: tuple[str | None] | None = None  # the caller's target, once called


class _Effect(NamedTuple):
    """One command's result for the shell to apply."""

    sets: tuple[tuple[str, _Value], ...] = ()  # variable writes
    cell: int | None = None  # new value of D
    cursor: tuple[int, int] | None = None
    heading: int | None = None
    teleport: tuple[int, int] | None = None
    take: object = None  # a buffer index removed, before pushes
    pushes: tuple[_Value, ...] = ()
    out: str = ""
    call: tuple[str, tuple[_Value, ...], str | None] | None = None
    ret: tuple[_Value] | None = None  # RETURN's value
    arg_used: bool = False


def _value(arg: _Arg, variables: Mapping[str, _Value], cell: int) -> _Value:
    if arg is None:
        return cell
    if isinstance(arg, _Var):
        return variables.get(arg.name, NULL)
    return arg


def _cell_value(value: _Value) -> int:
    got = _to_int(value)
    return 0 if got is None else got


class _View(NamedTuple):
    """What a command may read: the frame's state and INPUT's value."""

    variables: Mapping[str, _Value]
    cell: int
    cursor: tuple[int, int]
    dims: tuple[int, int]
    heading: int
    position: tuple[float, float]
    buffer: tuple[_Value, ...] | deque[_Value]
    checkpoints: tuple[tuple[int, int, int], ...]
    read: _Value | None

    def val(self, arg: object) -> _Value:
        return _value(arg, self.variables, self.cell)  # type: ignore[arg-type]


def _store_to(target: object, value: _Value, *, arg_used: bool = False) -> _Effect:
    if target is None:
        return _Effect(cell=_cell_value(value), arg_used=arg_used)
    return _Effect(sets=((target, value),), arg_used=arg_used)  # type: ignore[arg-type]


def _do_go(args: tuple[object, ...], v: _View) -> _Effect:
    relative, target = args
    amount = v.cell if target is None else _to_int(v.val(target))
    if amount is None:
        raise HaltError(f"GO needs a number, got {v.val(target)!r}")
    return _Effect(heading=((v.heading if relative else 0) + amount) % 360)


def _do_goto(args: tuple[object, ...], v: _View) -> _Effect:
    wanted = v.cell if args[0] is None else _to_int(v.val(args[0]))
    found = [(x, y) for i, x, y in v.checkpoints if i == wanted]
    if not found:
        return _Effect()  # a warning
    px, py = v.position
    dist = sorted(((x - px) ** 2 + (y - py) ** 2, (x, y)) for x, y in found)
    if len(dist) > 1 and dist[0][0] == dist[1][0]:
        raise HaltError("GOTO picks randomly among equidistant checkpoints")
    return _Effect(teleport=dist[0][1])


def _do_switch(args: tuple[object, ...], v: _View) -> _Effect:
    mode, arg = args
    value = v.val(arg)
    if mode == "":
        turn = _to_bool(value)
    elif mode == "!":
        turn = not _to_bool(value)
    else:
        number = _number(value)
        equal = number is not None and float(v.cell) == (
            number.value if isinstance(number, _Float) else number
        )
        turn = equal == (mode == "=")
    return _Effect(heading=(v.heading + 90) % 360) if turn else _Effect()


def _do_input(args: tuple[object, ...], v: _View) -> _Effect:
    typ, target = args
    assert v.read is not None
    value = v.read if typ is None else _cast(v.read, typ)  # type: ignore[arg-type]
    return _store_to(target, value, arg_used=True)


def _do_peek(_args: tuple[object, ...], v: _View) -> _Effect:
    got = _to_int(v.buffer[0]) if v.buffer else None
    return _Effect() if got is None else _Effect(cell=got)


def _do_arith(verb: str) -> Any:
    def run(args: tuple[object, ...], v: _View) -> _Effect:
        source, by, giving = args
        start = v.cell if source is None else v.variables.get(source, NULL)  # type: ignore[call-overload]
        result = _arith(verb, start, v.val(by))
        return _store_to(giving if giving is not None else source, result)

    return run


def _do_split(args: tuple[object, ...], v: _View) -> _Effect:
    text = _to_str(v.val(args[0]))
    if args[1] is None:
        return _Effect(pushes=tuple(text.split() or [""]))
    sep = _to_str(v.val(args[1]))
    if not sep:
        raise HaltError("SPLIT OVER an empty separator")
    return _Effect(pushes=tuple(text.split(sep)))


def _do_call(args: tuple[object, ...], v: _View) -> _Effect:
    name, call_args, giving = args
    values = tuple(v.val(a) for a in call_args)  # type: ignore[attr-defined]
    return _Effect(call=(name, values, giving))  # type: ignore[arg-type]


def _do_cursor(verb: str) -> Any:
    return lambda _a, v: _Effect(cursor=_move_cursor(verb, v.cursor, v.dims))


_DO: dict[str, Any] = {
    "START": lambda _a, _v: _Effect(),
    "CHECKPOINT": lambda _a, _v: _Effect(),
    "WARN": lambda _a, _v: _Effect(),
    "GO": _do_go,
    "GOTO": _do_goto,
    "SWITCH": _do_switch,
    "STORE": lambda args, v: _store_to(args[1], v.val(args[0])),
    "INPUT": _do_input,
    "PRINT NEWLINE": lambda _a, _v: _Effect(out="\n"),
    "PRINT": lambda args, v: _Effect(out=_to_str(v.val(args[0]))),
    "PUSH": lambda args, v: _Effect(pushes=(v.val(args[0]),)),
    "REMOVE": lambda args, v: _remove_effect(args, v.buffer, v.cell, v.val),
    "PEEK": _do_peek,
    "SPLIT": _do_split,
    "CALL": _do_call,
    "RETURN": lambda args, v: _Effect(ret=(v.val(args[0]),)),
}
_DO.update(
    {verb: _do_arith(verb) for verb in ("INCREMENT", "DECREMENT", "MULTIPLY", "DIVIDE")}
)
_DO.update(
    {
        verb: _do_cursor(verb)
        for verb in ("NEXT VALUE", "PREVIOUS VALUE", "NEXT ROW", "PREVIOUS ROW", "HOME")
    }
)


def _advance(
    cmd: _Cmd,
    variables: Mapping[str, _Value],
    cell: int,
    cursor: tuple[int, int],
    dims: tuple[int, int],
    heading: int,
    position: tuple[float, float],
    buffer: tuple[_Value, ...] | deque[_Value],
    checkpoints: tuple[tuple[int, int, int], ...],
    read: _Value | None = None,
) -> _Effect:
    """Return the effect of one command.  Pure: ``read`` is INPUT's value."""
    view = _View(
        variables, cell, cursor, dims, heading, position, buffer, checkpoints, read
    )
    effect: _Effect = _DO[cmd.verb](cmd.args, view)
    return effect


def _move_cursor(
    verb: str, cursor: tuple[int, int], dims: tuple[int, int]
) -> tuple[int, int]:
    (cx, cy), (w, h) = cursor, dims
    if verb == "HOME":
        return 0, 0
    if verb == "NEXT VALUE":
        return (cx + 1, cy) if cx + 1 < w else (0, (cy + 1) % h)
    if verb == "PREVIOUS VALUE":
        return (cx - 1, cy) if cx > 0 else (w - 1, (cy - 1) % h)
    if verb == "NEXT ROW":
        return 0, (cy + 1) % h
    return 0, (cy - 1) % h


def _remove_effect(
    args: tuple[object, ...],
    buffer: tuple[_Value, ...] | deque[_Value],
    cell: int,
    val: Any,
) -> _Effect:
    where, typ, target = args
    if where == "this":
        index: int | None = cell
    elif where == "top":
        index = len(buffer) - 1
    else:
        index = _to_int(val(where))
    if index is None or not 0 <= index < len(buffer):
        value: _Value = NULL  # a warning
        take = None
    else:
        value, take = buffer[index], index
    if isinstance(typ, str):
        value = _cast(value, typ)
    if not isinstance(target, str):
        return _Effect(cell=_cell_value(value), take=take)
    return _Effect(sets=((target, value),), take=take)


def _advance_move(
    position: tuple[float, float],
    heading: int,
    radius: int,
    cells: Mapping[tuple[int, int], tuple[int, ...]],
) -> tuple[tuple[float, float], frozenset[int]]:
    """Move one unit along ``heading``; return the position and nodes held."""
    x, y = position
    if heading % 90 == 0:
        dx, dy = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[heading // 90]
    else:
        angle = math.radians(heading)
        dx, dy = math.cos(angle), math.sin(angle)
    x, y = _f16(x + dx), _f16(y + dy)
    held: list[int] = []
    for cx in range(math.floor(x - radius) + 1, math.ceil(x + radius)):
        for cy in range(math.floor(y - radius) + 1, math.ceil(y + radius)):
            if (cx - x) ** 2 + (cy - y) ** 2 < radius * radius:
                held.extend(cells.get((cx, cy), ()))
    return (x, y), frozenset(held)


_WORKSPACE_MODEL = WorkspaceModel(
    "gridscript-v1", ("frames", "variables", "dataspace", "buffer", "input_cursor")
)


class _Machine:
    """A GridScript run: a stack of program and subroutine frames."""

    def __init__(self, code: str | tuple[_Body, ...], io: IO) -> None:
        self.bodies = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.frames = [self._frame(0, None)]
        self.halted = False
        self.moves = 0
        self.steps = dict(self.bodies[0].meta).get("steps")
        self._writer = _BufferedOutput()

    def _frame(self, body: int, args: deque[_Value] | None) -> _Frame:
        b = self.bodies[body]
        meta = dict(b.meta)
        x, y = b.start
        return _Frame(
            body,
            float(x),
            float(y),
            0,
            meta["width"],
            meta["height"],
            meta["datawidth"],
            meta["dataheight"],
            meta["radius"],
            args=args,
        )

    @property
    def ip(self) -> tuple[int, int, int, int, int] | None:
        """Return the body and the tracer coordinates as exact integer ratios."""
        if not self.frames:
            return None
        f = self.frames[-1]
        return (f.body, *f.x.as_integer_ratio(), *f.y.as_integer_ratio())

    def _state(self) -> tuple[object, ...]:
        return tuple(
            (
                f.body,
                f.x,
                f.y,
                f.heading,
                f.inside,
                f.moved,
                tuple(f.pending),
                tuple(sorted(f.variables.items(), key=lambda kv: kv[0])),
                tuple(sorted(f.data.items())),
                f.cursor,
                tuple(f.buffer),
                None if f.args is None else tuple(f.args),
                f.giving,
            )
            for f in self.frames
        )

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        accepted = self._writer.accepted
        frames = tuple(
            (f.body, f.x, f.y, f.heading, f.inside, f.moved, tuple(f.pending), f.cursor)
            for f in self.frames
        )
        return _WORKSPACE_MODEL.capture(
            frames=(
                WorkspaceVariant("pending_output", (frames, accepted))
                if accepted
                else frames
            ),
            variables=tuple(frozenset(f.variables.items()) for f in self.frames),
            dataspace=tuple(frozenset(f.data.items()) for f in self.frames),
            buffer=tuple(tuple(f.buffer) for f in self.frames),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = (self.halted, self._state(), self.moves, self.io.progress())
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def _read(self, frame: _Frame) -> _Value:
        if frame.args is not None:
            if not frame.args:
                raise HaltError("a subroutine INPUT has no argument left")
            return frame.args[0]
        try:
            return self.io.input_str().removesuffix("\r")
        except EOFError:
            return NULL

    def step(self) -> None:
        """Run one pending command, or move the tracer one unit."""
        if self.halted:
            return
        frame = self.frames[-1]
        if not frame.pending:
            self._move(frame)
            return
        body = self.bodies[frame.body]
        cmd = body.nodes[frame.pending[0]][2]
        read = self._read(frame) if cmd.verb == "INPUT" else None
        effect = _advance(
            cmd,
            frame.variables,
            frame.data.get(frame.cursor, 0),
            frame.cursor,
            (frame.datawidth, frame.dataheight),
            frame.heading,
            (frame.x, frame.y),
            frame.buffer,
            body.checkpoints,
            read,
        )
        self._apply(frame, effect)
        frame.pending.popleft()

    def _move(self, frame: _Frame) -> None:
        if self.steps is not None and self.moves >= self.steps:
            raise HaltError(f"more than @steps {format_integer(self.steps)} moves")
        body = self.bodies[frame.body]
        (x, y), held = _advance_move(
            (frame.x, frame.y), frame.heading, frame.radius, body.cells
        )
        self.moves += 1
        frame.x, frame.y = x, y
        if not (1 <= x <= frame.width and 1 <= y <= frame.height):
            self._finish(None)
            return
        new = held if not frame.moved else held - frame.inside
        frame.inside, frame.moved = held, True
        frame.pending.extend(sorted(new))

    def _finish(self, value: tuple[_Value] | None) -> None:
        """End the top frame: halt the program or return to the caller."""
        done = self.frames.pop()
        if not self.frames:
            self.halted = True
            return
        caller = self.frames[-1]
        assert done.giving is not None
        (target,) = done.giving
        if target is not None:
            caller.variables[target] = NULL if value is None else value[0]
        elif value is not None:
            caller.data[caller.cursor] = _cell_value(value[0])

    def _apply(self, frame: _Frame, effect: _Effect) -> None:
        for name, value in effect.sets:
            frame.variables[name] = value
        if effect.cell is not None:
            if effect.cell:
                frame.data[frame.cursor] = effect.cell
            else:
                frame.data.pop(frame.cursor, None)
        if effect.cursor is not None:
            frame.cursor = effect.cursor
        if effect.heading is not None:
            frame.heading = effect.heading
        if effect.teleport is not None:
            frame.x, frame.y = map(float, effect.teleport)
        if isinstance(effect.take, int):
            del frame.buffer[effect.take]
        frame.buffer.extend(effect.pushes)
        if effect.out:
            self._writer.write(self.io, effect.out)
        if effect.arg_used and frame.args is not None:
            frame.args.popleft()
        if effect.call is not None:
            name, values, giving = effect.call
            index = next(i for i, b in enumerate(self.bodies) if b.name == name and i)
            callee = self._frame(index, deque(values))
            callee.giving = (giving,)
            self.frames.append(callee)
        if effect.ret is not None:
            self._finish(effect.ret)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("GridScript machines require text source")
    if options:
        raise TypeError("GridScript machines accept no runtime options")
    bodies = _parse(source)
    return RuntimePlan(lambda io: _Machine(bodies, io), lambda io: _execute(bodies, io))


def _execute(code: str | tuple[_Body, ...], io: IO) -> CompletionReport:
    """Run a GridScript program until its tracer leaves the program space."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a GridScript program until its tracer leaves the program space."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
