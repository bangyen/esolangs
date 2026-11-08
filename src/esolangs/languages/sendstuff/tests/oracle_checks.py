"""Independent eager message-list model of base SendStuff, capped at 48 sends.

https://esolangs.org/wiki/SendStuff, revision 109482, overview and commands.
Named graph assembler, all base commands, fanout and cycles; macros remain
in raw tests. Interleave orientation and input framing follow Decisions.
"""

import re
from itertools import product

from esolangs.languages.sendstuff.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults
from tests.support.model_input import token_span


def _assemble(forest):
    names, commands, params, up, down = {}, ["root"], [0], [[]], [[]]

    def tree(parent, relation, node):
        if isinstance(node, str):
            index, text = names[node], node
        else:
            name, command, param, children = node
            index = len(commands)
            names[name] = index
            commands.append(command)
            params.append(param)
            up.append([])
            down.append([])
            body = " ".join(tree(index, kind, child) for kind, child in children)
            text = f"{name}({command} {param} {body})"
        if relation == ">":
            down[parent].append(index)
        elif relation == "<":
            up[index].append(parent)
        return relation + text

    source = "\n".join(tree(0, kind, node) for kind, node in forest)
    targets = tuple(tuple(a + b) for a, b in zip(up, down, strict=True))
    return source, (tuple(commands), tuple(params), targets)


def _node(command, param=0, children=(), *, name=""):
    return name, command, param, children


def _read(command, stdin, cursor):
    if command == "Input":
        if cursor == len(stdin):
            return [], cursor, None
        return [ord(stdin[cursor])], cursor + 1, None
    start, cursor = token_span(stdin, cursor)
    if start == cursor:
        return [], cursor, None
    text = stdin[start:cursor]
    if not re.fullmatch(r"[+-]?[0-9]+", text):
        return [], cursor, "argument"
    value = int(text)
    return ([value], cursor, None) if value >= 0 else ([], cursor, "halt")


def _arithmetic(command, param, value):
    if command == "Interleave":
        width = max(1, param.bit_length(), value.bit_length())
        bits = "".join(
            a + b
            for a, b in zip(f"{param:0{width}b}", f"{value:0{width}b}", strict=True)
        )
        return int(bits, 2)
    if command in ("LeftHalf", "RightHalf"):
        shift = 1 if command == "LeftHalf" else 0
        bits = bin(value)[2:][::-1][shift::2][::-1]
        return int(bits or "0", 2)
    return {
        "Constant": lambda: param,
        "Add": lambda: value + param,
        "Subtract": lambda: value - param,
        "Multiply": lambda: value * param,
        "Divide": lambda: param // value,
        "DivideBy": lambda: value // param,
        "Modulo": lambda: param % value,
        "ModuloBy": lambda: value % param,
    }[command]()


def _results(command, param, value):
    if command == "CountUp":
        return list(range(value + 1))
    if command == "CountDown":
        return list(range(value, -1, -1))
    if command in ("Output", "OutputNumber"):
        return []
    try:
        result = _arithmetic(command, param, value)
    except ZeroDivisionError:
        return []
    return [result] if result >= 0 else []


def _model(program, stdin):
    commands, params, targets = program
    pending = [(0, target, 0) for target in targets[0]]
    cursor, output, trace = 0, "", []

    def row():
        return (program, tuple(pending)), not pending, output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if not pending:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        _, receiver, value = pending[0]
        command, param, text = commands[receiver], params[receiver], ""
        if command in ("Input", "InputNumber"):
            results, cursor, error = _read(command, stdin, cursor)
            if error:
                return error, [*trace, row()]
        else:
            if command == "Output":
                if value > 0x10FFFF:
                    return "halt", [*trace, row()]
                text = chr(value)
            elif command == "OutputNumber":
                text = str(value)
            results = _results(command, param, value)
        pending = [
            (receiver, target, result)
            for result in results
            for target in targets[receiver]
        ] + pending[1:]
        output += text
    return None, trace


def _view(machine):
    program = machine.program
    pending, frames = [], machine.state
    while frames is not None:
        (sender, (first, step, count), k, j), frames = frames
        for index in range(k, count):
            pending.extend(
                (sender, target, first + step * index)
                for target in program.targets[sender][j if index == k else 0 :]
            )
    return ((program.commands, program.params, program.targets), tuple(pending))


def _check(factory, forest, stdin="unused"):
    source, program = _assemble(forest)
    assert observed(factory, source, stdin, _view, cap=48) == _model(program, stdin), (
        source,
        stdin,
    )


def check_raw_sendstuff():
    sink = (">", _node("OutputNumber"))
    for value, param, command in product(
        (0, 1, 2, 5, 13),
        (0, 1, 3, 6),
        (
            "Constant",
            "Add",
            "Subtract",
            "Multiply",
            "Divide",
            "DivideBy",
            "Modulo",
            "ModuloBy",
            "Interleave",
            "LeftHalf",
            "RightHalf",
        ),
    ):
        node = _node("Constant", value, ((">", _node(command, param, (sink,))),))
        _check(_Machine, ((">", node),))
    for limit, command, delta in product(range(5), ("CountUp", "CountDown"), (0, 3)):
        branch = _node(command, 0, (sink, (">", _node("Add", delta, (sink,)))))
        _check(_Machine, ((">", _node("Constant", limit, ((">", branch),))),))
    for command, stdin in product(
        ("Input", "InputNumber"),
        ("", " \n", "Aλ\n", "0 3 7", "-2", "1_0", "٣", "+65 X"),
    ):
        loop = _node(command, 0, (sink, (">", "loop")), name="loop")
        _check(_Machine, ((">", loop),), stdin)
    for value in (0, 65, 0x10FFFF, 0x110000):
        _check(_Machine, ((">", _node("Constant", value, ((">", _node("Output")),))),))
    _check(_Machine, ())
    _check(
        _Machine,
        (
            ("|", _node("OutputNumber", name="out")),
            (
                ">",
                _node(
                    "Constant",
                    5,
                    (
                        ("<", _node("Add", 1, ((">", "out"),), name="upstream")),
                        (">", "out"),
                    ),
                    name="front",
                ),
            ),
            (">", "upstream"),
        ),
    )
    _check(_Machine, ((">", _node("Add", 1, ((">", "spin"), sink), name="spin")),))
    for code in ("wat", ">(Sub 1)", ">missing", ">a(Add 1) >a(Add 2)", "<(Add 1)"):
        assert observed(_Machine, code, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongSend(_Machine):
        def step(self):
            super().step()
            if self.state:
                (node, (first, step, count), k, j), rest = self.state
                self.state = ((node, (first + 1, step, count), k, j), rest)

    reject_faults(_check, _Machine, WrongSend, ((">", _node("Constant", 2, (sink,))),))
