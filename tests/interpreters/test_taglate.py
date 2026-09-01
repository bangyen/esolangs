"""Unit tests for the Taglate interpreter.

Taglate is a queue-based language: the first line seeds a queue of integers
(0-65535, wrapping), and the remaining lines hold commands (arithmetic,
rotate/discard, loops, character I/O, the ``j`` counter trick, and the
Google Translate URL ``t`` command).
"""

from typing import ClassVar

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.queue_based.taglate import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestTaglate:
    def test_output_hello(self) -> None:
        assert run_and_capture(["Hi", "ii"]) == "Hi"

    def test_add(self) -> None:
        # ord('1') + ord('2') = 99 = 'c'
        assert run_and_capture(["12", "ai"]) == "c"

    def test_subtract_wraps(self) -> None:
        # ord('1') - ord('2') = -1, wrapping to 65535
        assert run_and_capture(["12", "bi"]) == chr(65535)

    def test_multiply(self) -> None:
        assert run_and_capture(["11", "ci"]) == chr(49 * 49)

    def test_divide(self) -> None:
        assert run_and_capture(["93", "di"]) == chr(57 // 51)

    def test_divide_by_zero_halts(self) -> None:
        """Division by zero is invalid, so the interpreter halts on it."""
        import pytest

        with pytest.raises(HaltError):
            run_and_capture(["1\x00", "di"])

    def test_rotate(self) -> None:
        assert run_and_capture(["12", "ei"]) == "2"

    def test_discard(self) -> None:
        assert run_and_capture(["12", "fi"]) == "2"

    def test_loop_outputs_until_empty(self) -> None:
        assert run_and_capture(["11", "gyigz"]) == "11"

    def test_loop_skipped_when_front_zero(self) -> None:
        assert run_and_capture(["\x001", "gyigz"]) == ""

    def test_j_decrements_nonzero(self) -> None:
        assert run_and_capture(["1", "ji"]) == "0"

    def test_j_zero_becomes_one(self) -> None:
        assert run_and_capture(["11", "bji"]) == chr(1)

    def test_input_appends_to_back(self) -> None:
        assert run_and_capture(["0", "fhi"], inputs=["x"]) == "x"

    def test_empty_program(self) -> None:
        assert run_and_capture([]) == ""
        assert run_and_capture([""]) == ""

    def test_generator_round_trips(self) -> None:
        for text in ("Hello, World!", "Hi", "123", "\x00"):
            assert esolangs.run("Taglate", esolangs.generate("Taglate", text)) == text

    def test_generator_rejects_newlines(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="newline"):
            esolangs.generate("Taglate", "a\nb")

    def test_google_translate_url(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=Hi&op=translate"
        assert run_and_capture(["Hi", "t" + "i" * len(expected)]) == expected

    def test_google_translate_url_encodes_unsafe_chars(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=a%20b&op=translate"
        assert run_and_capture(["a b", "t" + "i" * len(expected)]) == expected

    def test_lone_g_is_ignored(self) -> None:
        assert run_and_capture(["1", "gi"]) == "1"

    def test_a_g_at_the_very_end_has_nothing_to_pair_with(self) -> None:
        """The pairing looks ahead, so it must first check there is an ahead.

        ``test_lone_g_is_ignored`` puts the ``g`` before an ``i``, where the
        look-ahead reads a real character and only the comparison decides.
        A ``g`` as the last character has no next character at all.
        """
        assert run_and_capture(["1", "ig"]) == "1"

    def test_only_y_and_z_pair_with_a_g(self) -> None:
        """Any other character after a ``g`` leaves the ``g`` alone.

        Both are then skipped, since neither is a command.  Widening the
        set that pairs would make the two characters one token, which
        matches none of the commands and so falls through to ``t`` --
        replacing the queue with the URL instead of leaving it alone.
        """
        assert run_and_capture(["1", "gXi"]) == "1"

    def test_a_skipped_character_advances_the_cursor(self) -> None:
        """Passing over a non-command moves on, rather than restarting.

        Every program here begins with a command, so a tokenizer that
        reset to a fixed position on a skip would still have finished
        them.  A non-command after a command does not finish: the scan
        returns to that same character forever.
        """
        assert run_and_capture(["1", "ix"]) == "1"

    def test_the_command_lines_are_joined_without_a_separator(self) -> None:
        """``gy`` split across two lines is still one token.

        Every multi-line program keeps each token whole on its line, so
        anything at all could sit at the join and the tokens would come
        out the same.  Here the ``g`` ends one line and the ``y`` starts
        the next: joined directly they open a loop that drains the queue,
        and separated the ``gz`` below is left with no partner, which is
        rejected once the queue is non-empty at it.
        """
        assert run_and_capture(["11", "g", "yigz"]) == "11"

    def test_unmatched_loop_markers_rejected(self) -> None:
        """An unmatched gy/gz is a malformed program.

        ``match=`` is a substring search, and both messages contain the
        word it looks for -- so each is asserted whole here, since the
        message is the only thing that says which marker was the loose
        one.
        """
        import pytest

        with pytest.raises(ValueError) as caught:
            run_and_capture(["\x001", "gy"])
        assert str(caught.value) == "unmatched 'gy'"

        with pytest.raises(ValueError) as caught:
            run_and_capture(["1", "gz"])
        assert str(caught.value) == "unmatched 'gz'"

    def test_arithmetic_wraps_at_the_queue_ceiling(self) -> None:
        """Sums and products come back mod 65536, the top of the range.

        ``test_subtract_wraps`` pins the modulus from below, where a
        negative result comes back near the ceiling and one more or one
        less would show -- but addition and multiplication each carry
        their own, and no program overflowed either.  65535 + 1 wraps to
        zero, and 65535 squared to one.
        """
        assert run_and_capture([chr(65535) + chr(1), "ai"]) == "\x00"
        assert run_and_capture([chr(65535) + chr(65535), "ci"]) == "\x01"

    def test_the_counter_wraps_at_the_same_ceiling(self) -> None:
        """``j`` on a seed above the range comes back inside it.

        Its subtraction is guarded by the value being nonzero, so the
        wrap is only reachable from a seed character above U+FFFF --
        which is the one way a value over 65535 enters the queue, since
        every other command already wrapped.
        """
        assert run_and_capture([chr(65537), "ji"]) == "\x00"

    def test_a_loop_runs_until_its_head_reaches_zero(self) -> None:
        """``gz`` goes back while the front is nonzero, not while it is
        anything but one.

        Every loop here either never repeats or empties its queue, so the
        countdown's last laps were never run.  This one holds a single
        value and decrements it in place: stopping at zero prints zero,
        while stopping one lap early prints one.
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
        assert (machine.ind, machine.queue) == (0, [97, 98, 99])
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
