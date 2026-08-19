"""Fuzz the program generators.

Random text must produce programs that round-trip through their interpreters
(where one exists) or at least generate without crashing, and random truth
tables must produce correct programs from the boolean generator.
Fixed seeds keep the tests deterministic.
"""

import importlib
import io
import random
import string
from contextlib import redirect_stdout, suppress
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.registry import BY_FUNCTION
from esolangs.tools import boolean

# generator function name -> trailing output appended after the printed text
_TRAILING = {"nevermind": "\n"}

# characters that push generators beyond their byte/ASCII range, so the
# byte- and ASCII-oriented generators exercise their documented rejections.
# é (233) sits above ASCII but in the byte range; Ā (256) and Ǆ (452) sit
# above the byte range.
_UNICODE = "\u00e9\u0100\u01c4"  # é, Ā, Ǆ

# generator function name -> Language metadata, restricted to the generators
# whose interpreter lives in-repo (so their programs round-trip).
ROUND_TRIP = {
    name: (lang.interpreter, lang.split, dict(lang.kwargs), _TRAILING.get(name, ""))
    for name, lang in BY_FUNCTION.items()
    if lang.interpreter
}

# generators whose interpreters live in extra/: no round-trip, just no crash
NO_INTERPRETER = {
    name: lang.generator
    for name, lang in BY_FUNCTION.items()
    if lang.generator and not lang.interpreter
}


def _random_text() -> str:
    pool = string.printable + _UNICODE
    return "".join(random.choice(pool) for _ in range(random.randint(1, 12)))


def test_text_generators_round_trip() -> None:
    random.seed(0)
    for _ in range(25):
        text = _random_text()
        for name, (module, split, kwargs, suffix) in ROUND_TRIP.items():
            try:
                generator = BY_FUNCTION[name].generator
                assert generator is not None
                program = generator(text)
            except ValueError:
                # every generator may document limits; the slow_acv_mammalian search
                # itself is proven total, so it may only reject for non-byte
                # characters (which _UNICODE includes)
                if name == "slow_acv_mammalian":
                    assert any(ord(c) > 255 for c in text)
                continue
            run = importlib.import_module("esolangs.interpreters." + module).run
            argument = program.splitlines() if split else program
            buffer = io.StringIO()
            try:
                with redirect_stdout(buffer):
                    run(argument, io=IO(), **kwargs)
            except SystemExit:
                assert name == "container"
            assert buffer.getvalue() == text + suffix


def test_extra_language_generators_do_not_crash() -> None:
    random.seed(1)
    for _ in range(25):
        text = _random_text()
        for _fn, fn in NO_INTERPRETER.items():
            # a generator may still document an unsupported case
            with suppress(ValueError):
                fn(text)


def test_polynomial_wide_unicode_round_trip() -> None:
    """Polynomial round-trips text with wide codepoint deltas.

    The shared fuzz pool tops out at U+01C4 (delta ~450), well below the
    range that used to corrupt float64 root-finding.  Polynomial now recovers
    instructions by factoring the integer polynomial, so ASCII-adjacent CJK
    and emoji (deltas in the thousands) must round-trip too.
    """
    random.seed(6)
    run = importlib.import_module("esolangs.interpreters.register_based.polynomial").run
    gen = BY_FUNCTION["polynomial"].generator
    assert gen is not None
    wide = "".join(
        chr(c) for c in [0x4E2D, 0x4E00, 0x1F600, 0x3042, 0x3044, 0x00E9, 0x1F642]
    )
    pool = string.printable + wide
    for _ in range(20):
        text = "".join(random.choice(pool) for _ in range(random.randint(1, 10)))
        program = gen(text)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(program, io=IO())
        assert buffer.getvalue() == text, text


def test_boolean_generators_random_tables() -> None:
    random.seed(2)
    runners = [
        (boolean.sophie, "register_based.sophie", False, ""),
        (boolean.modulous, "stack_based.modulous", False, ""),
        (boolean.brainif, "tape_based.brainif", True, ""),
        (boolean.nevermind, "register_based.nevermind", True, "\n"),
        (boolean.circlefuck, "tape_based.circlefuck", False, ""),
        (boolean.dimensional, "tape_based.dimensional", False, ""),
        (boolean.brainfuck, "tape_based.brainfuck", False, ""),
        (boolean.sbleq, "tape_based.sbleq", False, ""),
        (boolean.jaune, "tape_based.jaune", False, ""),
        (boolean.container, "other.container", True, ""),
    ]
    for n in (1, 2, 3, 4):
        for _ in range(3):
            table = "".join(random.choice("01") for _ in range(2**n))
            for builder, module, split, suffix in runners:
                program = builder(table)
                run = importlib.import_module("esolangs.interpreters." + module).run
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    buffer = io.StringIO()
                    with (
                        patch("builtins.input", side_effect=bits),
                        redirect_stdout(buffer),
                        suppress(SystemExit),
                    ):
                        run(program.splitlines() if split else program, io=IO())
                    assert buffer.getvalue() == str(int(table[combo])) + suffix


def test_dotlang_boolean_random_tables() -> None:
    """Random tables round-trip: warp names route each combination correctly.

    Dotlang's ``W~`` reads a warp name, so the input for a combination is
    the name sequence the generator's preorder-index scheme assigns to each
    read site (the user cannot type plain ``0``/``1`` lines).
    """
    from esolangs.tools.boolean.other import _dotlang_suffix

    random.seed(5)
    run = importlib.import_module("esolangs.interpreters.grid_based.dotlang").run
    for n in (1, 2, 3, 4):
        for _ in range(3):
            table = "".join(random.choice("01") for _ in range(2**n))
            program = boolean.dotlang(table)
            for combo in range(2**n):
                names: list[str] = []
                idx = 0
                for d in range(n):
                    bit = (combo >> (n - 1 - d)) & 1
                    names.append(f"{bit}{_dotlang_suffix(idx)}")
                    idx = idx + 1 + (bit * (2 ** (n - d - 1) - 1))
                buffer = io.StringIO()
                with (
                    patch("builtins.input", side_effect=names),
                    redirect_stdout(buffer),
                ):
                    run(program.splitlines(), io=IO())
                assert buffer.getvalue() == str(int(table[combo]))


def test_byte_function_generator_random_tables() -> None:
    random.seed(4)
    run = importlib.import_module("esolangs.interpreters.tape_based.circlefuck").run
    for n in (1, 2, 3):
        for _ in range(3):
            table = [random.randint(0, 255) for _ in range(2**n)]
            program = boolean.circlefuck_byte(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                buffer = io.StringIO()
                with patch("builtins.input", side_effect=bits), redirect_stdout(buffer):
                    run(program, io=IO())
                assert buffer.getvalue() == chr(table[combo])


def test_binary_generator_random_tables() -> None:
    random.seed(3)
    run = importlib.import_module("esolangs.interpreters.grid_based.dig").run
    for n in (1, 2, 3, 4):
        for _ in range(3):
            table = "".join(random.choice("01") for _ in range(2**n))
            program = boolean.dig(table)
            for combo in range(2**n):
                inputs = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                buffer = io.StringIO()
                with (
                    patch("builtins.input", side_effect=inputs),
                    redirect_stdout(buffer),
                ):
                    run(program.splitlines(), io=IO())
                assert buffer.getvalue() == str(int(table[combo]))
