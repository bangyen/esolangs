"""Every generator names its folding mechanism, or why it has none.

The canonical set (``docs/CONTRIBUTING.md``) drops ignored inputs
(``essential_inputs``/``read_at``) and folds constant subtrees
(``constant_span_test``); folding also drops an ignored input, so any of the
three helpers satisfies the ignored piece.  ``docs/limitations.md`` records
the exemptions.  This pins the presence proxy over every boolean generator --
the shape test (``test_generator_shape_is_what_the_catalogue_says``) checks the
behaviour for tree and reducing shapes, this catches a new generator that
quietly drops the helper.  Exceptions live in
``tests/support/fixtures/canonical_folding_catalogue.toml`` so this file names no
language; the screens (``constant.py``, ``ignored_input.py``) bound the pieces.
"""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

from esolangs.registry import LANGUAGES

IGNORED = ("essential_inputs", "read_at", "constant_span_test")
CONSTANT = ("constant_span_test",)

CATALOGUE = (
    Path(__file__).parents[1] / "support/fixtures" / "canonical_folding_catalogue.toml"
)


def _catalogue() -> tuple[dict[str, str], dict[str, str]]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))
    return data.get("ignored", {}), data.get("constant", {})


def _source(name: str) -> str:
    """The defining module, its package siblings, and the shared helpers."""
    fn = LANGUAGES[name].boolean
    assert fn is not None
    path = Path(inspect.getsourcefile(fn))
    # A package generator is one file among its package's; a single-file
    # generator's own directory is the category, and the shared helpers live
    # at the tools root beside it.
    directories = (
        [path.parent] if path.name == "__init__.py" else [path.parent, path.parents[1]]
    )
    if path.name == "generator.py":
        directories.append(Path(__file__).parents[2] / "src/esolangs/tools")
    siblings = {
        sibling for directory in directories for sibling in directory.glob("*.py")
    }
    parts = [path.read_text(encoding="utf-8")]
    parts.extend(
        sibling.read_text(encoding="utf-8")
        for sibling in sorted(siblings)
        if sibling != path and not sibling.name.startswith("__")
    )
    return "\n".join(parts)


def _generators() -> set[str]:
    return {name for name, lang in LANGUAGES.items() if lang.boolean is not None}


def _lacking(helpers: tuple[str, ...]) -> set[str]:
    return {
        name
        for name in _generators()
        if not any(helper in _source(name) for helper in helpers)
    }


def test_the_catalogue_covers_exactly_the_exceptions() -> None:
    """The only generators without a helper are the declared ones."""
    ignored, constant = _catalogue()
    assert _lacking(IGNORED) == set(ignored), sorted(_lacking(IGNORED) - set(ignored))
    assert _lacking(CONSTANT) == set(constant), sorted(
        _lacking(CONSTANT) - set(constant)
    )


def test_declared_exceptions_state_a_reason() -> None:
    ignored, constant = _catalogue()
    assert all(reason.strip() for reason in (*ignored.values(), *constant.values()))
