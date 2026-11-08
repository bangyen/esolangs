"""Independent bounded statement parser and complete workspace boundary witness."""

import itertools
import re

import pytest

from esolangs.languages.basicfuck.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support.workspace_oracle import (
    charged_bits,
    check_erasures,
    workspace_model,
    workspace_view,
)

_WORKSPACE = workspace_model("basicfuck-v1", "instruction cells input_cursor")
_NAME = re.compile(r"[A-Za-z_]\w*\Z")
_RESERVED = {"if", "while", "read", "write"}


def _directive(line):
    fields = line.split()
    if len(fields) not in (3, 4) or fields[0] != "#basicfuck":
        raise ValueError
    if not fields[1].startswith("t=") or not fields[2].startswith("r="):
        raise ValueError
    size = fields[1][2:]
    if size != "unbounded" and not re.fullmatch(r"\d+", size):
        raise ValueError
    ends = fields[2][2:].split("~")
    if len(ends) != 2 or any(s and not re.fullmatch(r"-?\d+", s) for s in ends):
        raise ValueError
    low, high = (int(s) if s else None for s in ends)
    mode = None
    if len(fields) == 4:
        if fields[3] not in ("o=wrap", "o=halt", "o=nearest"):
            raise ValueError
        mode = fields[3][2:]
    if low is not None or high is not None:
        if mode is None or (mode == "wrap" and None in (low, high)):
            raise ValueError
        if low is not None and high is not None and low > high:
            raise ValueError
    else:
        mode = None
    return size, low, high, mode


def _allocations(line):
    if not line.startswith("#allocate"):
        raise ValueError
    names, extent = {}, 0
    for item in line[9:].split(","):
        pieces = item.strip().split("->")
        name = pieces[0]
        if not _NAME.fullmatch(name) or name in names or name in _RESERVED:
            raise ValueError
        if len(pieces) > 2 or (len(pieces) == 2 and not pieces[1].isdigit()):
            raise ValueError
        names[name] = extent
        extent += int(pieces[1]) if len(pieces) == 2 else 1
    return names, extent


def _parse(source):
    lines = [s.split("//", 1)[0].strip() for s in source.split("\n")]
    lines = list(filter(None, lines))
    if len(lines) < 2:
        raise ValueError
    size, low, high, mode = _directive(lines[0])
    names, extent = _allocations(lines[1])
    body = " ".join(lines[2:])
    tokens = re.findall(r"[A-Za-z_]\w*|\d+|\+=|-=|->|<-|[^\s]", body)
    at, variable = 0, False

    def take(want=None):
        nonlocal at
        if at == len(tokens) or (want is not None and tokens[at] != want):
            raise ValueError
        word = tokens[at]
        at += 1
        return word

    def ref():
        name = take()
        if name not in names:
            raise ValueError
        shift = 0
        if at < len(tokens) and tokens[at] == "->":
            take("->")
            number = take()
            if not number.isdigit():
                raise ValueError
            shift = int(number)
        return names[name] + shift

    def block(*, nested=False):
        nonlocal variable
        result = []
        while at < len(tokens) and tokens[at] != "}":
            word = tokens[at]
            if word in ("if", "while"):
                take()
                negated = at < len(tokens) and tokens[at] == "!"
                if negated:
                    take("!")
                take("(")
                index = ref()
                take(")")
                take("{")
                result.append((word, index, not negated, block(nested=True)))
            elif word in ("read", "write"):
                take()
                take("->" if word == "read" else "<-")
                result.append((word, ref()))
                take(";")
            else:
                index = ref()
                sign = take()
                if sign not in ("+=", "-="):
                    raise ValueError
                literal = at < len(tokens) and tokens[at].isdigit()
                operand = int(take()) if literal else ref()
                variable |= not literal
                result.append(
                    ("add", index, 1 if sign == "+=" else -1, literal, operand)
                )
                take(";")
        if nested:
            take("}")
        return result

    tree = block()
    if at != len(tokens):
        raise ValueError
    length = extent if size == "unbounded" else int(size) - int(variable)
    if extent > length:
        raise ValueError
    return _flatten(tree), length, (low, high, mode)


