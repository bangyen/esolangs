"""Unit tests for the Interprogck8 interpreter.

Every wiki example is executed here, including the truth-machine's, which
the wiki writes with 49 colons where its own dice rule needs 24 colons and
a dot.  Both spellings are run: the verbatim one to pin what the example
actually does, and the corrected one to pin the loop/halt structure the
example was reaching for.
"""

from unittest.mock import patch

import pytest

from esolangs import ProgramArtifact
from esolangs.exceptions import HaltError
from esolangs.languages.interprogck8 import interpreter as native
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import FirstDraw, Seeded
from esolangs.vm import SnapshotVM, make_vm, run_until_halt_or_all_branches_cycle

# The wiki's Hello World, verbatim.
HELLO = """nNnN
@id
@nt
@nt
@nt
div
@id
@id
@id
@nt
div
@id
@nt
@nt
@nt
div
div
@nd
@nd
@nd
div
Empty_
div
@id
@id
@id
@id
@id
@nd
@nd
@nd
@nd
@nd
div
@id
@id
@nd
@nd
@nd
@nd
div
@nd
@nd
@nd
div
@dd
@nd
@nd
@nd
@nd
div
@dd
@nd
@nd
div
NnNn
@id
div"""

CAT = "<\nu\ndiv\nEXE\n>\nEXE"

# The wiki's truth machine.  Its literal is 49 *colons*, which the dice
# rule makes 98, so neither input ever equals it and both branches print
# "T".  ``TRUTH_FIXED`` is the same program with the literal the example
# needed (49 pips: 24 colons and a dot).
_WIKI_LITERAL = ":" * 49
TRUTH_WIKI = (
    f"u\n{{values/=/=/=[{_WIKI_LITERAL} {_WIKI_LITERAL}]}}\n<\ndiv\nEXE\n>\nIFQ\ndiv"
)
TRUTH_FIXED = f"u\n{{values/=/=/={native._dice(49)}}}\n<\ndiv\nEXE\n>\nIFQ\ndiv"

DICE = "[. :::]\n$ay"


