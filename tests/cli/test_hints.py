"""Hints attached to source, runtime and detector errors."""

import pytest

import esolangs
from esolangs import vm
from esolangs._execution import interpreter_errors
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other._packlang_parse import _Parser
from esolangs.interpreters.source_hints import keyword_hint
from esolangs.raster import Raster
from esolangs.vm import make_vm


@pytest.mark.medium
@pytest.mark.parametrize("language", ["brainfuck", "BF-PDA", "Boolfuck"])
def test_vm_load_retains_the_delimiter_and_position(language):
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        make_vm(language, "[", stdin="")
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


def test_datatype_typo_uses_the_parser_vocabulary():
    with pytest.raises(ValueError, match="unknown datatype") as caught:
        _Parser(["Intger"]).parse_type()
    assert caught.value.__notes__ == ["hint: did you mean 'Integer'?"]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "stdin", "hint"),
    [
        ("Modulous", "[PSH INT nope]", "", "decimal integer"),
        ("Modulous", "[PSH INT -1][PRT]", "", "between 0 and 1114111"),
        ("Dimensional", "x", "oops", "base-16 integer"),
        ("3x", "?", "nope", "fraction with nonzero denominator"),
        ("Befunge", "&@", "nope", "whitespace-separated decimal integer"),
    ],
)
def test_builtin_value_errors_get_operand_or_input_hints(language, source, stdin, hint):
    with pytest.raises(ValueError, match=r".+") as caught:
        esolangs.run(language, source, stdin=stdin, timeout=1)
    assert any(hint in note for note in caught.value.__notes__)


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
@pytest.mark.parametrize(
    ("language", "scale", "hint"),
    [
        ("Line", None, "dark connected paths"),
        ("Piet", 2, "dividing both image dimensions"),
    ],
)
def test_raster_interpreters_retain_geometry_hints(language, scale, hint):
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        esolangs.run(language, image, scale=scale, timeout=1)
    assert hint in caught.value.__notes__[0]


@pytest.mark.medium
def test_text_encoding_hint_is_available_before_interpreter_loading():
    with pytest.raises(esolangs.ProgramError, match="invalid UTF-8") as caught:
        esolangs.run("brainfuck", b"\xff", timeout=1)
    assert caught.value.__notes__ == [
        "hint: save the text program as UTF-8 before running it"
    ]


@pytest.mark.parametrize(
    ("function", "expression", "message", "hint"),
    [
        ("_eval", [], "malformed expression", "nonempty"),
        ("_eval", ["e", "yr"], "malformed comparison", "operator"),
        ("_eval", ["e", "ry"], "malformed arithmetic", "operator"),
        (
            "_compare",
            ["e", "yr", "BAD", "yr", "e"],
            "unrecognized comparison operator",
            "after yr",
        ),
        (
            "_arithmetic",
            ["e", "ry", "BAD", "ry", "e"],
            "unrecognized arithmetic operator",
            "after ry",
        ),
    ],
)
def test_qoibl_hand_built_expression_guards(function, expression, message, hint):
    from esolangs.interpreters.register_based import qoibl

    with pytest.raises(ValueError, match=message) as caught:
        getattr(qoibl, function)(expression, {}, lambda: 0, lambda _: None)
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "message", "hint"),
    [
        ("Modulous", "[PRT INT]", "the stack is empty", "push a value"),
        ("Modulous", "[RND 0]", "upper bound", "at least 1"),
        ("Alight", "begin;var v;set v 1/0;end;", "division by zero", "divisor"),
        ("Alight", 'begin;var v;set v at{"AB",1};end;', "0.5 + k", "0.5, 1.5"),
        ("Befunge", "10/.@", "divides by zero", "divisor"),
        ("Fish", "+", "something smells fishy", "push a value"),
        ("FALSE", "%", "stack is empty", "push a value"),
        ("Fargo", "% 0 nope 1\n", "undefined function", "define the function"),
        ("Jaune", "1@", "undefined subroutine", "define the subroutine"),
        ("Subleq", "0 0", "incomplete Subleq", "three addresses"),
        ("Painfuck", "i", HaltError.DEFAULT, "decimal integer"),
        ("Super SNUSP", '"1_{1[', "negative", "nonnegative shift"),
    ],
)
def test_runtime_hints_for_executed_programs(language, source, message, hint):
    with pytest.raises(HaltError) as caught:
        esolangs.run(
            language, source, stdin="x" if language == "Painfuck" else "", timeout=1
        )
    assert message in str(caught.value)
    assert hint in caught.value.__notes__[0]


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


def test_variable_suggestions_use_the_live_scope():
    from esolangs.interpreters.other.packlang import _get
    from esolangs.interpreters.stack_based.modulous import _named

    for lookup, scope in [(_get, (("COUNT", 1),)), (_named, {"COUNT": 1})]:
        with pytest.raises(HaltError) as caught:
            lookup(scope, "COUTN")
        assert caught.value.__notes__ == ["hint: did you mean 'COUNT'?"]


def test_internal_tree_errors_and_explicit_aborts_have_no_repair_hint():
    from esolangs.interpreters.other.packlang import _node

    with pytest.raises(HaltError) as caught:
        _node("broken internal tree")
    assert not hasattr(caught.value, "__notes__")
    assert not hasattr(HaltError(), "__notes__")


def test_root_hint_does_not_require_an_exact_root():
    from esolangs.interpreters.grid_based.super_snusp import _floor_root

    assert _floor_root(2, 2) == 1
    with pytest.raises(HaltError) as caught:
        _floor_root(-2, 2)
    assert "even degrees need nonnegative radicands" in caught.value.__notes__[0]


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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source"),
    [("Modulous", "[RND 257][END]"), ("Super SNUSP", '"999{>=')],
)
def test_larger_search_bounds_do_not_override_fixed_transition_caps(language, source):
    with pytest.raises(TimeoutError) as caught:
        vm.run_until_halt_or_all_branches_cycle(
            vm.make_vm(language, source), limit=100000
        )
    assert "cap on a single transition" in str(caught.value)
    assert "256" in caught.value.__notes__[0]
    assert "limit does not raise this transition cap" in caught.value.__notes__[0]
