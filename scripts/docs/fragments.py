"""Per-process caching for the per-package ``language.toml`` aggregates.

Each fragment dataset has one aggregator, and each re-scanned and
re-parsed every package's ``language.toml`` on every call.  That is
fine for a single load and ruinous for a caller looping over the
registry: the new-language check loads the proof status once per
language, and an uncached load re-parses ~90 fragments and re-checks
every evidence anchor each time (the all-languages check went from
2.2s on the old single-ledger tree to 19.8s).

Aggregates are therefore cached per process against a fingerprint of
the fragment set -- (package, mtime, size) per file, recomputed on
every call for the price of a stat sweep.  Adding, removing, or
editing a fragment changes the fingerprint, so a process that mutates
the tree, as the scaffold and removal flows do, never reads a stale
aggregate; no flow has to remember to invalidate.
"""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry import Language

#: The file each package keeps its fragment datasets in.
FRAGMENT = "language.toml"

#: Cache key for a registry-stamped aggregate: the packages dir, the
#: registry's (id, name) stamp, and the fragment fingerprint.
AggregateKey = tuple[
    Path, tuple[tuple[str, str], ...], tuple[tuple[str, int, int], ...]
]


def fingerprint(packages: Path) -> tuple[tuple[str, int, int], ...]:
    """Return the fragment set's stamp: (package, mtime, size) per file."""
    if not packages.is_dir():
        return ()
    return tuple(
        (path.parent.name, path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(packages.glob(f"*/{FRAGMENT}"))
    )


def cached[K, T](cache: dict[K, T], key: K, build: Callable[[], T]) -> T:
    """Return ``cache[key]``, calling ``build`` to fill it on a miss.

    Mutable results are deep-copied on the way out: the cached
    aggregate is shared by every caller in the process, and one
    caller's edits must not leak into another's view.
    """
    if key not in cache:
        cache[key] = build()
    result = cache[key]
    if isinstance(result, (dict, list)):
        return copy.deepcopy(result)
    return result


def aggregate[T](
    cache: dict[AggregateKey, T],
    packages: Path,
    languages: Iterable[Language],
    build: Callable[[Path, list[Language]], T],
) -> T:
    """Return the aggregate over ``packages`` for ``languages``, cached.

    The key is the packages dir, the registry's (id, name) stamp, and
    the fragment fingerprint; on a miss ``build`` receives the packages
    dir and the materialized registry.
    """
    langs = list(languages)
    stamp = tuple((lang.id, lang.name) for lang in langs)
    key = (packages, stamp, fingerprint(packages))
    return cached(cache, key, lambda: build(packages, langs))


def registry() -> tuple[Language, ...]:
    """Return the registered languages, in registry order."""
    from esolangs.registry import LANGUAGES

    return tuple(LANGUAGES.values())


def section(path: Path, name: str) -> dict[str, Any] | None:
    """Return ``path``'s ``[name]`` table, or None when it has none."""
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(name)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [{name}] must be a table")
    return table


def sections(
    packages: Path, languages: Iterable[Language], name: str
) -> Iterator[tuple[Language, Path, dict[str, Any]]]:
    """Yield each registered package's ``[name]`` table, in registry order.

    A repeated language id, or the section in an unregistered package,
    raises ``ValueError``.
    """
    seen: set[str] = set()
    for lang in languages:
        if lang.id in seen:
            raise ValueError(f"duplicate language id: {lang.id}")
        seen.add(lang.id)
        path = packages / lang.id / FRAGMENT
        if path.is_file() and (table := section(path, name)) is not None:
            yield lang, path, table
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and section(path, name) is not None:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
