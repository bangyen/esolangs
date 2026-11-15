"""Execution tests for the Befunge classic."""

from ctypes import c_long, sizeof
from dataclasses import replace

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.languages.befunge.interpreter import (
    _advance,
    _Machine,
    prepare_machine,
    run,
)
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Seeded
from esolangs.vm import (
    make_vm,
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_cycle,
)
from tests.interpreters.runner import run_program
from tests.support.factories import reject_rng_options, rng_factory
from tests.support.raises import assert_halts_with_hint, assert_rejected_with_hint
from tests.support.vm_support import (
    assert_rejected_input_retry,
    assert_rejected_output_retry,
)


@pytest.mark.medium
def test_invalid_numeric_reads_keep_the_fault_and_prefix() -> None:
    too_large = str(1 << (sizeof(c_long) * 8 - 1))
    for token, error_type in (("oops", esolangs.ArgumentError), (too_large, HaltError)):
        assert_rejected_input_retry(
            "Befunge",
            '"A",&.@',
            token + " 17",
            "17",
            "A17 ",
            position=len(token),
            reads=1,
            error_type=error_type,
            prefix=4,
            partial="A",
        )
    assert_rejected_input_retry(
        "Befunge", "10/.@", "oops 7", "7", "7 ", position=4, reads=1, prefix=2
    )


def run_befunge(program: str, stdin: str = "", rng: object = None) -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin, rng=rng)


@pytest.mark.medium
def test_scoped_termination_keeps_public_failure_evidence() -> None:
    api = esolangs.Language("Befunge")
    record = api.catalog.languages[api.name]
    contract = replace(
        record.contract, answer_mode="termination", answer_values=("halts", "diverges")
    )
    scoped = esolangs.Catalog([replace(record, contract=contract)]).bind(api.name)
    local = esolangs.ExecutionLimits(max_steps=500)
    worker = esolangs.ExecutionLimits(max_steps=500, total_timeout=5)
    successes = []
    for limits in (local, worker):
        halted = scoped.evaluate(scoped.from_source("@"), [0], limits=limits)
        assert halted.answer == "0"
        successes.append(halted)
        with pytest.raises(
            esolangs.InterpreterLimitError, match="depends on its own draws"
        ) as stopped:
            scoped.evaluate(scoped.from_source("?@"), [0], limits=limits)
        assert stopped.value.observation == esolangs.ExecutionResult("", 0, 0, 0)
        assert stopped.value.__notes__
        with pytest.raises(
            esolangs.InterpreterLimitError, match="cannot be safely forked"
        ) as unforkable:
            scoped.evaluate(scoped.from_source("&@"), [0], limits=limits)
        assert unforkable.value.observation == esolangs.ExecutionResult("", 0, 0, 0)
    assert successes[0] == successes[1]
    with pytest.raises(esolangs.InterpreterLimitError, match="cannot be safely forked"):
        scoped.evaluate(scoped.from_source("&@"), [0])
    with pytest.raises(esolangs.ExecutionCapError, match="branching states") as capped:
        scoped.evaluate(
            scoped.from_source("@"), [0], limits=esolangs.ExecutionLimits(max_steps=0)
        )
    assert capped.value.bound == "max_steps"
    _check_shared_branch_evidence(scoped, local, worker)


def _check_shared_branch_evidence(scoped, local, worker) -> None:
    from esolangs.runtime._json import worker_dumps
    from esolangs.runtime._result_wire import _state_wire, encode_decision

    for source, answer in ((">   <", "1"), ("@", "0")):
        program = scoped.from_json(scoped.to_json(scoped.from_source(source)))
        native = scoped.evaluate(program, [0], limits=local)
        isolated = scoped.evaluate(program, [0], limits=worker)
        assert native == isolated
        assert isolated.answer == answer
        for result in (native, isolated):
            branch = result.termination.branches
            first, outcomes = branch.transitions[0]
            assert branch.root is first
            assert branch.root.grid is outcomes[0].grid
            if branch.halts:
                assert outcomes[0] is branch.terminal
        nodes = (
            branch.root,
            branch.terminal,
            *(
                node
                for state, targets in branch.transitions
                for node in (state, *targets)
            ),
        )
        split = sum(len(worker_dumps(_state_wire(node))) for node in nodes)
        assert 2 * len(worker_dumps(encode_decision(isolated.termination))) < split


