"""Exact old Packlang scalar engine plus independently declared full projections."""

# The old four engine functions are retained as AST, without target imports.
from dataclasses import dataclass
from itertools import product
from typing import NamedTuple


@dataclass(frozen=True)
class Case:
    """The old source builder inputs, not native parser output."""

    kind: object
    statements: tuple
    stdin: str = "unused"


def _expr(expr):
    if not isinstance(expr, tuple):
        return str(expr)
    kind, *args = expr
    if kind == "not":
        return "!(" + _expr(args[0]) + ")"
    assert kind == "xor"
    return "(" + _expr(args[0]) + " ^ " + _expr(args[1]) + ")"


def _source(kind, statements):
    datatype = (
        kind if isinstance(kind, str) else "Integer(" + ",".join(map(str, kind)) + ")"
    )
    body = []
    for op, value in statements:
        if op in ("INIT", "INCR", "DECR"):
            body.append(op + " " + value)
        elif op in ("read", "write"):
            body.append(
                ("charGet" if op == "read" else "charPut") + "(" + _expr(value) + ")"
            )
        else:
            assert op == "value"
            body.append(_expr(value))
    return (
        "Package : IO { "
        + datatype
        + " cell; Integer main { "
        + ";".join(body)
        + "; } } scope;"
    )


def _eval(expr, values):
    if isinstance(expr, str):
        return values[expr]
    if type(expr) is int:
        return expr
    kind, *args = expr
    if kind == "not":
        return int(_eval(args[0], values) == 0)
    return _eval(args[0], values) ^ _eval(args[1], values)


def _model(kind, statements, stdin):
    low, high, under, over = (0, 255, 255, 0) if isinstance(kind, str) else kind
    values, trace = ({"cell": low}, [])
    pc = result = cursor = reads = 0
    output, done = ("", False)

    def row():
        state = None if done else (pc, tuple(sorted(values.items())), result)
        return ((state, reads), done, output, cursor, cursor)

    for op, arg in statements:
        trace.append(row())
        try:
            if op == "INIT":
                values[arg]
                values[arg] = low
            elif op in ("INCR", "DECR"):
                value = values[arg] + (1 if op == "INCR" else -1)
                values[arg] = under if value < low else over if value > high else value
            elif op == "read":
                if cursor == len(stdin):
                    value = 10
                else:
                    value = ord(stdin[cursor])
                    cursor, reads = (cursor + 1, reads + 1)
                values[arg]
                values[arg] = value
            elif op == "write":
                output += chr(_eval(arg, values) % 256)
            else:
                result = _eval(arg, values)
        except KeyError:
            return ("halt", [*trace, row()])
        pc += 1
    trace.append(row())
    done = True
    return (None, trace + [row()] * 4)


def cases():
    """Enumerate all 1132 unchanged old records, without running a target."""
    records = []

    def add(_factory, kind, statements, stdin="unused"):
        records.append(Case(kind, statements, stdin))

    kinds = ("Integer", "Char", (0, 1, 1, 0), (2, 4, 3, 2), (0, 3, 2, 1))
    actions = (
        ("INIT", "cell"),
        ("INCR", "cell"),
        ("DECR", "cell"),
        ("write", "cell"),
        ("write", ("xor", "cell", 65)),
        ("value", ("not", "cell")),
    )
    for kind, first, second, third in product(kinds, actions, actions, actions):
        add(None, kind, (first, second, third))
    for kind, stdin in product(
        kinds, ("", "A", "\nZ", "λ", "ÿ", "Ā", "😀", "\x00", "abc")
    ):
        add(
            None,
            kind,
            (
                ("read", "cell"),
                ("write", "cell"),
                ("INCR", "cell"),
                ("write", "cell"),
                ("read", "cell"),
                ("value", "cell"),
            ),
            stdin,
        )
    for operation in (("INCR", "missing"), ("read", "missing"), ("write", "missing")):
        add(None, "Integer", (operation,))
    for expr in (
        ("xor", 48, ("not", ("xor", 7, 7))),
        ("xor", 48, ("not", ("xor", 7, 6))),
        ("xor", 48, ("not", ("not", ("xor", 7, 6)))),
    ):
        add(None, "Integer", (("write", expr),))
    add(None, "Integer", (("write", 104), ("write", 105), ("value", 0)))
    assert len(records) == 1132
    return records


class Row(NamedTuple):
    """Complete independent scalar frame and all owned IO phases."""

    frame: object
    reads: int
    halted: bool
    output: str
    cursor: int
    past: int
    character: bool
    newline: bool
    successful: int
    error: str | None

    def old_view(self):
        """Return the exact old five-field observation."""
        return (
            (self.frame, self.reads),
            self.halted,
            self.output,
            self.cursor,
            self.cursor,
        )

    def frame_values(self):
        """Declare every frame field in the scalar-only source family."""
        if self.halted:
            return ()
        pc, store, result = self.frame
        return (("scope", "main", pc, frozenset(store), result, None, None),)


def plan(case):
    """Enrich the unchanged old trace using declared read/write microphases."""
    assert len(case.statements) < 48
    error, views = _model(case.kind, case.statements, case.stdin)
    rows, past, character, newline, successful = [], 0, False, False, 0
    for index, view in enumerate(views):
        failure = error if index == len(views) - 1 else None
        if index and not views[index - 1][1]:
            prior, _done, old_output, cursor, _progress = views[index - 1]
            pc, _store, _result = prior[0]
            if pc < len(case.statements):
                op, _arg = case.statements[pc]
                if op == "read":
                    character = True
                    if cursor == len(case.stdin):
                        past += 1
                    else:
                        newline = False
                elif op == "write" and failure is None:
                    assert len(view[2]) == len(old_output) + 1
                    newline = view[2][-1] != "\n"
            successful += failure is None
        (frame, reads), halted, output, cursor, progress = view
        assert progress == cursor
        row = Row(
            frame,
            reads,
            halted,
            output,
            cursor,
            past,
            character,
            newline,
            successful,
            failure,
        )
        assert row.old_view() == view
        rows.append(row)
    return error, rows


def expression(value):
    if type(value) is int:
        return ("lit", value)
    if type(value) is str:
        return ("var", value)
    return (value[0], *(expression(item) for item in value[1:]))


def bounds(kind):
    return (0, 255, 255, 0, None) if type(kind) is str else (*kind, None)


def body(case):
    result = []
    for op, value in case.statements:
        if op in ("INIT", "INCR", "DECR"):
            result.append((op.lower(), value, None))
        elif op == "read":
            result.append(("read", value, None))
        else:
            result.append(("print" if op == "write" else "val", expression(value)))
    return tuple(result)


def program_key(case):
    return (
        (((("scope", "main"), "scope", (), body(case), (), ()),)),
        (("scope", frozenset({"IO"})),),
        ((("scope", "cell"), *bounds(case.kind)),),
    )


def io_values(case, row):
    return {
        "_source": case.stdin,
        "_supplied": case.stdin.count("\n")
        + int(bool(case.stdin) and not case.stdin.endswith("\n")),
        "_offset": row.cursor,
        "_line_reads": 0,
        "_character_reads": row.character,
        "_past_end": row.past,
        "_pending": "",
        "_reads": row.cursor,
        "_consumed": row.cursor,
        "_newline": row.newline,
        "_buffer": (row.output, "\n", len(row.output), None),
    }
