"""Header assembler and variable-machine model of HQ9+ with headers.

https://esolangs.org/wiki/HQ9%2B_with_headers, revision 129344. Startup,
semantic lists, arithmetic, text/code output, input, jumps and halt, capped
at 64 ops. Forks, hex conditionals and song formatting retain raw tests.
"""

from itertools import product

import pytest

from esolangs.languages.hq9_with_headers.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "hq9-with-headers-v1", "instruction cells input_cursor"
)


def _spell(operation):
    kind, *args = operation
    if kind in {"ADD", "SUB", "MUL", "DIV"}:
        return "[" + kind + " " + " ".join(args) + "]"
    if kind == "set":
        return args[0] + " = " + str(args[1])
    if kind == "inc":
        return args[0] + "++"
    if kind == "out":
        return "p(V" + args[0] + ")"
    if kind in {"readc", "readn"}:
        return "[>>" + ("," if kind == "readc" else ".") + " " + args[0] + "]"
    if kind == "code":
        return "p({{CODE}})"
    if kind == "text":
        text = "".join(
            "@" + format(ord(c), "02X") if c in '"@\n\r' else c for c in args[0]
        )
        return 'p("' + text + '")'
    assert kind == "nop", "unsupported semantic command"
    return "p()"


def _assemble(startup, body, flow):
    suffix = {"once": "", "loop": ",'J_1", "zero": ",'JZv#1", "halt": ",'H"}[flow]
    lines = [
        "==== HEADER ====",
        "COMMAND FLOW",
        "    1" + suffix,
        "CHARACTER SEMANTICS",
        "    Q",
    ]
    body_lines = []
    for op in body:
        body_lines.append(len(lines))
        lines.append("        " + _spell(op))
    lines.append("STARTUP")
    startup_lines = []
    for op in startup:
        startup_lines.append(len(lines))
        lines.append("    " + _spell(op))
    lines += ["CHECKSUM", f"    {ord('Q') % 1024 + 43}", "==== END HEADER ====", "Q"]
    ops, places = [*startup, *body], [*startup_lines, *body_lines]
    if flow != "once":
        ops.append(
            ("jump", len(startup))
            if flow == "loop"
            else ("jz", "v", len(startup))
            if flow == "zero"
            else ("halt",)
        )
        places.append(2)
    return "\n".join(lines), ops, places


def _names(ops):
    names = []
    for kind, *args in ops:
        refs = (
            args
            if kind in {"ADD", "SUB", "MUL", "DIV"}
            else args[:1]
            if kind in {"set", "inc", "out", "readc", "readn", "jz"}
            else []
        )
        for name in refs:
            if name not in names:
                names.append(name)
    return names


def _read(kind, stdin, cursor):
    if kind == "readc":
        return (ord(stdin[cursor]), cursor + 1) if cursor < len(stdin) else (0, cursor)
    digits = "0"
    while cursor < len(stdin):
        c, cursor = stdin[cursor], cursor + 1
        if not "0" <= c <= "9":
            break
        digits += c
    return int(digits), cursor


def _math(kind, left, right):
    if kind == "ADD":
        return left + right
    if kind == "SUB":
        return left - right
    if kind == "MUL":
        return left * right
    return left // right


def _model(ops, places, stdin):
    names = _names(ops)
    variables, trace, output = dict.fromkeys(names), [], ""
    pc = cursor = 0

    def get(name):
        if variables[name] is None:
            raise KeyError(name)
        return variables[name]

    def row():
        state = (
            pc,
            tuple(variables[n] for n in names),
            (places[pc] if pc < len(ops) else -1,),
        )
        return state, pc >= len(ops), output, cursor, cursor

    for tick in range(65):
        trace.append(row())
        if pc >= len(ops):
            return None, trace + [row()] * 3
        if tick == 64:
            break
        kind, *args = ops[pc]
        after = pc + 1
        try:
            if kind == "set":
                variables[args[0]] = args[1]
            elif kind in {"ADD", "SUB", "MUL", "DIV"}:
                variables[args[2]] = _math(kind, get(args[0]), get(args[1]))
            elif kind == "inc":
                variables[args[0]] = get(args[0]) + 1
            elif kind == "out":
                output += str(get(args[0]))
            elif kind == "text":
                output += args[0]
            elif kind == "code":
                output += "Q"
            elif kind in {"readc", "readn"}:
                variables[args[0]], cursor = _read(kind, stdin, cursor)
            elif kind == "jump":
                after = args[0]
            elif kind == "jz":
                if get(args[0]) == 0:
                    after = args[1]
            elif kind == "halt":
                after = len(ops)
        except (KeyError, ZeroDivisionError):
            return "halt", [*trace, row()]
        pc = after
    return None, trace


def _view(machine):
    return (
        machine.state[0],
        tuple(v for chunk in machine.state[1] for v in chunk),
        machine.ip,
    )


def _check(factory, startup, body, stdin="unused", flow="once"):
    source, ops, places = _assemble(startup, body, flow)
    expected = _model(ops, places, stdin)
    checked = workspace.workspace_view(
        expected[1], _WORKSPACE, lambda row: (row[0][0], row[0][1], row[-1]), _view
    )
    assert observed(factory, source, stdin, checked, cap=64) == expected, (
        startup,
        body,
        stdin,
        flow,
    )


def _assign(name, value):
    if value >= 0:
        return (("set", name, value),)
    return ("set", name, 0), ("set", "tmp", -value), ("SUB", name, "tmp", name)


def check_raw_hq9_with_headers():
    for left, right, kind in product(
        (-7, 0, 3, 2**32 + 1), (-2, 0, 5), ("ADD", "SUB", "MUL", "DIV")
    ):
        _check(
            _Machine,
            (*_assign("v", left), *_assign("u", right)),
            ((kind, "v", "u", "w"), ("out", "w"), ("inc", "w"), ("out", "w")),
        )
    for startup, body, flow in product(
        ((("set", "v", 0),), (("set", "v", 1),)),
        ((("inc", "v"), ("out", "v")), (("text", "@\nλ"), ("code",)), (("nop",),)),
        ("once", "loop", "zero", "halt"),
    ):
        _check(_Machine, startup, body, flow=flow)
    for kind, stdin in product(
        ("readc", "readn"), ("", "12x7", " -12", "λ\n", "\x00", "0")
    ):
        _check(
            _Machine,
            (("nop",),),
            ((kind, "v"), ("out", "v"), ("readc", "v"), ("out", "v")),
            stdin,
        )
    for body in ((("out", "v"),), (("inc", "v"),), (("DIV", "v", "v", "v"),)):
        _check(_Machine, (("nop",),), body)
    source, _, _ = _assemble((("nop",),), (("nop",),), "once")
    for broken in (
        "",
        source.replace("124", "125"),
        source.replace("    1", "  1", 1),
        source.replace("==== END HEADER ====", "missing"),
    ):
        assert observed(_Machine, broken, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongOutput(_Machine):
        def __init__(self, code, io):
            write = io.print_num
            io.print_num = lambda value: write(value + 1)
            super().__init__(code, io)

    for factory in (stalled(_Machine), WrongOutput, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, (("set", "v", 1),), (("out", "v"),))

    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(
                workspace.missing_workspace(_Machine, component),
                (("set", "v", 1),),
                (("out", "v"),),
            )
