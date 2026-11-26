"""Execution tests for the interpreter-only Malbolge classic."""

from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, HaltError, Language
from esolangs.languages.malbolge import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import run_program
from tests.support.raises import assert_rejected_with_hint

#: Kamila Szewczyk's "Hello, world." -- the reference output is lowercase.
HELLO = (
    "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/"
    "Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj"
)

#: The wiki's cat, which copies input and then loops forever at EOF.
CAT = '(=BA#9"=<;:3y7x54-21q/p-,+*)"!h%B0/.\n~P<\n<:(8&\n66#"!~}|{zyxwvu\ngJ%'


def test_the_crazy_operation_at_zero() -> None:
    # Each of the five base-9 di-trits maps 0 to 4, over places 9**0..9**4.
    assert native._crazy(0, 0) == 4 * sum(9**place for place in range(5))


def test_decipherment_and_halt() -> None:
    # 'Q' at cell 0 deciphers to 'v', the halt instruction.
    assert native._op(ord("Q"), 0) == "v"
    assert native._op(0, 0) is None  # not a graphic cell: execution stops


def test_memory_is_filled_and_sized() -> None:
    memory = native._initial_memory("Q")
    assert len(memory) == native._WORDS
    assert memory[0] == ord("Q")
    assert memory[1] == native._crazy(memory[0], 0)
    assert memory[2] == native._crazy(memory[1], memory[0])


def test_each_machine_receives_fresh_memory() -> None:
    # The image is cached; a machine that wrote through it would leak.
    native._Machine("Q", ScriptedIO("")).memory[0] = 0
    assert native._Machine("Q", ScriptedIO("")).memory[0] == ord("Q")


