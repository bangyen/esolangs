"""Qoibl parser depth regressions."""

import inspect
import sys

import pytest

import esolangs
from esolangs.interpreters.register_based.qoibl import tokenize


@pytest.mark.medium
@pytest.mark.slow
class TestTheTokenizerCarriesItsOwnStack:
    @staticmethod
    def _majority(n: int) -> str:
        return "".join(str(int(bin(r).count("1") * 2 > n)) for r in range(2**n))

    def test_a_program_past_the_old_wall_tokenizes(self) -> None:
        """4929 characters, against a default limit of 1000.

        Twelve inputs, not the six this needed when a program cost a
        Shannon tree: the table now rides in one literal, so a six-input
        majority is 513 characters and would clear the old wall by being
        small rather than by the tokenizer carrying its own stack.
        """
        program = esolangs.generate("Qoibl", self._majority(12))
        assert len(program) > 3000
        assert tokenize(program)

    def test_it_runs_under_a_limit_far_below_the_old_need(self) -> None:
        """The direct measure of shallowness, and it needed 1375 before.

        The ceiling is set relative to the stack this test is already
        standing on -- lowering the limit below the live depth kills the
        interpreter outright, and pytest's own frames are not a constant.
        """
        program = esolangs.generate("Qoibl", self._majority(6))
        stdin = esolangs.encode_inputs("Qoibl", [0] * 6, self._majority(6))
        live = len(inspect.stack())
        previous = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(live + 200)
            assert esolangs.run("Qoibl", program, stdin, timeout=120).endswith("0")
        finally:
            sys.setrecursionlimit(previous)
