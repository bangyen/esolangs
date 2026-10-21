"""Seeded token mutants of a generator, run against its tests.

``rank`` lists the largest generators ``mutants_swept.toml`` does not record.
``sweep`` takes package directories (``abcdirection``), prices one baseline
run each, then applies ``--per-language`` seeded mutants one at a time:
operator swaps (``+``/``-``, ``<``/``<=``, ``and``/``or``, ...) and integer
constants plus one, in generator source only.  Each runs the package's tests
plus the registry tests matching its name, ``pytest -x``; a mutant that no
test kills is a survivor to triage by hand.

Mutants edit source in place, so a sweep refuses to run outside a git
worktree.  Caps: a run gets three times its baseline (60 s at least), the
sweep a global budget, and a language three consecutive timeouts.  Records
append to ``--out`` as JSON lines; add swept packages to
``mutants_swept.toml`` once triaged.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import tokenize
import tomllib
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "esolangs" / "languages"
SWEPT = Path(__file__).parent / "baselines/mutants_swept.toml"
SWAP = {
    "+": "-",
    "-": "+",
    "<": "<=",
    "<=": "<",
    ">": ">=",
    ">=": ">",
    "==": "!=",
    "!=": "==",
    "and": "or",
    "or": "and",
    "*": "+",
    "//": "%",
}


class Mutant(TypedDict):
    """One token edit: where, and the old and new spelling."""

    file: str
    line: int
    col: int
    old: str
    new: str


def generator_files(package: str) -> list[Path]:
    """Return the package's generator source: ``generator.py`` or ``generator/``."""
    root = LANGUAGES / package
    files = [root / "generator.py"] if (root / "generator.py").exists() else []
    if (root / "generator").is_dir():
        files += sorted(
            f for f in (root / "generator").rglob("*.py") if "tests" not in f.parts
        )
    return files


def _replaced(text: str, mutant: Mutant) -> str:
    lines = text.split("\n")
    row, col, old = mutant["line"], mutant["col"], mutant["old"]
    line = lines[row - 1]
    if line[col : col + len(old)] != old:
        raise ValueError(f"{mutant} does not match its line")
    lines[row - 1] = line[:col] + mutant["new"] + line[col + len(old) :]
    return "\n".join(lines)


def candidates(package: str, count: int) -> list[Mutant]:
    """Return ``count`` compiling mutants, seeded by the package name."""
    found: list[Mutant] = []
    for path in generator_files(package):
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        for i, token in enumerate(tokens):
            old = token.string
            if token.type == tokenize.OP or (
                token.type == tokenize.NAME and old in ("and", "or")
            ):
                if old not in SWAP:
                    continue
                new = SWAP[old]
            elif token.type == tokenize.NUMBER and re.fullmatch(r"\d+", old):
                if int(old) < 2:
                    continue
                new = str(int(old) + 1)
            else:
                continue
            row, col = token.start
            if lines[row - 1].lstrip().startswith(("#", "from ", "import ")):
                continue
            previous = tokens[i - 1]
            if (
                old == "-"
                and previous.type == tokenize.OP
                and previous.string in "(,=[:"
            ):
                continue  # a unary minus, not a subtraction
            found.append(
                Mutant(
                    file=str(path.relative_to(ROOT)),
                    line=row,
                    col=col,
                    old=old,
                    new=new,
                )
            )
    random.Random(f"mutants-{package}").shuffle(found)
    kept: list[Mutant] = []
    for mutant in found:
        if len(kept) == count:
            break
        source = (ROOT / mutant["file"]).read_text(encoding="utf-8")
        try:
            compile(_replaced(source, mutant), mutant["file"], "exec")
        except SyntaxError:
            continue
        kept.append(mutant)
    return kept


def registry_keyword(package: str) -> str:
    """Return the ``-k`` expression selecting the package's registry tests."""
    sys.path.insert(0, str(ROOT / "src"))
    from esolangs.registry import LANGUAGES as REGISTRY

    names = [
        lang.name for lang in REGISTRY.values() if lang.id.replace("-", "_") == package
    ]
    if not names:
        raise SystemExit(f"{package}: no registered language has this package")
    name = names[0]
    words = " and ".join(re.findall(r"[A-Za-z0-9_]+", name))
    return f"{package} or ({words})" if words else package


