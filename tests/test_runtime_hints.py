"""Runtime repair notes preserve diagnostics, output and transport."""

import json
import pickle

import pytest

import esolangs
from esolangs._execution import interpreter_errors
from esolangs._isolated import _decode
from esolangs.exceptions import HaltError
from esolangs.vm import make_vm
from tests.cli_support import call_both


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
