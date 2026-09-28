"""What every screen shares: the tables, and one build of each.

Run a screen from the repository root as ``python scripts/screens/<name>.py``;
each puts this directory on ``sys.path`` for the import, as
``check_generator_sizes.py`` does for ``benchmark``.
"""

from collections.abc import Callable, Iterator

from esolangs.registry import LANGUAGES, resolve

#: Every two- and three-input table, MSB first.
PAIRS = [format(i, "04b") for i in range(16)]
TABLES = [format(i, "08b") for i in range(256)]


def generators() -> Iterator[tuple[str, Callable[[str], object]]]:
    """Yield ``(registry name, generator)`` for every text boolean generator."""
    for key, lang in sorted(LANGUAGES.items()):
        if lang.boolean is not None:
            yield key, lang.boolean


def sizes(gen: Callable[[str], object], tables: list[str]) -> dict[str, int | None]:
    """Build every table once; ``None`` marks an arity the generator refuses.

    ``ValueError`` is the refusal; anything else is a real failure and
    propagates.
    """
    out: dict[str, int | None] = {}
    for table in tables:
        try:
            out[table] = len(str(gen(table)))
        except ValueError:
            out[table] = None
    return out


def chosen(names: list[str]) -> list[tuple[str, Callable[[str], object]]]:
    """Return ``generators()`` narrowed to ``names``, or all of it for none.

    A name is resolved as ``esolangs`` resolves one, so a display name, a
    lower-case key or a punctuation-free spelling all select the language.
    """
    if not names:
        return list(generators())
    wanted = {resolve(name) for name in names}
    return [(key, gen) for key, gen in generators() if key in wanted]
