"""Construction symbols reached through a generator's imports."""

from __future__ import annotations

import ast
import inspect
from functools import cache, lru_cache
from pathlib import Path

from esolangs.registry import LANGUAGES

# A primitive's implementation cannot establish another generator mechanism:
# essential_inputs uses residual IDs to detect dependencies, not emit sharing.
_PRIMITIVES = frozenset(
    {
        "essential_inputs",
        "read_at",
        "constant_span_test",
        "subtree_ids",
        "_residual_ids",
        "SubtreeDiagram",
        "input_orders",
        "in_input_order",
        "_greedy_input_order",
        "permute_truth_table",
        "_validate_truth_table",
        "_validate_shape",
    }
)


class _References(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.attributes: dict[str, set[str]] = {}
        self.bound: set[str] = set()
        self.imports: list[tuple[int, ast.Import | ast.ImportFrom]] = []
        self.depth = 0

    def visit(self, node: ast.AST) -> None:
        self.depth += 1
        try:
            super().visit(node)
        finally:
            self.depth -= 1

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append((self.depth, node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append((self.depth, node))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id not in self.bound:
            self.names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id not in self.bound:
            self.attributes.setdefault(node.value.id, set()).add(node.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        previous = self.bound
        self.bound = previous | {
            arg.arg
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        }
        if node.args.vararg is not None:
            self.bound.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            self.bound.add(node.args.kwarg.arg)
        for statement in node.body:
            self.visit(statement)
        self.bound = previous

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        previous = self.bound
        self.bound = previous | {
            arg.arg
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        }
        if node.args.vararg is not None:
            self.bound.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            self.bound.add(node.args.kwarg.arg)
        self.visit(node.body)
        self.bound = previous

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)


# Key by contents so edits are visible even when size and mtime stay fixed.
@lru_cache(maxsize=256)
def _parsed_source(source: str) -> tuple[ast.Module, dict[str, ast.AST]]:
    tree = ast.parse(source)
    definitions: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            definitions[node.name] = node
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
    return tree, definitions


@lru_cache(maxsize=2048)
def _symbol_references(
    tree: ast.Module, selected: ast.AST | None, name: str
) -> tuple[
    frozenset[str],
    dict[str, frozenset[str]],
    tuple[ast.Import | ast.ImportFrom, ...],
]:
    """Reuse a definition's references across generator traversals."""
    references = _References()
    if selected is None:
        references.names.add(name)
    else:
        references.visit(selected)
    # Stable depth order matches ast.walk without a second traversal.
    imports = tuple(
        node for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)
    ) + tuple(node for _, node in sorted(references.imports, key=lambda item: item[0]))
    return (
        frozenset(references.names),
        {key: frozenset(values) for key, values in references.attributes.items()},
        imports,
    )


def construction_symbols(path: Path, root: Path, symbol: str) -> set[str]:
    """Follow referenced definitions, excluding siblings and unused imports."""
    pending = [(path, symbol)]
    seen: set[tuple[Path, str]] = set()
    reached: set[str] = set()

    @cache
    def parse(file: Path) -> tuple[ast.Module, dict[str, ast.AST]]:
        return _parsed_source(file.read_text(encoding="utf-8"))

    while pending:
        file, name = pending.pop()
        if (file, name) in seen:
            continue
        seen.add((file, name))
        tree, definitions = parse(file)
        selected = definitions.get(name)
        if selected is not None:
            reached.add(name)
            if (
                file.is_relative_to(root / "esolangs/generation")
                and name in _PRIMITIVES
            ):
                continue
        names, attributes, nodes = _symbol_references(tree, selected, name)
        imports: dict[str, tuple[str, str | None]] = {}
        package = file.relative_to(root).with_suffix("").parts[:-1]
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                parts = (node.module or "").split(".") if node.module else []
                if node.level:
                    parts = [*package[: len(package) - node.level + 1], *parts]
                module = ".".join(parts)
                imports.update(
                    (alias.asname or alias.name, (module, alias.name))
                    for alias in node.names
                )
            elif isinstance(node, ast.Import):
                imports.update(
                    (alias.asname or alias.name, (alias.name, None))
                    for alias in node.names
                )
        for reference in sorted(names):
            if reference not in imports:
                if reference in definitions:
                    pending.append((file, reference))
                continue
            module, target = imports[reference]
            if module not in {
                "esolangs.generation",
                "esolangs.languages",
            } and not module.startswith(
                ("esolangs.generation.", "esolangs.languages.")
            ):
                continue
            base = root.joinpath(*module.split("."))
            dependency = base.with_suffix(".py")
            if not dependency.is_file():
                dependency = base / "__init__.py"
            if target is not None:
                child = base / f"{target}.py"
                child_package = base / target / "__init__.py"
                if child.is_file() or child_package.is_file():
                    dependency = child if child.is_file() else child_package
                    target = None
            if not dependency.is_file():
                continue
            targets = (
                {target}
                if target is not None
                else attributes.get(reference, frozenset())
            )
            pending.extend((dependency, target) for target in sorted(targets))
    return reached


@cache
def generator_symbols(name: str) -> set[str]:
    """Return the generator and its statically referenced construction symbols."""
    fn = LANGUAGES[name].boolean
    assert fn is not None
    source = inspect.getsourcefile(fn)
    assert source is not None
    return construction_symbols(
        Path(source), Path(__file__).parents[2] / "src", fn.__name__
    )