def test_string_mode_pushes_and_commas_emit() -> None:
    assert run_befunge('"!dlroW ,olleH",,,,,,,,,,,,,@') == "Hello, World!"


def test_arithmetic_prints_with_the_reference_trailing_space() -> None:
    assert run_befunge("99*.@") == "81 "
    assert run_befunge("78*1+.@") == "57 "


def test_division_and_modulo_truncate_toward_zero() -> None:
    assert run_befunge("07-2 /.@") == "-3 "
    assert run_befunge("07-2 %.@") == "-1 "


def test_an_empty_stack_is_a_zero_divisor_like_any_other() -> None:
    """The implicit 0 and an explicit one take the same path."""
    assert run_befunge("/.@", "7\n") == "7 "
    assert run_befunge("%.@", "8\n") == "8 "
    assert run_befunge("0/.@", "7\n") == run_befunge("/.@", "7\n")


def test_a_zero_divisor_with_nothing_to_read_halts() -> None:
    """The documented HaltError, through ``run`` rather than ``_advance``."""
    for program in ("10/.@", "/.@", "10%.@"):
        with pytest.raises(HaltError, match="needs a result"):
            run_befunge(program)
    with pytest.raises(EOFError):
        run_program(run, ["&.@"], suppress_eof=False)


def test_a_zero_divisor_reads_the_result() -> None:
    assert run_befunge("10/.@", "7\n") == "7 "
    assert run_befunge("10%.@", "8\n") == "8 "
    for command in "/%":
        state = ((0, 0, 1, 0), ((command,),), (0, (1, None)), False, False)
        with pytest.raises(HaltError, match="needs a result"):
            _advance(state)


def test_program_uses_the_80_by_25_torus() -> None:
    machine = _Machine(["<"], IO())
    machine.step()
    assert machine.ip == (0, 79, -1, 0)
    assert len(machine.state[1]) == 25
    assert len(machine.state[1][0]) == 80


def test_oversized_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" " * 80 + "@"], IO())
    with pytest.raises(ValueError, match="80x25"):
        _Machine([" "] * 26, IO())


def test_both_conditionals_turn_the_pointer() -> None:
    """``_``/``|`` set a new heading from the popped value, then move."""
    for command, zero, nonzero in (
        ("_", (1, 0), (-1, 0)),
        ("|", (0, 1), (0, -1)),
    ):
        grid = ((command,),)
        moved, _ = _advance(((0, 0, 1, 0), grid, (0, None), False, False))
        assert moved[0][2:4] == zero
        moved, _ = _advance(((0, 0, 1, 0), grid, (1, None), False, False))
        assert moved[0][2:4] == nonzero


def test_bridge_skips_the_next_cell() -> None:
    # `#` steps over the 9, so the emitted value is 5.
    assert run_befunge("5#9.@") == "5 "


@pytest.mark.medium
def test_put_writes_and_get_reads_the_grid() -> None:
    """``p`` pops y, x, v and writes a byte; ``g`` reads one back."""
    from esolangs.languages.befunge.tests.oracle_checks import check_raw_befunge

    check_raw_befunge()
    wrote, _ = _advance(
        ((0, 0, 1, 0), (("p",), (" ",)), (1, (0, (64, None))), False, False)
    )
    assert wrote[1][1][0] == "@"
    read, _ = _advance(((0, 0, 1, 0), (("g",), ("@",)), (1, (0, None)), False, False))
    assert read[2] == (64, None)


def test_put_outside_the_grid_is_ignored() -> None:
    # The stack is (v, x, y) with y on top; both coordinates are off a 1x1 grid.
    moved, _ = _advance(((0, 0, 1, 0), (("p",),), (5, (5, (65, None))), False, False))
    assert moved[1] == (("p",),)


