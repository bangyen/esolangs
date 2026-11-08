"""Independent syllable assembler and accumulator/deque/function model.

https://esolangs.org/wiki/CV(N)(C), memory, command table and examples.
CV/CVN/CVNC families, arithmetic precedence, input, loops and gotos, 48
commands. Published ambiguities retain the public contract's Decisions.
"""

import ast
import math
from itertools import product

import pytest

from esolangs.languages.cvnc.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support import workspace_oracle as workspace
from tests.support.model_input import token_span

_WORKSPACE = workspace.workspace_model(
    "cvnc-v1", "instruction accumulator deque function input_cursor"
)

_SYMBOLS = {"d": "a", "b": "+", "t": "-", "ɡ": "×", "q": "÷", "ʔ": "(", "ʡ": ")"}


def _evaluate(node, bindings):
    if isinstance(node, ast.Name):
        return bindings[node.id]
    if not isinstance(node, ast.BinOp):
        raise ValueError("invalid function")
    left, right = _evaluate(node.left, bindings), _evaluate(node.right, bindings)
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return max(0, left - right)
    if isinstance(node.op, ast.Mult):
        return left * right
    if not isinstance(node.op, ast.FloorDiv):
        raise ValueError("invalid function")
    return left // right


def _apply(function, accumulator):
    """Validate tokens before AST evaluation; literal conversion keeps its phase."""
    source, bindings = [], {"a": accumulator}
    operators = {"+": "+", "-": "-", "×": "*", "÷": "//"}
    operand, depth = True, 0
    for token in function:
        if operand:
            if token == "(":
                source.append(token)
                depth += 1
                continue
            if token == "a":
                source.append(token)
            elif token.isdigit():
                name = f"n{len(bindings)}"
                bindings[name] = int(token)
                source.append(name)
            else:
                return accumulator
            operand = False
        elif token in operators:
            source.append(operators[token])
            operand = True
        elif token == ")" and depth:
            source.append(token)
            depth -= 1
        else:
            return accumulator
    if operand or depth:
        return accumulator
    return _evaluate(ast.parse(" ".join(source), mode="eval").body, bindings)


def _read(kind, stdin, cursor):
    if kind == "ʒ":
        if cursor == len(stdin):
            return None, cursor, "input"
        return ord(stdin[cursor]) % 256, cursor + 1, None
    start, cursor = token_span(stdin, cursor)
    if start == cursor:
        return None, cursor, "input"
    try:
        value = max(0, int(stdin[start:cursor]))
    except ValueError:
        value = 0
    return value, cursor, None


def _vowel(token, accumulator, function):
    if token == "i":
        return accumulator + 1
    if token == "ə":
        return max(0, accumulator - 1)
    if token == "æ":
        return accumulator * accumulator
    if token == "o":
        return math.isqrt(accumulator)
    return _apply(function, accumulator)


def _function(token, accumulator, queue, function):
    if token in _SYMBOLS:
        function.append(_SYMBOLS[token])
    elif token == "c":
        function.clear()
    else:
        at = 0 if token == "p" else -1
        function.append(str(queue[at]))
        queue.pop(at)
    return accumulator


def _nasal(token, accumulator, queue):
    if token == "m":
        queue.insert(0, accumulator)
    elif token == "n":
        queue.append(accumulator)
    else:
        return queue.pop(0 if token == "ŋ" else -1)
    return accumulator


def _model(syllables, stdin):
    tokens, starts = [], []
    for syllable in syllables:
        starts.append(len(tokens))
        tokens.extend("ɡ" if c == "g" else c for c in syllable)
    offsets = [i for i, token in enumerate(tokens) for _ in token]
    pairs, pending = {}, []
    for i, token in enumerate(tokens):
        if token in ("ɰ", "ɰ̊"):
            pending.append(i)
        elif token == "ʋ":
            previous = pending.pop()
            pairs[previous], pairs[i] = i, previous
    pc = accumulator = cursor = 0
    queue, function, output, trace = [], [], "", []

    def row():
        state = (
            pc,
            accumulator,
            tuple(queue),
            tuple(function),
            tuple(tokens),
            tuple(starts),
        )
        return state, pc >= len(tokens), output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if pc >= len(tokens):
            return None, trace + [row()] * 3
        if tick == 48:
            break
        token = tokens[pc]
        pc += 1
        try:
            if token in "θf":
                output += str(accumulator) if token == "θ" else chr(accumulator % 256)
            elif token in "sʒ":
                value, cursor, error = _read(token, stdin, cursor)
                if error:
                    return error, [*trace, row()]
                accumulator = value
            elif token in "iəæou":
                accumulator = _vowel(token, accumulator, function)
            elif token in "mnŋɲ":
                accumulator = _nasal(token, accumulator, queue)
            elif token in "ɹj":
                positions = offsets if token == "ɹ" else starts
                pc = (
                    positions[accumulator]
                    if accumulator < len(positions)
                    else len(tokens)
                )
            elif token == "ʋ":
                pc = pairs[pc - 1]
            elif token in ("ɰ", "ɰ̊"):
                if (accumulator == 0) == (token == "ɰ̊"):
                    pc = pairs[pc - 1] + 1
            else:
                accumulator = _function(token, accumulator, queue, function)
        except (IndexError, ZeroDivisionError):
            return "halt", [*trace, row()]
        except ValueError:
            return "syntax", [*trace, row()]
    return None, trace


