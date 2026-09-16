"""Covers :mod:`esolangs.tools.pct_codes`, and the ladder and deep routes."""

import importlib
import itertools

import pytest


class TestPctSquaredHelpers:
    """The %^2^-1 spelling helpers, at the inputs their guards exist for.

    These are pure functions over small integers, so the edges the search
    itself only reaches incidentally are reachable directly: a width that
    admits no spelling and the zero shortcut.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    def test_sub_of_width_rejects_an_unreachable_split(self) -> None:
        """A width too narrow to spell ``k`` has no ``i``/``s`` split."""
        assert self.module()._sub_of_width(1, 1) is None  # noqa: SLF001

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_zero_needs_no_width(self, name: str) -> None:
        """Subtracting nothing is width zero, not a search."""
        assert getattr(self.module(), name)(0) == 0

    @pytest.mark.parametrize("name", ["_even_width_for"])
    @pytest.mark.parametrize("k", [1, 2, 3, 7])
    def test_unspellable_weights_return_none(self, name: str, k: int) -> None:
        """Some weights have no even-width spelling at all."""
        assert getattr(self.module(), name)(k) is None

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_odd_starting_width_is_bumped_even(self, name: str) -> None:
        """``k == 8`` starts the scan at an odd width, so it is bumped."""
        width = getattr(self.module(), name)(8)
        assert width is not None
        assert width % 2 == 0

    def test_a_ladder_refuses_an_unspellable_base(self) -> None:
        """The lead is spelled first, so its width decides before any weight.

        7 is one of the four values with no even-width spelling, and a
        ladder led by it cannot be built whatever its weights are.
        """
        assert self.module()._ladder_setters((12,), 7) is None  # noqa: SLF001

    def test_a_ladder_refuses_an_unspellable_weight(self) -> None:
        """One bad weight refuses the ladder even under a legal lead.

        The base here spells at width 4, so the refusal can only come from
        the weight -- which separates this from the lead's own guard.
        """
        assert self.module()._ladder_setters((7,), 12) is None  # noqa: SLF001

    def test_a_ladder_spells_both_branches_at_one_width(self) -> None:
        """A legal ladder holds and subtracts at the same length.

        The hold is ``pp`` repeated and the subtraction is the same width,
        so no program leaks which bit it embeds through ``len()``.
        """
        got = self.module()._ladder_setters((12,), 12)  # noqa: SLF001
        assert got is not None
        setters, lead = got
        hold, code = setters[0]
        assert len(hold) == len(code)
        assert lead == code

    def test_every_tabulated_ladder_entry_computes_its_split(self) -> None:
        """Each built ladder entry is checked by arithmetic, not trust.

        The suffix was once found by a breadth-first composition over the
        rungs, then frozen as data; it is computed now, so this re-derives
        what the search used to guarantee: running the suffix over every
        rung of its ladder's stage-one vector -- through :func:`_apply`,
        the exact model of the interpreter's step -- leaves each row's
        answer in the accumulator.  ``l`` is a no-op to the model, so the
        final value is what the program prints.
        """
        module = self.module()
        for table, (index, suffix) in module._ladder_built().items():  # noqa: SLF001
            weights, base = module._LADDERS[index]  # noqa: SLF001
            spelled = module._ladder_setters(weights, base)  # noqa: SLF001
            assert spelled is not None
            setters, lead = spelled
            vec = module._ladder_vector(setters, lead, 3)  # noqa: SLF001
            for row, want in enumerate(table):
                got = module._apply(vec[row], suffix)  # noqa: SLF001
                assert got == int(want), (table, row)

    def test_ladder_gadgets_match_frozen_spellings(self) -> None:
        """The gadget rule reproduces the five searched spellings, byte for byte.

        These strings are what the rung-composition search froze; the
        module now spells each from its ``(cut, slope)`` pair, so this is
        the fixture that keeps the construction honest.  The order matters
        too -- the fold is first-claim-wins over shortest-first gadgets.
        """
        module = self.module()
        assert module._LADDER_GADGETS == (  # noqa: SLF001
            "pspmsmipsp",
            "mpspmipsp",
            "smpspmipsp",
            "mmpspmipsp",
            "pspmimmipsp",
        )

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
        fold_step = module._fold_step  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001
        double = ("m", 0, 0, frozenset())

        # A doubling has to leave the whole state inside the window.
        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert fold_step(too_wide, double) is None

        # A single point at the origin has a zero span, which is refused by
        # the same guard's lower bound -- there is nothing to scale.
        flat = ((0, 0, "a", frozenset({0})),)
        assert fold_step(flat, double) is None

        # A state that does fit doubles: the normalization re-anchors the
        # top at 0, so what the scaling shows up as is the doubled gap.
        fits = ((10, 0, "a", frozenset({0})), (0, 0, "a", frozenset({1})))
        doubled = fold_step(fits, double)
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
        assert fold_step(two_classes, all_wipe) is None

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        assert fold_step(one_class, all_wipe) == ((0, 0, "a", frozenset({0, 1})),)

    def test_a_rise_relocates_survivors_above_the_victims(self) -> None:
        """``u`` mirrors ``d``: the survivors move relative to the victim bottom.

        The two directions are separate arms of the same wipe, and only the
        dive is on the common path, so the rise is driven here directly.
        Both must land every group inside the window and keep one merged
        victim point, which is what makes the resulting state legal.
        """
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001
        clean_amount = module._fold_clean_amount  # noqa: SLF001

        state = (
            (0, 0, "a", frozenset({0})),
            (100, 0, "a", frozenset({1})),
            (300, 0, "a", frozenset({2})),
        )
        for kind in ("u", "d"):
            amount = clean_amount(state, kind, 1)
            assert amount is not None, kind
            moved = fold_step(state, (kind, 1, amount, frozenset()))
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
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001

        positions = ((0, 10, 20), ("a", "a", "a"))
        wide = (
            (0, 6000, "a", frozenset({0})),
            (10, 0, "a", frozenset({1})),
            (20, 0, "a", frozenset({2})),
        )
        assert fold_step(wide, ("u", 1, 3004, frozenset())) is None

        # Same geometry, ordinary extent: the wipe goes through.
        narrow = tuple(
            (p, 0, c, frozenset({i}))
            for i, (p, c) in enumerate(zip(*positions, strict=True))
        )
        assert fold_step(narrow, ("u", 1, 3004, frozenset())) is not None

    def test_a_clean_amount_needs_a_frame_to_land_in(self) -> None:
        """With no room to relocate into, there is no amount to return.

        A single point has no survivor to measure a window against, so the
        frame is undefined and the caller gets ``None`` rather than an
        amount that would collide.  A state with survivors returns the
        first free landing instead.
        """
        module = self.module()
        clean_amount = module._fold_clean_amount  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001

        assert clean_amount(((0, 0, "a", frozenset({0})),), "d", 1) is None

        spread = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        for kind in ("d", "u"):
            assert clean_amount(spread, kind, 1) == limit + 1

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
        fold_rule_move = module._fold_rule_move  # noqa: SLF001
        fold_step = module._fold_step  # noqa: SLF001
        fold_done = module._fold_done  # noqa: SLF001

        state = (
            (-40, 6000, "a", frozenset({0})),
            (-33, 2000, "b", frozenset({1})),
            (-26, 0, "a", frozenset({2})),
        )
        # The state is unfinished and the rules do offer a move for it ...
        assert fold_done(state) is False
        move = fold_rule_move(state)
        assert move is not None
        # ... but that very move is one the algebra will not take.
        assert fold_step(state, move) is None
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

    def test_sub_units_borrows_an_i_back_to_pay_a_remainder_of_one(self) -> None:
        """A remainder of 1 cannot be spelled directly, so a whole ``i`` is broken up.

        ``s`` takes 2 and ``i`` takes 3, so the shortest spelling packs
        as many ``i`` as it can.  A remainder of 1 has no spelling of its
        own -- nothing costs a single unit -- so the rule borrows one
        ``i`` back and pays the resulting 4 as two ``s``.  Every arm is
        pinned here because the lengths are what the width arithmetic
        upstream budgets against.
        """
        module = self.module()
        sub_units = module._sub_units  # noqa: SLF001

        # Exact multiples of 3: all i, nothing left over.
        assert sub_units(3) == "i"
        assert sub_units(9) == "iii"
        # Remainder 2: one trailing s pays it exactly.
        assert sub_units(2) == "s"
        assert sub_units(5) == "is"
        # Remainder 1: borrow an i back, so 4 units spell as two s.
        assert sub_units(4) == "ss"
        assert sub_units(7) == "iss"
        assert sub_units(10) == "iiss"

        # Whatever the arm, the spelling has to be worth what was asked,
        # and no other spelling of the same value may be shorter.
        for units in range(2, 40):
            spelled = sub_units(units)
            assert spelled.count("i") * 3 + spelled.count("s") * 2 == units, units
            best = min(
                (
                    threes + twos
                    for threes in range(units // 3 + 1)
                    for twos in range(units // 2 + 1)
                    if threes * 3 + twos * 2 == units
                ),
                default=None,
            )
            assert len(spelled) == best, units

    def test_a_ladder_cut_that_overshoots_backs_the_doubling_off(self) -> None:
        """When the largest power overshoots the cut, ``j`` steps down one.

        ``j`` is picked as the largest doubling that fits under the cut,
        but that first choice can leave a remainder that is negative (the
        threshold already passed the cut) or odd (``k`` pays it two units
        at a time and cannot spell a half).  Either way the only repair is
        a smaller ``j``, and the assertions just past it are what say the
        second choice always lands -- so a gadget still comes back.
        """
        module = self.module()
        ladder_gadget = module._ladder_gadget  # noqa: SLF001

        def chosen_j(cut: int) -> tuple[int, bool]:
            """Return the j the gadget settles on, and whether it backed off."""
            j = (3004 // cut).bit_length() - 1
            remainder = -(-3004 // (1 << j)) - cut
            if remainder < 0 or remainder % 2 != 0:
                return j - 1, True
            return j, False

        # The back-off is the common case, not a corner: most cuts need it.
        assert sum(chosen_j(cut)[1] for cut in range(1, 3005)) > 1000

        # A slope has to be a whole number of doublings at the settled j,
        # so it is picked from that j rather than fixed in advance.
        backed_off = ladder_gadget(1, 2 << chosen_j(1)[0])
        assert chosen_j(1)[1] is True
        assert "psp" in backed_off
        assert backed_off.endswith("ipsp")

        # A cut that does not overshoot keeps its first j, same shape.
        clean_cut = next(cut for cut in range(1, 3005) if not chosen_j(cut)[1])
        clean = ladder_gadget(clean_cut, 2 << chosen_j(clean_cut)[0])
        assert "psp" in clean
        assert clean.endswith("ipsp")

    def test_built_ladder_matches_the_frozen_witnesses(self) -> None:
        """The fold reproduces the table it replaced, entry for entry.

        These twenty-four are what the breadth-first harvest froze: the
        table each ladder-plus-suffix pair serves, and the pair the harvest
        picked for it.  Two things the fold may legitimately differ on are
        allowed for: it names two tables the harvest never listed (the
        constants, which every earlier path serves in a tenth the
        characters), and for two more it picks a shorter gadget than the
        harvest did.  What is asserted is that every frozen table is still
        served and that the pair chosen computes it -- and, where the pair
        differs, that the ladder is not what the generator emits anyway.
        """
        frozen = {
            "00010011": (0, "mpspmipspsl"),
            "11101100": (0, "mpspmipspipl"),
            "00110111": (0, "smpspmipspsl"),
            "11001000": (0, "smpspmipspipl"),
            "00000111": (1, "mpspmipspsl"),
            "11111000": (1, "mpspmipspipl"),
            "00011111": (1, "smpspmipspsl"),
            "11100000": (1, "smpspmipspipl"),
            "00000001": (2, "mpspmipspsl"),
            "11111110": (2, "mpspmipspipl"),
            "00010111": (2, "smpspmipspsl"),
            "11101000": (2, "smpspmipspipl"),
            "11111011": (3, "mmpspmipspsl"),
            "00000100": (3, "mmpspmipspipl"),
            "01111011": (3, "pspmimmipspsl"),
            "10000100": (3, "pspmimmipspipl"),
            "01011011": (4, "pspmimmipspsl"),
            "10100100": (4, "pspmimmipspipl"),
            "00001011": (5, "pspmimmipspsl"),
            "11110100": (5, "pspmimmipspipl"),
            "00011011": (6, "pspmsmipspsl"),
            "11100100": (6, "pspmsmipspipl"),
            "00111011": (7, "pspmimmipspsl"),
            "11000100": (7, "pspmimmipspipl"),
        }
        module = self.module()
        built = module._ladder_built()  # noqa: SLF001
        assert frozen.keys() <= built.keys()
        assert set(built) - set(frozen) == {"00000000", "11111111"}
        for table, witness in frozen.items():
            index, suffix = built[table]
            weights, base = module._LADDERS[index]  # noqa: SLF001
            spelled = module._ladder_setters(weights, base)  # noqa: SLF001
            assert spelled is not None
            setters, lead = spelled
            vector = module._ladder_vector(setters, lead, 3)  # noqa: SLF001
            for row, want in enumerate(table):
                got = module._apply(vector[row], suffix)  # noqa: SLF001
                assert got == int(want), (table, row)
            if (index, suffix) != witness:
                # Two tables are reached by a shorter gadget than the
                # harvest picked.  Both compute the table, and neither is
                # emitted: every earlier path serves these in a tenth the
                # characters, so the ladder is never consulted for them.
                assert module.pct_squared_minus_one(table) != module._ladder(  # noqa: SLF001
                    table, 3
                )

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

    def test_the_ladder_declines_other_arities(self) -> None:
        """Every shipped ladder has three weights, so only ``n == 3`` serves.

        The harvest the tabulation froze was empty at every other arity;
        the guard makes that an explicit decline rather than a lookup miss.
        """
        module = self.module()
        assert module._ladder("0110", 2) is None  # noqa: SLF001
        assert module._ladder("01" * 8, 4) is None  # noqa: SLF001
