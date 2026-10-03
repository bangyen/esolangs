"""Independent CV(N)(C) function validity and arithmetic checks."""


# ruff: noqa: RUF001 -- IPA commands are the language alphabet.

import itertools

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.cvnc import _applied, _Machine, run
from tests.interpreters.cvnc_reference import Reference, applied


def check(function, accumulator):
    try:
        expected = applied(accumulator, function)
    except HaltError:
        with pytest.raises(HaltError):
            _applied(accumulator, function)
    else:
        assert _applied(accumulator, function) == expected, (function, accumulator)


@pytest.mark.medium
def test_function_syntax_before_arithmetic():
    symbols = ("a", "0", "2", "+", "-", "*", "/", "(", ")")
    for length in range(5):
        for function in itertools.product(symbols, repeat=length):
            for accumulator in (0, 1, 7):
                check(function, accumulator)


@pytest.mark.medium
def test_function_precedence_unsigned_subtraction_and_parentheses():
    atoms = (("a",), ("0",), ("3",), ("(", "a", "-", "3", ")"))
    for left, middle, right in itertools.product(atoms, repeat=3):
        for first, second in itertools.product(("+", "-", "*", "/"), repeat=2):
            function = (*left, first, *middle, second, *right)
            for accumulator in (0, 1, 2, 5, 256):
                check(function, accumulator)


@pytest.mark.parametrize(
    ("source", "output", "halts"),
    [
        ("cəndiqipiθu", "3", True),
        ("cəndiqipibiθu", "4", False),
        ("cəndiqipi\u0294iθu", "4", False),
    ],
)
def test_public_invalid_division_function_and_positive_control(source, output, halts):
    io = ScriptedIO("")
    if halts:
        with pytest.raises(HaltError):
            run(source, io)
    else:
        run(source, io)
    assert io.getvalue() == output


def trace(source, stdin="", limit=100):
    try:
        reference = Reference(source, stdin)
    except ValueError:
        with pytest.raises(ValueError, match=r"."):
            _Machine(source, ScriptedIO(stdin))
        return None
    io = ScriptedIO(stdin)
    machine = _Machine(source, io)
    assert (machine.tokens, machine.starts, machine.pairs) == (
        reference.tokens,
        reference.starts,
        reference.pairs,
    )
    seen = set()
    for _ in range(limit):
        state = (
            reference.pointer,
            reference.accumulator,
            tuple(reference.deque),
            tuple(reference.function),
            reference.offset,
        )
        assert machine.snapshot() == state
        assert io.getvalue() == reference.output
        assert machine.halted == reference.halted
        if reference.halted or state in seen:
            return reference
        seen.add(state)
        try:
            reference.step()
        except (EOFError, HaltError) as error:
            with pytest.raises(type(error)):
                machine.step()
            assert machine.snapshot() == (
                reference.pointer,
                reference.accumulator,
                tuple(reference.deque),
                tuple(reference.function),
                reference.offset,
            )
            assert io.getvalue() == reference.output
            return reference
        machine.step()
    pytest.fail("bounded CV(N)(C) control exhausted")


@pytest.mark.medium
def test_syllables_command_sequences_and_io():
    consonants = "θfsʒpkdbt\u0261q\u0294ʡc"
    for consonant, vowel, nasal in itertools.product(
        consonants, "iəæou", ("", "m", "n", "ŋ", "ɲ")
    ):
        for stdin in ("", " -7 junk 257", "٣ 0\nΩ"):
            trace("cincon" + consonant + vowel + nasal, stdin)
    for source in (
        "",
        "s",
        "is",
        "susŋ",
        "suŋ",
        "suŋs",
        "suŋsu",
        "ci cu",
        "ci\tcu",
        "ci\rcu",
        "ci\ncu",
        "gicu",
        "ciu",
        "cimn",
        "ɰu",
        "ʋu",
        "ɰ̊u",
    ):
        trace(source)


