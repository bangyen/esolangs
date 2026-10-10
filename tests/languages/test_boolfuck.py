"""Boolfuck through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api


class TestPointerFallback:
    """A tape machine that names no state still shows where it points."""

    def test_the_debugger_mirrors_the_pointer(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", ">>,", stdin="")
        assert dbg.ptr == 0
        dbg.step()
        assert dbg.ptr == 1
