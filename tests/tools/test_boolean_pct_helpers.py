"""Covers :mod:`esolangs.tools.pct_codes` and the fold's move algebra."""

import importlib
import itertools

from tests.tools.pct_support import _fold_clean_amount, _fold_rule_move, _fold_step


class TestPctSquaredHelpers:
    """The %^2^-1 fold's move algebra, at the states its guards exist for.

    These are pure functions over small states, so the edges a plan only
    reaches incidentally are reachable directly.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    def test_the_move_algebra_refuses_what_it_cannot_place(self) -> None:
        """Each refusal in ``_fold_step`` is a placement the window forbids.

        These are the guards a plan search only meets by accident, so they
        are driven from constructed states instead: a doubling whose result
        leaves the window, a degenerate state with nothing to double, and
        an everything-wipe while two classes are still live (which would
        merge points the suffix still has to tell apart).  Each is paired
        with the state that *is* accepted, so a guard that stopped firing
        would fail here rather than silently widening the algebra.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001
        double = ("m", 0, 0, frozenset())

        # A doubling has to leave the whole state inside the window.
        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert _fold_step(too_wide, double) is None

        # A single point at the origin has a zero span, which is refused by
        # the same guard's lower bound -- there is nothing to scale.
        flat = ((0, 0, "a", frozenset({0})),)
        assert _fold_step(flat, double) is None

        # A state that does fit doubles: the normalization re-anchors the
        # top at 0, so what the scaling shows up as is the doubled gap.
        fits = ((10, 0, "a", frozenset({0})), (0, 0, "a", frozenset({1})))
        doubled = _fold_step(fits, double)
        assert doubled is not None
        positions = sorted(p for p, _, _, _ in doubled)
        assert positions[-1] - positions[0] == 20

        # The everything-wipe merges all points onto one, so it is legal
        # only once a single class is left.
        all_wipe = ("d", 2, limit + 1, frozenset())
        two_classes = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "b", frozenset({1})),
        )
        assert _fold_step(two_classes, all_wipe) is None

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        assert _fold_step(one_class, all_wipe) == ((0, 0, "a", frozenset({0, 1})),)

    def test_a_rise_relocates_survivors_above_the_victims(self) -> None:
        """``u`` mirrors ``d``: the survivors move relative to the victim bottom.

        The two directions are separate arms of the same wipe, and only the
        dive is on the common path, so the rise is driven here directly.
        Both must land every group inside the window and keep one merged
        victim point, which is what makes the resulting state legal.
        """
        state = (
            (0, 0, "a", frozenset({0})),
            (100, 0, "a", frozenset({1})),
            (300, 0, "a", frozenset({2})),
        )
        for kind in ("u", "d"):
            amount = _fold_clean_amount(state, kind, 1)
            assert amount is not None, kind
            moved = _fold_step(state, (kind, 1, amount, frozenset()))
            assert moved is not None, kind
            # One group is wiped onto the origin; the other two survive.
            assert len(moved) == 3, kind
            assert any(p == 0 for p, _, _, _ in moved), kind
            # Every id is still accounted for -- a wipe merges, never drops.
            assert {x for _, _, _, ids in moved for x in ids} == {0, 1, 2}, kind

    def test_a_wipe_whose_survivors_will_not_fit_is_refused(self) -> None:
        """The span is re-checked *after* the relocation, not only before it.

        A wipe's amount is picked from the landing window, so it always
        passes the window check -- but an extent rides along with its group
        and is not scaled by the move, so a wide enough one puts the
        relocated state outside the accumulator's range even at a legal
        amount.  That is what the second span check catches, and nothing
        earlier can: the same wipe on the same positions is accepted once
        the extent is small.
        """
        positions = ((0, 10, 20), ("a", "a", "a"))
        wide = (
            (0, 6000, "a", frozenset({0})),
            (10, 0, "a", frozenset({1})),
            (20, 0, "a", frozenset({2})),
        )
        assert _fold_step(wide, ("u", 1, 3004, frozenset())) is None

        # Same geometry, ordinary extent: the wipe goes through.
        narrow = tuple(
            (p, 0, c, frozenset({i}))
            for i, (p, c) in enumerate(zip(*positions, strict=True))
        )
        assert _fold_step(narrow, ("u", 1, 3004, frozenset())) is not None

    def test_a_clean_amount_needs_a_frame_to_land_in(self) -> None:
        """With no room to relocate into, there is no amount to return.

        A single point has no survivor to measure a window against, so the
        frame is undefined and the caller gets ``None`` rather than an
        amount that would collide.  A state with survivors returns the
        first free landing instead.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001

        assert _fold_clean_amount(((0, 0, "a", frozenset({0})),), "d", 1) is None

        spread = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        for kind in ("d", "u"):
            assert _fold_clean_amount(spread, kind, 1) == limit + 1

    def test_a_reduction_gives_up_when_its_own_move_is_refused(self) -> None:
        """The rules can name a move the algebra then rejects, and that ends it.

        These are two different refusals and only one of them is "no move
        exists": here ``_fold_rule_move`` does return an op -- a rise of the
        bottom group -- but the extents riding along put the relocated state
        outside the window, so ``_fold_step`` refuses it.  The reduction
        stops rather than skipping to a second-choice move, because the
        rules are a construction and not a search.
        """
        module = self.module()
        fold_reduce = module._fold_reduce  # noqa: SLF001
        fold_done = module._fold_done  # noqa: SLF001

        state = (
            (-40, 6000, "a", frozenset({0})),
            (-33, 2000, "b", frozenset({1})),
            (-26, 0, "a", frozenset({2})),
        )
        # The state is unfinished and the rules do offer a move for it ...
        assert fold_done(state) is False
        move = _fold_rule_move(state)
        assert move is not None
        # ... but that very move is one the algebra will not take.
        assert _fold_step(state, move) is None
        assert fold_reduce(state, fold_done, budget=5) is None

    def test_a_reduction_gives_up_when_no_move_applies(self) -> None:
        """``_fold_reduce`` returns ``None`` rather than an unfinished plan.

        A state whose only candidate moves are refused cannot be driven to
        the done condition, and reporting a partial op list would hand the
        emitter a plan that does not reach the answer.  The budget is
        small here so the loop ends on the refusal, not on exhaustion.
        """
        module = self.module()
        fold_reduce = module._fold_reduce  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001

        never_done = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        assert fold_reduce(never_done, lambda _state: False, budget=3) is None

        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert fold_reduce(too_wide, lambda _state: False, budget=3) is None

    def test_the_all_wipe_candidate_needs_one_class_and_something_to_move(
        self,
    ) -> None:
        """``_fold_moves`` offers the everything-wipe only where it is legal.

        It collapses every point onto one, so it is offered only once a
        single class remains -- and only when some group still carries a
        position or an extent, since collapsing an already-collapsed state
        is not a move.
        """
        module = self.module()
        fold_moves = module._fold_moves  # noqa: SLF001

        def kinds(state: object) -> list[tuple[str, int]]:
            return [(m[0], m[1]) for m in fold_moves(state)]

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        # k == len(state) is the everything-wipe.
        assert ("d", 2) in kinds(one_class)

        two_classes = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "b", frozenset({1})),
        )
        assert ("d", 2) not in kinds(two_classes)

        # Already collapsed: nothing to offer at all.
        assert kinds(((0, 0, "a", frozenset({0})),)) == []

    def test_built_fold_skeletons_match_the_mined_plans(self) -> None:
        """The peel/park/close rule reproduces the mined plans exactly.

        These twelve are what the harvest froze: the plan for each run-length
        word the three-phase construction serves.  The module builds them
        from ``r``, ``delta`` and ``pat[1]`` now; this remembers what they
        were.  ``pat[1]`` is ignored at ``r == 5`` -- both pairs there agree
        -- so the ten distinct plans cover twelve keys.
        """
        mined = {
            (2, 0, 0): (("u", 1, "cmax"),),
            (2, 0, 1): (("d", 1, "cmax"),),
            (2, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax")),
            (3, 0, 0): (("d", 1, "cmax"), ("u", 2, "cmax")),
            (3, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax")),
            (4, 0, 0): (
                ("d", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
            (4, 0, 1): (
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (4, 1, 1): (
                ("d", 1, "cmax"),
                ("d", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "cmax"),
                ("d", 1, "land2"),
                ("d", 2, "cmax"),
            ),
            (5, 0, 0): (
                ("d", 1, "cmax"),
                ("u", 2, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (5, 0, 1): (
                ("d", 1, "cmax"),
                ("u", 2, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (5, 1, 0): (
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("u", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
            (5, 1, 1): (
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("u", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
        }
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        assert {k for k in mined if module._fold_served(*k)} == set(mined)  # noqa: SLF001
        for key, plan in mined.items():
            assert module._fold_skeleton(*key) == plan, key  # noqa: SLF001

    def test_fold_served_is_reachability(self) -> None:
        """``_fold_served`` accepts exactly the buildable low-run keys.

        The predicate replaced a twelve-entry table whose comment called
        its four absences a corpus measurement.  They are structural, so
        this re-derives the set rather than pinning it: enumerating every
        run pattern reproduces the accepted keys exactly, and no key the
        predicate accepts is one no pattern can produce.

        ``delta`` is set when every middle index of the pattern is ``1``.
        For ``r`` of 2, 3 and 4 that set contains index 1, so ``delta``
        implies ``pat[1]``; at ``r == 3`` index 1 is the *only* middle, so
        the implication runs both ways there.
        """
        module = self.module()
        reachable = set()
        for r in range(1, 13):
            for pat in itertools.product((0, 1), repeat=r):
                mids = {(r - 1) // 2, r // 2}
                delta = 1 if all(pat[i] for i in mids) else 0
                reachable.add((r, delta, pat[1] if r > 1 else 0))

        accepted = {
            k
            for k in itertools.product(range(9), (0, 1), (0, 1))
            if module._fold_served(*k)  # noqa: SLF001
        }
        assert accepted == {k for k in reachable if 2 <= k[0] <= 5}
        assert not accepted - reachable