def go(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    native.run(code, io, Seeded(0))
    return io.getvalue()


class TestWikiExamples:
    def test_hello_world(self) -> None:
        assert go(HELLO) == "Hello World\n"

    def test_cat_echoes_then_runs_out(self) -> None:
        """``EXE`` inside the body recurses, so the cat reads until EOF."""
        io = ScriptedIO("ab\ncd\n")
        with pytest.raises(EOFError):
            native.run(CAT, io)
        assert io.getvalue() == "ac"

    def test_wiki_truth_machine_is_degenerate(self) -> None:
        """49 colons is 98 pips, so both inputs take the ``T`` branch.

        This is the example's own arithmetic, not a reading of it: under
        any rule where ``:`` is two pips the literal cannot be 49, and the
        dice-roll example (``[. :::]``, a 1-6 roll) needs that rule.
        """
        assert native._pips(_WIKI_LITERAL) == 98
        assert go(TRUTH_WIKI, "0\n") == "T"
        assert go(TRUTH_WIKI, "1\n") == "T"

    @pytest.mark.parametrize(
        ("bit", "output", "halts"), [("0", "T", True), ("1", "Q", False)]
    )
    def test_corrected_truth_machine_loops_on_one(
        self, bit: str, output: str, *, halts: bool
    ) -> None:
        """With a 49-pip literal the structure is a truth machine.

        ``0`` prints once and halts; ``1`` never halts, which is *proved*
        by a repeated state rather than waited out -- the frame stack pops
        an exhausted body, so the tail call runs at constant depth.
        """
        io = ScriptedIO(bit + "\n")
        machine = native._Machine(TRUTH_FIXED, io)
        machine.step()  # the ``u``: the branch search declines input lines
        assert run_until_halt_or_all_branches_cycle(machine) is halts
        printed = ScriptedIO(bit + "\n")
        stepped = native._Machine(TRUTH_FIXED, printed)
        for _ in range(200):  # the search drops output; a plain run shows it
            stepped.step()
        assert stepped.halted is halts
        assert set(printed.getvalue()) == {output}

    def test_dice_roll_stays_in_range(self, monkeypatch) -> None:
        """``[. :::]`` rolls 1-6, and ``$ay`` writes a readable literal."""
        for seed in range(20):
            io = ScriptedIO("")
            native.run(DICE, io, Seeded(seed))
            assert 1 <= native._pips(io.getvalue()) <= 6

        from tests.support.prepared_support import check_random_plan_reuse

        check_random_plan_reuse(
            "Interprogck8", DICE, native, "_prepare_source", monkeypatch
        )

    def test_each_dice_face_prints_its_pips(self) -> None:
        for source in (DICE, "[::: .]\n$ay"):
            for face in range(1, 7):
                io = ScriptedIO("")
                native.run(source, io, FirstDraw(face - 1))
                assert io.getvalue() == ":" * (face // 2) + "." * (face % 2)


class TestDiceLiterals:
    @pytest.mark.parametrize(
        ("literal", "value"), [(".", 1), (":", 2), (":.", 3), ("::", 4)]
    )
    def test_pips(self, literal: str, value: int) -> None:
        """The wiki's worked examples: ``.`` is 1, ``:`` 2, ``:.`` 3."""
        assert native._pips(literal) == value

    def test_round_trip(self) -> None:
        """``$ay``'s spelling reads back as the value it was written for."""
        for value in range(1, 256):
            assert native._pips(native._dice(value)) == value

    def test_zero_has_no_literal(self) -> None:
        """No dice face is blank, so 0 prints nothing and is not readable."""
        assert native._dice(0) == ""
        assert go("NnNn\n$ay") == ""

    def test_non_literal_input_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError):
            go("$py", "7\n")


class TestCommands:
    def test_accumulator_loads_wrap_at_byte_boundaries(self) -> None:
        for value in (0, 254, 255, 256, 257, 258, 337, 340, 511, 512, 955):
            literal = ":" * (value // 2) + "." * (value % 2)
            inputs = [("u", chr(value) + "\n")]
            if value:
                inputs += [("$py", literal + "\n"), (f"[{literal} {literal}]", "")]
            for source, data in inputs:
                io = ScriptedIO(data)
                machine = native._Machine(source, io, FirstDraw(0))
                machine.step()
                assert machine.state.acc == value % 256
                assert io.position() == len(data)
                before = machine.snapshot()
                machine.step()
                assert machine.snapshot() == before
                assert go(source + "\ndiv", data) == chr(value % 256)
                assert go(f"<\n{source}\n>\nEXE\ndiv", data) == chr(value % 256)

    def test_values_reads_each_argument_by_its_own_kind(self) -> None:
        """A nested ``$py`` parses pips; a nested ``u`` takes a byte.

        Typing the read by the *line* would apply one rule to both, which
        is the only thing this path exercises: ``:`` is 2 as a literal and
        58 as a byte, so the two arms disagree unless each is read right.
        """
        # $py reads ":" as 2; u reads "\x02" as 2; the third is the acc (2).
        assert go("NnNn\n@nd\n@nd\n{values/=$py/=u/=}\ndiv", ":\n\x02\n") == "Q"
        # Same inputs, but the first arg is now a byte read: 58 != 2.
        assert go("NnNn\n@nd\n@nd\n{values/=u/=u/=}\ndiv", ":\n\x02\n") == "T"

    def test_developer_prints_something_fixed(self) -> None:
        assert go("developer") == go("developer")

    def test_tilde_is_usually_silent(self) -> None:
        """One run in ten prints; a seeded source makes that checkable."""
        outputs = {go("~", "") for _ in range(1)}
        assert outputs <= {"", "Interprogck8\n"}

    def test_tilde_prints_exactly_on_the_zero_draw(self) -> None:
        for first, expected in ((0, "Interprogck8\n"), (1, ""), (9, "")):
            io = ScriptedIO("")
            native.run("~", io, FirstDraw(first))
            assert io.getvalue() == expected


class TestDownAccLines:
    def test_zero_falls_through(self) -> None:
        assert go("NnNn\nDownAccLines\nnNnN\ndiv") == "A"

    def test_skips_the_accumulator_in_lines(self) -> None:
        """acc=2 skips two lines, so the two ``div``s in between go unrun."""
        assert go("NnNn\n@nd\n@nd\nDownAccLines\nEmpty_\ndiv\nnNnN\ndiv") == "A"

    def test_landing_past_the_end_halts(self) -> None:
        """Landing exactly one past the last line ends the run, not errors."""
        assert go("nNnN\ndiv\nNnNn\nDownAccLines") == "A"

    def test_running_off_the_end_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError):
            go("NnNn\n@id\nDownAccLines\nx")

    def test_inside_a_function_is_refused(self) -> None:
        """A frame index is not a program line, so the jump names nothing."""
        with pytest.raises(HaltError):
            go("<\nNnNn\nDownAccLines\n>\nEXE")


class TestFunctions:
    def test_definition_is_skipped_not_executed(self) -> None:
        """``<`` captures the body and jumps past it; only ``EXE`` runs it."""
        assert go("<\nnNnN\ndiv\n>\nEXE\nEXE") == "AA"

    def test_ift_and_ifq(self) -> None:
        assert go("<\nnNnN\ndiv\n>\n{values/=/=/=.}\nIFT") == "A"
        assert go("<\nnNnN\ndiv\n>\n{values/=/=/=}\nIFT") == ""
        assert go("<\nnNnN\ndiv\n>\n{values/=/=/=}\nIFQ") == "A"

    def test_redefining_replaces_the_slot(self) -> None:
        """There is one slot, so a second ``<`` overwrites the first body."""
        assert go("<\nnNnN\ndiv\n>\n<\nEmpty_\ndiv\n>\nEXE") == " "

    def test_unclosed_function_is_refused(self) -> None:
        with pytest.raises(HaltError):
            go("<\nnNnN")

    def test_nested_opener_is_refused(self) -> None:
        with pytest.raises(HaltError):
            go("<\n<\n>\n>\nEXE")


class TestRestart:
    def test_z_deletes_the_previous_line_and_starts_over(self) -> None:
        """``z`` drops itself and the line above, then reruns from the top.

        First pass prints ``A`` and reaches ``z``; the program becomes
        ``nNnN div @id div`` and reruns, printing ``A`` then 75 (``K``).
        The second pass has no ``z``, so the restart is not a loop.
        """
        assert go("nNnN\ndiv\nEmpty_\nz\n@id\ndiv") == "AAK"

    def test_z_on_the_first_line_is_refused(self) -> None:
        with pytest.raises(HaltError):
            go("z\nx")

    def test_z_inside_a_function_is_refused(self) -> None:
        with pytest.raises(HaltError):
            go("x\n<\nz\n>\nEXE")


class TestErrors:
    def test_empty_program_halts_silently(self) -> None:
        """No lines, nothing to run: the cursor starts past the end."""
        io = ScriptedIO("")
        native.run("", io)
        assert io.getvalue() == ""

    def test_unknown_line_is_a_runtime_error(self) -> None:
        """Refused when *executed*, not at parse time: ``DownAccLines`` and
        ``z`` make lines legally unreachable, so an upfront scan would
        reject working programs.
        """
        with pytest.raises(HaltError):
            go("nonsense")
        assert go("NnNn\n@nd\nDownAccLines\nnonsense\nnNnN\ndiv") == "A"

    def test_blank_line_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError):
            go("\nx")

    def test_empty_input_line_is_refused(self) -> None:
        """The spec's EmptyInputError, overriding the repo's read-as-0."""
        with pytest.raises(HaltError):
            go("u", "\n")

    def test_exhausted_input_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            go("u", "")


