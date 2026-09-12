r"""Regression fuzz tests: random programs must not crash interpreters."""

import importlib
import io
import random
from collections.abc import Callable
from contextlib import redirect_stdout, suppress
from typing import Any
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.queue_based.bitdeque import run as bitdeque_run
from esolangs.interpreters.register_based.bio import run as bio_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.eval import run as eval_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.minifuck import run as minifuck_run
from esolangs.interpreters.tape_based.slow_acv_mammalian import run as mammalian_run
from esolangs.vm import run_until_halt_or_all_branches_cycle

minsky_run = importlib.import_module(
    "esolangs.interpreters.register_based.minsky_swap"
).run


def run_safely(fn: Callable[..., Any], program: str | list[str]) -> None:
    r"""Run a program, asserting it raises nothing unexpected."""
    buffer = io.StringIO()
    with patch("builtins.input", return_value="0"), redirect_stdout(buffer):
        fn(program, io=IO())


def _random_string(alphabet: str, max_len: int) -> str:
    return "".join(random.choice(alphabet) for _ in range(random.randint(1, max_len)))


def test_minifuck_random() -> None:
    random.seed(1)
    for _ in range(50):
        run_safely(minifuck_run, _random_string("<.[", 30))


def test_mammalian_random() -> None:
    random.seed(2)
    words = [
        "SEED",
        "CONFLAGRATE",
        "EXCRETE",
        "CONSUME",
        "FISSION",
        "DIGEST",
        "SPRINT",
        "LEAPFROG",
        "ACCEPT",
        "PRONOUNCE",
    ]
    for _ in range(50):
        code = " ".join(random.choice(words) for _ in range(random.randint(1, 15)))
        run_safely(mammalian_run, code)


def test_brainif_random() -> None:
    random.seed(3)
    for _ in range(50):
        lines = [
            "if {} {}".format(
                random.randint(0, 5),
                random.choice(["increment", "right", "left", "output"]),
            )
            for _ in range(random.randint(1, 8))
        ]
        run_safely(brainif_run, lines)


def test_bitdeque_random() -> None:
    random.seed(5)
    words = ["PUSH", "POP", "EJECT", "INJECT", "INVERT"]
    for _ in range(50):
        code = " ".join(random.choice(words) for _ in range(random.randint(1, 10)))
        run_safely(bitdeque_run, code)


def test_bfstack_random() -> None:
    random.seed(6)
    for _ in range(50):
        code = _random_string("><+-.", 30)
        # '.' on an empty stack is an.
        with suppress(HaltError):
            run_safely(bfstack_run, code)


def test_bio_random() -> None:
    random.seed(7)
    for _ in range(50):
        # Random text is rarely a legal.
        # its commands when it loads,.
        # outcome and only an.
        with suppress(ValueError):
            run_safely(bio_run, _random_string("0O1Ixyz;{}", 30))


def test_minsky_random() -> None:
    random.seed(9)
    for _ in range(50):
        code = _random_string("+*~", 30)
        # every ~ needs a matching.
        # the end terminate instead of.
        run_safely(minsky_run, code + "\n" + " ".join(["99"] * code.count("~")))


def test_qoibl_random() -> None:
    random.seed(10)
    for _ in range(50):
        run_safely(
            qoibl_run, _random_string("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()[]{}", 30)
        )


def test_eval_random() -> None:
    random.seed(11)
    for _ in range(50):
        # empty-stack pop / evaluating.
        with suppress(HaltError):
            run_safely(eval_run, _random_string("0+-.=~^`;*?!", 30))


def test_painfuck_random_including_random_skip() -> None:
    r"""Fuzz ``y`` through every coin outcome, not one seeded outcome."""
    from esolangs.interpreters.tape_based.painfuck import _CYCLES, _Machine

    random.seed(12)
    # Input, pointer-moving, and.
    # unbounded.
    # ``y``; the ordinary fuzzer.
    # Painfuck translates source by.
    # translation so the executable.
    alphabet = "zhwqyed"

    def source_for(commands: str) -> str:
        return "".join(
            next(
                cycle[(cycle.index(command) - index) % len(cycle)]
                for cycle in _CYCLES
                if command in cycle
            )
            for index, command in enumerate(commands)
        )

    for _ in range(12):
        machine = _Machine(source_for("y" + _random_string(alphabet, 3)), IO())
        try:
            run_until_halt_or_all_branches_cycle(machine)
        except TimeoutError as error:
            pytest.fail(f"Painfuck branch fuzz was undecided: {error}")


def test_wii2d_random_turns() -> None:
    r"""Fuzz WII2D's ``?`` by exploring its four headings at each turn."""
    from esolangs.interpreters.grid_based.wii2d import _Machine

    random.seed(13)
    for _ in range(25):
        width = 4
        code = ["".join(random.choice("?.") for _ in range(width)) for _ in range(3)]
        # One start marker is required.
        # contains only a halt and the.
        start_col = random.randrange(width)
        code[-1] = code[-1][:start_col] + "!" + code[-1][start_col + 1 :]
        try:
            run_until_halt_or_all_branches_cycle(_Machine(code, IO()))
        except TimeoutError as error:
            pytest.fail(f"WII2D branch fuzz was undecided: {error}")
