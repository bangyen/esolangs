"""Fuzz the program generators.

Random text must produce programs that round-trip through their interpreters
(where one exists) or at least generate without crashing, and random truth
tables must produce correct programs from the boolean and binary generators.
Fixed seeds keep the tests deterministic.
"""

import importlib
import io
import random
import string
from contextlib import redirect_stdout
from unittest.mock import patch

import esolangs.tools.generate as gen
from esolangs.tools import binary, boolean

# generator -> (interpreter module, split lines, extra kwargs, trailing output)
ROUND_TRIP = {
    "six_five": ("tape_based.6-5", False, {}, ""),
    "ascii_art": ("tape_based.ascii-art", False, {}, ""),
    "bfstack": ("stack_based.bfstack", False, {}, ""),
    "bio": ("register_based.bio", False, {}, ""),
    "brainif": ("tape_based.brainif", True, {}, ""),
    "circlefuck": ("tape_based.circlefuck", False, {}, ""),
    "clockwise": ("other.clockwise", True, {}, ""),
    "container": ("other.container", True, {}, ""),
    "dig": ("register_based.dig", True, {}, ""),
    "dotlang": ("register_based.dotlang", True, {}, ""),
    "eval": ("stack_based.eval", False, {}, ""),
    "excon": ("tape_based.excon", False, {}, ""),
    "huf": ("register_based.huf", False, {}, ""),
    "mammalian": ("tape_based.mammalian", False, {}, ""),
    "minifuck": ("tape_based.minifuck", False, {}, ""),
    "modulous": ("stack_based.modulous", False, {}, ""),
    "nevermind": ("other.nevermind", True, {}, "\n"),
    "polynomial": ("register_based.polynomial", False, {}, ""),
    "qoibl": ("register_based.qoibl", True, {}, ""),
    "sophie": ("register_based.sophie", False, {}, ""),
    "suffolk": ("tape_based.suffolk", False, {"limit": 1}, ""),
    "temporary": ("stack_based.temporary", False, {}, ""),
    "wii2d": ("register_based.WII2D", True, {}, ""),
    "ztoalc": ("other.ztoalc", True, {}, ""),
}

# generators whose interpreters live in extra/: no round-trip, just no crash
NO_INTERPRETER = {
    "forth": gen.forth,
    "laserfuck": gen.laserfuck,
    "magnitude": gen.magnitude,
    "painfuck": gen.painfuck,
    "_123": gen._123,
    "nocomment": gen.nocomment,
    "unsquare": gen.unsquare,
    "home_row": gen.home_row,
}


def _random_text():
    return "".join(
        random.choice(string.printable) for _ in range(random.randint(1, 12))
    )


def test_text_generators_round_trip():
    random.seed(0)
    for _ in range(25):
        text = _random_text()
        for name, (module, split, kwargs, suffix) in ROUND_TRIP.items():
            try:
                program = getattr(gen, name)(text)
            except ValueError:
                assert (
                    name != "mammalian"
                )  # never rejects; everything else documents limits
                continue
            run = importlib.import_module("esolangs.interpreters." + module).run
            argument = program.splitlines() if split else program
            buffer = io.StringIO()
            try:
                with redirect_stdout(buffer):
                    run(argument, **kwargs)
            except SystemExit:
                assert name == "container"
            assert buffer.getvalue() == text + suffix


def test_extra_language_generators_do_not_crash():
    random.seed(1)
    for _ in range(25):
        text = _random_text()
        for _fn, fn in NO_INTERPRETER.items():
            try:
                fn(text)
            except ValueError:
                pass  # a generator may still document an unsupported case


def test_boolean_generators_random_tables():
    random.seed(2)
    runners = [
        (boolean.sophie, "register_based.sophie", False, ""),
        (boolean.modulous, "stack_based.modulous", False, ""),
        (boolean.brainif, "tape_based.brainif", True, ""),
        (boolean.nevermind, "other.nevermind", True, "\n"),
        (boolean.circlefuck, "tape_based.circlefuck", False, ""),
    ]
    for n in (1, 2, 3, 4):
        for _ in range(3):
            table = "".join(random.choice("01") for _ in range(2**n))
            for builder, module, split, suffix in runners:
                program = builder(table, n)
                run = importlib.import_module("esolangs.interpreters." + module).run
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    buffer = io.StringIO()
                    with patch("builtins.input", side_effect=bits):
                        with redirect_stdout(buffer):
                            run(program.splitlines() if split else program)
                    assert buffer.getvalue() == str(int(table[combo])) + suffix


def test_byte_function_generator_random_tables():
    random.seed(4)
    run = importlib.import_module("esolangs.interpreters.tape_based.circlefuck").run
    for n in (1, 2, 3):
        for _ in range(3):
            table = [random.randint(0, 255) for _ in range(2**n)]
            program = boolean.circlefuck_byte(table, n)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                buffer = io.StringIO()
                with patch("builtins.input", side_effect=bits):
                    with redirect_stdout(buffer):
                        run(program)
                assert buffer.getvalue() == chr(table[combo])


def test_binary_generator_random_tables():
    random.seed(3)
    run = importlib.import_module("esolangs.interpreters.register_based.dig").run
    for n in (1, 2, 3, 4):
        for _ in range(3):
            table = "".join(random.choice("01") for _ in range(2**n))
            bits = [int(c) for c in table]

            def fn(*args, bits=bits):
                index = 0
                for a in args:
                    index = index * 2 + int(a)
                return bits[index]

            program = binary.convert(fn, n)
            for combo in range(2**n):
                inputs = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                buffer = io.StringIO()
                with patch("builtins.input", side_effect=inputs):
                    with redirect_stdout(buffer):
                        run(program.splitlines())
                assert buffer.getvalue() == str(int(table[combo]))
