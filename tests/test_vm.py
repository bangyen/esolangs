"""Stepping every language, and what the wrapper exposes between commands."""

import contextlib

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import UnknownLanguageError
from esolangs.vm import VM

from .samples import (
    CIRCUIT_PRIME_TESTER,
    FLOWCHART_CAT,
    FLOWCHART_TRUTH_MACHINE,
    SAMPLES,
    STREETCODE,
    STREETCODE_GAP,
    bits_of,
)


def _run_all(vm: VM) -> str:
    while not vm.halted:
        vm.step()
    return vm.output


class TestProtocol:
    @pytest.mark.medium
    @pytest.mark.parametrize("language", ["Line", "Piet"])
    def test_raster_languages_step_their_pixels(self, language: str) -> None:
        source = esolangs.generate(language, "01")
        pixels = esolangs.Raster.from_png(source.to_png())
        vm = debugger_api.make_vm(language, pixels, "1\n")
        assert isinstance(vm, VM)
        assert _run_all(vm) == "1"
        assert vm.ip is None
        debugger = debugger_api.make_debugger(language, pixels, "0\n")
        assert _run_all(debugger.vm) == "0"


class TestBrainfuck:
    def test_tape_and_cursor_evolve(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "++.")
        assert (vm.ip, vm.memory, vm.output) == (0, [0], "")
        vm.step()
        assert (vm.ip, vm.memory) == (1, [1])
        vm.step()
        assert (vm.ip, vm.memory) == (2, [2])
        vm.step()
        assert vm.output == "\x02"
        assert vm.halted


class TestSbleq:
    def test_oisc_cells_and_ip(self) -> None:
        vm = debugger_api.make_vm("S*bleq", "-3 11 3")
        assert (vm.ip, vm.memory, vm.stack) == (0, [-3, 11, 3], [])
        vm.step()
        assert (vm.ip, vm.halted, vm.output) == (3, True, "\x00")