def test_a_known_program_prints_its_greeting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reference Hello World is the end-to-end check."""
    assert run_program(native.run, HELLO) == "Hello, world."

    from .oracle_checks import check_raw_malbolge

    check_raw_malbolge(HELLO, CAT)
    _check_output_retry(monkeypatch)


def _check_output_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    greeting = "Hello, world."
    api = Language("Malbolge")
    limits = ExecutionLimits(max_steps=2500)
    clean = api.make_debugger(HELLO)
    boundaries = []
    for _ in range(2500):
        before, observation = clean.snapshot(), clean.observation
        clean.step()
        if observation.output != clean.observation.output:
            boundaries.append((before, observation))
            if len(boundaries) == 8:
                break
    assert len(boundaries) == 8
    assert clean.run(limits=limits) == "halted"
    complete, final = clean.observation, clean.snapshot()
    assert complete == api.run(HELLO, limits=limits).unwrap()
    assert complete.output == greeting
    write = ScriptedIO._write

    def check(index: int, accepted: int) -> None:
        attempts: list[object] = []
        refusal = HaltError("transient output refusal")
        char = greeting[index]

        def refuse(io: ScriptedIO, value: object) -> None:
            attempts.append(value)
            if len(attempts) == index + 1:
                write(io, char[:accepted])
                raise refusal
            write(io, value)

        with monkeypatch.context() as patch:
            patch.setattr(ScriptedIO, "_write", refuse)
            debug = api.make_debugger(HELLO)
            with pytest.raises(HaltError, match="output refusal") as caught:
                debug.run(limits=limits)
            assert caught.value is refusal
            before, observation = boundaries[index]
            partial = replace(observation, output=observation.output + char[:accepted])
            assert refusal.observation == debug.observation == partial
            assert not debug.halted
            assert debug.snapshot() == ((*before, accepted) if accepted else before)
            assert debug.run(limits=limits) == "halted"
            assert debug.observation == complete
            assert debug.snapshot() == final
            assert refusal.observation == partial
        raw = greeting if accepted else greeting[:index] + char + greeting[index:]
        assert attempts == list(raw)

    for index in range(len(boundaries)):
        for accepted in (0, 1):
            check(index, accepted)


def test_the_snapshot_memory_follows_every_write() -> None:
    """The chunked snapshot rebuilds written chunks and shares the rest."""
    machine = native._Machine(HELLO, ScriptedIO(""))
    from scripts.benchmark import WrittenState, state_bits

    before = machine.snapshot()
    saved = machine.workspace_snapshot()
    retained = {saved}
    reference = WorkspaceModel(
        "malbolge-reference-test-v1",
        ("accumulator", "instruction", "data", "stopped", "memory", "input_cursor"),
    )
    old_meter = WrittenState(WorkspaceSnapshot(reference, before))
    new_meter = WrittenState(saved)
    while not machine.halted:
        machine.step()
        snapshot = machine.snapshot()
        chunks = snapshot[4]
        assert isinstance(chunks, tuple)
        assert [word for chunk in chunks for word in chunk] == machine.memory
        workspace = machine.workspace_snapshot()
        assert workspace.parts[:4] == machine.state
        assert tuple(word for page in workspace.parts[4] for word in page) == tuple(
            machine.memory[: native._WORDS]
        )
        assert workspace.parts[5] == machine.io.progress()
        old_meter.sample(WorkspaceSnapshot(reference, snapshot))
        new_meter.sample(workspace)
        assert new_meter.bits == old_meter.bits
        assert saved in retained
        assert state_bits(workspace.parts[4], {}) == sum(
            word.bit_length() or 1 for word in machine.memory[: native._WORDS]
        )
    assert sum(a is not b for a, b in zip(chunks, before[4], strict=True)) < 100


def test_a_one_character_program_halts_immediately() -> None:
    assert run_program(native.run, "Q") == ""


def test_input_is_a_character_stream() -> None:
    io = ScriptedIO("Hi!")
    machine = native._Machine(CAT, io)
    for _ in range(200):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue().startswith("Hi!")


def test_a_non_instruction_source_character_is_rejected() -> None:
    # 'x' at cell 0 deciphers to something outside the eight instructions.
    assert native._op(ord("x"), 0) not in "ji*p</vo"
    with pytest.raises(ValueError, match="does not decipher"):
        native._initial_memory("x")


def test_an_empty_program_halts_at_once() -> None:
    assert run_program(native.run, " ") == ""


def test_a_halted_state_advances_to_itself() -> None:
    done = (0, 0, 0, True)
    assert native._advance(done, list(native._initial_memory("Q"))) == (done, (), None)


def test_both_pointers_wrap_past_the_last_cell() -> None:
    # 52 at cell 59048 deciphers to 'o', a no-op, so the step only advances
    # c and d, and both leave the last cell for cell 0.
    last = native._WORDS - 1
    memory = [0] * last + [52]
    assert native._op(memory[last], last) == "o"
    (_a, c, d, halted), _writes, _effect = native._advance(
        (0, last, last, False), memory
    )
    assert (c, d, halted) == (0, 0, False)


def test_a_read_with_no_input_is_the_eof_value() -> None:
    # 'q' at cell 4 deciphers to '/', the input instruction; an absent input
    # leaves the EOF sentinel in ``a`` rather than raising.
    memory = [ord("q")] * 8
    (a, _c, _d, halted), _writes, _effect = native._advance((0, 4, 0, False), memory)
    assert a == native._EOF
    assert not halted


def test_a_non_graphic_rewrite_skips_the_encipherment() -> None:
    # The apostrophe is the cell that deciphers to '*': rotating 39 gives 13,
    # below the graphic range, so the cell keeps the value and is not
    # re-enciphered.
    (a, _c, _d, halted), writes, _effect = native._advance(
        (0, 0, 0, False), [ord("'")] * 8
    )
    assert not halted
    assert a == 13
    assert writes == ((0, 13),)


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Malbolge", "?", "position-dependent")

    from .workspace_checks import check_workspace_malbolge

    check_workspace_malbolge()
