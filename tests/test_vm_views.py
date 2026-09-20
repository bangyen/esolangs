"""Named VM views and their compact formatting."""

import contextlib

import pytest

import esolangs


def _view_cases() -> list[tuple[str, object]]:
    """Return every ``(language, example)`` pair the view sweep can drive.

    An example is keyed by the language's slug, its stem, or the slug of its
    display name, so all three are tried -- matching on only one silently
    skips a third of the registry.
    """
    from esolangs.registry import LANGUAGES, canonical_id
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    known = set(esolangs.list_languages())
    by_id: dict[str, str] = {}
    for name, lang in LANGUAGES.items():
        for key in (lang.id, name, canonical_id(name), name.lower()):
            by_id.setdefault(key, name)
    cases: list[tuple[str, object]] = []
    for eid, example in BOOLEAN_EXAMPLES.items():
        name = (
            by_id.get(eid)
            or by_id.get(example.stem)
            or by_id.get(canonical_id(eid.replace("-", " ")))
        )
        if name is None or name not in known:
            continue
        cases.append((name, example))
    return cases


_VIEW_CASES = _view_cases()


_VIEW_IDS = [name for name, _ in _VIEW_CASES]


class TestViews:
    """The machine's own named state, found rather than listed."""

    def test_it_finds_the_names_the_machine_gives_its_state(self) -> None:
        vm = esolangs.make_vm("brainfuck", "+++")
        vm.step()
        assert dict(vm.views)["ptr"] == "0"
        assert dict(vm.views)["ind"] == "1"

    def test_it_leaves_out_what_every_language_already_offers(self) -> None:
        vm = esolangs.make_vm("brainfuck", "+++")
        named = dict(vm.views)
        for standard in ("ip", "memory", "stack", "output", "halted"):
            assert standard not in named

    def test_it_leaves_out_the_traits_and_the_snapshot_hooks(self) -> None:
        vm = esolangs.make_vm("brainfuck", "+++")
        named = dict(vm.views)
        for machinery in ("snapshot", "self_halts", "ip_shape"):
            assert machinery not in named

    def test_a_language_whose_state_is_all_standard_names_nothing(self) -> None:
        # Not every machine keeps anything beyond the common five, and an
        # empty result is the right answer rather than a failure.
        assert esolangs.make_vm("Sophie", "").views == ()

    def test_a_long_sequence_is_cut_before_it_is_formatted(self) -> None:
        # A tape can be thousands of cells; the view has to be short, and
        # cheap to produce, at every step.
        from esolangs.vm import _abbreviate

        text = _abbreviate(list(range(4096)))
        assert len(text) < 80
        assert "+4088 more" in text

    def test_a_short_sequence_is_shown_whole(self) -> None:
        from esolangs.vm import _abbreviate

        assert _abbreviate([1, 2, 3]) == "[1, 2, 3]"

    def test_a_sequence_of_exactly_the_limit_is_shown_whole(self) -> None:
        """The cut is one *past* the limit, not at it.

        Pinned at the edge because that is the only length where the two
        readings differ; a sweep found a widened comparison here passing
        every other test in this class.
        """
        from esolangs.vm import _VIEW_ITEMS, _abbreviate

        assert "more" not in _abbreviate(list(range(_VIEW_ITEMS)))
        assert "more" in _abbreviate(list(range(_VIEW_ITEMS + 1)))

    def test_a_long_scalar_is_truncated(self) -> None:
        from esolangs.vm import _abbreviate

        assert len(_abbreviate("x" * 500)) <= 60

    def test_the_scalar_cut_is_pinned_at_its_edge(self) -> None:
        """Sixty characters survive whole; sixty-one is cut.

        The length measured is the *repr*, not the value -- a 58-character
        string reprs to 60 with its quotes -- and asserting only that a
        500-character value comes back short says nothing about where the
        edge is, which a sweep found free to move either way.
        """
        from esolangs.vm import _abbreviate

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

        vm = esolangs.make_vm("brainfuck", "+")
        object.__setattr__(vm, "_machine", _Machine())
        assert _DelegatingVM.views.fget(vm) == (("fine", "7"),)

    @pytest.mark.parametrize(("name", "example"), _VIEW_CASES, ids=_VIEW_IDS)
    def test_a_language_can_be_asked_on_a_real_program(self, name, example) -> None:
        """No interpreter's properties raise when read as views.

        Driven from the committed examples rather than an empty program,
        because several languages reject one -- and an empty program would
        not reach the state the views describe anyway.

        One case per language rather than one loop over all of them: the
        loop did the same work but landed on a single xdist worker, where it
        measured ~1.2s against the 1s fast band while taking 0.38s alone.
        Any change to the suite's test count could tip it either way, so it
        was a band failure waiting on an unrelated commit.  Split, each case
        is a few milliseconds and the failing language is named by the test
        id instead of by an assertion message.
        """
        stdin = "".join(line + "\n" for line in example.inputs)
        vm = esolangs.make_vm(name, example.build(), stdin)
        assert all(isinstance(part, str) for view in vm.views for part in view), name
        # Again once the machine has moved, since a view reads state
        # that the initial one may not have reached.
        with contextlib.suppress(Exception):
            vm.step()
        assert all(isinstance(part, str) for view in vm.views for part in view), name

    def test_the_view_sweep_reaches_most_of_the_registry(self) -> None:
        """The split above is only meaningful if it still covers the registry.

        Kept as its own assertion because a parametrized sweep that silently
        resolved zero languages would otherwise pass by vacuously collecting
        no cases at all.
        """
        assert len(_VIEW_CASES) > 50, f"only reached {len(_VIEW_CASES)} languages"