def _view(machine):
    function = tuple(
        token.replace("*", "×").replace("/", "÷") for token in machine.function
    )
    return (
        machine.pointer,
        machine.accumulator,
        machine.deque,
        function,
        tuple(machine.tokens),
        tuple(machine.starts),
    )


def _check(factory, syllables, stdin="unused"):
    expected = _model(syllables, stdin)
    source = "\n".join("".join(s) for s in syllables)
    checked = workspace.workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (
            row[0][0],
            row[0][1],
            row[0][2],
            tuple(token.replace("×", "*").replace("÷", "/") for token in row[0][3]),
            row[-1],
        ),
        _view,
    )
    assert observed(factory, source, stdin, checked, cap=48) == expected, (
        syllables,
        stdin,
    )


def check_raw_cvnc():
    for c, v, n in product(
        ("θ", "f", "s", "ʒ", "p", "k", "d", "b", "t", "ɡ", "g", "q", "ʔ", "ʡ", "c"),
        "iəæou",
        ("", "m", "n", "ŋ", "ɲ"),
    ):
        _check(_Machine, ((c, v, *n),), "3 A")
    choices = (
        ("c", "i", "n"),
        ("c", "æ", "m"),
        ("c", "u", "ŋ"),
        ("d", "u"),
        ("b", "u"),
        ("s", "ə"),
        ("θ", "u"),
        ("f", "o"),
    )
    for first, second in product(choices, repeat=2):
        _check(_Machine, (first, second), "7")
    for value, vowel in product((0, 1, 5, 10, 255, 321), "iəæou"):
        _check(_Machine, (("s", "u"), ("c", vowel), ("f", "u")), str(value))
    for char in ("\0", "\u0100", "\u0101", "中"):
        _check(_Machine, (("ʒ", "u"), ("θ", "u")), char)
    for push, pop in product("mn", ("ŋ", "ɲ")):
        syllables = (("s", "u", push),) * 3 + (("c", "u", pop),) * 2
        _check(_Machine, (*syllables, ("θ", "u")), "1 3 6")
    for value, word in product(
        (0, 1, 3), ("d", "dbd", "dbdɡd", "dtdbd", "ʔdbdʡɡd", "dq", "p", "pk")
    ):
        _check(
            _Machine,
            (("s", "u", "n"), *((c, "u") for c in word), ("θ", "u")),
            str(value),
        )
    for left, right in product((0, 1, 3), repeat=2):
        _check(
            _Machine,
            (
                ("s", "u", "m"),
                ("s", "u", "n"),
                ("c", "u"),
                ("p", "u"),
                ("b", "u"),
                ("k", "u"),
                ("θ", "u"),
            ),
            f"{left} {right}",
        )
    for syllables in (
        (("s", "i", "n"), ("s", "u", "ŋ", "s")),
        (("s", "u"), ("ɰ̊", "ə"), ("ʋ", "u")),
        (("s", "u"), ("ɰ", "i"), ("ʋ", "u")),
        (("s", "u"), ("ɹ", "u")),
        (("s", "u"), ("j", "u")),
    ):
        for stdin in ("0 1 2", "1", "3", "99"):
            _check(_Machine, syllables, stdin)
    for stdin in ("", " -3 x", "bad\n", "λ\n", "\n"):
        _check(_Machine, (("s", "u"), ("ʒ", "u"), ("θ", "u")), stdin)
    for source in ("", "s", "a", "susŋ", "su su", "ɰ̊u", "ʋu"):
        assert observed(_Machine, source, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    numeric = (("s", "u"), ("ʒ", "u"), ("θ", "u"))
    for stdin in (
        "+" + "1" * 5000 + " Z",
        "-" + "9" * 5000 + " Z",
        "١_٢ X",
        "1_0 X",
        "bad X",
        " \t",
        "1" * 5000 + "x Z",
    ):
        _check(_Machine, numeric, stdin)
    square = (("s", "u"),) + (("c", "æ"),) * 14
    for suffix in ((("θ", "u"),), (("c", "u", "n"), ("p", "u"), ("θ", "u"))):
        _check(_Machine, (*square, *suffix), "2")
    _check(
        _Machine, (("s", "u", "n"), ("d", "u"), ("b", "u"), ("p", "u"), ("θ", "u")), "3"
    )

    class WrongFunction(_Machine):
        def step(self):
            super().step()
            self.function = tuple("*" if c == "+" else c for c in self.function)

    for factory in (stalled(_Machine), WrongFunction, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, (("d", "u"), ("b", "u"), ("d", "u")))
    workspace.check_erasures(
        _WORKSPACE, _check, _Machine, (("s", "u"), ("c", "i", "n")), "3"
    )
