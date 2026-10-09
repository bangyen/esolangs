"""Decleq through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api


class TestDecleqNegativeAddressing:
    """A write past the left end escaped as a bare ``IndexError``."""

    def test_it_halts_instead_of_leaking(self) -> None:
        """Four characters, reduced from a 20,000-character random program."""
        with pytest.raises(esolangs.HaltError, match="past the left end"):
            esolangs.run("Decleq", "4 -8", stdin="", timeout=2)

    def test_the_documented_negative_write_is_unchanged(self) -> None:
        """Indexing from the right is deliberate and pinned elsewhere."""
        vm = debugger_api.make_vm("Decleq", "0 -1 3")
        vm.step()
        assert list(vm.memory)[:3] == [0, -1, -1]