class TestBranchingSearch:
    """``[a b]`` and ``~`` draw, so a hang proof must hold over every draw."""

    def test_a_draw_forks_into_every_outcome(self) -> None:
        """Every distinct byte result is reachable, including wrapped ranges."""
        for low, high in ((1, 2), (254, 258), (256, 258), (1, 513)):
            machine = native._Machine(
                f"[{native._dice(low)} {native._dice(high)}]\ndiv", ScriptedIO("")
            )
            start = machine.branching_snapshot()
            assert not machine.branching_halted(start)
            successors = machine.branching_successors(
                start, max(100, min(high - low + 1, 256))
            )
            assert successors is not None
            assert {s[2] for s in successors} == {v % 256 for v in range(low, high + 1)}
            needed = len({v % 256 for v in range(low, high + 1)})
            assert machine.branching_successors(start, needed - 1) is None
            exact = machine.branching_successors(start, needed)
            assert exact is not None
            assert set(exact) == set(successors)

        class NoDraw:
            """Forbid using the live provider to enumerate outcomes."""

            def __init__(self):
                self.calls = []

            def randbelow(self, upper):
                self.calls.append(upper)
                raise AssertionError("live branch provider called")

        provider = NoDraw()
        large = ":" * 128
        for line, values in (
            ("{values/=[. :]/=./=.}", {81, 84}),
            ("{values/=[. :]/=[. :]/=[. :]}", {81, 84}),
            ("{values/=[. .]/=./=.}", {81}),
            ("{values/=[. :]/=:/=:}", {81, 84}),
            ("{values/=[. :]/=:/=...}", {84}),
            ("{values/=[. ]/=/=}", {81, 84}),
            ("{values/=/=/=}", {81}),
            (f"{{values/=[{large} {large}:]/=./=.}}", {84}),
        ):
            port = ScriptedIO("")
            machine = native._Machine(line + "\nx", port, provider)
            start = machine.branching_snapshot()
            saved = machine.snapshot()
            workspace = machine.workspace_snapshot()
            hashes = hash(saved), hash(workspace)
            successors = machine.branching_successors(start, len(values))
            assert successors is not None
            assert {state[2] for state in successors} == values
            assert machine.branching_successors(start, len(values) - 1) is None
            assert machine.snapshot() == saved
            assert machine.workspace_snapshot() == workspace
            assert (hash(saved), hash(workspace)) == hashes
            assert (port.getvalue(), port.position(), port.reads, port.past_end) == (
                "",
                0,
                0,
                0,
            )
            assert provider.calls == []

        machine = native._Machine("[. :]", ScriptedIO(""), provider)
        with patch.object(native, "_outcomes", side_effect=AssertionError("evaluated")):
            assert machine.branching_successors(machine.branching_snapshot(), 0) is None
        with pytest.raises(AssertionError, match="live branch provider called"):
            machine.step()
        assert provider.calls == [2]

        # Q loops; independent range draws can produce T and fall off the code.
        source = "{values/=[. :]/=./=.}\n<\nx\nEXE\n>\nIFQ"
        actual = native._Machine(source, ScriptedIO(""), FirstDraw(1))
        for _ in range(3):
            actual.step()
        assert actual.halted
        assert actual.state.acc == 84
        assert actual.io.getvalue() == ""
        guarded = NoDraw()
        machine = native._Machine(source, ScriptedIO(""), guarded)
        before = machine.snapshot()
        assert run_until_halt_or_all_branches_cycle(machine, limit=32) is True
        assert machine.snapshot() == before
        assert guarded.calls == []
        vm = make_vm("Interprogck8", ProgramArtifact(source, "Interprogck8"))
        assert isinstance(vm, SnapshotVM)
        before = vm.snapshot()
        assert run_until_halt_or_all_branches_cycle(vm, limit=32) is True
        assert vm.snapshot() == before
        assert vm.output == ""

    def test_tilde_has_one_outcome_the_state_can_see(self) -> None:
        """``~``'s ten draws differ only in output, which is left out."""
        machine = native._Machine("~\nx", ScriptedIO(""))
        successors = machine.branching_successors(machine.branching_snapshot(), 100)
        assert successors is not None
        assert len(successors) == 1
        start = machine.branching_snapshot()
        assert machine.branching_successors(start, 0) is None
        assert machine.branching_successors(start, 1) == successors

    @pytest.mark.parametrize("line", ["[. :", "[. :x"])
    def test_a_range_missing_its_closer_is_refused(self, line: str) -> None:
        """An unclosed ``[`` is no range: its last character is not a bracket."""
        with pytest.raises(HaltError, match="unknown instruction"):
            go(line)

    def test_a_reading_line_declines_to_fork(self) -> None:
        """Siblings cannot share one input cursor, so the search declines."""
        machine = native._Machine("u\ndiv", ScriptedIO("a\n"))
        assert machine.branching_successors(machine.branching_snapshot(), 100) is None
        port = ScriptedIO("A\n")
        machine = native._Machine("{values/=bad/=u/=}", port)
        assert machine.branching_successors(machine.branching_snapshot(), 1) is None
        assert (port.position(), port.reads, port.past_end) == (0, 0, 0)

    def test_an_unexecutable_line_fails_the_search(self) -> None:
        """A native error cannot become a divergence verdict."""
        machine = native._Machine("nonsense", ScriptedIO(""))
        with pytest.raises(HaltError, match="unknown instruction"):
            machine.branching_successors(machine.branching_snapshot(), 100)
        for line in ("{values/=[. :]/=./=bad}", "{values/=[bad .]/=x/=y}"):
            machine = native._Machine(line, ScriptedIO(""))
            with pytest.raises(HaltError, match="not a dice literal: 'bad'"):
                machine.branching_successors(machine.branching_snapshot(), 1)

    def test_a_finished_program_is_branching_halted(self) -> None:
        machine = native._Machine("x", ScriptedIO(""))
        machine.step()
        assert machine.branching_halted(machine.branching_snapshot())
        state = machine.branching_snapshot()
        assert machine.branching_successors(state, 0) is None
        assert machine.branching_successors(state, 1) == (state,)


