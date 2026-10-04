"""Execute shared Brainfuck settings and the encoded-language delegates."""

from itertools import product

import pytest

from esolangs._brainfuck import BrainfuckDialect
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import brainfuck, factor, unary
from esolangs.interpreters.tape_based.brainfuck import _Machine as BFMachine
from esolangs.interpreters.tape_based.factor import _Machine as FactorMachine
from esolangs.interpreters.tape_based.unary import _Machine as UnaryMachine
from esolangs.tools.brainfuck import brainfuck as build_bf
from esolangs.tools.factor import _encode
from esolangs.tools.factor import factor as build_factor
from tests.interpreters.test_unary import _source


@pytest.mark.medium
@pytest.mark.parametrize("modulus", [50, 255, 256, 65536, None])
@pytest.mark.parametrize("boundary", ["clamp", "wrap", "error"])
@pytest.mark.parametrize("eof", ["error", "zero", "minus_one", "unchanged"])
def test_generated_programs(modulus, boundary, eof):
    options = {
        "cell_modulus": modulus,
        "tape_size": 8,
        "boundary": boundary,
        "eof": eof,
    }
    for table in ("01", "10", "0000", "1111", "0110", "0001", "01101001"):
        n = (len(table) - 1).bit_length()
        for build, execute in ((build_bf, brainfuck.run), (build_factor, factor.run)):
            program = build(table, **options)
            for row, bits in enumerate(product("01", repeat=n)):
                io = ScriptedIO("".join(bits))
                execute(program, io, **options)
                assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", [format(value, "04b") for value in range(16)])
@pytest.mark.parametrize("modulus", [None, 50, 255, 65536])
def test_every_two_input_table(table, modulus):
    for build, execute in ((build_bf, brainfuck.run), (build_factor, factor.run)):
        program = build(table, cell_modulus=modulus)
        for row in range(4):
            io = ScriptedIO(format(row, "02b"))
            execute(program, io, cell_modulus=modulus)
            assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("eof", "expected"), [("zero", 0), ("minus_one", 254), ("unchanged", 1)]
)
@pytest.mark.parametrize("language", ["brainfuck", "factor", "unary"])
def test_delegated_eof(language, eof, expected):
    program = "+,."
    module = {"brainfuck": brainfuck, "factor": factor, "unary": unary}[language]
    source = (
        str(_encode(program))
        if language == "factor"
        else _source(program)
        if language == "unary"
        else program
    )
    io = ScriptedIO("")
    module.run(source, io, cell_modulus=255, eof=eof)
    assert io.getvalue() == chr(expected)
    with pytest.raises(EOFError):
        module.run(source, ScriptedIO(""), eof="error")


@pytest.mark.medium
@pytest.mark.parametrize("language", ["brainfuck", "factor", "unary"])
def test_delegated_width_and_wrap(language):
    program = "<-."
    module = {"brainfuck": brainfuck, "factor": factor, "unary": unary}[language]
    source = (
        str(_encode(program))
        if language == "factor"
        else _source(program)
        if language == "unary"
        else program
    )
    io = ScriptedIO("")
    module.run(source, io, cell_modulus=65536, tape_size=2, boundary="wrap")
    assert io.getvalue() == chr(65535)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("program", "boundary", "expected"),
    [
        ("<+>.", "wrap", 0),
        ("<+>.", "clamp", 0),
        (">>+<.", "clamp", 0),
        (">>+<.", "wrap", 0),
        ("<+<.", "clamp", 1),
        ("<+<.", "wrap", 0),
    ],
)
def test_finite_tape(program, boundary, expected):
    io = ScriptedIO("")
    machine = BFMachine(program, io, tape_size=2, boundary=boundary)
    while not machine.halted:
        machine.step()
    assert io.getvalue() == chr(expected)
    assert machine.ptr in (0, 1)
    assert len(machine.tape) <= 2


@pytest.mark.medium
@pytest.mark.parametrize(("program", "size"), [("<", None), (">>", 2), ("<", 2)])
def test_error_boundaries(program, size):
    with pytest.raises(HaltError, match="left the"):
        brainfuck.run(program, ScriptedIO(""), tape_size=size, boundary="error")


@pytest.mark.medium
def test_unbounded_cells_keep_literal_loop_semantics():
    machine = BFMachine("+[+]", ScriptedIO(""), cell_modulus=None)
    for _ in range(20):
        machine.step()
    assert not machine.halted
    assert machine.tape[0] > 1
    io = ScriptedIO("😀")
    brainfuck.run(",.", io, cell_modulus=None)
    assert io.getvalue() == "😀"
    machine = BFMachine("-,", ScriptedIO(""), cell_modulus=None, eof="minus_one")
    machine.step()
    machine.step()
    assert machine.tape == (-1,)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"cell_modulus": 1}, "cell_modulus"),
        ({"cell_modulus": True}, "cell_modulus"),
        ({"tape_size": 0}, "tape_size"),
        ({"boundary": "grow"}, "boundary"),
        ({"boundary": "wrap"}, "tape_size"),
        ({"eof": "ignore"}, "eof"),
    ],
)
def test_invalid_settings(options, message):
    with pytest.raises(ValueError, match=message):
        BFMachine("", ScriptedIO(""), **options)
    with pytest.raises(ValueError, match=message):
        FactorMachine("invalid", ScriptedIO(""), **options)
    with pytest.raises(ValueError, match=message):
        UnaryMachine("invalid", ScriptedIO(""), **options)


@pytest.mark.parametrize("build", [build_bf, build_factor])
def test_generator_rejects_insufficient_storage(build):
    with pytest.raises(ValueError, match="cell_modulus at least 50"):
        build("0110", cell_modulus=49)
    with pytest.raises(ValueError, match="tape cells"):
        build("0110", tape_size=4)


def test_eof_helper_and_settings_isolation():
    with pytest.raises(EOFError):
        BrainfuckDialect().exhausted(3)
    for build in (build_bf, build_factor):
        baseline = build("0110")
        build("0110", cell_modulus=None, eof="zero")
        assert build("0110") == baseline


@pytest.mark.medium
def test_finite_tapes_reject_the_growth_certificate():
    from esolangs.vm import run_until_halt_or_growth

    # A finite six-cell tape returns to the seeded cell and halts; the
    # unbounded tape's translated wave cannot certify this run.
    machine = BFMachine(
        "+[>+]", ScriptedIO(""), cell_modulus=2, tape_size=6, boundary="wrap"
    )
    before = machine.snapshot()
    with pytest.raises(TypeError, match="rightward-growing"):
        run_until_halt_or_growth(machine)
    assert machine.snapshot() == before
    for _ in range(100):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert run_until_halt_or_growth(BFMachine("+[>+]", ScriptedIO(""))) is False
    for delegate in (
        FactorMachine(str(_encode("+>")), ScriptedIO(""), tape_size=6),
        UnaryMachine(_source("+>"), ScriptedIO(""), tape_size=6),
    ):
        with pytest.raises(TypeError, match="rightward-growing"):
            run_until_halt_or_growth(delegate)


@pytest.mark.medium
def test_eof_traits_follow_each_run():
    from esolangs.vm import machine_traits

    assert machine_traits("Unary")["eof_is_a_value"]
    for eof in ("error", "zero", "minus_one", "unchanged"):
        for constructor, source in (
            (BFMachine, ""),
            (FactorMachine, "1"),
            (UnaryMachine, "0"),
        ):
            assert constructor(source, ScriptedIO(""), eof=eof).eof_is_a_value == (
                eof != "error"
            )
