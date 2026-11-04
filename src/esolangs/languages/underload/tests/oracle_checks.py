"""Nested strings, invalid commands and dynamic evaluation without a generator."""

import itertools
import random

import pytest

from esolangs.languages.underload.interpreter import _Machine
from tests.interpreters.stack_oracles import agrees_stack, underload


def check_raw_underload() -> None:
    atoms = ("()", "(x)", "((x))", "~", ":", "!", "*", "a", "^", "S", " ", "(", ")")
    corpus = list(
        map(
            "".join,
            itertools.chain.from_iterable(
                itertools.product(atoms, repeat=n) for n in range(3)
            ),
        )
    )
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
    results = []
    results.extend(
        agrees_stack(_Machine, underload, code, "unused", dynamic=True)[-1]
        for code in corpus
    )
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
        agrees_stack(MissingSplice, underload, "((yes)S)^", dynamic=True)
