"""Unit tests for the Taglate interpreter."""

import importlib
from typing import ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.queue_based.taglate import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_lines
from tests.raises import raises_message

run_and_capture = run_lines(run)


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 17, 257])
def test_consecutive_rotations_compose(count):
    seed = "ABC"
    offset = count % len(seed)
    assert run_and_capture([seed, "e" * count + "iii"]) == seed[offset:] + seed[:offset]


@pytest.mark.parametrize(
    ("seed", "commands", "stdin"),
    [
        ("ABC", "eeqeeiii", ""),
        (chr(3), "gy" + "e" * 31 + "jgzi", ""),
        ("", "h" + "e" * 17 + "i", "A"),
        ("", "ee", ""),
        ("A", "iee", ""),
        ("A", "e" * 17 + "gz", ""),
        ("\x00A", "gy" + "e" * 17, ""),
        ("ABC", "ffi", ""),
        ("ABC", "fffhiii", "A"),
        ("ABC", "f" * 17 + "i", ""),
        ("", "ff", ""),
    ],
)
def test_batched_run_matches_single_steps(seed, commands, stdin, monkeypatch):
    from esolangs._drive import drive
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based import taglate

    original = taglate._Machine  # noqa: SLF001
    machines = []

    def create(code, port):
        machine = original(code, port)
        machines.append(machine)
        return machine

    monkeypatch.setattr(taglate, "_Machine", create)
    ports = [ScriptedIO(stdin), ScriptedIO(stdin)]
    reference = original([seed, commands], ports[0])
    errors = []
    for execute in (
        lambda: drive(reference),
        lambda: taglate.run([seed, commands], ports[1]),
    ):
        try:
            execute()
        except (HaltError, EOFError, ValueError) as error:
            errors.append((type(error), error.args))
        else:
            errors.append(None)
    assert errors[0] == errors[1]
    assert ports[0].getvalue() == ports[1].getvalue()
    assert reference.snapshot() == machines[0].snapshot()


@pytest.mark.parametrize("seed", ["", "A"])
@pytest.mark.parametrize("command", ["a", "b", "c", "d"])
def test_binary_underflow_retains_consumed_pops(seed, command):
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based.taglate import _Machine

    machine = _Machine([seed, command], ScriptedIO(""))
    with pytest.raises(HaltError, match="queue is empty"):
        machine.step()
    assert machine.queue == ()
    assert machine.ind == 0


def test_repeated_programs_keep_parser_state_private():
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based.taglate import _Machine

    code = ["ABC", "gyeigz"]
    first = _Machine(code, ScriptedIO(""))
    second = _Machine(code, ScriptedIO(""))
    first.tokens[0] = "i"
    first.match.clear()
    assert second.tokens == ["gy", "e", "i", "gz"]
    assert second.match == {0: 3, 3: 0}
    third = _Machine(code, ScriptedIO(""))
    assert third.tokens == second.tokens
    assert third.match == second.match
    code[1] = "i"
    changed = _Machine(code, ScriptedIO(""))
    assert changed.tokens == ["i"]
    assert changed.match == {}