class TestNestedArguments:
    def test_an_omitted_range_bound_is_the_accumulator(self) -> None:
        """``[ ]`` with both bounds empty can only roll the accumulator."""
        assert go("nNnN\n[ ]\ndiv") == "A"

    def test_a_nested_py_supplies_a_range_bound(self) -> None:
        assert go("NnNn\n[. $py]\ndiv", ":\n") in {chr(1), chr(2)}

    def test_a_malformed_range_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError):
            go("[. : .]")

    def test_a_nested_range_supplies_a_comparison_argument(self) -> None:
        """``[. .]`` can only be 1, so it agrees with an accumulator of 1."""
        assert go("NnNn\n@nd\n{values/=/=/=[. .]}\ndiv") == "Q"

    def test_a_stray_closer_is_a_no_op(self) -> None:
        """A ``>`` reached outside a captured body does nothing."""
        assert go("nNnN\n>\ndiv") == "A"

    def test_an_empty_function_body_returns_at_once(self) -> None:
        assert go("<\n>\nnNnN\nEXE\ndiv") == "A"


class TestConstructedGuards:
    """Guards no whole program reaches, driven on hand-built states.

    Each is a real refusal the transition owes its caller; none is
    reachable from source text, because ``_capture`` skips a body before
    it can run and the shell always supplies the reads a line asks for.
    """

    def test_an_opener_inside_a_body_is_refused(self) -> None:
        inside = native._State(("<", "x"), 0, 0, ("<",), ((("<",), 0),))
        with pytest.raises(HaltError, match="inside other functions"):
            native._capture(inside)

    @pytest.mark.parametrize(
        "line", ["{values/=a/=b}", "{valuesX/=a/=b/=c}", "{values/=a/=b/=c/=d}"]
    )
    def test_a_misshapen_comparison_is_not_a_comparison(self, line: str) -> None:
        """Not a comparison, so running it is the unknown-line error."""
        assert native._split_args(line) is None
        with pytest.raises(HaltError, match="unknown instruction"):
            go(line)

    def test_a_malformed_argument_reads_no_input(self) -> None:
        """``x$py]`` is not a range, so the line takes no byte: its error is
        the unknown-literal one, not end-of-input."""
        with pytest.raises(HaltError):
            go("{values/=x$py]/=/=}", "")

    def test_a_range_bound_with_no_byte_is_refused(self) -> None:
        with pytest.raises(HaltError, match="read nothing"):
            native._roll("[$py .]", 0, None, None)

    def test_a_comparison_argument_with_no_byte_is_refused(self) -> None:
        with pytest.raises(HaltError, match="read nothing"):
            native._value("$py", 0, None, None)


class TestMachine:
    def test_snapshot_covers_the_slot_and_the_cursor(self) -> None:
        """Two states differing only in the slot must not compare equal."""
        first = native._Machine("x\nx", ScriptedIO(""))
        second = native._Machine("x\nx", ScriptedIO(""))
        assert first.snapshot() == second.snapshot()
        second.state = second.state.__class__(second.state.lines, slot=("x",))
        assert first.snapshot() != second.snapshot()

    def test_accepts_a_line_list(self) -> None:
        """The registry sets ``split=True``, so ``run`` takes lines."""
        io = ScriptedIO("")
        native.run(["nNnN", "div"], io)
        assert io.getvalue() == "A"
