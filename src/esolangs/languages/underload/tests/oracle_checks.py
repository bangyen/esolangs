"""Nested strings, invalid commands and dynamic evaluation without a generator."""

import random
from itertools import product

import pytest

from esolangs.languages.underload.interpreter import _Machine
from tests.interpreters.stack_oracles import agrees_stack, underload
from tests.support.workspace_oracle import (
    charged_bits,
    missing_workspace,
    workspace_model,
)

_WORKSPACE = workspace_model("underload-v1", "program instruction stack input_cursor")


def _parts(row):
    return row.code, row.ip, row.stack, row.consumed


def _check(factory, code, stdin="unused"):
    return agrees_stack(
        factory, underload, code, stdin, dynamic=True, workspace=(_WORKSPACE, _parts)
    )


def check_raw_underload() -> None:
    atoms = ("()", "(x)", "((x))", "~", ":", "!", "*", "a", "^", "S", " ", "(", ")")
    corpus = ["".join(chars) for n in range(3) for chars in product(atoms, repeat=n)]
    corpus += [
        "((yes)S)^((no)S)^",
        "(:^):^",
        "(λ)S",
        "(a)(b)*S",
        "((:))^",
        "\t\n",
        "(x)Q",
        "(x))",
        "(x)((",
    ]
    rng = random.Random(20261102)
    corpus += [
        "".join(rng.choices([*atoms[:11], "((x)S)", "(:^)"], k=8)) for _ in range(64)
    ]
    results = [_check(_Machine, code)[-1] for code in corpus]
    assert {r.error for r in results} == {None, "halt"}
    assert any(not r.halted and not r.error for r in results)
    assert any(r.code != code for code, r in zip(corpus, results, strict=True))
    assert underload("((yes)S)^", "")[-1].output == "yes"
    assert not underload("(:^):^", "")[-1].halted

    class MissingSplice(_Machine):
        def step(self):
            program, at, stack = self.state
            if at < len(program) and program[at] == "^" and stack:
                self.state = program, at + 1, stack[:-1]
            else:
                super().step()

    with pytest.raises(AssertionError):
        _check(MissingSplice, "((yes)S)^")

    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), "((yes)S)^")
    for code, bits in (
        ("", 0),
        ("(x)", 10),
        ("(x)!", 11),
        ("()^", 2),
        ("((yes)S)^", 172),
    ):
        rows = _check(_Machine, code, "")
        assert charged_bits(_WORKSPACE, map(_parts, rows)) == bits

    class WrongText(_Machine):
        def __init__(self, code, io):
            super().__init__(code, io)
            write = io.print_str
            io.print_str = lambda text: write("X" * len(text))

    with pytest.raises(AssertionError):
        _check(WrongText, "((yes)S)^")
