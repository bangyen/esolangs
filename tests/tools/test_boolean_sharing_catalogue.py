"""Every tree-shaped generator names its sharing mechanism, or why it has none.

The canonical set (``docs/CONTRIBUTING.md``) shares repeated subtrees
(``subtree_ids``); ``docs/limitations.md`` §Scaling records which generators
are exempt and why.  That record was prose checked by hand, so a new or
changed tree-shaped generator could drop its sharing silently.  This pins the
presence proxy: a tree-shaped boolean generator references a canonical sharing
helper, a declared language-local one, or is exempt with a stated reason.  The
exceptions live in ``tests/fixtures/sharing_catalogue.toml`` so this file names
no language; the measured bounds stay with ``scripts/screens/sharing.py``.
"""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

from esolangs.registry import LANGUAGES
from esolangs.registry._language import Shape

#: The canonical helper a generator's module references to share subtrees.
CANONICAL = ("subtree_ids", "SubtreeDiagram")

CATALOGUE = Path(__file__).parents[1] / "fixtures" / "sharing_catalogue.toml"


def _catalogue() -> tuple[dict[str, str], dict[str, str]]:
    data = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))
    return data.get("local", {}), data.get("exempt", {})


def _source(name: str) -> str:
    """The defining module and its sibling modules, as text."""
    fn = LANGUAGES[name].boolean
    assert fn is not None
    path = Path(inspect.getsourcefile(fn))
    parts = [path.read_text(encoding="utf-8")]
    parts.extend(
        sibling.read_text(encoding="utf-8")
        for sibling in sorted(path.parent.glob("*.py"))
        if sibling != path and not sibling.name.startswith("__")
    )
    return "\n".join(parts)


def _tree_generators() -> set[str]:
    return {
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None and lang.shape is Shape.TREE
    }


def test_the_catalogue_covers_exactly_the_exceptions() -> None:
    """The only tree generators without a canonical helper are the declared ones."""
    local, exempt = _catalogue()
    tree = _tree_generators()
    assert set(local) | set(exempt) <= tree
    lacking = {name for name in tree if not any(h in _source(name) for h in CANONICAL)}
    assert lacking == set(local) | set(exempt), (
        "a tree-shaped generator has no canonical sharing helper and no declared "
        f"reason: {sorted(lacking - set(local) - set(exempt))}"
    )


def test_declared_local_helpers_are_present() -> None:
    """A language-local sharing helper named in the catalogue really is referenced."""
    local, _ = _catalogue()
    for name, token in local.items():
        assert token in _source(name), f"{name} no longer references {token}"
