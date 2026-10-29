r"""Interpreter for HQ9+ with headers.

A source is one header block, then the program.  The header's sections
give each program character a list of semantic commands, a startup list,
a checksum, and the command flow: a permutation of the program's command
numbers, from 1, interleaved with jumps.  Startup runs first, then the
flow left to right; the run halts past its end or at ``'H``.  One step is
one semantic command or one flow jump.  The wiki's HQ9+ example prints
``Hello, World!QHQQHQ``; its infinite loop and truth machine run as
stated.

Commands:
    ``p()`` nothing; ``p("S")`` S with ``@XX`` hex byte escapes;
    ``p(Vv)`` v in decimal; ``p({{CODE}})`` the program;
    ``p({{99BOB}})`` the song; ``v++``; ``v = n``; ``placeholders = S``
    nothing; ``[ADD v u w]`` and ``SUB``, ``MUL``, ``DIV`` set w to v op
    u; ``[~:: v u h i]`` runs the hex-encoded command h if v > u, else i;
    ``[>>, v]`` reads a character's code; ``[>>. v]`` a decimal.  Flow:
    ``'JZv#n`` jumps to command n if v is 0; ``'J_n`` jumps; ``'H``
    halts; ``'Fv#n`` jumps to n; ``/...`` is a comment.

Input/output:
    ``[>>, v]`` reads one character, 0 at EOF; ``[>>. v]`` appends digits
    to an assumed 0 up to the first non-digit, which it consumes, or EOF.
    Output is the printed text.

Errors:
    ProgramError: No leading ``==== HEADER ====``, a missing end marker or
        a second header; indentation not a multiple of 4 or deeper than
        its section allows; an unknown, missing or repeated section or
        subsection; a subsection name longer than one character; a
        malformed semantic command or flow element; a flow that is not a
        permutation of the commands; a jump past the last command; a
        program character with no semantics; a wrong checksum.
    HaltError: Reading a variable never set; ``DIV`` by 0.

Decisions:
    * "Instruction n" is command n, wherever the flow lists it: the truth
      machine's ``'JZtruth#3`` must reach command 3 at flow position 5.
    * ``'F`` always takes the spec's can't-fork branch: v keeps its value
      and the flow jumps to n.  A fork would make output order a race.
    * One header block: a second one has no stated meaning.
    * ``{{CODE}}`` prints the program without line breaks, the text the
      checksum sums.
    * ``{{99BOB}}`` is implementation-defined; it prints HQ9+'s ``9``.
    * Integers are unbounded; ``DIV`` floors.  The page gives no width.
    * A ``\`` continuation appends the next raw line, spaces included.
    * A command in ``CHARACTER SEMANTICS`` may be empty and does nothing.
    * Extension sections and flow elements (a leading ``"``) are accepted
      as sections and refused in the flow, where no semantics exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.languages.hq9.interpreter import _SONG
from esolangs.runtime import persistent
from esolangs.runtime._digits import digit_limit_for
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_BEGIN = "==== HEADER ===="
_END = "==== END HEADER ===="
_REQUIRED = ("COMMAND FLOW", "CHARACTER SEMANTICS", "STARTUP", "CHECKSUM")
_VAR = r"([a-z]+)"
_HEX = r"((?:[0-9A-F]{2})+)"
_SEMANTICS = [
    ("nop", re.compile(r"p\(\)|placeholders\s*=.*")),
    ("text", re.compile(r'p\("((?:[^"@]|@[0-9A-F]{2})*)"\)')),
    ("var", re.compile(rf"p\(V{_VAR}\)")),
    ("code", re.compile(r"p\(\{\{CODE\}\}\)")),
    ("song", re.compile(r"p\(\{\{99BOB\}\}\)")),
    ("inc", re.compile(rf"{_VAR}\+\+")),
    ("set", re.compile(rf"{_VAR}\s*=\s*([0-9]+)")),
    ("arith", re.compile(rf"\[(ADD|SUB|MUL|DIV) +{_VAR} +{_VAR} +{_VAR}\]")),
    ("gt", re.compile(rf"\[~:: +{_VAR} +{_VAR} +{_HEX} +{_HEX}\]")),
    ("readc", re.compile(rf"\[>>, +{_VAR}\]")),
    ("readn", re.compile(rf"\[>>\. +{_VAR}\]")),
]
_FLOW = [
    ("jz", re.compile(rf"'JZ{_VAR}#([0-9]+)")),
    ("jump", re.compile(r"'J_([0-9]+)")),
    ("halt", re.compile(r"'H")),
    ("fork", re.compile(rf"'F{_VAR}#([0-9]+)")),
]

#: ``(op index, variable values)``; an unset variable holds ``None``.
type _State = tuple[int, persistent.Chunked[int | None]]


@dataclass(frozen=True, slots=True)
class _Op:
    """One step.  ``args`` are variable slots; ``target`` an op index."""

    kind: str
    line: int
    args: tuple[int, ...] = ()
    text: str = ""
    value: int = 0
    target: int = 0


@dataclass(frozen=True, slots=True)
class _Node:
    """A header line and the lines indented under it."""

    text: str
    line: int
    children: tuple[_Node, ...]


#: A header line under construction: line number, text, lines under it.
type _Raw = tuple[int, str, list[_Raw]]


def _fail(line: int, message: str) -> ValueError:
    return ValueError(f"HQ9+ with headers: line {line + 1}: {message}")


def _match(
    patterns: list[tuple[str, re.Pattern[str]]], text: str, line: int, what: str
) -> tuple[str, tuple[str, ...]]:
    """The first pattern ``text`` matches whole: its kind and groups."""
    for kind, pattern in patterns:
        match = pattern.fullmatch(text)
        if match:
            return kind, tuple(g or "" for g in match.groups())
    raise _fail(line, f"unknown {what} {text!r}")


def _header_lines(lines: list[str]) -> list[tuple[int, str]]:
    r"""Join ``\`` continuations and drop blank lines; keep line numbers."""
    out: list[tuple[int, str]] = []
    k = 0
    while k < len(lines):
        start, text = k, lines[k].rstrip(" ")
        while text.endswith("\\"):
            k += 1
            if k == len(lines):
                raise _fail(start, "a continuation runs past the header")
            text = text[:-1] + lines[k].rstrip(" ")
        if text:
            out.append((start + 1, text))
        k += 1
    return out


def _tree(lines: list[tuple[int, str]]) -> list[_Node]:
    """Nest the header lines by their 4-space indentation."""
    roots: list[_Raw] = []
    stack: list[_Raw] = []
    for line, text in lines:
        body = text.lstrip(" ")
        indent = len(text) - len(body)
        if indent % 4 or indent // 4 > len(stack):
            raise _fail(line, "indentation is not one more multiple of 4")
        del stack[indent // 4 :]
        node: _Raw = (line, body, [])
        (stack[-1][2] if stack else roots).append(node)
        stack.append(node)

    def freeze(node: _Raw) -> _Node:
        return _Node(node[1], node[0], tuple(freeze(c) for c in node[2]))

    return [freeze(r) for r in roots]


def _leaves(node: _Node) -> tuple[_Node, ...]:
    """The section's lines, which must not have lines under them."""
    for child in node.children:
        if child.children:
            raise _fail(child.children[0].line, f"too deep inside {node.text}")
    return node.children


