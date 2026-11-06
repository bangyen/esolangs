"""Tree reducer for the Hot specification."""

from itertools import product

import pytest

from esolangs.languages.hot.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "hot-v1",
    (
        "expression",
        "pending_bit",
        "input_ended",
        "output_odd",
        "stopped",
        "input_cursor",
    ),
)

_ARITY = dict(zip("KSFABCD01", (2, 3, 1, 1, 1, 1, 1, 2, 0), strict=True))


def _apply(head, args):
    for arg in args:
        head = head, arg
    return head


def _parse(source):
    tokens = iter(c for c in source if not c.isspace())

    def group(*, nested=False):
        terms = []
        for token in tokens:
            if token == ")":
                if nested and terms:
                    return _apply(terms[0], terms[1:])
                raise ValueError
            if token == "(":
                terms.append(group(nested=True))
            elif token in _ARITY:
                terms.append(token)
            else:
                raise ValueError
        if nested or not terms:
            raise ValueError
        return _apply(terms[0], terms[1:])

    return group()


def _spine(tree):
    args = []
    while isinstance(tree, tuple):
        tree, arg = tree
        args.append(arg)
    args.reverse()
    return tree, args + ["F"] * (_ARITY[tree] - len(args))


def _model(source, stdin):
    try:
        tree = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    # Each input character contributes a marker and a payload on demand.
    stream = iter(stdin)
    pending = None
    ended = halted = False
    cursor = parity = 0
    output = ""
    trace = []
    stopped = 0
    error = None
    for step in range(20):
        head, args = _spine(tree)
        trace.append(
            (
                ([head, *args], pending, ended, bool(parity)),
                halted,
                output,
                cursor,
                cursor,
            )
        )
        if error or (step == 16 and not halted):
            break
        if halted:
            stopped += 1
            if stopped == 4:
                break
            continue
        used, tail = args[: _ARITY[head]], args[_ARITY[head] :]
        match head:
            case "K" | "0":
                replacement = used[int(head == "0")]
            case "S":
                x, y, z = used
                replacement = (x, z), (y, z)
            case "1":
                replacement = "K"
            case "F" | "B":
                replacement = _apply(used[0], "BA" if head == "F" else "DC")
            case "A":
                if pending is not None:
                    bit, pending = pending, None
                elif ended:
                    bit = 0
                else:
                    char = next(stream, "")
                    cursor += bool(char)
                    if char in ("0", "1"):
                        bit, pending = 1, int(char)
                    elif char in ("", "\n"):
                        bit, ended = 0, True
                    else:
                        error = "argument"
                        continue
                replacement = used[0], str(bit)
            case _:
                replacement = used[0]
                if parity:
                    output += str(int(head == "D"))
                elif head == "C":
                    halted = True
                parity ^= 1
        tree = _apply(replacement, tail)
    return error, trace


def _check(factory, code, stdin):
    expected = _model(code, stdin)

    def state(machine):
        return machine.stack, machine.pending, machine.ended, machine.odd

    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (
            (row[0][0][0], tuple(row[0][0][1:])),
            *row[0][1:],
            row[1],
            row[-1],
        ),
        state,
    )
    assert observed(factory, code, stdin, checked, cap=16) == expected


def check_raw_hot():
    corpus = [" ".join(chars) for chars in product(_ARITY, repeat=2)]
    corpus += [
        "S(SKK)(SKK)(S(SKK)(SKK))",
        "0 (C K) (D K)",
        "K",
        "",
        "()",
        "K)",
        "(K",
        "X",
    ]
    for code, stdin in product(corpus, ("", "0", "1", "01\nX", "X")):
        _check(_Machine, code, stdin)

    # A second read after the terminator must leave trailing input untouched.
    _check(_Machine, "A (K (A K))", "\nX")

    class MissingMarker(_Machine):
        def _read(self):
            return int(self.io.input_char() == ord("1"))

    with pytest.raises(AssertionError):
        _check(MissingMarker, "A K", "0")
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), "A K", "0")