def _pytest(package: str, *, stop: bool) -> list[str]:
    command = ["uv", "run", "pytest", "-q", "-n", "4", "-p", "no:cacheprovider"]
    command += ["--tb=no", "-rf", "-m", "not weekly", *(["-x"] if stop else [])]
    return [
        *command,
        f"src/esolangs/languages/{package}",
        "tests",
        "-k",
        registry_keyword(package),
    ]


def _clear_bytecode() -> None:
    for cache in (ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(command: list[str], timeout: float) -> tuple[str, str]:
    """Return the status and output of one capped test run."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    with subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        env=env,
    ) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return "timeout", ""
        return ("killed" if process.returncode else "survived"), output


def _in_worktree() -> bool:
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return "/worktrees/" in git_dir


def sweep(packages: list[str], out: Path, per_language: int, budget: float) -> int:
    """Run every package's mutants; return 1 if a baseline fails."""
    began = time.monotonic()
    # A baseline alone may take minutes with nothing printed; say what runs.
    print(
        f"{len(packages)} package(s), up to {per_language} mutants each, "
        f"{budget / 3600:g} h budget; records append to {out}",
        flush=True,
    )
    with out.open("a", encoding="utf-8") as sink:
        for package in packages:
            print(f"{package}: baseline test run (15 min cap)", flush=True)
            start = time.monotonic()
            status, output = _run(_pytest(package, stop=False), 900)
            baseline = time.monotonic() - start
            if status != "survived":
                print(
                    f"{package}: baseline {status}\n{output[-2000:]}", file=sys.stderr
                )
                return 1
            timeout, streak = max(60.0, 3 * baseline), 0
            for mutant in candidates(package, per_language):
                if time.monotonic() - began > budget:
                    print("global budget spent")
                    return 0
                if streak == 3:
                    print(f"{package}: skipped after three consecutive timeouts")
                    break
                path = ROOT / mutant["file"]
                original = path.read_text(encoding="utf-8")
                try:
                    path.write_text(_replaced(original, mutant), encoding="utf-8")
                    _clear_bytecode()
                    status, output = _run(_pytest(package, stop=True), timeout)
                finally:
                    path.write_text(original, encoding="utf-8")
                streak = streak + 1 if status == "timeout" else 0
                failed = sorted(set(re.findall(r"^FAILED (\S+)", output, re.MULTILINE)))
                line = original.split("\n")[mutant["line"] - 1].strip()
                record = mutant | {"package": package, "status": status}
                sink.write(
                    json.dumps(record | {"failed": failed[:3], "code": line}) + "\n"
                )
                sink.flush()
                print(
                    package,
                    status,
                    mutant["file"],
                    mutant["line"],
                    mutant["old"],
                    "->",
                    mutant["new"],
                    flush=True,
                )
    _clear_bytecode()
    return 0


def rank(count: int) -> list[str]:
    """Return the ``count`` largest unswept generators, by source lines."""
    swept = set(tomllib.loads(SWEPT.read_text(encoding="utf-8"))["swept"])
    sizes = []
    for package in sorted(p.name for p in LANGUAGES.iterdir() if p.is_dir()):
        files = generator_files(package)
        if files and package not in swept:
            lines = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)
            sizes.append((lines, package))
    return [package for _, package in sorted(sizes, reverse=True)[:count]]


def main(argv: list[str] | None = None) -> int:
    """Parse the subcommand and run it."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    ranked = commands.add_parser("rank", help="largest generators not yet swept")
    ranked.add_argument("--count", type=int, default=10)
    run = commands.add_parser("sweep", help="run seeded mutants of packages")
    run.add_argument("packages", nargs="+")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--per-language", type=int, default=30)
    run.add_argument("--budget", type=float, default=2 * 3600, help="seconds")
    args = parser.parse_args(argv)
    if args.command == "rank":
        print("\n".join(rank(args.count)))
        return 0
    if not _in_worktree():
        parser.error("mutants edit source in place: run a sweep in a git worktree")
    return sweep(args.packages, args.out, args.per_language, args.budget)


if __name__ == "__main__":
    sys.exit(main())
