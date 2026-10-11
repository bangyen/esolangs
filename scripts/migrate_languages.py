"""Plan language colocation; pass --apply to migrate selected flat modules."""

from __future__ import annotations

import argparse
import symtable
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
    for module, leaf in modules:
        source = root / "src" / module.replace(".", "/")
        if source.is_dir():
            return "package", []
        source = source.with_suffix(".py")
        if not source.is_file():
            return "missing source", []
        moves.append(
            Move(
                source,
                package / f"{leaf}.py",
                f"esolangs.languages.{lang.id}.{leaf}",
                leaf == "interpreter",
            )
        )
    return ("flat", moves) if moves else ("no implementation", [])


def apply(moves: list[Move]) -> None:
    """Preflight every write before preserving sources and installing aliases."""
    writes: dict[Path, str] = {}
    for move in moves:
        if move.target.exists() or move.target.parent.exists():
            raise FileExistsError(f"refusing to overwrite {move.target.parent}")
        if move.source in writes or move.target in writes:
            raise ValueError(
                f"shared implementation requires manual migration: {move.source}"
            )
        source = move.source.read_text(encoding="utf-8")
        symbols = symtable.symtable(source, str(move.source), "exec")
        names = tuple(
            sorted(
                symbol.get_name()
                for symbol in symbols.get_symbols()
                if (symbol.is_assigned() or symbol.is_imported())
                and not symbol.get_name().startswith("__")
            )
        )
        if not names:
            raise ValueError(f"no static exports in {move.source}")
        writes[move.target] = source
        writes[move.source] = _compatibility_module(
            move.module, names, interpreter=move.interpreter
        )
    for move in moves:
        writes[move.target.parent / "__init__.py"] = (
            '"""Language implementation modules."""\n'
        )
    for path, source in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


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
    args = parser.parse_args(argv)
    unknown = set(args.names) - LANGUAGES.keys()
    if unknown:
        parser.error(f"unknown languages: {', '.join(sorted(unknown))}")
    moves = []
    blocked = []
    for name in args.names or LANGUAGES:
        status, owned = plan(LANGUAGES[name])
        print(f"{status}: {name}")
        moves.extend(owned)
        if status not in {"flat", "colocated"} and not args.flat:
            blocked.append(name)
    if args.apply:
        if blocked:
            parser.error(f"manual migration required: {', '.join(blocked)}")
        apply(moves)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