def test_integer_and_character_input(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_befunge("&.@", "5\n") == "5 "
    assert run_befunge("~,@", "A\n") == "A"
    assert_rejected_output_retry(
        "Befunge", "99*.1.@", "81 ", "81 1 ", prefix=3, monkeypatch=monkeypatch
    )


def test_random_direction_uses_the_supplied_draw() -> None:
    # Right, down, left, up is the documented draw order; each moves one cell
    # from the `?` at (1,1).
    grid = ("...", ".?.", "...")
    state = ((1, 1, 1, 0), tuple(tuple(row) for row in grid), None, False, False)
    for direction, (x, y) in enumerate(((2, 1), (1, 2), (0, 1), (1, 0))):
        moved, _ = _advance(state, random_dir=direction)
        assert moved[0][:2] == (x, y)


def test_a_seeded_run_is_reproducible(monkeypatch) -> None:
    program = "@@@\n@?@\n@@@"
    assert run_befunge(program, rng=Seeded(0)) == run_befunge(program, rng=Seeded(0))
    from esolangs.languages.befunge import interpreter
    from tests.support.prepared_support import check_random_plan_reuse

    # Each draw follows a straight branch that prints 1, 2, 3 or 4 and halts.
    rows = ["?1.@" + " " * 73 + "@.3", "2", ".", "@"]
    rows += [""] * 18 + ["@", ".", "4"]
    check_random_plan_reuse(
        "Befunge", "\n".join(rows), interpreter, "_parse_grid", monkeypatch
    )

    source = ["?@"]
    rng, before, options, factory = rng_factory(prepare_machine, source)
    source[0] = "@"
    options.clear()
    first, second = factory(IO()), factory(IO())
    assert first is not second
    assert first._rng is second._rng is rng
    assert rng._random.getstate() == before
    initial = second.snapshot()
    first.step()
    assert rng._random.getstate() != before
    assert second.snapshot() == initial
    assert not first.halted
    reject_rng_options(prepare_machine, "invalid", "split text", [";"])


@pytest.mark.medium
def test_integer_subclass_seed_keeps_native_worker_and_vm_results(monkeypatch) -> None:
    from esolangs.runtime import _execution

    class Seed(int):
        def __int__(self):
            raise AssertionError("seed backing value must be used")

    seeds = []

    def receive(seed):
        assert type(seed) is int
        seeds.append(seed)
        return Seeded(seed)

    monkeypatch.setattr(_execution, "Seeded", receive)
    # All four branches after ? print and halt, with a different digit each.
    rows = ["?1.@" + " " * 73 + "@.3", "2", ".", "@"]
    rows += [""] * 18 + ["@", ".", "4"]
    source = "\n".join(rows)
    api = esolangs.Language("Befunge")
    expected = api.run(source, seed=-7)
    assert expected.output != api.run(source, seed=-1).output
    seeds.clear()
    assert api.run(source, seed=Seed(-7)) == expected
    assert api.prepare(source).run(seed=Seed(-7), isolated=True) == expected
    vm = api.make_vm(source, seed=Seed(-7))
    assert run_until_halt(vm, limit=8)
    assert vm.output == expected.output
    assert seeds.count(-7) == 2


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], IO())


def test_a_repeated_push_keeps_the_persistent_stack() -> None:
    """The one-cell source executes once per 80-column playfield lap."""
    machine = _Machine(["1"], IO())
    assert run_until_halt(machine, 20_000) is False
    assert machine.stack == [1] * 250


def test_a_done_state_is_its_own_successor() -> None:
    done = ((0, 0, 1, 0), (("@",),), None, False, True)
    assert _advance(done) == (done, None)


def test_complement_greater_than_and_discard() -> None:
    assert run_befunge("0!.@") == "1 "
    assert run_befunge("1!.@") == "0 "
    assert run_befunge("21`.@") == "1 "  # 2 > 1
    assert run_befunge("12`.@") == "0 "
    assert run_befunge("12$.@") == "1 "


def test_the_four_heading_commands_set_the_direction() -> None:
    for command, heading in (
        (">", (1, 0)),
        ("<", (-1, 0)),
        ("^", (0, -1)),
        ("v", (0, 1)),
    ):
        moved, _ = _advance(((0, 0, 0, 0), ((command,),), None, False, False))
        assert moved[0][2:4] == heading


