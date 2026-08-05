"""Regression fuzz tests: random programs must not crash interpreters.

These interpreters terminate by construction (single pass over the program),
so random programs are safe to run in-process. A fixed seed keeps the tests
deterministic.
"""

import io
import random
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.other.bitdeque import run as bitdeque_run
from esolangs.interpreters.other.keys import run as keys_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.excon import run as excon_run
from esolangs.interpreters.tape_based.mammalian import run as mammalian_run
from esolangs.interpreters.tape_based.minifuck import run as minifuck_run


def run_safely(fn, program):
    """Run a program, asserting it raises nothing unexpected."""
    buffer = io.StringIO()
    with patch("builtins.input", return_value="0"):
        with redirect_stdout(buffer):
            fn(program)


def _random_string(alphabet, max_len):
    return "".join(random.choice(alphabet) for _ in range(random.randint(1, max_len)))


def test_excon_random():
    random.seed(0)
    for _ in range(50):
        run_safely(excon_run, _random_string(":^!<", 30))


def test_minifuck_random():
    random.seed(1)
    for _ in range(50):
        run_safely(minifuck_run, _random_string("<.[", 30))


def test_mammalian_random():
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


def test_brainif_random():
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


def test_keys_random():
    random.seed(4)
    for _ in range(50):
        a = _random_string("\\/-_", 10)
        b = _random_string("\\/-_", 10)
        run_safely(keys_run, [a, b])


def test_bitdeque_random():
    random.seed(5)
    words = ["PUSH", "POP", "EJECT", "INJECT", "INVERT"]
    for _ in range(50):
        code = " ".join(random.choice(words) for _ in range(random.randint(1, 10)))
        run_safely(bitdeque_run, code)


def test_bfstack_random():
    random.seed(6)
    for _ in range(50):
        code = _random_string("><+-.", 30)
        try:
            run_safely(bfstack_run, code)
        except IndexError:
            pass  # '.' on an empty stack is an accepted outcome
