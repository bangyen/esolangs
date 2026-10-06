"""Covers the pool half of :mod:`esolangs.tools.minifuck.pool`."""

import importlib

import pytest

from esolangs.tools.minifuck import _solve
from esolangs.tools.minifuck.pool import (
    _POOL_CODES,
    _embed,
)
from esolangs.tools.minifuck.sim import _clamp, _Joint, _Sim
from tests.tools.minifuck_pool_oracle import (
    _POOL_PTR_MAX,
    _endgame,
    _find_pool,
)
from tests.tools.minifuck_support import (
    _MinifuckCase,
    _mux_separate,
    _pool_reaches,
)


class TestMinifuckPool(_MinifuckCase):
    """The pool codes, the rule that picks one, and the endgame printing through it."""

    def test_the_pool_codes_cover_every_route(self) -> None:
        """The fixed codes must serve every route that reaches the endgame."""

        for table_int in range(16):
            table = format(table_int, "04b")
            assert _solve.__wrapped__(table), table

    def test_the_pool_rule_declines_outside_its_domain(self) -> None:
        """The bound is a refusal, not a gap in a table."""

        ptr_max = _POOL_PTR_MAX

        outside = _Sim(512)
        outside.tape = 156
        outside.ptr = 3
        joint = _Joint.__new__(_Joint)
        joint.ms = [outside]

        assert ptr_max == 2, "the bound this test pins has moved"
        assert _find_pool(joint, 1, 12) is None
        # ... while the simulator still finds a code from there.
        served = [code for code in _POOL_CODES if _pool_reaches(joint, code, 1, 12)]
        assert served, "expected the scan to still answer outside the domain"

    def test_pool_reaches_refuses_a_code_that_kills_a_row(self) -> None:
        """``_pool_reaches`` rejects code that kills or desynchronises a row."""

        joint = _mux_separate(2)
        joint.emit("x")
        _clamp(joint)
        cell7 = 0
        walk_out = min(_mux_separate(2).ptrs()) - 3
        # ``[[`` leaves a row dead or mid-skip, so the code is refused before
        # the walk out is priced -- a dead row cannot be walked at all.
        assert not _pool_reaches(joint, "[[", cell7, walk_out)
        # ``x`` writes under the pointer and is refused as well.
        assert not _pool_reaches(joint, "x", cell7, walk_out)
        # A code that ends past the walk-out target is refused rather than
        # walked backwards: the walk out only ever moves right, so a pointer
        # already beyond it can never arrive.
        assert not _pool_reaches(joint, "[x", cell7, 0)
        # Bare navigation is refused too: reaching the state is not enough,
        # the code has to leave the answer where the read will find it.
        assert not _pool_reaches(joint, "", cell7, walk_out)
        # Exactly one of the pool's own codes serves this joint -- the guards
        # are a filter over the list, not a formality that passes everything.
        served = [
            code for code in _POOL_CODES if _pool_reaches(joint, code, cell7, walk_out)
        ]
        assert len(served) == 1, served

    def test_the_pool_search_needs_the_rows_to_agree_on_the_pointer(self) -> None:
        """A pool is only a pool if every row reads it from one place."""
        from esolangs.tools.minifuck.sim import _clamp
        from tests.tools.minifuck_pool_oracle import _find_pool

        spread = _embed(2)
        assert len(set(spread.ptrs())) > 1, "the embed should leave rows apart"
        assert _find_pool(spread, 0, 12) is None

        clamped = _embed(2)
        _clamp(clamped)
        assert len(set(clamped.ptrs())) == 1

    def test_the_endgame_refuses_an_impossible_setup(self) -> None:
        """Two ways the endgame cannot run, reported rather than emitted."""

        module = importlib.import_module("tests.tools.minifuck_pool_oracle")
        from esolangs.tools.minifuck.sim import _clamp

        joint = _embed(2)
        _clamp(joint)

        with pytest.raises(ValueError, match="must sit past the pool"):
            _endgame(joint.fork(), 3, "[<", 0)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_find_pool", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="no pool pattern"):
                _endgame(joint.fork(), 12, "[<", 0)

    def test_the_walk_needs_a_converged_pointer_going_right(self) -> None:
        """``[x`` walks are only safe rightward from one shared position."""
        from esolangs.tools.minifuck.sim import _clamp, _walk_to

        spread = _embed(2)
        with pytest.raises(ValueError, match="converged pointer"):
            _walk_to(spread, 0)

        clamped = _embed(2)
        _clamp(clamped)
        with pytest.raises(ValueError, match="cannot walk left"):
            _walk_to(clamped, -5)
