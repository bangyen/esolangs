"""Independent byte ordering, EOF, branching and self-modification controls."""

import importlib
import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import INTERPRETERS
from tests.interpreters.semantic_oracles import (
    Observation,
    boolfuck,
    cyclic_tag,
    smallfuck,
    subleq,
)

ORACLES = {
    "Boolfuck": boolfuck,
    "Subleq": subleq,
    "Cyclic tag": cyclic_tag,
    "Smallfuck": smallfuck,
}


def observed(language, code, stdin, cap):
    module = importlib.import_module(INTERPRETERS[language])
    io = ScriptedIO(stdin)
    machine = module._Machine(code, io)  # noqa: SLF001
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    if machine.halted and getattr(machine, "dumps_on_the_post_halt_step", False):
        machine.step()
    if language == "Cyclic tag":
        assert machine.stack == []
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


def cyclic_tag_corpus():
    words = [
        "".join(bits) for n in range(3) for bits in itertools.product("01", repeat=n)
    ]
    for count in (1, 2):
        for rules in itertools.product(words, repeat=count):
            for data in words:
                yield ";".join(rules) + "," + data
    yield from [" 1;  ;\t0, 1\n0", "\u2003;\n1;\t, 10", " ; ; , ", "11,1"]
    rng = random.Random(1703)
    for _ in range(64):
        rules = [
            "".join(rng.choices("01", k=rng.randrange(5)))
            for _ in range(rng.randrange(1, 6))
        ]
        yield ";".join(rules) + "," + "".join(rng.choices("01", k=rng.randrange(9)))


@pytest.mark.parametrize(
    ("language", "corpus"),
    [
        ("Boolfuck", boolfuck_corpus),
        ("Subleq", subleq_corpus),
        ("Cyclic tag", cyclic_tag_corpus),
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
        ("Cyclic tag", "", ValueError),
        ("Cyclic tag", "1", ValueError),
        ("Cyclic tag", "1,,0", ValueError),
        ("Cyclic tag", "x,1", ValueError),
        ("Cyclic tag", "1,0;1", ValueError),
        ("Cyclic tag", ",2", ValueError),
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
        ("Subleq", "6 -1 0 6 6 -1 -1", "\xff"),
        ("Smallfuck", ">>*", "1"),
        ("Smallfuck", "<", "0"),
        ("Smallfuck", ">", "0"),
        ("Cyclic tag", ",", ""),
        ("Cyclic tag", ",1", "1"),
        ("Cyclic tag", "0;,1", "0"),
    ],
)
def test_oracle_positive_controls(language, code, output):
    result = ORACLES[language](code, "\x81", 200)
    assert result.halted
    assert result.output == output
    assert observed(language, code, "\x81", 200) == result


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("Boolfuck", "+[]"),
        ("Subleq", "0 0 0"),
        ("Smallfuck", "*[]"),
        ("Cyclic tag", "1,1"),
        ("Cyclic tag", "11,1"),
    ],
)
def test_step_cap_never_counts_as_a_halt(language, code):
    result = ORACLES[language](code, "", 200)
    assert not result.halted
    assert observed(language, code, "", 200) == result


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Boolfuck", "Subleq", "Cyclic tag", "Smallfuck"])
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
        if language == "Cyclic tag":
            io = ScriptedIO("unused")
            module = importlib.import_module(INTERPRETERS[language])
            module.run(source, io)
            assert io.getvalue() == expected
            assert io.position() == 0


@pytest.mark.parametrize("cap", [0, 1, 2, 17, 200])
def test_cyclic_tag_schedule_and_dump_at_step_boundaries(cap):
    for code in cyclic_tag_corpus():
        expected = cyclic_tag(code, "ignored input", cap)
        assert observed("Cyclic tag", code, "ignored input", cap) == expected, (
            code,
            cap,
        )


def test_cyclic_tag_dumps_final_deletion_once_without_reading_stdin():
    module = importlib.import_module(INTERPRETERS["Cyclic tag"])
    io = ScriptedIO("unused")
    machine = module._Machine("0;,1", io)  # noqa: SLF001
    machine.step()
    machine.step()
    assert machine.halted
    assert io.getvalue() == ""
    machine.step()
    assert io.getvalue() == cyclic_tag("0;,1", "unused", 2).output == "0"
    machine.step()
    assert io.getvalue() == "0"
    assert io.position() == 0


@pytest.mark.medium
@pytest.mark.parametrize("table", [format(value, "08b") for value in range(256)])
def test_cyclic_tag_every_three_input_table_in_independent_engine(table):
    template = esolangs.generate("Cyclic tag", table)
    for row, answer in enumerate(table):
        bits = [int(bit) for bit in format(row, "03b")]
        source = esolangs.instantiate("Cyclic tag", template, bits)
        result = cyclic_tag(source, "", 200)
        assert result.halted, (table, row)
        assert result.output == answer, (table, row)
        assert observed("Cyclic tag", source, "", 200) == result, (table, row)
        module = importlib.import_module(INTERPRETERS["Cyclic tag"])
        io = ScriptedIO("unused")
        module.run(source, io)
        assert io.getvalue() == answer
        assert io.position() == 0


def test_cyclic_tag_snapshot_distinguishes_growth_at_equal_program_position():
    module = importlib.import_module(INTERPRETERS["Cyclic tag"])
    machine = module._Machine("11,1", ScriptedIO())  # noqa: SLF001
    machine.step()
    before = machine.snapshot()
    cursor = machine.ip
    machine.step()
    assert machine.ip == cursor
    assert machine.live == "111"
    assert machine.snapshot() != before


@pytest.mark.parametrize("source", [" , 1 ", "1;0,", "0;0,10", "00,01"])
def test_cyclic_tag_run_matches_reference_controls(source):
    result = cyclic_tag(source, "unused", 200)
    assert result.halted
    io = ScriptedIO("unused")
    module = importlib.import_module(INTERPRETERS["Cyclic tag"])
    module.run(source, io)
    assert io.getvalue() == result.output
    assert io.position() == 0