def _split(code: str) -> tuple[list[_Node], list[str]]:
    """The header tree and the program lines."""
    lines = code.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].rstrip(" \t") != _BEGIN:
        raise _fail(0, f"the source must start with {_BEGIN!r}")
    ends = [k for k, text in enumerate(lines) if text.rstrip(" \t") == _END]
    if not ends:
        raise _fail(0, f"no {_END!r}")
    end = ends[0]
    program = lines[end + 1 :]
    if any(text.rstrip(" \t") in (_BEGIN, _END) for text in program):
        raise _fail(end + 1, "only one header block is supported")
    return _tree(_header_lines(lines[1:end])), program


class _Compiler:
    """Lays semantic commands and the flow out as one flat op list."""

    def __init__(self, program: str) -> None:
        self.program = program
        self.ops: list[_Op] = []
        self.slots: dict[str, int] = {}

    def slot(self, name: str, line: int) -> int:
        if name == "placeholders":
            raise _fail(line, "'placeholders' is not a variable")
        return self.slots.setdefault(name, len(self.slots))

    def emit(self, text: str, line: int) -> None:
        """Append ``text``'s ops; a ``[~::]`` inlines both branches."""
        kind, groups = _match(_SEMANTICS, text, line, "semantic command")
        if kind == "text":
            decoded = re.sub(r"@([0-9A-F]{2})", lambda m: chr(int(m[1], 16)), groups[0])
            self.ops.append(_Op("text", line, text=decoded))
        elif kind in ("code", "song"):
            body = self.program if kind == "code" else _SONG
            self.ops.append(_Op("text", line, text=body))
        elif kind == "set":
            with digit_limit_for(len(groups[1])):
                value = int(groups[1])
            self.ops.append(
                _Op("set", line, (self.slot(groups[0], line),), value=value)
            )
        elif kind == "arith":
            names = groups[1:]
            args = tuple(self.slot(name, line) for name in names)
            self.ops.append(_Op("arith", line, args, text=groups[0]))
        elif kind == "gt":
            self._branch(groups, line)
        elif kind == "nop":
            self.ops.append(_Op("nop", line))
        else:
            self.ops.append(_Op(kind, line, (self.slot(groups[0], line),)))

    def _branch(self, groups: tuple[str, ...], line: int) -> None:
        v, u, then, other = groups
        test = len(self.ops)
        self.ops.append(_Op("gt", line, (self.slot(v, line), self.slot(u, line))))
        self.emit(bytes.fromhex(then).decode("latin-1"), line)
        skip = len(self.ops)
        self.ops.append(_Op("jump", line))
        self.ops[test] = replace(self.ops[test], target=len(self.ops))
        self.emit(bytes.fromhex(other).decode("latin-1"), line)
        self.ops[skip] = replace(self.ops[skip], target=len(self.ops))