def test_reads_past_the_end_halt() -> None:
    with pytest.raises(HaltError, match="random draw"):
        _advance(((0, 0, 1, 0), (("?",),), None, False, False))
    # ``_advance`` is called with no character supplied; the shell's read
    # raises EOF before this guard, so this is a direct-call contract.
    with pytest.raises(HaltError, match="no input left"):
        _advance(((0, 0, 1, 0), (("~",),), None, False, False))


def test_the_branching_protocol_forks_the_draw() -> None:
    """The hang search walks one state per direction ``?`` may take."""
    machine = _Machine(["?"], IO())
    start = machine.branching_snapshot()
    assert not machine.branching_halted(start)
    assert machine.branching_successors(start, 3) is None
    assert len(machine.branching_successors(start, 4)) == 4
    # A read cell cannot be forked, and a halted machine is its own successor.
    reading = _Machine(["~"], IO())
    assert reading.branching_successors(reading.branching_snapshot(), 4) is None
    # An ordinary command is deterministic: one successor.
    plain = _Machine(["0"], IO())
    assert plain.branching_successors(plain.branching_snapshot(), 0) is None
    assert len(plain.branching_successors(plain.branching_snapshot(), 4)) == 1
    halted = _Machine(["@"], IO())
    halted.step()
    final = halted.branching_snapshot()
    assert halted.branching_halted(final)
    assert halted.branching_successors(final, 0) is None
    assert halted.branching_successors(final, 4) == (final,)


def test_advance_refuses_input_the_shell_did_not_supply() -> None:
    empty = ((0, 0, 1, 0), (("&",),), None, False, False)
    with pytest.raises(HaltError, match="no input left"):
        _advance(empty)


def test_string_mode_pushes_read_and_random_cells_as_characters() -> None:
    """Inside ``"``, ``/ ~ & ?`` are pushed, never read or drawn (Befunge-93)."""
    assert run_befunge('"?&~/",,,,@') == "/~&?"


def test_only_ascii_digits_push() -> None:
    """``²`` passes ``str.isdigit`` but is not a Befunge-93 digit: a no-op."""
    assert run_befunge("².@") == "0 "


def test_a_non_byte_source_cell_is_rejected() -> None:
    """Befunge-93 playfield cells are bytes; ``Ā`` (U+0100) cannot be one."""
    with pytest.raises(ValueError, match="bytes"):
        run_befunge("Ā@")


def test_a_value_past_signed_long_aborts() -> None:
    """81**16 overflows the reference's C long (UB there): abort, not a bignum."""
    with pytest.raises(HaltError, match="signed-long"):
        run_befunge("99*:*:*:*:*.@")


