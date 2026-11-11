"""Execution tests for the Unlambda interpreter."""

import re
from collections import OrderedDict
from itertools import product

import pytest

from esolangs.languages.unlambda import interpreter as native
from esolangs.languages.unlambda.interpreter import (
    _Arg,
    _Cmd,
    _Cont,
    _Ret,
    _workspace_value,
)
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import run_program
from tests.support.raises import assert_rejected_with_hint

#: The wiki's Hello world: a left-nested chain of prints, newline first.
#: Spelled from its atoms rather than by hand, because ``n`` atoms need
#: exactly ``n - 1`` backticks and miscounting them is a parse error.
_HELLO_ATOMS = ["r", *(f".{char}" for char in "Hello, world"), "i"]
HELLO = "`" * (len(_HELLO_ATOMS) - 1) + "".join(_HELLO_ATOMS)


@pytest.mark.parametrize(
    ("program", "stdin", "expected"),
    [
        pytest.param(HELLO, "", "\nHello, world", id="the_reference_greeting_prints"),
        pytest.param(
            "`@`d``|ii", "Q\n", "Q", id="the_pipe_hands_over_the_character_read"
        ),
        # The spec's no-character branch, which ``@`` cannot reach here.
        pytest.param("``|ii", "", "", id="the_pipe_before_any_read_is_v"),
        pytest.param("`@`d``|ii", "\n", "\n", id="an_empty_line_reads_as_a_newline"),
        # ``s i (k v)`` applied to the continuation applies it to v, and the
        # print after that application never runs.
        pytest.param(
            "``c``si`kv.A", "", "", id="a_continuation_abandons_the_rest_of_its_caller"
        ),
    ],
)
def test_output(program: str, stdin: str, expected: str) -> None:
    assert run_program(native.run, program, stdin) == expected


def _applicative_oracle():
    """Evaluate finite application trees using ordinary Python closures."""

    def execute(tree, output):
        if isinstance(tree, tuple):
            function, argument = tree
            return execute(function, output)(execute(argument, output))
        if tree == "i":
            return lambda value: value
        if tree == "k":
            return lambda value: lambda _discard: value
        if tree == "s":
            return lambda f: lambda g: lambda x: f(x)(g(x))

        def emit(value):
            output.append(tree[1:])
            return value

        return emit

    def encode(tree):
        if isinstance(tree, tuple):
            return chr(96) + "".join(map(encode, tree))
        return tree

    atoms = ("i", "k", ".A", ".B")
    for f, g, x in product(atoms, repeat=3):
        for tree in (
            (("k", f), g),
            ((("s", f), g), x),
            (f, (g, x)),
            ((("k", f), g), x),
        ):
            output = []
            execute(tree, output)
            io = ScriptedIO("unused")
            machine = native._Machine(encode(tree), io)
            for _ in range(128):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert io.getvalue() == "".join(output), tree
            assert io.position() == 0


def test_the_combinators() -> None:
    _applicative_oracle()
    assert run_program(native.run, "`i`.Xi") == "X"
    assert run_program(native.run, "``k`.Ai`.Bi") == "AB"  # A then B, value is A's
    assert run_program(native.run, "```s.A.Bi") == "AB"
    assert run_program(native.run, "`v`.Ai") == "A"  # the argument still evaluates


def test_d_delays_and_applying_the_promise_forces_it() -> None:
    assert run_program(native.run, "`d`.Ai") == ""  # never forced
    assert run_program(native.run, "``d`.Aii") == "A"  # forced by the application


def test_a_read_and_a_test_on_the_character() -> None:
    program = "`@`d````?0i`d`.zivi"
    assert run_program(native.run, program, "0\n") == "z"
    assert run_program(native.run, program, "1\n") == ""

    from esolangs.languages.unlambda import interpreter
    from esolangs.registry import LANGUAGES
    from scripts import tracediff

    source = "``cd``d`@|`cd"
    program = next(
        item for item in tracediff.corpus("Unlambda", 0, max_n=0) if item[0] == source
    )
    assert program == (source, "cat\n")
    events = tracediff.trace(
        interpreter, program, frozenset(), runtime=LANGUAGES["Unlambda"].runtime
    )
    assert tracediff._halts(events)
    assert events[-1][2] == "cat\n"


