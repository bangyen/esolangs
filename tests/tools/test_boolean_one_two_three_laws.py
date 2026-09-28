"""Re-derives the 123 separation laws :data:`_LAWS` ships as constants.

Split from ``test_boolean_one_two_three.py`` to keep both under the file cap;
both tests replay candidate laws independently of ``_separated``.
"""

import pytest


class TestSeparationLaws:
    """The first law is the least mean; the rest are the greedy cover."""

    @pytest.mark.slow
    def test_the_separation_law_is_the_least_mean(self) -> None:
        """The law's constants are re-derived, not trusted.

        ``_LAWS`` claims one selection rule at every arity: over constant
        walk seeds and alternating pure-test displacement vectors, the law
        with the least mean template length.  Re-running that sweep at
        ``n <= 2`` fails a hand-edited constant rather than shipping it;
        ``n == 3`` is 13 laws over 256 tables, minutes rather than seconds.
        """
        from itertools import product

        from esolangs.tools.one_two_three import (
            _LAWS,
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _on_mark,
            _verdict_junky,
            _work,
        )

        def prototype(n: int, walk: int, disps: tuple[int, ...]) -> object:
            """Replay one candidate law, or ``None`` if it does not fit.

            A candidate that walks a row off the ring raises exactly as a
            build would; here that only means "not this law", so the
            raise is caught rather than propagated.
            """
            # pylint: disable=duplicate-code
            # The overlap with ``_separated``'s replay is the point, not
            # an oversight: this test re-derives the shipped constants,
            # so it has to replay the law independently.  Sharing a
            # helper would check the generator against itself and a bug
            # in the replay would pass here, so the copy stays and the
            # similarity check is told so rather than left to fail in CI.
            _work[0] = _WORK_BUDGET
            try:
                b = _Builder(n)
                for i in range(n):
                    if walk:
                        b.run("2" * walk)
                    b.fill(i)
                for d in range(4 * 2**n + 9):
                    probe = b.clone()
                    if d:
                        probe.run("2" * d)
                    if any(r.pos < 0 for r in probe.live()):
                        continue
                    if not any(_on_mark(r) for r in probe.live()):
                        if d:
                            b.run("2" * d)
                        b.test()
                        break
                else:
                    return None
                for i, step in enumerate(disps):
                    b.run(("1" if i % 2 == 0 else "2") * step)
                    b.test()
            except ConstructError:
                return None
            poss = [r.pos for r in b.live()]
            if len(set(poss)) != len(poss) or any(p % 2 == 0 for p in poss):
                return None
            return b

        def mean_length(n: int, proto: object) -> float | None:
            total = 0
            tables = ["".join(t) for t in product("01", repeat=2**n)]
            for table in tables:
                _work[0] = _WORK_BUDGET
                b = proto.clone()  # type: ignore[attr-defined]
                try:
                    _verdict_junky(b, table)
                    _endgame(b)
                except ConstructError:
                    return None
                total += len(b.template())
            return total / len(tables)

        for n in (1, 2):
            ranked = []
            for walk in range(9):
                for depth in range(5):
                    for disps in product(range(1, 11), repeat=depth):
                        proto = prototype(n, walk, disps)
                        if proto is None:
                            continue
                        mean = mean_length(n, proto)
                        if mean is not None:
                            ranked.append((mean, walk, disps))
            assert ranked, n
            ranked.sort()
            _best_mean, best_walk, best_disps = ranked[0]
            assert ((best_walk,) * n, best_disps) == _LAWS[n][0], (n, ranked[:3])

    @pytest.mark.weekly  # ~6 min: 380 of 3.8M laws separate at three inputs
    @pytest.mark.cost_evidence("a stored extra law displaced from the greedy cover")
    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_the_extra_laws_are_the_greedy_cover(self, n: int) -> None:
        """The extra laws are re-derived by the rule ``_LAWS`` states.

        Seeds of 0..6 per fill, up to four displacements of 1..10, in that
        enumeration order; a law counts only if it separates and builds
        every table.  Each pick is the first law that most shrinks the total
        of the per-table minimum, starting from the first law and the chain.
        """
        from itertools import product

        from esolangs.tools.one_two_three import (
            _LAWS,
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _construct_small,
            _endgame,
            _on_mark,
            _verdict_junky,
            _work,
        )
        from esolangs.tools.one_two_three_construct import (
            _construct_linear,
            _WorkExhaustedError,
        )

        tables = [format(v, f"0{2**n}b") for v in range(2 ** (2**n))]

        def sizes(walks: tuple[int, ...], disps: tuple[int, ...]) -> list[int] | None:
            """Every table's template length under one law, or ``None``."""
            _work[0] = _WORK_BUDGET
            try:
                b = _Builder(n)
                for i, walk in enumerate(walks):
                    if walk:
                        b.run("2" * walk)
                    b.fill(i)
                for d in range(4 * 2**n + 9):
                    probe = b.clone()
                    if d:
                        probe.run("2" * d)
                    if any(r.pos < 0 for r in probe.live()):
                        continue
                    if not any(_on_mark(r) for r in probe.live()):
                        if d:
                            b.run("2" * d)
                        b.test()
                        break
                else:
                    return None
                for i, step in enumerate(disps):
                    b.run(("1" if i % 2 == 0 else "2") * step)
                    b.test()
                poss = [r.pos for r in b.live()]
                if len(set(poss)) != len(poss) or any(p % 2 == 0 for p in poss):
                    return None
                out = []
                for table in tables:
                    _work[0] = _WORK_BUDGET
                    trial = b.clone()
                    _verdict_junky(trial, table)
                    _endgame(trial)
                    out.append(len(trial.template()))
            except (ConstructError, _WorkExhaustedError):  # "not this law"
                return None
            return out

        laws = {
            (walks, disps): got
            for walks in product(range(7), repeat=n)
            for depth in range(5)
            for disps in product(range(1, 11), repeat=depth)
            if (got := sizes(walks, disps)) is not None
        }
        best = [
            min(len(_construct_small(t, n)), len(_construct_linear(t, n)))
            for t in tables
        ]
        picked = []
        for _ in range(3):
            total, law = min(
                (sum(map(min, zip(best, got, strict=True))), i, law)
                for i, (law, got) in enumerate(laws.items())
            )[0::2]
            if total == sum(best):
                break
            picked.append(law)
            best = [min(a, b) for a, b in zip(best, laws[law], strict=True)]
        assert tuple(picked) == _LAWS[n][1:]
