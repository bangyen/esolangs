"""Named VM views and their compact formatting."""

import esolangs.debugger as debugger_api


class TestViews:
    """The machine's own named state, found rather than listed."""

    def test_it_finds_the_names_the_machine_gives_its_state(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "+++")
        vm.step()
        assert dict(vm.views)["ptr"] == "0"
        assert dict(vm.views)["ind"] == "1"

    def test_it_leaves_out_what_every_language_already_offers(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "+++")
        named = dict(vm.views)
        for standard in ("ip", "memory", "stack", "output", "halted"):
            assert standard not in named

    def test_it_leaves_out_the_traits_and_the_snapshot_hooks(self) -> None:
        vm = debugger_api.make_vm("brainfuck", "+++")
        named = dict(vm.views)
        for machinery in ("snapshot", "self_halts", "ip_shape"):
            assert machinery not in named

    def test_a_language_whose_state_is_all_standard_names_nothing(self) -> None:
        # Not every machine keeps anything beyond the common five, and an
        # empty result is the right answer rather than a failure.
        assert debugger_api.make_vm("Sophie", "").views == ()

    def test_a_long_sequence_is_cut_before_it_is_formatted(self) -> None:
        # A tape can be thousands of cells; the view has to be short, and
        # cheap to produce, at every step.
        from esolangs._vm_views import _abbreviate

        text = _abbreviate(list(range(4096)))
        assert len(text) < 80
        assert "+4088 more" in text

    def test_a_sequence_of_exactly_the_limit_is_shown_whole(self) -> None:
        """The cut is one *past* the limit, not at it.

        Pinned at the edge because that is the only length where the two
        readings differ; a sweep found a widened comparison here passing
        every other test in this class.
        """
        from esolangs._vm_views import _VIEW_ITEMS, _abbreviate

        assert "more" not in _abbreviate(list(range(_VIEW_ITEMS)))
        assert "more" in _abbreviate(list(range(_VIEW_ITEMS + 1)))

    def test_the_scalar_cut_is_pinned_at_its_edge(self) -> None:
        """Sixty characters survive whole; sixty-one is cut.

        The length measured is the *repr*, not the value -- a 58-character
        string reprs to 60 with its quotes -- and asserting only that a
        500-character value comes back short says nothing about where the
        edge is, which a sweep found free to move either way.
        """
        from esolangs._vm_views import _abbreviate

        assert _abbreviate("x" * 58) == repr("x" * 58)
        assert len(repr("x" * 58)) == 60
        cut = _abbreviate("x" * 59)
        assert cut.endswith("...")
        assert len(cut) == 60

    def test_a_view_that_raises_is_skipped_rather_than_fatal(self) -> None:
        """One broken property must not take the whole screen down."""
        from esolangs.vm import _DelegatingVM

        class _Machine:
            @property
            def fine(self) -> int:
                return 7

            @property
            def broken(self) -> int:
                raise RuntimeError("no")

        vm = debugger_api.make_vm("brainfuck", "+")
        object.__setattr__(vm, "_machine", _Machine())
        assert _DelegatingVM.views.fget(vm) == (("fine", "7"),)
