"""Run Pylint with each file's similarity hashes computed once."""

import sys
from collections.abc import Generator
from functools import cache
from weakref import WeakKeyDictionary

import astroid  # type: ignore[import-untyped]
from astroid import builder, nodes, rebuilder
from pylint.checkers import symilar
from pylint.lint import Run


def main() -> None:
    """Keep Pylint's diagnostics, including local message controls."""
    original = symilar.hash_lineset
    original_parse = astroid.parse
    original_process = symilar.SimilaritiesChecker.process_module
    original_build = builder.AstroidBuilder._data_build  # noqa: SLF001
    sources: WeakKeyDictionary[nodes.Module, str] = WeakKeyDictionary()
    current: tuple[str, nodes.Module] | None = None

    def build(
        self: builder.AstroidBuilder, data: str, modname: str, path: str | None
    ) -> tuple[nodes.Module, rebuilder.TreeRebuilder]:
        node, tree = original_build(self, data, modname, path)
        sources[node] = data
        return node, tree

    def parse(
        code: str,
        module_name: str = "",
        path: str | None = None,
        apply_transforms: bool = True,  # noqa: FBT001, FBT002 - astroid.parse signature
    ) -> nodes.Module:
        if (
            current is not None
            and code == current[0]
            and not module_name
            and path is None
            and apply_transforms
        ):
            return current[1]
        return original_parse(code, module_name, path, apply_transforms)

    def process(self: symilar.SimilaritiesChecker, node: nodes.Module) -> None:
        nonlocal current
        previous = current
        source = sources.get(node)
        current = (source, node) if source is not None else None
        try:
            original_process(self, node)
        finally:
            current = previous

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
    builder.AstroidBuilder._data_build = build  # noqa: SLF001
    astroid.parse = parse
    symilar.SimilaritiesChecker.process_module = process  # type: ignore[method-assign]
    symilar.Symilar._find_common = find_common  # type: ignore[method-assign]  # noqa: SLF001
    try:
        Run(sys.argv[1:])
    finally:
        symilar.hash_lineset = original
        builder.AstroidBuilder._data_build = original_build  # noqa: SLF001
        astroid.parse = original_parse
        symilar.SimilaritiesChecker.process_module = original_process  # type: ignore[method-assign]
        symilar.Symilar._find_common = compare  # type: ignore[method-assign]  # noqa: SLF001
        keys.cache_clear()
        cached.cache_clear()
        sources.clear()


if __name__ == "__main__":
    main()
