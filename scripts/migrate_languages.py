"""Plan language colocation; pass --apply to migrate selected flat modules."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from esolangs.registry import LANGUAGES, Language

ROOT = Path(__file__).parents[1]
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from new_language import _compatibility_module  # noqa: E402


@dataclass(frozen=True)
class Move:
    """A source file and its canonical destination."""

    source: Path
    target: Path
    module: str
    interpreter: bool
    legacy: str = ""


def plan(lang: Language, root: Path = ROOT) -> tuple[str, list[Move]]:
    """Classify a language and resolve its actual implementation modules."""
    package = root / "src/esolangs/languages" / lang.id
    if package.exists():
        return "colocated", []
    modules = []
    if lang.interpreter:
        modules.append((f"esolangs.interpreters.{lang.interpreter}", "interpreter"))
    if lang.boolean:
        modules.append((lang.boolean.__module__, "generator"))
    moves = []
    packaged = False
    for module, leaf in modules:
        source = root / "src" / module.replace(".", "/")
        is_package = source.is_dir()
        packaged |= is_package
        if not is_package:
            source = source.with_suffix(".py")
        if (
            not (source / "__init__.py").is_file()
            if is_package
            else not source.is_file()
        ):
            return "missing source", []
        moves.append(
            Move(
                source,
                package / (leaf if is_package else f"{leaf}.py"),
                f"esolangs.languages.{lang.id}.{leaf}",
                leaf == "interpreter",
                legacy=module,
            )
        )
    return (
        ("package" if packaged else "flat", moves)
        if moves
        else ("no implementation", [])
    )


def _exports(source: str) -> tuple[str, ...]:
    """Collect module definitions without inlined comprehension temporaries."""
    names: set[str] = set()
    imported: set[str] = set()
    explicit: set[str] = set()
    tree = ast.parse(source)
    for statement in tree.body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.List | ast.Tuple)
        ):
            explicit.update(
                item.value
                for item in statement.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
    pending: list[ast.AST] = list(ast.parse(source).body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Import | ast.ImportFrom):
            imported.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
            explicit.update(
                alias.name for alias in node.names if alias.asname == alias.name
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias):
            names.add(node.name.id)
        elif isinstance(
            node,
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp | ast.Lambda,
        ):
            continue
        else:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            pending.extend(ast.iter_child_nodes(node))
    return tuple(
        sorted(
            name for name in (names - imported) | explicit if not name.startswith("__")
        )
    )


def _rewrite_imports(source: str, replacements: dict[str, str]) -> str:
    """Rewrite module references while retaining program literals and comments."""
    data = source.encode()
    offsets = [0]
    for line in data.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import | ast.ImportFrom) or (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(
                node.value == old or node.value.startswith(old + ".")
                for old in replacements
            )
        ):
            assert node.end_lineno is not None
            assert node.end_col_offset is not None
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            text = data[start:end].decode()
            for old, new in replacements.items():
                text = re.sub(r"\b" + re.escape(old) + r"(?=\.|\b)", new, text)
            edits.append((start, end, text.encode()))
    for start, end, payload in sorted(edits, reverse=True):
        data = data[:start] + payload + data[end:]
    return data.decode()


def _entry_keywords(source: str) -> str:
    """Preserve the shared CLI entry point's source shape and raster loader."""
    keywords = []
    for node in ast.walk(ast.parse(source)):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "script_main"
        ):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "shape"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value in {"text", "keep", "strip"}
            ):
                value = repr(keyword.value.value)
            elif (
                keyword.arg == "loader"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "load_source"
            ):
                value = "_implementation.load_source"
            else:
                raise ValueError("unsupported interpreter entry point")
            keywords.append(f", {keyword.arg}={value}")
    return "".join(keywords)


def apply(moves: list[Move]) -> None:
    """Preflight every write, preserve implementations, and install aliases."""
    writes: dict[Path, str] = {}
    deletes = set()
    seen = set()
    replacements = {move.legacy: move.module for move in moves if move.legacy}
    for move in moves:
        if move.target.exists() or move.target.parent.exists():
            raise FileExistsError(f"refusing to overwrite {move.target.parent}")
        if move.source in seen:
            raise ValueError(
                f"shared implementation requires manual migration: {move.source}"
            )
        seen.add(move.source)
        package = move.source.is_dir()
        files = sorted(move.source.rglob("*.py")) if package else [move.source]
        descendants = []
        for original in files:
            relative = original.relative_to(move.source) if package else Path(".")
            target = move.target / relative if package else move.target
            source = _rewrite_imports(
                original.read_text(encoding="utf-8"), replacements
            )
            writes[target] = source
            names = _exports(source)
            if not package or relative == Path("__init__.py"):
                if not names:
                    raise ValueError(f"no static exports in {original}")
                writes[original] = _compatibility_module(
                    move.module,
                    names,
                    interpreter=move.interpreter,
                    entry_keywords=_entry_keywords(
                        (move.source / "__main__.py").read_text()
                        if package and (move.source / "__main__.py").exists()
                        else source
                    )
                    if move.interpreter
                    else "",
                )
            else:
                parts = relative.with_suffix("").parts
                suffix = ".".join(
                    parts[:-1] if original.name == "__init__.py" else parts
                )
                if original.name != "__main__.py":
                    descendants.append(suffix)
                    writes[original.with_suffix(".pyi")] = (
                        "".join(
                            f"from {move.module}.{suffix} import {name} as {name}\n"
                            for name in names
                        )
                        or '"""Compatibility module."""\n'
                    )
                deletes.add(original)
        if package:
            entry = move.source / "__init__.py"
            registrations = "".join(
                f'sys.modules[__name__ + ".{suffix}"] = importlib.import_module(\n'
                f'    "{move.module}.{suffix}"\n)\n'
                for suffix in sorted(descendants)
            )
            anchor = "sys.modules[__name__] = _implementation\n"
            writes[entry] = writes[entry].replace(anchor, anchor + registrations)
    for move in moves:
        writes[move.target.parent / "__init__.py"] = (
            '"""Language implementation modules."""\n'
        )
    for path, source in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    for path in deletes:
        path.unlink()


def main(argv: list[str] | None = None) -> int:
    """Print the plan; reject unsafe selections before applying any writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "names",
        nargs="*",
        choices=None,
        help="registry names; default: entire registry",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--flat", action="store_true", help="select only flat layouts")
    parser.add_argument("--packages", action="store_true", help="allow package layouts")
    args = parser.parse_args(argv)
    unknown = set(args.names) - LANGUAGES.keys()
    if unknown:
        parser.error(f"unknown languages: {', '.join(sorted(unknown))}")
    moves = []
    blocked = []
    for name in args.names or LANGUAGES:
        status, owned = plan(LANGUAGES[name])
        print(f"{status}: {name}")
        if status == "flat" or (
            status == "package" and args.packages and not args.flat
        ):
            moves.extend(owned)
        elif status != "colocated" and not args.flat:
            blocked.append(name)
    if args.apply:
        if blocked:
            parser.error(f"manual migration required: {', '.join(blocked)}")
        apply(moves)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