def _flatten(tree):
    instructions = []

    def flatten(nodes):
        for node in nodes:
            if node[0] in ("if", "while"):
                start = len(instructions)
                instructions.append(None)
                flatten(node[3])
                if node[0] == "while":
                    instructions.append(("jump", start))
                instructions[start] = ("test", node[1], node[2], len(instructions))
            else:
                instructions.append(node)

    flatten(tree)
    return instructions


def _fit_reference(value, low, high, mode):
    outside = (low is not None and value < low) or (high is not None and value > high)
    if not outside:
        return value
    if mode == "halt":
        raise IndexError
    if mode == "wrap":
        return low + (value - low) % (high - low + 1)
    if low is not None:
        value = max(low, value)
    return min(high, value) if high is not None else value


def model(source, stdin, cap=64):
    """Return error category and all bounded boundaries, including failed steps."""
    try:
        instructions, length, (low, high, mode) = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    pc, cells, cursor, output = 0, [0] * length, 0, ""

    def view():
        return ((pc, tuple(cells)), pc == len(instructions), output, cursor, cursor)

    def cell(index):
        if index >= len(cells):
            raise IndexError
        return cells[index]

    rows, error = [view()], None
    for _ in range(cap):
        if pc == len(instructions):
            break
        op = instructions[pc]
        try:
            next_pc = pc + 1
            if op[0] == "read":
                if cursor == len(stdin):
                    raise EOFError
                value = ord(stdin[cursor])
                cursor += 1
                cell(op[1])
                cells[op[1]] = _fit_reference(value, low, high, mode)
            elif op[0] == "write":
                value = cell(op[1])
                if not 0 <= value <= 0x10FFFF:
                    raise IndexError
                output += chr(value)
            elif op[0] == "add":
                amount = op[4] if op[3] else cell(op[4])
                cells[op[1]] = _fit_reference(
                    cell(op[1]) + op[2] * amount, low, high, mode
                )
            elif op[0] == "test":
                if bool(cell(op[1])) != op[2]:
                    next_pc = op[3]
            else:
                next_pc = op[1]
            pc = next_pc
        except EOFError:
            error = "input"
        except IndexError:
            error = "halt"
        rows.append(view())
        if error:
            break
    if error is None and pc == len(instructions):
        rows.extend([view()] * 3)
    return error, rows


def _source(body, *, size="unbounded", bounds="0~255", mode="wrap", names="a,b"):
    suffix = "" if mode is None else f" o={mode}"
    return f"#basicfuck t={size} r={bounds}{suffix}\n#allocate {names}\n{body}"