#: ``\b. ((b (`d `.Xi)) v)``: ``k`` keeps the promise and ``v`` swallows it,
#: so forcing the survivor with ``i`` prints X only on ``@``'s success branch.
#: ``v`` absorbs every argument, so the failure arm cannot run anything of its
#: own -- silence is what it looks like, and that is the language's, not this
#: interpreter's.
_ON_READ = "``@``s``si`k`d`.Xi`kvi"


def test_a_read_at_end_of_input_takes_the_spec_branch() -> None:
    """``@`` hands its argument ``v`` at EOF rather than letting it escape."""
    assert run_program(native.run, _ON_READ, "0\n", suppress_eof=False) == "X"
    assert run_program(native.run, _ON_READ, "", suppress_eof=False) == ""


def test_a_read_that_found_nothing_clears_the_character() -> None:
    """Wiki: ``|`` applies to ``v`` once EOF has been reached, so Q is gone."""
    assert run_program(native.run, "``k`@i``k`@i``|ii", "Q", suppress_eof=False) == ""


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("", "cannot be empty"),
        ("`i", "missing one of its two terms"),
        ("ii", "spells a second one"),
        ("`i.", "has no character after it"),
        ("z", "not an Unlambda command"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(native.run, program)


def test_the_parser_is_iterative_over_a_long_chain() -> None:
    """Parsing and logical projection preserve deep terms and DAG multiplicity."""
    from scripts.benchmark import state_bits

    depth = 5000
    term = native._parse("`" * depth + "i" * (depth + 1))
    assert isinstance(term, native._App)
    left, right = _workspace_value(term), _workspace_value(term)
    assert hash(left) == hash(right)
    assert left == right
    cache = OrderedDict()
    assert _workspace_value(term, cache) == left
    assert len(cache) == 2048
    assert state_bits(left, {}) == 8 * (depth + 1)
    shared = _Cmd("i")
    for _ in range(16):
        shared = native._App(shared, shared)
    assert state_bits(_workspace_value(shared), {}) == 8 * 2**16


def test_the_continuation_is_the_stack_the_vm_shows() -> None:
    machine = native._Machine("`.A`.Bi", ScriptedIO(""))
    machine.step()
    assert machine.stack  # a frame is waiting on the argument
    while not machine.halted:
        machine.step()
    assert not machine.stack


def test_snapshots_compare_continuations_by_their_frames() -> None:
    """Two runs build distinct linked continuations; the cycle detector
    needs them equal, and hashed alike, exactly when their frames are."""
    runs = [
        native._Machine(code, ScriptedIO(""))
        for code in ("``ci`.Ai", "``ci`.Ai", "``ci`.Bi")
    ]
    for _ in range(3):
        for machine in runs:
            machine.step()
    same, twin, other = (machine.snapshot() for machine in runs)
    assert same == twin
    assert hash(same) == hash(twin)
    for snapshot in (same, twin, other):
        restored = _state_from_wire(_state_wire(snapshot))
        assert restored == snapshot
        assert hash(restored) == hash(snapshot)
    assert same != other
    kont = runs[0].state[1]
    assert kont is not None
    for payload in ((), (1,)):
        packet = _state_wire(kont)
        packet["owned"]["value"] = _state_wire(payload)
        with pytest.raises(ValueError, match="snapshot"):
            _state_from_wire(packet)
    assert kont != kont.rest
    assert kont != kont.frames()

    from scripts.benchmark import state_bits

    continuation = native._Kont(_Arg(_Cmd("i")), None)
    machine = native._Machine("i", ScriptedIO())
    machine.state = (_Ret(_Cont(continuation)), continuation, None, False)
    saved = machine.workspace_snapshot()
    retained = {saved}
    before = state_bits(saved.parts, {})
    continuation.depth = 10**9
    machine.snapshot = lambda: ("unrelated cycle key",)
    machine._workspace_cache.clear()
    assert machine.workspace_snapshot() == saved
    assert state_bits(machine.workspace_snapshot().parts, {}) == before
    assert saved in retained
    machine.step()
    assert machine.workspace_snapshot() != saved
    assert saved in retained


def test_continuations_of_different_lengths_are_unequal() -> None:
    """A stack of one frame is not a longer stack of the same frame."""
    one = native._Kont("f", None)  # type: ignore[arg-type]
    three = native._Kont("f", native._Kont("f", native._Kont("f", None)))  # type: ignore[arg-type]
    assert one != three
    assert three != one


def test_d_applied_as_a_value_promises_what_it_was_given() -> None:
    """``d`` delays whatever is *written* after it, so reaching it as a plain
    function needs a combinator to hand it an already-evaluated argument.
    ``c`` is the one that can: it applies ``d`` to the continuation, and the
    answer is a promise of that value rather than of an unevaluated term."""
    machine = native._Machine("`cd", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert isinstance(machine.state[0].value, native._Promise)
    # Applying that promise forces it, and the continuation answers ``i``.
    assert run_program(native.run, "```cdii") == ""


def test_e_ends_the_run_before_a_pending_print() -> None:
    """``e`` ends the run while the argument is evaluating, so ``.A`` never fires."""
    assert run_program(native.run, "`.Ai") == "A"
    assert run_program(native.run, "`.A`ei") == ""


def test_a_comment_runs_to_the_end_of_the_line_or_the_source(monkeypatch) -> None:
    assert run_program(native.run, "`.A# ignored `.B\ni") == "A"
    assert run_program(native.run, "`.Ai# tail") == "A"

    from esolangs.languages.unlambda import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Unlambda",
        "`.Ai# tail",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("", "A"),) * 3,
    )


