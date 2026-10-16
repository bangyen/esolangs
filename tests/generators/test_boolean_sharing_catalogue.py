"""Every tree-shaped generator shares repeated subtrees, or says why it cannot.

The canonical set (``docs/CONTRIBUTING.md``) shares repeated subtrees.  A
source scan for ``subtree_ids`` cannot tell sharing from folding (the helper
does both), so this measures it: a generator outside ``[sharing.exempt]`` in
``ledgers/generator_catalogue.toml`` builds a repeated-block table or parity
at most 0.90x its distinct-block or dense twin at some probed arity.
Non-sharers measured 0.95x or more on every probe, sharers 0.88x or less.
"""

from __future__ import annotations

import random
import tomllib
from pathlib import Path

import pytest

import esolangs
from esolangs.generation.helpers import essential_inputs
from esolangs.registry import LANGUAGES
from esolangs.registry._language import Shape
from tests.generators.source_support import generator_symbols as _source
from tests.support.generator_support import assert_proved_resource_cap
from tests.support.source_support import source_units
from tests.support.witness_tables import dense, parity

CATALOGUE = Path(__file__).parents[2] / "ledgers" / "generator_catalogue.toml"

#: Arities probed, smallest first; routes switch with size (Inject shares
#: only through n=4, Back only from n=6, thisthat's DAG fires on parity).
_ARITIES = (4, 5, 6, 8)
_BAR = 0.90


def _catalogue() -> tuple[dict[str, str], dict[str, str]]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))["sharing"]
    return data.get("local", {}), data.get("exempt", {})


def _tree_generators() -> set[str]:
    return {
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None and lang.shape is Shape.TREE
    }


def _blocks(n: int, seed: int) -> tuple[str, str]:
    """``B C C B`` and ``B C D E`` over distinct blocks, every input essential."""
    rng = random.Random(seed)
    while True:
        b, c, d, e = (
            "".join(rng.choice("01") for _ in range(2 ** (n - 2))) for _ in range(4)
        )
        pair = b + c + c + b, b + c + d + e
        if len({b, c, d, e}) == 4 and all(
            len(essential_inputs(t, n)) == n for t in pair
        ):
            return pair


def _ratios(name: str, n: int):
    build = LANGUAGES[name].boolean
    assert build is not None
    yield source_units(build(parity(n))) / source_units(build(dense(n)))
    pairs = [_blocks(n, seed) for seed in range(8)]
    rep = sum(source_units(build(t)) for t, _ in pairs)
    yield rep / sum(source_units(build(t)) for _, t in pairs)


def test_the_catalogue_names_tree_generators() -> None:
    local, exempt = _catalogue()
    assert set(local) | set(exempt) <= _tree_generators()
    assert not set(local) & set(exempt)
    assert all(reason.strip() for reason in exempt.values())


def test_declared_local_helpers_are_present() -> None:
    """A language-local sharing helper named in the catalogue really is referenced."""
    local, _ = _catalogue()
    for name, token in local.items():
        assert token in _source(name), f"{name} no longer references {token}"


@pytest.mark.parametrize("name", sorted(_tree_generators() - set(_catalogue()[1])))
def test_a_sharing_generator_shrinks_a_repeated_table(name: str) -> None:
    seen = []
    try:
        for n in _ARITIES:
            for ratio in _ratios(name, n):
                if ratio <= _BAR:
                    return
                seen.append(round(ratio, 2))
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(name)
        pytest.skip("sharing probe exceeds a proved language resource cap")
    pytest.fail(
        f"{name} shares nothing (parity/dense, repeated/distinct by arity: {seen}): "
        "share repeated subtrees or add [sharing.exempt] with the reason"
    )
