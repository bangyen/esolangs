"""Balanced area grows about as fast as the table: no atom outgrows the square.

Nothing measured this until 2026-10-29: ABCDirection's ``T / 2`` select run
held its balanced area at ``T**2 / 4`` (the scan put it at ``T**1.98``), and
Streetcode, Flowchart, LaserFuck, Packlang and Freestajlo grew as ``T**2``
for the same reason -- one piece as wide as a fraction of the table.
"""

import math
import pathlib
import random
import tomllib

import pytest

import esolangs
from esolangs.exceptions import GeneratorCapError
from esolangs.generation.wrap import balance_score
from esolangs.registry import LANGUAGES

#: Area may grow as ``T**1.25`` from n=10 to 12.  The fixed generators sit at
#: 0.68-1.05; Circuit Diagram, entering its H-tree pool, at 1.22.
EXPONENT = 1.25


def _area(program: object) -> int:
    rows = getattr(program, "rows", None)
    if rows is not None:
        return len(rows) * max(len(row) for row in rows)
    return balance_score(str(program))[0] ** 2


def _mean_area(name: str, n: int) -> float:
    rng = random.Random(4242 + n)
    tables = ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(2)]
    return sum(_area(esolangs.generate(name, t, balance=True)) for t in tables) / 2


_LANGUAGES_DIR = pathlib.Path(esolangs.__file__).parent / "languages"


def _recorded(name: str, key: str) -> str:
    """The language's ``[balance_growth]`` entry: ``open`` growth, or a
    proved ``wall`` citing the syntax rule; "" if none."""
    path = _LANGUAGES_DIR / LANGUAGES[name].id / "language.toml"
    if not path.exists():
        return ""
    return tomllib.loads(path.read_text()).get("balance_growth", {}).get(key, "")


def _cases() -> list[object]:
    """Every generator; a recorded open growth is a strict xfail, so a fix
    shows up as an unexpected pass."""
    return [
        pytest.param(
            name,
            marks=pytest.mark.xfail(strict=True, reason=_recorded(name, "open"))
            if _recorded(name, "open")
            else (),
        )
        for name in sorted(name for name, lang in LANGUAGES.items() if lang.boolean)
    ]


@pytest.mark.weekly
@pytest.mark.cost_evidence("T**2 balanced area: ABCDirection 6ae9ae798, five more")
@pytest.mark.parametrize("name", _cases())
def test_balanced_area_grows_about_linearly(name: str) -> None:
    """Exempt: a capped generator, a line-bound (``no_wrap``) language with
    no ``balance`` hook, whose layout the generator does not choose, and a
    recorded ``wall``: a line carries O(log T) bits, so area >= T**2/log**2 T."""
    language = LANGUAGES[name]
    if language.no_wrap and language.balance is None:
        pytest.skip(language.no_wrap)
    if wall := _recorded(name, "wall"):
        pytest.skip(wall)
    try:
        high = _mean_area(name, 12)
    except GeneratorCapError as error:
        pytest.skip(str(error))
        raise  # unreachable: skip raises; keeps ``high`` bound for checkers
    exponent = math.log(high / _mean_area(name, 10)) / math.log(4)
    assert exponent <= EXPONENT, f"{name}: balanced area ~ T**{exponent:.2f}"
