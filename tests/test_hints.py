"""Hints attached to source, runtime and detector errors."""

import json
import pickle
from pathlib import Path

import pytest

import esolangs
from esolangs import vm
from esolangs._execution import interpreter_errors
from esolangs._isolated import _decode
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Parser
from esolangs.interpreters.source_hints import keyword_hint
from esolangs.raster import Raster
from esolangs.vm import make_vm
from tests.cli_support import call_both

# Actual malformed sources, including runtime validation and shared parsers.
_BAD_SOURCE = [
    ("AddSubJump", "ASJ 1", "2 to 4 address operands"),
    ("A Painter Ant", "?", "n/e/s/w"),
    ("Alight", "begin;vra x;end;", "did you mean 'var'"),
    ("Algebraic Programming Language", "1(2)", "1*(2)"),
    ("Back", "", "* halts"),
    ("B-tapemark", ">a!", "uppercase"),
    ("BF-PDA", "[", "close this '['"),
    ("brainfuck", "[", "close this '['"),
    ("BFStack", ">[", "close the loop"),
    ("BIO", "?", "complete BIO"),
    ("bit~", "{", "loop opener"),
    ("Bitdeque", "PUHS", "did you mean 'PUSH'"),
    ("Bitwise Cyclic Tag", "x,1", "program,data"),
    ("Cyclic tag", "0,1;", "semicolons only before"),
    ("Boolfuck", "[", "close this '['"),
    ("Subleq", "x", "decimal integers"),
    ("BrainIf", "if 0 move up", "move left or move right"),
    ("BrainIf", "if 0 incremnt", "did you mean 'increment'"),
    ("SLOW ACV MAMMALIAN", "PRONOUNCEE", "did you mean 'PRONOUNCE'"),
    ("Circlefuck", r"\xG0", "two hex digits"),
    ("Circuit Diagram", "?", "supported Circuit Diagram"),
    ("Clockwise", "", "ring"),
    ("Collatz Multiverse", "?", "DO PRINT"),
    ("CV(N)(C)", "ŋ", "non-nasal consonant"),
    ("Unary", "1", "only 0"),
    ("Decleq", "x", "decimal integers"),
    ("Container", "a+1", "name:"),
    ("Crement", "J 0 0", "+A, -A, +D, -D, +J or -J"),
    ("Dig", "", "@ halts"),
    ("Dimensional", "=g0", "hexadecimal digits"),
    ("EGL", "1,1:(", "pair every ("),
    ("Fargo", "% 0\n$", "pending prefix call"),
    ("Flowchart", "?", "Flowchart nodes"),
    ("Forbin", "", "main"),
    ("Grapheme", "a", "uppercase Latin"),
    ("Home Row", "l", "loop opener"),
    ("Inject", "name;", "repeat the opening"),
    ("Jaune", "?", "decimal number"),
    ("Minsky Swap", "~", "1-based jump target"),
    ("Modulous", "[JMP F]", "required operand"),
    ("NoComment", " ", "spaces and tabs"),
    ("Packlang", "?", "punctuation"),
    ("Polynomial", "x", "f(x) ="),
    ("Qoibl", "tt", "complete each expression"),
    ("RAM0", "1" * 4301, "PYTHONINTMAXSTRDIGITS"),
    ("S*bleq", "-4 0 0", "nonnegative memory address"),
    ("3D Brainfuck", "[", "close this '['"),
    ("Sophie", "#$#[", "matching partner"),
    ("Streetcode", "", "two-cell-wide street"),
    ("Super SNUSP", "", "nonempty grid"),
    ("Suffolk", "", "nonempty program"),
    ("Taglate", "\x001\ngy", "loop opener"),
    ("Vandevelo", "x?", "assign the variable"),
    ("Befunge", "", "@ halts"),
    ("FALSE", "[", "close the lambda"),
    ("FRACTRAN", "2 3/0", "nonzero denominator"),
    ("Fish", "", "; halts"),
    ("Malbolge", "?", "position-dependent"),
    ("Smallfuck", "[", "close this '['"),
    ("Thue", "a::=b", "line containing only ::="),
    ("Unlambda", "`i", "exactly two expressions"),
]


