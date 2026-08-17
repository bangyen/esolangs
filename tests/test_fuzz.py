"""Regression fuzz tests: random programs must not crash interpreters.

These interpreters terminate by construction (single pass over the program),
so random programs are safe to run in-process. A fixed seed keeps the tests
deterministic.
"""

import importlib
import io
import random
from collections.abc import Callable
from contextlib import redirect_stdout, suppress
from typing import Any
from unittest.mock import patch

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.queue_based.bitdeque import run as bitdeque_run
from esolangs.interpreters.register_based.bio import run as bio_run
from esolangs.interpreters.register_based.huf import run as huf_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.eval import run as eval_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.excon import run as excon_run
from esolangs.interpreters.tape_based.minifuck import run as minifuck_run
from esolangs.interpreters.tape_based.slow_acv_mammalian import run as mammalian_run

minsky_run = importlib.import_module(
    "esolangs.interpreters.register_based.minsky_swap"
).run


def run_safely(fn: Callable[..., Any], program: str | list[str]) -> None:
    """Run a program, asserting it raises nothing unexpected."""
    buffer = io.StringIO()
    with patch("builtins.input", return_value="0"), redirect_stdout(buffer):
        fn(program, io=IO())


def _random_string(alphabet: str, max_len: int) -> str:
    return "".join(random.choice(alphabet) for _ in range(random.randint(1, max_len)))


def test_excon_random() -> None:
    random.seed(0)
    for _ in range(50):
        # a pointer fault (too many <) is a valid HaltError outcome
        with suppress(HaltError):
            run_safely(excon_run, _random_string(":^!<", 30))


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
        # '.' on an empty stack is an accepted outcome
        with suppress(HaltError):
            run_safely(bfstack_run, code)


def test_bio_random() -> None:
    random.seed(7)
    for _ in range(50):
        # pop from an empty stack is an accepted outcome
        with suppress(HaltError):
            run_safely(bio_run, _random_string("0O1Ixyz;{}", 30))


def test_huf_random() -> None:
    random.seed(8)
    for _ in range(50):
        run_safely(huf_run, _random_string("#@-*0123456789", 30))


def test_minsky_random() -> None:
    random.seed(9)
    for _ in range(50):
        code = _random_string("+*~", 30)
        # every ~ needs a matching number on the jump line; jump targets past
        # the end terminate instead of self-looping
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
        # empty-stack pop / evaluating a non-string are accepted
        with suppress(HaltError):
            run_safely(eval_run, _random_string("0+-.=~^`;*?!", 30))