class TestTaglate:
    @pytest.mark.parametrize(
        ("seed", "commands", "expected"),
        [
            pytest.param("Hi", "ii", "Hi", id="output_hello"),
            pytest.param("12", "ai", "c", id="add"),
            pytest.param("12", "ei", "2", id="rotate"),
            pytest.param("11", "gyigz", "11", id="loop_outputs_until_empty"),
            pytest.param("\x001", "gyigz", "", id="loop_skipped_when_front_zero"),
            pytest.param("1", "ji", "0", id="j_decrements_nonzero"),
            # Any other character after a ``g`` leaves the ``g`` alone.
            pytest.param("1", "gXi", "1", id="only_y_and_z_pair_with_a_g"),
            # Passing over a non-command moves on, rather than restarting.
            pytest.param("1", "ix", "1", id="a_skipped_character_advances_the_cursor"),
        ],
    )
    def test_output(self, seed: str, commands: str, expected: str) -> None:
        assert run_and_capture([seed, commands]) == expected

    def test_subtract_wraps(self) -> None:
        # ord('1') - ord('2') = -1, wrapping to 65535
        assert run_and_capture(["12", "bi"]) == chr(65535)

    def test_multiply_wraps(self) -> None:
        assert run_and_capture([chr(65535) + chr(2), "ci"]) == chr(65534)

    def test_divide_by_zero_halts(self) -> None:
        """Division by zero is invalid, so the interpreter halts on it."""
        import pytest

        with pytest.raises(HaltError):
            run_and_capture(["1\x00", "di"])

    def test_j_zero_becomes_one(self) -> None:
        assert run_and_capture(["11", "bji"]) == chr(1)

    def test_empty_program(self) -> None:
        assert run_and_capture([]) == ""
        assert run_and_capture([""]) == ""

    def test_a_literal_line_is_printed_by_one_i_per_character(self) -> None:
        """``i`` advances one character of the line above it."""
        program = "Hello, World!\niiiiiiiiiiiii"
        assert esolangs.run("Taglate", program) == "Hello, World!"

    def test_google_translate_url(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=Hi&op=translate"
        assert run_and_capture(["Hi", "t" + "i" * len(expected)]) == expected

    def test_google_translate_url_encodes_unsafe_chars(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=a%20b&op=translate"
        assert run_and_capture(["a b", "t" + "i" * len(expected)]) == expected

    def test_the_command_lines_are_joined_without_a_separator(self) -> None:
        """``gy`` split across two lines is still one token."""
        assert run_and_capture(["11", "g", "yigz"]) == "11"

    def test_unmatched_loop_markers_rejected(self) -> None:
        """An unmatched gy/gz is a malformed program."""
        with raises_message(ValueError, "unmatched 'gy' at position 0"):
            run_and_capture(["\x001", "gy"])

        with raises_message(ValueError, "unmatched 'gz' at position 0"):
            run_and_capture(["1", "gz"])

    def test_arithmetic_wraps_at_the_queue_ceiling(self) -> None:
        """Sums and products come back mod 65536, the top of the range."""
        assert run_and_capture([chr(65535) + chr(1), "ai"]) == "\x00"
        assert run_and_capture([chr(65535) + chr(65535), "ci"]) == "\x01"

    def test_a_loop_runs_until_its_head_reaches_zero(self) -> None:
        """``gz`` goes back while the front is nonzero, not while it is
        anything but one.
        """
        assert run_and_capture([chr(3), "gyjgzi"]) == "\x00"

    def test_empty_queue_pop_halts(self) -> None:
        """Popping an empty queue in arithmetic is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture(["", "a"])
        with pytest.raises(HaltError):
            run_and_capture(["", "i"])


class TestStepMachine:
    def test_step_tracks_queue_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.taglate import _Machine

        machine = _Machine(["abc", "i"], ScriptedIO())
        assert (machine.ind, list(machine.queue)) == (0, [97, 98, 99])
        machine.step()  # i pops the front and prints it
        assert machine.io.getvalue() == "a"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based.taglate import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["abc", "i"]
    halting_program: ClassVar[list[str]] = ["abc", "i"]
    looping_program: ClassVar[list[str]] = ["1", "gy", "gz"]


class TestTheTwoQueueLanguagesDifferOnPurpose:
    """Both silently accepted nonsense; only one of them meant to."""

    def test_taglate_still_skips_a_non_command(self) -> None:
        """Deliberately unchanged, and the docstring now says why."""
        assert esolangs.run("Taglate", "1\nix", stdin="", timeout=5) == "1"
        assert esolangs.run("Taglate", "1\ngi", stdin="", timeout=5) == "1"

    def test_taglate_says_it_skips(self) -> None:
        """A surprising choice is only defensible while it is documented."""
        module = importlib.import_module("esolangs.interpreters.queue_based.taglate")
        doc = module.__doc__ or ""
        assert "is **skipped**" in doc
        assert "Bitdeque instead requires" in doc
