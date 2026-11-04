"""Raw BFStack corpus, including lazy bracket errors and a broken push control."""

import itertools
import random

import pytest

from esolangs.languages.bfstack.interpreter import _Machine
from tests.interpreters.stack_oracles import agrees_stack, bfstack


def check_raw_bfstack() -> None:
    corpus = list(
        map(
            "".join,
            itertools.chain.from_iterable(
                itertools.product("><+-,.[]x", repeat=n) for n in range(4)
            ),
        )
    )
    corpus += [
        ">+[",
        ">[",
        ">+[]",
        ">+[>+<-]>.",
        ",[.<,]",
        ">[[+]]",
        ">+[[",
        ">+<]",
        ">[[]",
        ">" + "+" * 256 + ".",
        ">-.",
    ]
    rng = random.Random(20261102)
    corpus += [
        "".join(
            rng.choices([">", "<", "+", "-", ",", ".", "[", "]", "[-]", "[>+<-]"], k=8)
        )
        for _ in range(64)
    ]
    results = []
    results.extend(
        agrees_stack(_Machine, bfstack, code, stdin)[-1]
        for stdin in ("", "\x00\xff", "A\nB", "λ")
        for code in corpus
    )
    assert {r.error for r in results} == {None, "input", "syntax", "halt"}
    assert any(not r.halted and not r.error for r in results)
    assert any(r.loops and r.halted for r in results)
    assert bfstack(">+[", "")[-1].loops == (2,)
    assert bfstack(">[", "")[-1].halted
    assert bfstack(">-.", "")[-1].output == "\xff"

    class WrongPush(_Machine):
        def step(self):
            push = not self.halted and self.code[self.ip] == ">"
            super().step()
            if push:
                self.state = type(self.state)(self.ind, (*self.stk[:-1], 1), self.lst)

    with pytest.raises(AssertionError):
        agrees_stack(WrongPush, bfstack, ">+.")