def test_advancing_a_finished_state_is_answered_not_stepped() -> None:
    machine = native._Machine("`.Ai", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert native._advance(machine.state) == (machine.state, None)


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Unlambda", "`i", "exactly two expressions")


def test_deep_snapshots_preserve_identity_execution_and_cycle_boundaries() -> None:
    """Deep identity terms stay finite, hashable and distinct from other values."""
    from copy import deepcopy
    from pickle import dumps, loads
    from unittest.mock import patch

    from esolangs.vm import run_until_halt_or_cycle

    captured_machine = native._Machine("``ci`.Ai", ScriptedIO())
    for _ in range(7):
        captured_machine.step()
    captured = captured_machine.snapshot()
    assert isinstance(captured[0], native._Apply)
    assert isinstance(captured[0].a, _Cont)
    assert captured[0].a.kont is captured[1]
    assert isinstance(captured[1], native._Kont)
    assert captured[1].__getstate__() == (captured[1].frame, captured[1].rest)
    for restored in (loads(dumps(captured, protocol=5)), deepcopy(captured)):
        assert isinstance(restored, tuple)
        assert isinstance(restored[0], native._Apply)
        assert isinstance(restored[0].a, _Cont)
        assert isinstance(restored[1], native._Kont)
        assert restored == captured
        assert hash(restored) == hash(captured)
        assert restored[0].a.kont is restored[1]
    with pytest.raises(TypeError, match="invalid continuation state"):
        captured[1].__setstate__((None, {"depth": 1, "frame": None, "rest": None}))
    reused = native._Kont(_Arg(_Cmd("v")), None)
    assert reused != captured[1]
    reused.__setstate__(captured[1].__getstate__())
    assert reused == captured[1]
    assert hash(reused) == hash(captured[1])

    depth = 1100
    code = "`" * depth + "i" * (depth + 1)
    port = ScriptedIO()
    machine = native._Machine(code, port)
    saved = machine.snapshot()
    retained = {saved}
    twin = native._Machine(code, ScriptedIO()).snapshot()
    assert saved == twin
    assert hash(saved) == hash(twin)
    other = native._Machine("`" * depth + "i" * depth + "v", ScriptedIO())
    assert saved != other.snapshot()
    with patch.object(native._ValueBase, "__hash__", return_value=0):
        # Fresh tuples avoid Python 3.14's cached hash across the patch.
        colliding = machine.snapshot()
        different = other.snapshot()
        same = native._Machine(code, ScriptedIO()).snapshot()
        assert hash(colliding) == hash(different)
        assert colliding != different
        assert colliding == same
    for _ in range(5 * depth + 2):
        assert not machine.halted
        machine.step()
    assert machine.halted
    assert machine.state == (_Ret(_Cmd("i")), None, None, True)
    assert port.getvalue() == ""
    assert port.reads == port.progress() == port.past_end == 0
    assert saved in retained
    assert saved == twin
    with pytest.raises(TimeoutError, match="undecided after 2 steps"):
        run_until_halt_or_cycle(native._Machine(code, ScriptedIO()), limit=2)
    assert run_until_halt_or_cycle(
        native._Machine(code, ScriptedIO()), limit=5 * depth + 2
    )
    assert run_until_halt_or_cycle(native._Machine("`ii", ScriptedIO()), limit=7)
    # S I I applied to itself revisits Apply(F, F): this is a genuine cycle,
    # rather than treating every nontrivial term as undecided or finished.
    assert not run_until_halt_or_cycle(
        native._Machine("```sii``sii", ScriptedIO()), limit=200
    )
    for char in "AB":
        output = ScriptedIO()
        printing = native._Machine("`" + code + "`." + char + "i", output)
        for _ in range(5 * depth + 20):
            if printing.halted:
                break
            printing.step()
        assert printing.halted
        assert output.getvalue() == char

    from dataclasses import fields, is_dataclass

    from esolangs._cycles import _halt_or_cycle_result
    from esolangs.results import ExecutionResult
    from esolangs.runtime._json import worker_dumps, worker_loads
    from esolangs.runtime._proof import TerminationResult
    from esolangs.runtime._result_wire import (
        decode_decision,
        decode_termination,
        encode_decision,
        encode_result,
    )

    def same_typed(left, right):
        pending = [(left, right)]
        while pending:
            one, two = pending.pop()
            assert type(one) is type(two)
            if isinstance(one, native._Kont):
                assert one.depth == two.depth
                pending.extend(((one.frame, two.frame), (one.rest, two.rest)))
            elif is_dataclass(one):
                pending.extend(
                    (getattr(one, field.name), getattr(two, field.name))
                    for field in fields(one)
                )
            elif isinstance(one, tuple):
                assert len(one) == len(two)
                pending.extend(zip(one, two, strict=True))
            else:
                assert one == two

    cycling = "`" + "```sii``sii" + code
    loop_port = ScriptedIO()
    loop = native._Machine(cycling, loop_port)
    states = []
    seen = {}
    for command in range(42):
        snapshot = loop.snapshot()
        states.append(snapshot)
        if snapshot in seen:
            assert (seen[snapshot], command) == (25, 41)
            break
        seen[snapshot] = command
        loop.step()
    assert len(states) == 42
    assert states[25] == states[41]
    assert (
        loop_port.getvalue(),
        loop_port.progress(),
        loop_port.reads,
        loop_port.past_end,
    ) == ("", 0, 0, 0)
    wire = _state_wire(states[25])
    restored = _state_from_wire(worker_loads(worker_dumps(wire)))
    same_typed(states[25], restored)
    assert restored == states[25]
    assert hash(restored) == hash(states[25])
    pending = [(wire, 0)]
    deepest = None
    while pending:
        value, level = pending.pop()
        if isinstance(value, dict):
            record = value.get("record")
            if (
                record
                and record["name"] == "_Cmd"
                and record["fields"]["name"] == "i"
                and (deepest is None or level > deepest[0])
            ):
                deepest = level, record["fields"]
            pending.extend((child, level + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, level + 1) for child in value)
    assert deepest is not None
    deepest[1]["name"] = "v"
    wrong = _state_from_wire(worker_loads(worker_dumps(wire)))
    assert wrong != restored
    with pytest.raises(AssertionError):
        same_typed(wrong, restored)
    decision_port = ScriptedIO()
    decision_machine = native._Machine(cycling, decision_port)
    decision = _halt_or_cycle_result(decision_machine, limit=128)
    assert decision.halts is False
    assert decision.cycle is not None
    assert decision.commands == 47
    assert (
        decision.cycle.first_pass,
        decision.cycle.repeat_pass,
        decision.cycle.commands_per_pass,
    ) == (31, 47, 1)
    decoded = decode_decision(worker_loads(worker_dumps(encode_decision(decision))))
    assert decoded == decision
    assert decoded.cycle is not None
    same_typed(decoded.cycle.state, decision.cycle.state)
    assert hash(decoded.cycle.state) == hash(decision.cycle.state)
    assert decision_machine.snapshot() == decision.cycle.state
    outcome = TerminationResult(
        ExecutionResult(
            decision_port.getvalue(),
            decision_port.position(),
            decision_port.reads,
            decision_port.past_end,
        ),
        decision,
    )
    assert outcome.observation == ExecutionResult("", 0, 0, 0)
    message = worker_loads(
        worker_dumps(
            {
                "execution": encode_result(outcome.observation),
                "decision": encode_decision(outcome.decision),
            }
        )
    )
    assert decode_termination("", message["execution"], message["decision"]) == outcome