class TestDimensional:
    def test_byte_value_exposed(self) -> None:
        vm = debugger_api.make_vm("Dimensional", "++.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()
        assert vm.memory == [1]
        vm.step()
        assert vm.memory == [2]
        vm.step()
        assert vm.output == "\x02"


class TestGrapheme:
    def test_stack_exposed(self) -> None:
        vm = debugger_api.make_vm("Grapheme", "FAFY")
        assert (vm.ip, vm.memory, vm.stack) == ((0,), [], [])
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 1
        assert vm.stack == [1]
        vm.step()  # Y prints
        assert vm.output == "1"
        assert vm.halted
        assert vm.ip == (len("FAFY"),)  # frames are gone once halted
        assert vm.memory == []

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            debugger_api.make_vm("Grapheme", "a")

    def test_ip_exposes_the_call_stack(self) -> None:
        # FAF pushes 1, EKE pushes the string "K"; G calls it as a nested
        # frame (K dups the shared stack's top), so ip grows to (caller pc,
        # callee pc) while that frame is active instead of folding it into
        # one cursor.
        vm = debugger_api.make_vm("Grapheme", "FAFEKEG")
        for _ in range(7):
            vm.step()
        assert vm.ip == (7, 0)  # caller's pc past G, callee's pc at its start
        assert vm.stack == [1]
        vm.step()  # the callee's K command runs, then the frame finishes
        assert vm.halted
        assert vm.ip == (7,)  # the callee frame is gone once it returns
        assert vm.stack == [1, 1]

    def test_caller_resumes_after_the_callee_returns(self) -> None:
        # Y after G still has to run once the callee pops, proving the
        # halted-``ip`` sentinel is the top-level frame's own end position,
        # not an artifact of the callee finishing on the caller's last pc.
        vm = debugger_api.make_vm("Grapheme", "FAFEKEGY")
        for _ in range(9):
            vm.step()
        assert vm.halted
        assert vm.output == "1"  # Y printed the duplicated int 1
        assert vm.ip == (len("FAFEKEGY"),)


class TestLaserFuck:
    def test_ip_is_position_and_heading(self) -> None:
        # the adapter's generator is seeded so its first draw is 0 (up), so
        # the laser at (2,4) moves up
        vm = debugger_api.make_vm("LaserFuck", "\u00ff   x\n    +\n    o")
        assert vm.ip == (2, 4, 0)  # the laser's start position and heading
        vm.step()
        assert vm.ip == (1, 4, 0)  # moved up onto the '+'
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (0, 4, 0)  # moved up onto the 'x', died
        assert vm.halted
        assert vm.output == ""  # the tape is not dumped until the next step
        assert vm.stack == []
        vm.step()  # the post-halt step dumps it, as run's own last step does
        assert vm.output == "\x01"
        vm.step()  # and the dump happens once, not once per step past the halt
        assert vm.output == "\x01"

    def test_dump_output_matches_interpreter(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine as _LFMachine
        from esolangs.interpreters.grid_based.laserfuck import run as lf_run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import Seeded

        program = "\u00ff   x\n    +\n    o"
        io_obj = ScriptedIO()
        # The VM builds its machine with ``Seeded(reproducible_seed)``, so
        # handing ``run`` the same source is what makes the two sides
        # comparable -- the heading is drawn, not passed, on both.
        lf_run(program.splitlines(), io_obj, rng=Seeded(_LFMachine.reproducible_seed))
        vm = debugger_api.make_vm("LaserFuck", program)
        _run_all(vm)
        vm.step()  # the dump, which run performs as its own last step
        assert vm.output == io_obj.getvalue()


class TestArrowQueue:
    def test_ip_is_position_and_heading(self) -> None:
        vm = debugger_api.make_vm("ArrowQueue", "~+*")
        assert vm.ip == (0, 0, 0)
        vm.step()
        assert vm.ip == (0, 1, 0)
        assert vm.stack == [0]
        vm.step()  # + pops the queued direction (right) and keeps going
        assert vm.ip == (0, 2, 0)
        assert vm.stack == []
        vm.step()  # * turns down off the single row and halts
        assert vm.halted
        assert vm.memory == []
        vm.step()  # stepping a halted VM is a no-op


class TestStreetcode:
    def test_car_position_heading_and_cells(self) -> None:
        vm = debugger_api.make_vm("Streetcode", STREETCODE)
        assert vm.ip == (2, 1, 1)  # on the C, heading east
        assert vm.memory == []
        vm.step()  # drives onto the first ^
        assert vm.ip == (2, 2, 1)
        vm.step()  # ^ increments the cell under CP
        assert vm.memory == [1]
        vm.step()  # ^ again
        assert vm.memory == [2]
        vm.step()  # O prints it
        assert vm.output == "\x02"
        assert vm.stack == []

    def test_memory_fills_the_gaps_between_written_cells(self) -> None:
        """The tape is a sparse dict, so a skipped cell still reads as zero."""
        vm = debugger_api.make_vm("Streetcode", STREETCODE_GAP)
        assert _run_all(vm) == ""
        assert vm.memory == [1, 0, 1]


class TestFlowchart:
    def test_live_pointer_position_and_heading(self) -> None:
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert vm.ip == (0, 10, 0, 1)  # on the opening ( ), heading east
        assert vm.stack == []
        vm.step()
        assert vm.ip == (0, 11, 0, 1)  # moved on, still travelling east

    def test_ip_is_none_once_every_pointer_has_stopped(self) -> None:
        """``ip`` reports the first live pointer, so a finished run has none."""
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_TRUTH_MACHINE, "0\n")
        assert _run_all(vm) == "0"
        assert vm.ip is None

    def test_the_deque_holds_what_the_pointers_read(self) -> None:
        """The cat reads its bits onto the shared tape before printing them."""
        vm = debugger_api.make_vm("Flowchart", FLOWCHART_CAT, "1\n")
        while not vm.halted and not vm.memory:
            vm.step()
        assert vm.memory == [1]


class TestCircuitDiagram:
    def test_wire_values_are_per_generation_events(self) -> None:
        vm = debugger_api.make_vm("Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(3))
        assert vm.ip is None  # nothing moves through a circuit
        assert vm.stack == []
        vm.step()
        assert vm.memory == [0, 0, 1, 1]  # the input port, most significant first
        assert _run_all(vm) == "1"

    def test_stepping_detects_exactly_the_primes(self) -> None:
        """The page's worked example, replayed a generation at a time."""
        detected = {
            n
            for n in range(16)
            if _run_all(
                debugger_api.make_vm(
                    "Circuit Diagram", CIRCUIT_PRIME_TESTER, bits_of(n)
                )
            )
            == "1"
        }
        assert detected == {2, 3, 5, 7, 11, 13}


class TestForth:
    def test_stack_and_active_frame_cursor(self) -> None:
        vm = debugger_api.make_vm("Forþ", "65.")
        assert vm.ip == (0,)
        assert vm.stack == []
        vm.step()  # 6 pushes
        assert (vm.ip, vm.stack) == ((1,), [6])
        vm.step()  # 5 pushes
        assert vm.stack == [6, 5]
        vm.step()  # . pops and prints the low byte
        assert vm.output == "\x05"
        vm.step()  # finalizing the finished frame halts the machine
        assert vm.halted
        assert vm.ip == (len("65."),)  # frames are gone once halted
        assert vm.memory == []

    def test_ip_exposes_the_call_stack(self) -> None:
        # '1{:}1;' stores the scope ':' under key 1, then calls it; ip
        # grows to (caller pc, callee pc) while the scope is active instead
        # of folding it into one cursor.
        vm = debugger_api.make_vm("Forþ", "1{:}1;")
        for _ in range(4):
            vm.step()
        assert vm.ip == (6, 0)  # caller's pc past ';', callee's pc at start
        assert vm.stack == [1]
        vm.step()  # the callee's ':' command runs (dup)
        assert vm.ip == (6, 1)
        assert vm.stack == [1, 1]
        vm.step()  # finalizing the finished callee frame halts the machine
        assert vm.halted
        assert vm.ip == (6,)  # the callee frame is gone once it returns


class TestBitdeque:
    def test_cursor_deque_and_register(self) -> None:
        vm = debugger_api.make_vm("Bitdeque", "PUSH INVERT")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [0])
        vm.step()  # PUSH appends the register
        assert (vm.ip, vm.memory) == (1, [0])
        vm.step()  # INVERT flips the register
        assert vm.stack == [1]
        assert vm.halted
        assert vm.output == ""  # the deque is not rendered until the next step
        vm.step()  # the post-halt step renders it, as run's own last step does
        assert vm.output == "0"
        vm.step()  # and rendering happens once, not once per step past the halt
        assert vm.output == "0"


class TestForbin:
    def test_locals_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Forbin", "main { x = 1; }")
        assert vm.ip == (0,)
        assert vm.memory == []
        assert vm.stack == []
        vm.step()
        assert vm.ip == (1,)
        assert vm.memory == [1]
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
        assert vm.memory == []  # the frame stack has emptied

    def test_ip_exposes_the_call_stack(self) -> None:
        # a statement-position call pushes a new frame, deepening ip
        vm = debugger_api.make_vm("Forbin", "main { f 0; }\nf x { y = 1; }")
        assert vm.ip == (0,)
        vm.step()  # f 0; pushes a frame for f, advancing main's own cursor
        assert vm.ip == (1, 0)
        vm.step()  # y = 1; inside f
        assert vm.ip == (1, 1)
        vm.step()  # f's body is exhausted; the frame pops
        assert vm.ip == (1,)
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted


class TestFargo:
    def test_frames_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Fargo", "$", "0\n")
        # `memory` is the whole state: the input read and the output built.
        assert (vm.ip, vm.memory, vm.stack) == (0, [0, 0], [])
        vm.step()  # the top-level line pushes its frame
        assert vm.ip == 1
        assert len(vm.stack) == 1
        frame = vm.stack[0]
        assert (frame.tokens, frame.pos, frame.fn_name) == (("$",), 0, "")  # type: ignore[attr-defined]
        vm.step()  # $ prints the number it was given
        assert vm.output == "0"
        vm.step()  # the frame pops, and the run is over
        assert (vm.stack, vm.halted) == ([], True)


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        # Naming the language it refused is the whole use of the message to
        # a caller who passed it by mistake, and it was unpinned.
        with pytest.raises(UnknownLanguageError, match="NoSuchLanguage"):
            debugger_api.make_vm("NoSuchLanguage", "+")


class TestEveryLanguageIsSteppable:
    """The two whole-registry invariants, as tests rather than prose."""

    def test_every_random_machine_implements_the_branching_protocol(self) -> None:
        """Randomness no longer costs a language its hang proof."""
        import importlib
        import inspect

        from esolangs.registry import INTERPRETERS

        methods = (
            "branching_snapshot",
            "branching_halted",
            "branching_successors",
        )

        random_languages: set[str] = set()
        missing: dict[str, list[str]] = {}
        for language, module_path in sorted(INTERPRETERS.items()):
            module = importlib.import_module(module_path)
            state = getattr(module, "_Machine")  # noqa: B009
            if "rng" not in inspect.signature(state.__init__).parameters:
                continue
            random_languages.add(language)
            absent = [name for name in methods if not hasattr(state, name)]
            if absent:
                missing[language] = absent

        assert missing == {}
        assert random_languages == {
            "Befunge",
            "Befunge-98",
            "Fish",
            "LaserFuck",
            "Modulous",
            "Painfuck",
            "Super SNUSP",
            "Thue",
            "thisthat",
        }, "the random set changed -- a new language needs a branching search"

    def test_memory_and_stack_are_copies_not_the_live_store(self) -> None:
        """A caller must not be able to write into a running machine.

        ``_DelegatingVM`` makes the copy once for every interpreter, so a tape
        language and FALSE (non-empty memory and stack) cover it.
        """
        for name in ("brainfuck", "FALSE"):
            program, stdin = SAMPLES[name]
            vm = debugger_api.make_vm(name, program, stdin)
            with contextlib.suppress(Exception):
                vm.step()
            before_mem, before_stk = list(vm.memory), list(vm.stack)
            vm.memory.append(12345)
            vm.stack.append("scribble")
            assert list(vm.memory) == before_mem, f"{name}: memory is live"
            assert list(vm.stack) == before_stk, f"{name}: stack is live"

    def test_stepping_is_reproducible_for_the_random_languages(self) -> None:
        """Four languages have a random instruction; the VM pins every one."""
        from esolangs.interpreters import randomness

        cases = {
            "Painfuck": "y",
            "Modulous": "[RND 9][PRT INT]",
            "LaserFuck": "*\no",
        }

        def trace(language: str, program: str) -> list[object]:
            vm = debugger_api.make_vm(language, program)
            seen: list[object] = []
            for _ in range(40):
                if vm.halted:
                    break
                with contextlib.suppress(Exception):
                    vm.step()
                ip = vm.ip
                seen.append(
                    (tuple(ip) if isinstance(ip, tuple) else ip, tuple(vm.memory))
                )
            return seen

        original = randomness.Seeded.randbelow
        for language, program in cases.items():
            drawn = []

            def counted(self, upper, _o=original, _d=drawn):
                _d.append(upper)
                return _o(self, upper)

            randomness.Seeded.randbelow = counted
            try:
                first = trace(language, program)
            finally:
                randomness.Seeded.randbelow = original
            assert drawn, f"{language}: the random instruction never ran"
            assert trace(language, program) == first, f"{language} is not reproducible"

    def test_the_stub_sources_reject_an_empty_range(self) -> None:
        """``randbelow`` checks its bound instead of ignoring it."""
        from esolangs.interpreters.randomness import FirstDraw, Seeded

        for source in (Seeded(0), FirstDraw(1)):
            for bad in (0, -1):
                with pytest.raises(ValueError, match=f"must be positive, got {bad}"):
                    source.randbelow(bad)

        assert Seeded(0).randbelow(1) == 0
        assert FirstDraw(1).randbelow(1) == 0
