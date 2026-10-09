"""Run Pylint with each file's similarity hashes computed once."""

import sys
from collections.abc import Generator
from functools import cache

from pylint.checkers import symilar
from pylint.lint import Run


def main() -> None:
    """Keep Pylint's diagnostics, including local message controls."""
    original = symilar.hash_lineset
    # The pairwise detector only reads these maps and copies mutable limits.
    # Without caching it rehashes each of 326 files for every other file.
    cached = cache(original)

    @cache
    def keys(lineset: symilar.LineSet, minimum: int) -> frozenset[symilar.LinesChunk]:
        return frozenset(cached(lineset, minimum)[0])

    compare = symilar.Symilar._find_common  # noqa: SLF001 - Pylint comparison hook

    def find_common(
        self: symilar.Symilar, lineset1: symilar.LineSet, lineset2: symilar.LineSet
    ) -> Generator[symilar.Commonality, None, None]:
        minimum = self.namespace.min_similarity_lines
        # An empty hash intersection cannot produce a common block. Cache
        # each file's keys instead of rebuilding both sets for every pair.
        if not keys(lineset1, minimum).isdisjoint(keys(lineset2, minimum)):
            yield from compare(self, lineset1, lineset2)

    symilar.hash_lineset = cached
    symilar.Symilar._find_common = find_common  # type: ignore[method-assign]  # noqa: SLF001
    try:
        Run(sys.argv[1:])
    finally:
        symilar.hash_lineset = original
        symilar.Symilar._find_common = compare  # type: ignore[method-assign]  # noqa: SLF001
        keys.cache_clear()
        cached.cache_clear()


if __name__ == "__main__":
    main()
