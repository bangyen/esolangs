"""Independent byte ordering, EOF, branching and self-modification controls."""

import importlib
import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.semantic_oracles import Observation, boolfuck, smallfuck, subleq

ORACLES = {"Boolfuck": boolfuck, "Subleq": subleq, "Smallfuck": smallfuck}


def observed(language, code, stdin, cap):
    module = importlib.import_module(
        f"esolangs.interpreters.tape_based.{language.lower()}"
    )
    io = ScriptedIO(stdin)
    machine = module._Machine(code, io)  # noqa: SLF001
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    if language == "Smallfuck" and machine.halted:
        machine.step()
    return Observation(
        io.getvalue(), tuple(machine.memory), machine.ip, io.position(), machine.halted
    )


def boolfuck_corpus():
    yield from (
        "".join(commands)
        for n in range(4)
        for commands in itertools.product("+<>;,", repeat=n)
    )
    yield from [
        "+[+]",
        "+[]",
        "[+;]",
        "+[>+<+]",
        "+[>+[+] <+]",
        ",;" * 17,
        "+" + ";" * 9,
        "ignored +;",
        "<+>+<;>;",
    ]
    rng = random.Random(1701)
    pieces = ["+", "<", ">", ",", ";", "[+]", "[>+<+]", "[]"]
    for _ in range(64):
        yield "".join(rng.choices(pieces, k=8))


def smallfuck_corpus():
    for n in range(5):
        yield from (
            "".join(commands) for commands in itertools.product("*<>", repeat=n)
        )
    yield from ["", "[]", "*[**]", "*[]", ">>*", "*[>*<*]", "[ignored]", "<*", ">"]
    rng = random.Random(1703)
    for _ in range(64):
        yield "".join(rng.choices(["*", "<", ">", "[**]", "[>*<*]", "[]"], k=8))


def subleq_corpus():
    yield from [
        "",
        "12 13 -1",
        "3 -1 0 321",
        "-1 9 0 9 -1 0 9 9 -1 0",
        "9 3 3 9 -1 6 9 9 -1 3",
        "12 13 6 12 -1 9 13 -1 9 12 12 -1 3 2",
        "12 13 6 12 -1 9 13 -1 9 12 12 -1 1 2",
        "0 0 0",
    ]
    rng = random.Random(1702)
    for _ in range(96):
        cells = []
        for _ in range(3):
            a, b = rng.choice([9, 10, 11]), rng.choice([9, 10, 11])
            mode = rng.randrange(3)
            if mode == 1:
                a = -1
            elif mode == 2:
                b = -1
            cells.extend([a, b, rng.choice([-1, 0, 3, 6, 12])])
        cells.extend(rng.choices([-257, -1, 0, 1, 256, 321], k=3))
        yield " ".join(map(str, cells))


@pytest.mark.parametrize(
    ("language", "corpus"),
    [
        ("Boolfuck", boolfuck_corpus),
        ("Subleq", subleq_corpus),
        ("Smallfuck", smallfuck_corpus),
    ],
)
@pytest.mark.parametrize("stdin", ["", "\x81\x02", "λ\n\xff" * 30])
def test_bounded_programs_match_independent_semantics(language, corpus, stdin):
    for code in corpus():
        try:
            expected = ORACLES[language](code, stdin, 200)
        except EOFError:
            with pytest.raises(EOFError):
                observed(language, code, stdin, 200)
        except ValueError:
            with pytest.raises(ValueError, match=r"."):
                observed(language, code, stdin, 200)
        except RuntimeError:
            with pytest.raises(esolangs.HaltError):
                observed(language, code, stdin, 200)
        else:
            assert observed(language, code, stdin, 200) == expected, (code, stdin)


@pytest.mark.parametrize(
    ("language", "code", "error"),
    [
        ("Boolfuck", "[", ValueError),
        ("Boolfuck", "]", ValueError),
        ("Smallfuck", "[", ValueError),
        ("Smallfuck", "]", ValueError),
        ("Smallfuck", "][", ValueError),
        ("Subleq", "x", ValueError),
        ("Subleq", "0", RuntimeError),
        ("Subleq", "-2 0 -1", ValueError),
    ],
)
def test_oracles_reject_invalid_programs(language, code, error):
    with pytest.raises(error):
        ORACLES[language](code, "", 200)
    runtime_error = esolangs.HaltError if error is RuntimeError else error
    with pytest.raises(runtime_error):
        observed(language, code, "", 200)


@pytest.mark.parametrize(
    ("language", "code", "output"),
    [
        ("Boolfuck", ",;" * 8, "\x81"),
        ("Boolfuck", "+;", "\x01"),
        ("Smallfuck", ">>*", "1"),
        ("Smallfuck", "<", "0"),
        ("Smallfuck", ">", "0"),
        ("Subleq", "6 -1 0 6 6 -1 -1", "\xff"),
    ],
)
def test_oracle_positive_controls(language, code, output):
    result = ORACLES[language](code, "\x81", 200)
    assert result.halted
    assert result.output == output
    assert observed(language, code, "\x81", 200) == result


@pytest.mark.parametrize(
    ("language", "code"),
    [("Boolfuck", "+[]"), ("Subleq", "0 0 0"), ("Smallfuck", "*[]")],
)
def test_step_cap_never_counts_as_a_halt(language, code):
    result = ORACLES[language](code, "", 200)
    assert not result.halted
    assert observed(language, code, "", 200) == result


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Boolfuck", "Subleq", "Smallfuck"])
@pytest.mark.parametrize(
    "table",
    [format(value, f"0{2**n}b") for n in (1, 2) for value in range(2 ** (2**n))]
    + ["00010111", "10010110", "01101001"],
)
def test_generated_programs_execute_in_independent_interpreters(language, table):
    code = esolangs.generate(language, table)
    assert isinstance(code, str)
    n = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in format(row, f"0{n}b")]
        if esolangs.describe(language)["parameterized"]:
            source, stdin = esolangs.instantiate(language, code, bits), ""
        else:
            source, stdin = code, esolangs.encode_inputs(language, bits, table)
        result = ORACLES[language](source, stdin, 100_000)
        assert result.halted, (language, table, row)
        assert result.output == expected, (language, table, row)