_LONG_BITS = sizeof(c_long) * 8  # 64, or 32 on Windows
# 2 squared to 2**(bits/2), times -(2**(bits/2 - 1)): -2**(bits-1), every push in range.
_MIN_LONG = "2" + ":*" * ((_LONG_BITS // 2).bit_length() - 1) + ":2/0\\-*"


def test_the_signed_long_range_is_inclusive_at_both_ends() -> None:
    """A C long's two ends are valid, one past the top is not, and 2**16 is no wrap."""
    low = -(1 << (_LONG_BITS - 1))
    assert run_befunge(_MIN_LONG + ".@") == f"{low} "
    assert run_befunge(_MIN_LONG + "1+0\\-.@") == f"{-low - 1} "
    with pytest.raises(HaltError, match="signed-long"):
        run_befunge(_MIN_LONG + "0\\-.@")
    assert run_befunge("99*:*:*.@") == "43046721 "


def test_a_byte_cell_at_the_top_of_the_range_is_accepted() -> None:
    """U+00FF is a byte: only cells above it are rejected."""
    assert run_befunge("\xff@") == ""


def test_get_at_the_first_column_past_the_grid_reads_zero() -> None:
    """x == 80 is off the 80-wide grid, so ``g`` pushes 0 rather than indexing."""
    assert run_befunge("88*88++0g.@") == "0 "


def test_the_branch_search_refuses_a_zero_divisor_read() -> None:
    """``/`` on an empty stack reads its result, so it cannot be forked."""
    machine = _Machine(["/"], IO())
    assert machine.branching_successors(machine.branching_snapshot(), 4) is None


def test_division_preserves_its_input_state() -> None:
    machine = _Machine(["42/1%"], IO())
    for _ in range(2):
        machine.step()
    before = machine.state
    first = _advance(before)
    assert _advance(before) == first
    assert before[2] == (2, (4, None))
    machine.step()
    assert machine.stack == [2]
    for _ in range(2):
        machine.step()
    assert machine.stack == [0]
    assert before[2] == (2, (4, None))


@pytest.mark.medium
def test_hints_for_bad_programs_and_input() -> None:
    assert_rejected_with_hint(
        "Befunge",
        "&@",
        "whitespace-separated decimal integer",
        stdin="oops",
        error=ValueError,
    )
    assert_halts_with_hint("Befunge", "10/.@", "divides by zero", "divisor")


def test_a_loop_that_never_draws_is_proved_by_the_snapshot_detector() -> None:
    """Befunge draws at ``?``; a program without one is still decidable.

    The detector refused every machine of a random language, this loop
    included, though a repeat with no draw in it proves the hang.
    """
    assert run_until_halt_or_cycle(make_vm("Befunge", ">v\n^<\n")) is False
    # A draw-free path to ``@`` is this run's halt too.
    assert run_until_halt_or_cycle(make_vm("Befunge", ">@\n")) is True
    # Once a draw can halt it, this run's own draw decides: refused, not guessed.
    with pytest.raises(TypeError, match="depends on its own draws"):
        run_until_halt_or_cycle(make_vm("Befunge", "?@@@@\n@\n"))


def test_a_clean_branch_can_prove_halt_after_an_unforkable_sibling() -> None:
    api = esolangs.Language("Befunge")
    source = "?@\n&"
    assert (
        api.run(source, seed=2, limits=esolangs.ExecutionLimits(max_steps=2)).steps == 2
    )
    with pytest.raises(esolangs.InputExhaustedError):
        api.run(source, seed=4, limits=esolangs.ExecutionLimits(max_steps=2))

    vm = api.make_vm(source, seed=4)
    saved = vm.snapshot()
    assert run_until_halt_or_all_branches_cycle(vm, limit=12) is True
    assert vm.snapshot() == saved
    with pytest.raises(TimeoutError, match="needs input"):
        run_until_halt_or_all_branches_cycle(api.make_vm("&@"), limit=4)

    for make in (api.make_vm, api.make_debugger):
        rejected = make('"A",&.@', stdin="oops 7")
        good = make('"A",&.@', stdin="7")
        for vm in (rejected, good):
            assert not run_until_halt(vm, limit=4)
            assert vm.output == "A"
        for proof in (run_until_halt_or_all_branches_cycle, run_until_halt_or_cycle):
            with pytest.raises(TimeoutError, match="needs input"):
                proof(rejected, limit=4)
        with pytest.raises(esolangs.ArgumentError, match="got 'oops'") as known:
            rejected.step()
        captured = known.value.observation
        assert (captured.input_position, captured.input_reads) == (4, 1)
        saved = rejected.snapshot()
        good.step()

        for proof in (run_until_halt_or_all_branches_cycle, run_until_halt_or_cycle):
            with pytest.raises(esolangs.ArgumentError, match="got 'oops'") as replay:
                proof(rejected, limit=4)
            assert replay.value is not known.value
            assert [
                *replay.value.__notes__,
                "the program printed 'A' before this",
            ] == known.value.__notes__
            assert replay.value.observation == esolangs.ExecutionResult("A", 4, 1, 0)
            assert replay.value.partial_output == "A"
            assert known.value.observation == captured
            assert rejected.snapshot() == saved
            assert proof(good, limit=4) is True
            assert good.output == "A"
        assert run_until_halt(good, limit=2)
        assert good.output == "A7 "