def corpus():
    """Yield deterministic grammar, range, alias, input and compiled-loop cases."""
    for mode, char, increment, count in itertools.product(
        ("wrap", "nearest", "halt"), ("\0", "A", "ÿ", "Ω"), (0, 1, 300), (0, 1, 4)
    ):
        yield (
            _source(
                f"read -> arr; counter += {count}; while (counter) {{ arr->1 += arr; "
                f"arr->1 += {increment}; counter -= 1; }} "
                "if !(counter) { write <- arr->1; } if (counter) { read -> arr; }",
                mode=mode,
                names="arr->2,counter",
            ),
            char + "sentinel",
            40,
        )
    bodies = (
        "",
        "a += 1;",
        "a -= a;",
        "a += 65; write <- a;",
        "read -> a; write <- a;",
        "if (a) { a->9 += 1; }",
        "if !(a) { b += 1; }",
        "while (a) { }",
        "while !(a) { b += 1; if (b) { a += b; } }",
        "a += 1; while (a) { }",
        "a += 3; while (a) { b += a; a -= 1; } write <- b;",
        "a += 2; if (a) { while (a) { if !(b) { b += 1; } a -= 1; } }",
        "a += 1; a += a; a -= a;",
        "read -> a->9;",
        "a->9 += b->9;",
        "write <- a->9;",
        "if (a->9) { }",
        "read -> a; read -> b; write <- b;",
    )
    for body, stdin in itertools.product(bodies, ("", "A\nΩQ")):
        yield _source(body), stdin, 64
    for bounds, mode in itertools.product(
        ("~", "0~", "~2", "-2~2", "48~49"), (None, "wrap", "nearest", "halt")
    ):
        for body in ("a -= 9; a += 12; write <- a;", "read -> a; write <- a;"):
            yield _source(body, bounds=bounds, mode=mode), "ΩQ", 64
    for size, names, body in itertools.product(
        (0, 1, 2, 3, 4),
        ("a", "a,b", "a->0,b", "a->2,b"),
        ("a->2 += 65; write <- a->2;", "a += b;", "if (a) { a += a; }"),
    ):
        yield _source(body, size=size, names=names), "Q", 64
    for body in (
        "a -= 1; write <- a;",
        "a += 1114112; write <- a;",
        "a += 1114111; write <- a;",
        "a += 55296; write <- a;",
    ):
        yield _source(body, bounds="~", mode=None), "", 64
    for source in (
        "",
        "#allocate a",
        _source("a += ;"),
        _source("if (a) {"),
        _source("if (a) { };"),
        _source("a->b += 1;"),
        _source("", names="read"),
        _source("", names="a,a"),
    ):
        yield source, "", 64
    yield _source("a += 65; write <- a; read -> b; read -> b;"), "X", 64
    for size, names, body, stdin in itertools.product(
        (0, "unbounded"),
        ("a->0", "a->0,b->0"),
        ("", "read -> a;", "write <- a;", "if (a) { }"),
        ("", "Q"),
    ):
        yield _source(body, size=size, names=names), stdin, 64
    for size in (0, 1):
        yield _source("a += b;", size=size, names="a->0,b->0"), "", 64
    for body in ("", "if (a) { a += 1; }"):
        yield _source(body, bounds="48~49"), "", 64
    for digits in ("\uff11\uff12", "\u0661\u0662", "1\uff12", "\u00b2"):
        yield _source(f"a += {digits}; write <- a;"), "", 64
        yield _source(f"a->{digits} += 65; write <- a->{digits};", size=20), "", 64
        yield _source("a += 1;", size=digits), "", 64
        yield _source("a += 20; write <- a;", bounds=f"0~{digits}"), "", 64
        yield _source("a += 1;", names=f"a->{digits}"), "", 64
    yield _source("// ignored\na += 1;", names="a->80"), "", 64
    yield _source("a += 40; while (a) { a -= 1; } write <- a;"), "", 192


def _agrees(factory, source, stdin, cap):
    expected = model(source, stdin, cap)
    checked = workspace_view(
        expected[1], _WORKSPACE, lambda row: (*row[0], row[-1]), lambda m: m.state
    )
    assert observed(factory, source, stdin, checked, cap=cap) == expected, source
    return expected


def check_raw_workspace_basicfuck():
    """Reject erased components and semantic faults against independent rows."""
    results = [_agrees(_Machine, *case) for case in corpus()]
    assert {error for error, _ in results} == {None, "syntax", "input", "halt"}
    source = _source("read -> a; a += 1; write <- a;")
    assert (
        charged_bits(
            _WORKSPACE, ((*row[0], row[-1]) for row in model(source, "AQQ")[1])
        )
        == 11
    )
    check_erasures(_WORKSPACE, _agrees, _Machine, source, "AQQ", 64)
    for factory in (stalled(_Machine), overread(_Machine)):
        with pytest.raises(AssertionError):
            _agrees(factory, source, "AQQ", 64)

    class WrongOverflow(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("o=wrap", "o=nearest"), io)

    class ExtraOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    for factory, code in ((WrongOverflow, _source("a -= 1;")), (ExtraOutput, source)):
        with pytest.raises(AssertionError):
            _agrees(factory, code, "AQQ", 64)