@pytest.mark.medium
@pytest.mark.parametrize("guard", [0, 1])
def test_brainif_unknown_command_is_a_cli_source_error(guard, tmp_path, capsys):
    path = tmp_path / "bad.brainif"
    path.write_text(f"if {guard} incremnt", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        call_both(["run", "BrainIf", str(path)], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "unknown BrainIf command" in captured.err
    assert "did you mean 'increment'" in captured.err


@pytest.mark.medium
@pytest.mark.parametrize("word", ["comment", "seed", "PRONOUNCEE"])
def test_mammalian_rejects_unknown_words_before_output(word):
    with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
        esolangs.run("SLOW ACV MAMMALIAN", f"PRONOUNCE {word}", timeout=1)


@pytest.mark.medium
@pytest.mark.parametrize(("language", "source", "hint"), _BAD_SOURCE)
def test_rejected_source_retains_a_repair_hint(language, source, hint):
    with pytest.raises(ValueError, match=r".+") as caught:
        esolangs.run(language, source, timeout=0.2)
    assert any(hint in note for note in caught.value.__notes__)


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", ["brainfuck", "BF-PDA", "Boolfuck", "3D Brainfuck"]
)
def test_vm_load_retains_the_delimiter_and_position(language):
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        make_vm(language, "[", "")
    assert str(caught.value) == "unmatched '[' at position 0"
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.medium
def test_vm_runtime_error_keeps_its_hint():
    vm = make_vm("Modulous", "[JMP F]", "")
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        vm.step()
    assert "required operand" in caught.value.__notes__[0]


@pytest.mark.medium
def test_isolated_error_keeps_the_hint():
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        esolangs.run("brainfuck", "[", isolated=True)
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.medium
@pytest.mark.parametrize("command", ["run", "debug"])
def test_cli_prints_runtime_hints(command, tmp_path: Path, capsys):
    source = tmp_path / "bad.mod"
    source.write_text("[JMP F]", encoding="utf-8")
    args = [command, "--timeout", "1", "Modulous", str(source)]
    with pytest.raises(SystemExit):
        call_both(args, capsys)
    streams = capsys.readouterr()
    text = streams.out + streams.err
    assert "missing operand in JMP F" in text
    assert "hint: supply the required operand" in text


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "output"),
    [
        ("brainfuck", "[]", ""),
        ("Bitdeque", "PUSH", "0"),
        ("Alight", "begin;var x;end;", ""),
        ("Packlang", "Package { Integer main { 0; } } demo;", ""),
        ("Forbin", "main { return 0; }", ""),
        ("FRACTRAN", "2 3/2", "3"),
        ("CV(N)(C)", "ci", ""),
        ("Circlefuck", r"\x40", ""),
    ],
)
def test_suggested_syntax_executes(language, source, output):
    assert esolangs.run(language, source, timeout=1) == output


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
        esolangs.run(language, source, stdin, timeout=1)
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


@pytest.mark.parametrize(
    ("message", "hint"),
    [
        ("could not convert string to float: 'x'", "decimal number"),
        ("bytes must be in range(0, 256)", "between 0 and 255"),
        ("malformed operand", "describe --spec 'A Painter Ant'"),
    ],
)
def test_unannotated_value_error_keeps_its_diagnostic(message, hint):
    with (
        pytest.raises(esolangs.ProgramError, match=r".+") as caught,
        interpreter_errors("recursion", language="A Painter Ant"),
    ):
        raise ValueError(message)
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


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
def test_tui_displays_a_runtime_hint():
    from esolangs.tui import render, replay

    frame = replay("Modulous", "[JMP F]", "", step=1)
    assert "hint: supply the required operand" in render(frame, width=120)


@pytest.mark.medium
def test_hints_do_not_discard_partial_output():
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        esolangs.run("Modulous", "[PSH INT 65][PRT][JMP F]", timeout=1)
    assert caught.value.partial_output == "A"
    assert "hint:" in caught.value.__notes__[0]
    assert "printed 'A'" in caught.value.__notes__[1]


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
        ("Modulous", "[SWP]", "SWP needs two", "push two values"),
        ("Modulous", "[RND 0]", "upper bound", "at least 1"),
        ("Alight", "begin;var v;set v 1/0;end;", "division by zero", "divisor"),
        ("Alight", "begin;out missing;end;", "no such variable", "declare"),
        ("Alight", 'begin;var v;set v at{"AB",1};end;', "0.5 + k", "0.5, 1.5"),
        ("Befunge", "10/.@", "divides by zero", "divisor"),
        ("Fish", "+", "something smells fishy", "push a value"),
        ("Fish", "10,", "something smells fishy", "nonzero divisor"),
        ("Fish", "12,[", "something smells fishy", "whole-number"),
        ("FALSE", "%", "stack is empty", "push a value"),
        ("FALSE", "1 0/", "divides by zero", "divisor"),
        ("Unsquare", "S", "swap needs two", "push 2 values"),
        ("Fargo", "% 0 nope 1\n", "undefined function", "define the function"),
        ("Fargo", "% 0 [?] [] 1 1\n", "out of range", "array bounds"),
        ("Jaune", "1@", "undefined subroutine", "define the subroutine"),
        ("Jaune", ";", "no active subroutine", "before returning"),
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
        esolangs.run("brainfuck", "+.,", timeout=2, isolated=isolated)
    assert caught.value.partial_output == "\x01"
    assert caught.value.reads == caught.value.supplied == 0
    hints = [note for note in caught.value.__notes__ if note.startswith("hint:")]
    assert len(hints) == 1
    assert "at least 1 input character" in hints[0]


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.medium
def test_runtime_error_keeps_partial_output_and_one_hint(isolated):
    with pytest.raises(HaltError) as caught:
        esolangs.run("Modulous", "[PSH INT 65][PRT][SWP]", isolated=isolated)
    assert str(caught.value) == "SWP needs two values on the stack and there are 0"
    assert caught.value.partial_output == "A"
    assert caught.value.__notes__[0] == "hint: push two values before SWP"
    assert sum(note.startswith("hint:") for note in caught.value.__notes__) == 1


