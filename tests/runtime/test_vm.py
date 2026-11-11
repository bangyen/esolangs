"""Stepping every language, and what the wrapper exposes between commands."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.runtime._vm_protocol import VM
from tests.support.pick import languages
from tests.support.reference import REFERENCE
from tests.support.vm_support import _run_all


class TestProtocol:
    @pytest.mark.medium
    @pytest.mark.parametrize(
        "language", languages(source_kind="raster", boolean_generator=True)
    )
    def test_raster_languages_step_their_pixels(
        self, language: str, native_png
    ) -> None:
        source = esolangs.generate(language, "01")
        pixels = esolangs.Raster.from_png(native_png(source))
        program = esolangs.Language(language).from_source(pixels)
        vm = debugger_api.make_vm(language, program, stdin="1\n")
        assert isinstance(vm, VM)
        assert _run_all(vm) == "1"
        assert vm.ip is None
        debugger = debugger_api.make_debugger(language, program, stdin="0\n")
        assert _run_all(debugger.vm) == "0"


class TestBrainfuck:
    def test_tape_and_cursor_evolve(self) -> None:
        vm = debugger_api.make_vm(REFERENCE, "++.")
        assert (vm.ip, vm.memory, vm.output) == (0, [0], "")
        vm.step()
        assert (vm.ip, vm.memory) == (1, [1])
        vm.step()
        assert (vm.ip, vm.memory) == (2, [2])
        vm.step()
        assert vm.output == "\x02"
        assert vm.halted


class TestEveryLanguageIsSteppable:
    """The two whole-registry invariants, as tests rather than prose."""

    def test_every_random_machine_implements_the_branching_protocol(self) -> None:
        """Randomness no longer costs a language its hang proof."""
        from esolangs._cycles import _BranchingStepMachine
        from esolangs.registry import LANGUAGES
        from tests.support.samples import SAMPLES

        observed = set()
        for name, language in LANGUAGES.items():
            if not language.runtime.random:
                continue
            source, stdin = SAMPLES[name]
            vm = debugger_api.make_vm(name, source, stdin=stdin)
            assert isinstance(vm._machine, _BranchingStepMachine), name
            observed.add(name)
        assert observed == set(languages(random=True))
        assert observed

    def test_the_stub_sources_reject_an_empty_range(self) -> None:
        """``randbelow`` checks its bound instead of ignoring it."""
        from esolangs.runtime.randomness import FirstDraw, Seeded

        for source in (Seeded(0), FirstDraw(1)):
            for bad in (0, -1):
                with pytest.raises(ValueError, match=f"must be positive, got {bad}"):
                    source.randbelow(bad)

        assert Seeded(0).randbelow(1) == 0
        assert FirstDraw(1).randbelow(1) == 0
