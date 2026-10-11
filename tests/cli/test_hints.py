"""Hints attached to source, runtime and detector errors."""

import pytest

import esolangs
from esolangs import vm
from esolangs._execution import interpreter_errors
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.source_hints import keyword_hint
from esolangs.raster import Raster
from esolangs.vm import make_vm
from tests.api.test_language_coupling import REFERENCE


@pytest.mark.medium
def test_vm_load_retains_the_delimiter_and_position():
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        make_vm(REFERENCE, "[", stdin="")
    assert str(caught.value) == "unmatched '[' at position 0"
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.medium
def test_isolated_error_keeps_the_hint():
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        esolangs.run("brainfuck", "[", isolated=True)
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.parametrize(
    ("word", "hint"),
    [
        ("push", "did you mean 'PUSH'?"),
        ("PUHS", "did you mean 'PUSH'?"),
        ("PRP", "use a command"),
        ("XYZ", "use a command"),
    ],
)
def test_keyword_hint_refuses_ambiguity(word, hint):
    assert keyword_hint(word, ("PUSH", "POP", "PRT"), "use a command") == hint


def test_input_hint_is_available_to_direct_interpreter_callers():
    with pytest.raises(
        esolangs.ArgumentError, match="input must be an integer"
    ) as caught:
        ScriptedIO("oops").input_num()
    assert "decimal integer" in caught.value.__notes__[0]


def test_bad_png_hint_survives_exception_translation():
    with pytest.raises(esolangs.ProgramError, match="bad signature") as caught:
        Raster.from_png(b"not an image")
    assert "export the image as PNG" in caught.value.__notes__[0]


@pytest.mark.medium
def test_text_encoding_hint_is_available_before_interpreter_loading():
    with pytest.raises(esolangs.ProgramError, match="invalid UTF-8") as caught:
        esolangs.run("brainfuck", b"\xff", timeout=1)
    assert caught.value.__notes__ == [
        "hint: save the text program as UTF-8 before running it"
    ]


def test_value_error_hint_without_language_context():
    with (
        pytest.raises(esolangs.ProgramError) as caught,
        interpreter_errors("recursion"),
    ):
        raise ValueError("malformed operand")
    assert str(caught.value) == "malformed operand"
    assert caught.value.__notes__ == [
        "hint: check the operands and input against the language's syntax"
    ]


def test_truncated_png_header_has_a_recovery_hint():
    import struct
    import zlib

    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 0) + b"IHDR"
    data += struct.pack(">I", zlib.crc32(b"IHDR") & 0xFFFFFFFF)
    with pytest.raises(esolangs.ProgramError, match="not a readable PNG") as caught:
        Raster.from_png(data)
    assert caught.value.__notes__ == [
        "hint: restore or re-export the drawing as a valid PNG"
    ]


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.medium
def test_input_exhaustion_keeps_counts_and_one_hint(isolated):
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        # 10s: an isolated spawn under a loaded full run took over 2s.
        esolangs.run("brainfuck", "+.,", timeout=10, isolated=isolated)
    assert caught.value.partial_output == "\x01"
    assert caught.value.reads == caught.value.supplied == 0
    hints = [note for note in caught.value.__notes__ if note.startswith("hint:")]
    assert len(hints) == 1
    assert "at least 1 input character" in hints[0]


@pytest.mark.medium
def test_timeout_hint_preserves_the_timeout_class():
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run("brainfuck", "+[]", max_steps=3)
    assert "check loop termination" in caught.value.__notes__[0]
    assert "before increasing" in caught.value.__notes__[0]


def test_recursion_limit_has_a_depth_hint():
    with (
        pytest.raises(esolangs.InterpreterLimitError) as caught,
        interpreter_errors("too deep"),
    ):
        raise RecursionError("internal recursion")
    assert str(caught.value) == "too deep"
    assert caught.value.__notes__ == [
        "hint: reduce expression nesting or recursion depth"
    ]


def test_missing_dependency_hint_names_the_environment(monkeypatch):
    from esolangs.raster import png
    from esolangs.raster.png import _require_image

    monkeypatch.setattr(png, "Image", None)
    with pytest.raises(esolangs.MissingDependencyError) as caught:
        _require_image()
    assert "esolangs[image]" in str(caught.value)
    assert "Python environment running esolangs" in caught.value.__notes__[0]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "language", "source", "message", "hint"),
    [
        (
            "run_until_halt_or_cycle",
            "brainfuck",
            "+[]",
            "undecided after 0 steps: neither halted nor repeated a state",
            "supported growth detector",
        ),
        (
            "run_until_halt_or_growth",
            "brainfuck",
            "+[]",
            (
                "undecided after 0 steps: neither halted nor grew "
                "by a provable translation"
            ),
            "run_until_halt_or_cycle",
        ),
    ],
)
def test_detector_bounds_preserve_the_exact_diagnostic(
    detector, language, source, message, hint
):
    machine = vm.make_vm(language, source)
    with pytest.raises(TimeoutError) as caught:
        getattr(vm, detector)(machine, limit=0)
    assert type(caught.value) is TimeoutError
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


def test_cycle_detector_requires_a_snapshot_machine():
    with pytest.raises(TypeError) as caught:
        vm.run_until_halt_or_cycle(object())
    assert str(caught.value) == (
        "object is not steppable with a snapshot: neither it nor any machine "
        "it wraps provides the required members"
    )
    assert "step, halted and snapshot" in caught.value.__notes__[0]
