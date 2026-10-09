"""Stepping every language, and what the wrapper exposes between commands."""

import contextlib

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import UnknownLanguageError
from esolangs.vm import VM

from .samples import (
    SAMPLES,
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
        vm = debugger_api.make_vm(language, pixels, stdin="1\n")
        assert isinstance(vm, VM)
        assert _run_all(vm) == "1"
        assert vm.ip is None
        debugger = debugger_api.make_debugger(language, pixels, stdin="0\n")
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
            "Fish",
            "INTERCAL",
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
            vm = debugger_api.make_vm(name, program, stdin=stdin)
            with contextlib.suppress(Exception):
                vm.step()
            before_mem, before_stk = list(vm.memory), list(vm.stack)
            vm.memory.append(12345)
            vm.stack.append("scribble")
            assert list(vm.memory) == before_mem, f"{name}: memory is live"
            assert list(vm.stack) == before_stk, f"{name}: stack is live"

    def test_stepping_is_reproducible_for_the_random_languages(self) -> None:
        """Each sampled random instruction steps the same way twice."""
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