def _sections(roots: list[_Node]) -> dict[str, _Node]:
    sections: dict[str, _Node] = {}
    for node in roots:
        if node.text.startswith('"'):
            continue
        if node.text not in _REQUIRED or node.text in sections:
            raise _fail(node.line, f"unknown or repeated section {node.text!r}")
        sections[node.text] = node
    for name in _REQUIRED:
        if name not in sections:
            raise _fail(0, f"missing section {name!r}")
    return sections


def _semantics(node: _Node) -> dict[str, tuple[_Node, ...]]:
    commands: dict[str, tuple[_Node, ...]] = {}
    for sub in node.children:
        if len(sub.text) != 1 or sub.text in commands:
            raise _fail(sub.line, f"bad or repeated command name {sub.text!r}")
        commands[sub.text] = _leaves(sub)
    return commands


def _flow_elements(node: _Node) -> tuple[list[str], int]:
    leaves = _leaves(node)
    text = "".join(leaf.text for leaf in leaves)
    line = leaves[0].line if leaves else node.line
    if not text:
        return [], line
    return [part.strip(" ") for part in text.split(",")], line


def parse(code: str) -> tuple[list[_Op], int]:
    """Return the ops and the variable count; malformed sources raise."""
    roots, program_lines = _split(code)
    sections = _sections(roots)
    program = "".join(program_lines)
    checksum = _leaves(sections["CHECKSUM"])
    want = sum(map(ord, program)) % 1024 + 43
    if len(checksum) != 1 or checksum[0].text != str(want):
        raise _fail(sections["CHECKSUM"].line, f"the checksum must be {want}")
    commands = _semantics(sections["CHARACTER SEMANTICS"])
    for at, char in enumerate(program):
        if char not in commands:
            raise _fail(0, f"program character {at} ({char!r}) has no semantics")
    scratch = _Compiler(program)
    for body in commands.values():  # an unused command must parse too
        for leaf in body:
            scratch.emit(leaf.text, leaf.line)
    compiler = _Compiler(program)
    for leaf in _leaves(sections["STARTUP"]):
        compiler.emit(leaf.text, leaf.line)
    elements, line = _flow_elements(sections["COMMAND FLOW"])
    starts: dict[int, int] = {}
    jumps: list[tuple[int, int]] = []
    for element in elements:
        if element.isdigit():
            number = int(element)
            if not 1 <= number <= len(program) or number in starts:
                raise _fail(line, f"flow element {element} is not a new command")
            starts[number] = len(compiler.ops)
            for leaf in commands[program[number - 1]]:
                compiler.emit(leaf.text, leaf.line)
            continue
        if element.startswith("/"):
            continue
        kind, groups = _match(_FLOW, element, line, "flow element")
        args = (compiler.slot(groups[0], line),) if kind in ("jz", "fork") else ()
        if kind != "halt":
            jumps.append((len(compiler.ops), int(groups[-1])))
        compiler.ops.append(_Op("jump" if kind == "fork" else kind, line, args))
    if len(starts) != len(program):
        raise _fail(line, "the flow must list every command exactly once")
    ops = compiler.ops
    for at, number in jumps:
        if number not in starts:
            raise _fail(ops[at].line, f"no command {number} to jump to")
        ops[at] = replace(ops[at], target=starts[number])
    return ops, len(compiler.slots)


