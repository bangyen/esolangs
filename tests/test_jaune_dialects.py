"""Jaune choices preserve generated functions and change gap witnesses."""

from itertools import product

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.jaune import run
from esolangs.tools.jaune import jaune


def execute(source, stdin="", **options):
    io = ScriptedIO(stdin)
    run(source, io, **options)
    return io.getvalue()


@pytest.mark.parametrize("source", ["9?^.", "9!^.", "9@^.", "v?^.", "v!^.", "v@^."])
@pytest.mark.parametrize("policy", ["error", "halt", "ignore"])
def test_unresolved_targets(source, policy):
    if policy == "error":
        with pytest.raises(esolangs.HaltError, match="undefined"):
            execute(source, "9", undefined_targets=policy)
    else:
        assert execute(source, "9", undefined_targets=policy) == (
            "0" if policy == "ignore" else ""
        )


@pytest.mark.parametrize("source", ["v^.", "v+^.", "v-^.", "v?^.", "v!^.", "v@^."])
def test_eof_unchanged_skips_read_operands(source):
    assert execute("7+" + source, eof="unchanged") == "7"


@pytest.mark.parametrize(("policy", "expected"), [("zero", "0"), ("minus_one", "-1")])
def test_eof_supplies_integer(policy, expected):
    assert execute("7+v^.", eof=policy) == expected


def test_eof_integer_is_a_runtime_target():
    assert execute("v@^.0$+;", eof="zero") == "1"
    assert execute("v@^.-1$2+;", eof="minus_one") == "2"


def test_cells_and_hold_wrap():
    assert execute("3+#>&^<2-^v^v+^v-^%^.", "5 3 4", cell_modulus=2) == "111000"


@pytest.mark.parametrize("boundary", ["wrap", "clamp"])
def test_finite_boundary_reaches_zero_initialized_cells(boundary):
    expected = "01" if boundary == "wrap" else "10"
    assert execute("+<^>^.", tape_size=3, boundary=boundary) == expected
    expected = "10" if boundary == "wrap" else "00"
    assert execute("+>>>^<^.", tape_size=3, boundary=boundary) == expected


@pytest.mark.parametrize("source", ["<.", ">>."])
def test_error_boundary(source):
    with pytest.raises(esolangs.HaltError, match="tape"):
        execute(source, tape_size=2, boundary="error")


@pytest.mark.parametrize(
    "options",
    [
        {"undefined_targets": "bad"},
        {"boundary": "wrap"},
        {"eof": "bad"},
        {"tape_size": 0},
        {"cell_modulus": 1},
    ],
)
def test_invalid_settings(options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Jaune", "^.", settings=DialectSettings(**options))


@pytest.mark.parametrize(("table", "size"), [("01", 1), ("0000", 2), ("0011", 2)])
def test_generator_capacity(table, size):
    settings = DialectSettings(tape_size=size, boundary="error")
    source = esolangs.generate("Jaune", table, settings=settings)
    assert (
        esolangs.evaluate("Jaune", source, inputs=(len(table) - 1).bit_length())
        == table
    )
    if size > 1:
        with pytest.raises(ValueError, match="tape cells"):
            jaune(table, tape_size=size - 1)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("modulus", "boundary", "eof", "targets"),
    [
        (None, "error", "error", "error"),
        (2, "wrap", "zero", "ignore"),
        (3, "clamp", "minus_one", "halt"),
        (256, "wrap", "unchanged", "error"),
    ],
)
def test_generated_corpus(modulus, boundary, eof, targets):
    settings = DialectSettings(
        cell_modulus=modulus,
        tape_size=4,
        boundary=boundary,
        eof=eof,
        undefined_targets=targets,
    )
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            for balanced in (False, True):
                source = esolangs.generate(
                    "Jaune", table, settings=settings, balance=balanced
                )
                assert esolangs.evaluate("Jaune", source, inputs=n) == table
    table = "01101001"
    source = esolangs.generate("Jaune", table, settings=settings)
    for row, bits in enumerate(product((0, 1), repeat=3)):
        assert (
            esolangs.run("Jaune", source, stdin=" ".join(map(str, bits))) == table[row]
        )


@pytest.mark.medium
def test_settings_survive_portable_isolation_and_overrides():
    settings = DialectSettings(tape_size=2, boundary="wrap", undefined_targets="ignore")
    source = esolangs.generate("Jaune", "0110", settings=settings)
    saved = esolangs.load_program("Jaune", esolangs.dump_program("Jaune", source))
    assert esolangs.evaluate("Jaune", saved, inputs=2, isolated=True) == "0110"
    assert (
        esolangs.run("Jaune", saved, stdin="1 0", settings=DialectSettings(eof="zero"))
        == "1"
    )


def test_metadata():
    choices = esolangs.describe("Jaune")["dialect_settings"]
    assert choices["undefined_targets"]["choices"] == ("error", "halt", "ignore")
    assert choices["boundary"]["requires"] == {"wrap": ("tape_size",)}


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_runtime_settings_reach_public_execution(isolated):
    from esolangs.vm import complete_vm, make_vm

    settings = DialectSettings(
        tape_size=3,
        boundary="wrap",
        eof="unchanged",
        undefined_targets="ignore",
        cell_modulus=2,
    )
    source = "+<^>^v+9@^."
    assert esolangs.run("Jaune", source, settings=settings, isolated=isolated) == "011"
    assert esolangs.run("Jaune", source, settings=settings, max_steps=20) == "011"
    assert complete_vm(make_vm("Jaune", source, settings=settings), 20) == "011"


def test_cli_portable_settings(tmp_path, capsys):
    from tests.cli_support import call_both

    document, _ = call_both(
        [
            "generate",
            "--portable",
            "--settings",
            '{"cell_modulus":2,"tape_size":2,"boundary":"wrap","undefined_targets":"halt"}',
            "Jaune",
            "0110",
        ],
        capsys,
    )
    path = tmp_path / "jaune.json"
    path.write_text(document)
    output, _ = call_both(
        [
            "evaluate",
            "--portable",
            "--inputs",
            "2",
            "Jaune",
            str(path),
        ],
        capsys,
    )
    assert output.strip() == "0110"
