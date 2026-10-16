"""Every generator names its folding mechanism, or why it has none.

The canonical set (``docs/CONTRIBUTING.md``) drops ignored inputs
(``essential_inputs``/``read_at``) and folds constant subtrees
(``constant_span_test``); folding also drops an ignored input, so any of the
three helpers satisfies the ignored piece.  ``docs/limitations.md`` records
the exemptions.  This pins the presence proxy over every boolean generator --
the shape test (``test_generator_shape_is_what_the_catalogue_says``) checks the
behaviour for tree and reducing shapes, this catches a new generator that
quietly drops the helper.  Exceptions live in
``ledgers/generator_catalogue.toml`` ``[folding]`` so this file names no
language.  A helper's presence is not its effect, so the last two tests
measure it at n=8: a constant table at most 0.6x a dense one (largest
measured 0.50x), an ignored input at most half a real one (0.32x, against
0.52x and 0.60x for the two in ``[folding.ignored_read]``).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from tests.generators.source_support import generator_symbols as _source
from tests.support.generator_support import assert_proved_resource_cap
from tests.support.source_support import source_units
from tests.support.witness_tables import dense

RESIDUALS = ("subtree_ids", "_residual_ids", "SubtreeDiagram")
IGNORED = ("essential_inputs", "read_at", "constant_span_test", *RESIDUALS)
CONSTANT = ("constant_span_test", *RESIDUALS)

CATALOGUE = Path(__file__).parents[2] / "ledgers" / "generator_catalogue.toml"


def _catalogue() -> tuple[dict[str, str], dict[str, str]]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))["folding"]
    return data.get("ignored", {}), data.get("constant", {})


def _native() -> tuple[dict[str, str], dict[str, str]]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))["folding"]
    return data.get("ignored_local", {}), data.get("constant_local", {})


def _generators() -> set[str]:
    return {name for name, lang in LANGUAGES.items() if lang.boolean is not None}


def _lacking(helpers: tuple[str, ...]) -> set[str]:
    return {
        name
        for name in _generators()
        if not any(helper in _source(name) for helper in helpers)
    }


# Reads every generator's source: ~0.97s alone, past the fast band under load.
@pytest.mark.medium
def test_the_catalogue_covers_exactly_the_exceptions() -> None:
    """The only generators without a helper are the declared ones."""
    ignored, constant = _catalogue()
    ignored_local, constant_local = _native()
    assert _lacking(IGNORED) == set(ignored) | set(ignored_local), sorted(
        _lacking(IGNORED) - set(ignored) - set(ignored_local)
    )
    assert _lacking(CONSTANT) == set(constant) | set(constant_local), sorted(
        _lacking(CONSTANT) - set(constant) - set(constant_local)
    )


def test_declared_exceptions_state_a_reason() -> None:
    ignored, constant = _catalogue()
    assert all(reason.strip() for reason in (*ignored.values(), *constant.values()))


def test_native_mechanisms_are_referenced() -> None:
    ignored, constant = _native()
    for name, mechanism in (*ignored.items(), *constant.items()):
        assert mechanism in _source(name), (name, mechanism)


_N = 8


def _folding(key: str) -> set[str]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))["folding"]
    return set(data.get(key, {}))


def _lift(inner: str, at: int, n: int) -> str:
    """``inner`` with an ignored input inserted before its input ``at``."""
    low = n - at
    return "".join(
        inner[row >> (low + 1) << low | row & ((1 << low) - 1)]
        for row in range(2 * len(inner))
    )


def _size(name: str, table: str) -> int:
    build = LANGUAGES[name].boolean
    assert build is not None
    try:
        return source_units(build(table))
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(name)
        pytest.skip("folding probe exceeds a proved language resource cap")


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(_generators() - _folding("constant")))
def test_a_constant_table_folds(name: str) -> None:
    ratio = min(_size(name, bit * 2**_N) for bit in "01") / _size(name, dense(_N))
    assert ratio <= 0.6, f"{name}: constant table {ratio:.2f}x dense at n={_N}"


@pytest.mark.medium
@pytest.mark.parametrize(
    "name",
    sorted(_generators() - _folding("ignored") - _folding("ignored_read")),
)
def test_an_ignored_input_costs_under_half_a_real_one(name: str) -> None:
    inner = dense(_N - 1)
    base = _size(name, inner)
    real = _size(name, dense(_N)) - base
    costs = [_size(name, _lift(inner, at, _N - 1)) - base for at in (0, 3, _N - 1)]
    assert max(costs) <= max(real, 0) / 2, (name, real, costs)
