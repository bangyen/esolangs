"""Revision 195344 operations; the repo fixes greeting and song punctuation."""

import itertools
import random
from functools import cache

import pytest

from esolangs.languages.hq9.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import WorkspaceWitness, missing_workspace


@cache
def _song():
    names = ["no more bottles", "1 bottle", *(f"{n} bottles" for n in range(2, 100))]
    verses = []
    for n in reversed(range(100)):
        first = f"{names[n]} of beer on the wall, {names[n]} of beer."
        last = (
            f"Take one down and pass it around, {names[n - 1]}"
            if n
            else "Go to the store and buy some more, 99 bottles"
        )
        verses.append(
            first[0].upper() + first[1:] + "\n" + last + " of beer on the wall.\n"
        )
    return "\n".join(verses)


def _model(source):
    output = ""
    trace = [((0, 0, source, (0,)), not source, "", 0, 0)]
    for i, char in enumerate(source[:64]):
        if char in "Hh":
            output += "Hello, world!\n"
        elif char in "Qq":
            output += source
        elif char == "9":
            output += _song()
        acc = source[: i + 1].count("+")
        trace.append(((i + 1, acc, source, (acc,)), i + 1 == len(source), output, 0, 0))
    if len(source) <= 64:
        trace.extend([trace[-1]] * 3)
    return None, trace


def _agrees(factory, source):
    expected = _model(source)

    views = iter(expected[1])
    witness = WorkspaceWitness(
        WorkspaceModel("hq9-v1", ("instruction", "accumulator", "input_cursor"))
    )

    def state(m):
        view, _halted, _output, _position, progress = next(views)
        instruction, accumulator, _source, _memory = view
        witness.sample(m.workspace_snapshot(), (instruction, accumulator, progress))
        return (*m.state, m.code, tuple(m.memory))

    assert observed(factory, source, "λ\nunused", state) == expected, source


def check_raw_hq9():
    atoms = "HhQq+x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += ["".join(rng.choices(atoms, k=16)) for _ in range(128)]
    corpus += ["9", "99", "+9Q", "H9h", "Q\x00λ\n", "+" * 80, "λ\n"]
    corpus.append("Q" + "+" * 80)
    for source in corpus:
        _agrees(_Machine, source)
    assert len(_song().split("\n\n")) == 100
    controls = {
        "case": "h",
        "quine": "Qq",
        "acc": "+",
        "song": "9",
        "input": "+",
        "posthalt": "H",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode in {"song", "quine"}:
                    write = io.print_str
                    io.print_str = lambda text: write(
                        "Q" if self.mode == "quine" else text[: text.rfind("\n\n") + 2]
                    )
                super().__init__(code, io)

            def step(self):
                pc, accumulator = self.state
                if self.halted:
                    if self.mode == "posthalt":
                        self.state = pc, accumulator + 1
                    super().step()
                    return
                if self.mode == "case" and self.code[pc] == "h":
                    self.state = pc + 1, accumulator
                    return
                if self.mode == "input":
                    self.io.input_char()
                super().step()
                if self.mode == "acc":
                    self.state = self.ip, 0

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    for component in ("instruction", "accumulator", "input_cursor"):
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "++Q")
    return len(corpus), len(controls) + 3
