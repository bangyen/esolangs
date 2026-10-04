"""Generated source retains dialect choices through public execution workflows."""

import pickle
from io import StringIO

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs.tagged import _Tagged
from esolangs.vm import complete_vm, make_vm
from tests.test_public_dialects import CASES


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
@pytest.mark.parametrize("balance", [False, True])
def test_generated_settings_are_reused(language, settings, balance):
    source = esolangs.generate(language, "0110", balance=balance, settings=settings)
    assert source.settings is settings
    assert esolangs.evaluate(language, source, inputs=2) == "0110"
    assert "".join(esolangs.iter_evaluate(language, source, inputs=2)) == "0110"
    bound = esolangs.Language(language)
    assert bound.evaluate(source, inputs=2) == "0110"
    for row, expected in enumerate("0110"):
        bits = tuple(map(int, format(row, "02b")))
        if esolangs.describe(language)["parameterized"]:
            program = esolangs.instantiate(language, source, bits, truth_table="0110")
            assert program.settings is settings
            stdin = ""
        else:
            program, stdin = source, esolangs.encode_inputs(language, bits, "0110")
        assert (
            esolangs.read_answer(language, esolangs.run(language, program, stdin))
            == expected
        )
        assert (
            esolangs.read_answer(
                language, esolangs.run(language, program, stdin, max_steps=100_000)
            )
            == expected
        )
        assert (
            esolangs.read_answer(
                language, complete_vm(make_vm(language, program, stdin), 100_000)
            )
            == expected
        )


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Alight", "Bitdeque", "Line"])
def test_isolation_retains_settings(language):
    settings = dict(CASES)[language]
    program = esolangs.generate(language, "0110", settings=settings, balance=True)
    assert esolangs.evaluate(language, program, inputs=2, isolated=True) == "0110"


@pytest.mark.parametrize("template", [False, True])
def test_text_pickle_retains_settings(template):
    settings = DialectSettings(index_base=1)
    source = esolangs.generate("Bitdeque", "0110", settings=settings)
    if not template:
        source = esolangs.instantiate("Bitdeque", source, [1, 0])
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings == settings
    assert type(restored) is type(source)
    if template:
        restored = esolangs.instantiate("Bitdeque", restored, [1, 0])
    assert esolangs.run("Bitdeque", restored) == "1"


@pytest.mark.parametrize("balance", [False, True])
def test_raster_scaling_retains_settings(balance):
    settings = DialectSettings(cell_modulus=2, tape_size=2, boundary="wrap")
    source = esolangs.generate(
        "Line", "01", scale=2, balance=balance, settings=settings
    )
    assert source.settings is settings
    assert source.tagged(source.language).settings is settings
    assert source.upscaled().settings is settings
    assert source.upscaled(2).settings is settings
    assert esolangs.run("Line", source, "1") == "1"
    assert Raster.from_png(source.to_png()).settings is None
    assert source.tagged("Piet").settings is None


def test_partial_overrides_merge_and_validate_dependencies():
    settings = DialectSettings(cell_modulus=2, tape_size=1, eof="unchanged")
    source = _Tagged("+>,+.", "brainfuck", settings)
    assert (
        esolangs.run("Brainfuck", source, settings=DialectSettings(boundary="wrap"))
        == "\x00"
    )
    assert (
        esolangs.run("Brainfuck", source, settings=DialectSettings(eof="zero"))
        == "\x01"
    )
    assert source.settings is settings
    with pytest.raises(esolangs.ArgumentError, match="wrap requires"):
        esolangs.run(
            "Brainfuck",
            source,
            settings=DialectSettings(boundary="wrap", tape_size=None),
        )
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run("Brainfuck", source, settings={})


@pytest.mark.parametrize("isolated", [False, True])
def test_loaded_text_tag_is_respected(isolated):
    source = _Tagged("+,.", "brainfuck", DialectSettings(eof="unchanged"))
    stream = StringIO()
    stream.read = lambda: source
    assert esolangs.run("Brainfuck", stream, isolated=isolated) == "\x01"
    stream = StringIO()
    stream.read = lambda: source
    assert complete_vm(make_vm("Brainfuck", stream), 10) == "\x01"


def test_plain_text_needs_explicit_settings():
    settings = DialectSettings(index_base=1)
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    assert not hasattr(str(template), "settings")
    filled = esolangs.instantiate("Bitdeque", str(template), [1, 0], settings=settings)
    assert filled.settings is settings
    assert esolangs.run("Bitdeque", filled) == "1"


def test_foreign_language_guard_precedes_retained_choices():
    source = esolangs.generate(
        "Alight", "01", settings=DialectSettings(expression_syntax="postfix")
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run("Brainfuck", source)


def test_empty_tag_metadata_and_template_override():
    source = esolangs.generate("Brainfuck", "01")
    assert source.settings is None
    assert (
        esolangs.run("Brainfuck", source, "1", settings=DialectSettings(eof="zero"))
        == "1"
    )
    settings = DialectSettings(index_base=1)
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    filled = esolangs.instantiate(
        "Bitdeque", template, [1, 0], settings=DialectSettings()
    )
    assert filled.settings == settings
    assert esolangs.run("Bitdeque", filled) == "1"


def test_inherited_choices_are_checked_before_input():
    from tests.test_public_dialects import Unreadable

    source = _Tagged("+.", "brainfuck", DialectSettings(tape_size=0))
    with pytest.raises(esolangs.ArgumentError, match="tape_size"):
        esolangs.run("Brainfuck", source, Unreadable())


def test_evaluation_inherits_loaded_metadata():
    source = _Tagged(",.", "brainfuck", DialectSettings(cell_modulus=256, eof="zero"))
    stream = StringIO()
    stream.read = lambda: source
    assert esolangs.evaluate("Brainfuck", stream, inputs=1) == "01"


def test_default_pickle_has_no_retained_choices():
    source = esolangs.generate("Brainfuck", "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run("Brainfuck", restored, "1") == "1"


def test_generation_rejects_untyped_settings():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.generate("Brainfuck", "01", settings={})
