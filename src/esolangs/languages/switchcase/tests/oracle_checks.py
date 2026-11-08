"""Structured cases rendered to source for differential execution."""

import re
from itertools import product

import pytest

from esolangs.languages.switchcase.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace
from tests.support.model_input import decimal_value

_WORKSPACE = workspace.workspace_model("switchcase-v1", "activation input_cursor")


def _source(cases):
    lines = []
    for name, arms in cases:
        lines.append("$" + name)
        for key, commands in arms.items():
            prefix = "!" if key == "!" else f"{key}?"
            lines.append(prefix + "".join(op + str(arg) for op, arg in commands))
    return "\n".join(lines)


def _output(op, value):
    """Render output or the range diagnostic before committing the activation."""
    try:
        if op == "@":
            return str(value), None
        if not 0 <= value < 0x110000:
            str(value)
            return "", "halt"
        return chr(value), None
    except ValueError:
        return "", "syntax"


def _model(cases, stdin):
    env = {"_": 0}
    case = index = cursor = 0
    arm = None
    output = ""
    error = None
    trace = []
    for step in range(25):
        halted = case == len(cases)
        trace.append(((case, arm, index, dict(env)), halted, output, cursor, cursor))
        if error:
            break
        if halted:
            trace.extend([trace[-1]] * 3)
            break
        if step == 24:
            break
        name, arms = cases[case]
        if name not in env:
            error = "halt"
            continue
        value = env[name]
        if arm is None:
            arm = next((key for key in (value, "!") if key in arms), None)
            case += arm is None
            continue
        if index == len(arms[arm]):
            case, arm, index = case + 1, None, 0
            continue
        op, arg = arms[arm][index]
        match op:
            case "+" | "-":
                env[name] += arg if op == "+" else -arg
            case "=":
                env[arg] = 0
            case "@" | ".":
                fragment, error = _output(op, value)
                if error:
                    continue
                output += fragment
            case ",":
                if cursor == len(stdin):
                    error = "input"
                    continue
                env[name] = ord(stdin[cursor])
                cursor += 1
            case "#":
                rest = stdin[cursor:]
                token = rest.split(maxsplit=1)
                if not token:
                    cursor = len(stdin)
                    error = "input"
                    continue
                word = token[0]
                cursor += len(rest) - len(rest.lstrip()) + len(word)
                if not re.fullmatch(r"[+-]?[0-9]+", word):
                    error = "argument"
                    continue
                env[name] = decimal_value(word)
            case "'":
                if not 1 <= arg <= len(cases):
                    error = "halt"
                    continue
                case, arm, index = arg - 1, None, 0
                continue
        index += 1
    return error, trace


def _check(factory, cases, stdin):
    def state(machine):
        case, arm, index, _ = machine.state
        return case, arm, index, machine.memory

    code = _source(cases)
    state = workspace.workspace_view(
        _model(cases, stdin)[1],
        _WORKSPACE,
        lambda row: ((*row[0][:3], frozenset(row[0][3].items())), row[-1]),
        state,
    )
    assert observed(factory, code, stdin, state, cap=24) == _model(cases, stdin), code


def check_raw_switchcase():
    ops = (
        ("+", 65),
        ("-", 1),
        ("=", "x"),
        ("@", ""),
        (".", ""),
        (",", ""),
        ("'", 1),
        ("'", 2),
        ("'", 3),
    )
    for pair, stdin in product(product(ops, repeat=2), ("", "Ā")):
        cases = [("_", {0: pair, "!": (("@", ""),)}), ("x", {0: (("@", ""),)})]
        _check(_Machine, cases, stdin)

    for stdin in ("", "  ", " -42 z", " +3", " Ā"):
        _check(_Machine, [("_", {0: (("#", ""), ("@", ""))})], stdin)
    _check(
        _Machine,
        [("_", {0: (("+", 1),)}), ("_", {0: ((".", ""),), "!": (("@", ""),)})],
        "",
    )

    _check(
        _Machine,
        [("_", {0: (("+", 7),)}), ("_", {7: (("@", ""),), "!": ((".", ""),)})],
        "",
    )

    numeric = [("_", {0: (("#", ""), ("@", ""))})]
    for stdin in (
        "3",
        "+" + "1" * 5000,
        "-" + "9" * 5000,
        "\u0661",
        "1_0",
        "1" * 5000 + "x",
        " \t",
    ):
        _check(_Machine, numeric, stdin)
    _check(_Machine, [("_", {0: (("#", ""), (".", ""))})], "1" * 5000)
    _check(
        _Machine,
        [("_", {0: ((",", ""), (".", ""), (",", ""), (".", ""))})],
        "\ud800\udfff",
    )
    for source in ("0?@", "$_\n!@", "$_\n0?@\n0?.", "$_\n0?x"):
        assert observed(_Machine, source, "", lambda m: m.state, cap=24) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )
    literal = "1" * 5000
    try:
        target = int(literal)
    except ValueError:
        assert observed(
            _Machine, "$_\n0?'" + literal, "", lambda m: m.state, cap=24
        ) == ("syntax", [(None, False, "", 0, 0)])
    else:
        _check(_Machine, [("_", {0: (("'", target),)})], "")

    class LostSelection(_Machine):
        def step(self):
            super().step()
            case, arm, index, env = self.state
            if arm is not None:
                self.state = case + 1, None, index, env

    with pytest.raises(AssertionError):
        _check(LostSelection, [("_", {0: (("@", ""),)})], "")

    workspace.check_erasures(
        _WORKSPACE, _check, _Machine, [("_", {0: (("#", ""), ("@", ""))})], "3"
    )
