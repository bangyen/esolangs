"""Boolfuck through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api
from esolangs.tui import History, render, replay


class TestPointerFallback:
    """A tape machine that names no state still shows where it points."""

    def test_boolfuck_frames_carry_a_pointer(self) -> None:
        history = History("Boolfuck", "+>", "")
        assert history.at(0).views == (("ptr", "0"),)
        frame = history.at(2)
        assert frame.views == (("ptr", "1"),)
        assert "ptr=1" in render(frame)

    def test_brainfucks_own_views_are_untouched(self) -> None:
        frame = replay("brainfuck", "+", "", 0)
        names = [name for name, _ in frame.views]
        assert "ind" in names
        assert len(names) > 1

    def test_the_debugger_mirrors_the_pointer(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", ">>,", stdin="")
        assert dbg.ptr == 0
        dbg.step()
        assert dbg.ptr == 1