def _get(store: persistent.Chunked[int | None], slot: int) -> int:
    value = persistent.get(store, slot)
    if value is None:
        raise HaltError("HQ9+ with headers: a variable was read before being set")
    return value


def _advance(
    state: _State, ops: list[_Op], value: int | None = None
) -> tuple[_State, int | str | None]:
    """Return the state after one op, and what it prints.

    Pure: a read arrives as ``value``.  A printed ``int`` is a decimal.
    """
    ip, store = state
    op = ops[ip]
    kind = op.kind
    nxt = ip + 1
    out: int | str | None = None
    if kind == "text":
        out = op.text
    elif kind == "var":
        out = _get(store, op.args[0])
    elif kind == "inc":
        store = persistent.put(store, op.args[0], _get(store, op.args[0]) + 1)
    elif kind == "set":
        store = persistent.put(store, op.args[0], op.value)
    elif kind in ("readc", "readn"):
        store = persistent.put(store, op.args[0], value)
    elif kind == "arith":
        x, y = _get(store, op.args[0]), _get(store, op.args[1])
        if op.text == "DIV" and y == 0:
            raise HaltError("HQ9+ with headers: DIV by 0")
        result = {
            "ADD": x + y,
            "SUB": x - y,
            "MUL": x * y,
            "DIV": x // y if y else 0,
        }[op.text]
        store = persistent.put(store, op.args[2], result)
    elif kind == "gt":
        if not _get(store, op.args[0]) > _get(store, op.args[1]):
            nxt = op.target
    elif kind == "jz":
        if _get(store, op.args[0]) == 0:
            nxt = op.target
    elif kind == "jump":
        nxt = op.target
    elif kind == "halt":
        nxt = len(ops)
    return (nxt, store), out


class _Machine:
    """The run state: op index and variable values."""

    eof_is_a_value = True
    ip_shape = "line"

    def __init__(self, code: str, io: IO) -> None:
        self.ops, count = parse(code)
        self.io = io
        self.state: _State = (0, persistent.chunked([None] * count))

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    @property
    def ip(self) -> tuple[int]:
        """The next op's source line, from 0; -1 once halted."""
        return (self.ops[self.state[0]].line if not self.halted else -1,)

    @property
    def memory(self) -> list[int]:
        """The variables in first-use order, unset ones as 0."""
        return [v or 0 for v in persistent.flatten(self.state[1])]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def _read(self, kind: str) -> int:
        """Serve ``[>>, v]`` (0 at EOF) or ``[>>. v]`` (digits to a non-digit)."""
        if kind == "readc":
            try:
                return self.io.input_char()
            except EOFError:
                return 0
        digits = "0"
        while True:
            try:
                char = self.io.input_char()
            except EOFError:
                break
            if not 48 <= char <= 57:
                break
            digits += chr(char)
        with digit_limit_for(len(digits)):
            return int(digits)

    def step(self) -> None:
        """Execute one op.

        The shell: the two ports live here and nothing else does.
        """
        if self.halted:
            return
        kind = self.ops[self.state[0]].kind
        value = self._read(kind) if kind in ("readc", "readn") else None
        self.state, out = _advance(self.state, self.ops, value)
        if isinstance(out, int):
            with digit_limit_for(out.bit_length() // 3 + 2):
                self.io.print_num(out)
        elif out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run an HQ9+ with headers program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
