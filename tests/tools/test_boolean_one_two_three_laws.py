"""Re-derives the 123 separation laws :data:`_LAWS` ships as constants."""

import pytest


class TestSeparationLaws:
    """The first law is the least mean; the rest are the greedy cover."""

    @pytest.mark.slow
    def test_the_separation_law_is_the_least_mean(self) -> None:
        """The law's constants are re-derived, not trusted."""
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
            """Replay one candidate law, or ``None`` if it does not fit."""
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
