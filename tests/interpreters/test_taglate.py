"""Unit tests for the Taglate interpreter."""

import importlib
from typing import ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.queue_based.taglate import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


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

    def test_bitdeque_refuses_a_word_it_does_not_know(self) -> None:
        """``findall`` kept what matched and dropped the rest in silence."""
        with pytest.raises(esolangs.ProgramError, match="not a Bitdeque command"):
            esolangs.run("Bitdeque", "PUSH FROB PUSH", stdin="", timeout=5)

    def test_bitdeque_refuses_the_lower_case_program(self) -> None:
        """The whole language was a no-op for anyone who guessed the case."""
        with pytest.raises(esolangs.ProgramError, match="upper case"):
            esolangs.run("Bitdeque", "push invert push", stdin="", timeout=5)

    def test_bitdeque_still_runs_a_real_program(self) -> None:
        """Three refusals are worth nothing if the valid case broke."""
        assert (
            esolangs.run("Bitdeque", "PUSH INVERT PUSH", stdin="", timeout=5) == "0 1"
        )

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