@pytest.mark.medium
def test_loops_gotos_codepoint_and_syllable_offsets():
    sources = (
        "cuɰ̊uθuʋu",
        "ciɰuθuʋu",
        "ciɰ̊uθəʋu",
        "cuɰuθiʋu",
        "cuɰ̊uɰuθuʋuʋu",
        "soθɰ̊oθʋi",
        "ʒuɰ̊fuʒʋu",
    )
    for source in sources:
        for stdin in ("", "0", "1", "HI\x00"):
            trace(source, stdin)
    for target in range(16):
        for source in ("suɹuɰ̊uθuʋu", "sujuɰ̊uθuʋu"):
            trace(source, str(target))


@pytest.mark.slow
def test_all_small_generated_tables():
    from esolangs.tools.cvnc import cvnc

    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            raw = cvnc(table)
            for width in (None, 1, 3, 11):
                source = (
                    raw
                    if width is None
                    else "\n".join(
                        raw[at : at + width] for at in range(0, len(raw), width)
                    )
                )
                for row, expected in enumerate(table):
                    stdin = " ".join(f"{row:0{n}b}")
                    reference = trace(source, stdin, limit=10000)
                    assert reference is not None
                    assert reference.halted
                    assert reference.output == expected


@pytest.mark.medium
def test_built_functions_end_to_end():
    commands = dict(zip("a+-*/()", "dbt\u0261q\u0294ʡ", strict=True))
    for function in (
        ("a",),
        ("a", "+", "2", "*", "3"),
        ("(", "a", "+", "2", ")", "*", "3"),
        ("a", "/", "2"),
        ("a", "-", "3", "+", "2"),
        ("a", "/", "0", "+"),
        ("a", "/", "0", "("),
        ("2", "3"),
        ("a", "/", "0"),
    ):
        source = "cu"
        inputs = []
        for symbol in function:
            if symbol.isdigit():
                source += "sənpə"
                inputs.append(str(int(symbol) + 1))
            else:
                source += commands[symbol] + "ə"
        source += "suθu"
        for accumulator in (0, 1, 7, 256):
            trace(source, " ".join([*inputs, str(accumulator)]))


@pytest.mark.slow
def test_wider_generated_decoders_and_shared_arms():
    import random

    from esolangs.tools.cvnc import cvnc

    for n in (4, 5, 6):
        rng = random.Random(n)
        tables = [f"{rng.getrandbits(1 << n):0{1 << n}b}" for _ in range(3)]
        tables += [
            "0" * (1 << n),
            "1" * (1 << n),
            "01" * (1 << (n - 1)),
            "1" + "0" * ((1 << n) - 1),
        ]
        for table in tables:
            source = cvnc(table)
            for row, expected in enumerate(table):
                reference = trace(source, " ".join(f"{row:0{n}b}"), limit=10000)
                assert reference is not None
                assert reference.halted
                assert reference.output == expected


@pytest.mark.medium
def test_distinct_deque_ends_and_function_persistence():
    for push, pop in itertools.product("mn", "ŋɲpk"):
        for prefix in ("ci", "cici"):
            trace(
                prefix
                + push
                + "cici"
                + push
                + "cicici"
                + push
                + "co"
                + pop
                + "co"
                + pop
                + "θu"
            )
    for source in ("dəsusucuθu", "dəsuθuθu", "cu", "cuʔu", "cu\u030a", "cu!"):
        trace(source, "3 4")


@pytest.mark.medium
def test_input_errors_unsigned_values_and_byte_boundaries():
    for source in ("sufufəθu", "ʒufufəθu", "susuθu", "ʒuʒuθu"):
        for stdin in (
            "",
            " \n\t",
            "-7",
            "junk",
            "127",
            "128",
            "255",
            "256",
            "257",
            "³",
            "٣ 0",
            "Ω\x00",
            "3 junk",
        ):
            trace(source, stdin)