@pytest.mark.medium
def test_vm_and_tui_display_runtime_hints():
    from esolangs.tui import render, replay

    machine = make_vm("Modulous", "[SWP]", "")
    with pytest.raises(HaltError) as caught:
        machine.step()
    assert caught.value.__notes__ == ["hint: push two values before SWP"]
    assert "hint: push two values" in render(replay("Modulous", "[SWP]", "", step=1))


@pytest.mark.medium
def test_cli_displays_runtime_hints(tmp_path, capsys):
    source = tmp_path / "runtime.mod"
    source.write_text("[SWP]")
    with pytest.raises(SystemExit):
        call_both(["run", "Modulous", str(source)], capsys)
    assert "hint: push two values before SWP" in capsys.readouterr().err


@pytest.mark.parametrize(
    "kind",
    [
        esolangs.InputExhaustedError,
        esolangs.ExecutionTimeoutError,
        esolangs.MissingDependencyError,
    ],
)
def test_constructor_hints_are_not_duplicated_by_isolation(kind):
    args = [0, 0, "character"] if kind is esolangs.InputExhaustedError else ["failed"]
    original = kind(*args)
    payload = {"error": kind.__name__, "args": args, "notes": original.__notes__}
    with pytest.raises(kind) as caught:
        _decode(json.dumps(payload), expired=False)
    assert str(caught.value) == str(original)
    assert caught.value.__notes__ == original.__notes__
    restored = pickle.loads(pickle.dumps(original))
    assert str(restored) == str(original)
    assert restored.__notes__ == original.__notes__


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


@pytest.mark.medium
def test_memory_limit_has_an_address_hint():
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        esolangs.run("S*bleq", "100000000000000000000 0 0", timeout=1)
    assert "smaller memory addresses" in caught.value.__notes__[0]


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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "output"),
    [
        ("Modulous", "[PSH INT 1][PSH INT 2][SWP][PRT INT][PRT INT]", "12"),
        ("Alight", "begin;var v;set v 1/1;end;", ""),
        ("Fish", "12,n;", "0.5"),
        ("FALSE", "1 1/.", "1"),
    ],
)
def test_repaired_operands_execute(language, source, output):
    assert esolangs.run(language, source, timeout=1) == output


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
            "run_until_halt_or_all_branches_cycle",
            "Modulous",
            "[RND 2][END]",
            "undecided after 0 branching states: the reachable graph may be unbounded",
            "branching state limit",
        ),
        (
            "run_until_halt_or_ancestor",
            "Forbin",
            "main { return 0; }",
            (
                "undecided after 0 pushed frames: neither halted nor repeated "
                "an ancestor's entry state"
            ),
            "pushed-frame limit",
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
        (
            "run_until_halt_or_value_growth",
            "Suffolk",
            "<",
            (
                "undecided after 0 steps: neither halted nor climbed "
                "by a provable affine step"
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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
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
def test_fixed_input_does_not_make_branch_input_forkable():
    source = "[INP INT][PRT INT][END]"
    with pytest.raises(TimeoutError) as caught:
        vm.run_until_halt_or_all_branches_cycle(vm.make_vm("Modulous", source, "42\n"))
    assert str(caught.value) == (
        "undecided: a branching transition needs input that cannot be safely forked"
    )
    assert "seeded single-path run" in caught.value.__notes__[0]
    assert "does not decide all random paths" in caught.value.__notes__[0]
    assert esolangs.run("Modulous", source, stdin="42\n", seed=1, timeout=1) == "42"


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


@pytest.mark.medium
def test_halt_and_cycle_verdicts_are_unchanged():
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+."), limit=10) is True
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+[]"), limit=10) is False
    assert (
        vm.run_until_halt_or_growth(vm.make_vm("brainfuck", "+[>+]"), limit=100)
        is False
    )
    assert (
        vm.run_until_halt_or_all_branches_cycle(vm.make_vm("Modulous", "[END]")) is True
    )
