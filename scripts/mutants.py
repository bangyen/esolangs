"""Seeded token mutants of a generator, run against its tests.

``rank`` lists the largest generators ``mutants_swept.toml`` does not record,
or records at a commit their code has since left.
``sweep`` takes package directories (``abcdirection``), prices one baseline
run each, then applies ``--per-language`` seeded mutants one at a time:
operator swaps (``+``/``-``, ``<``/``<=``, ``and``/``or``, ...) and integer
constants plus one, in generator source only.  Each runs the package's tests
plus the registry tests matching its name, ``pytest -x``; a mutant that no
test kills is a survivor to triage by hand.  The selection excludes the
harness's deadline tests, which no generator mutant can kill, and the
xdist worker count comes from ``MUTANTS_WORKERS`` (default 4).

Mutants edit source in place, so a sweep refuses to run outside a git
worktree.  Caps: a run gets three times its baseline (60 s at least), the
sweep a global budget, and a language three consecutive timeouts.  Records
append to ``--out`` as JSON lines; add swept packages to
``mutants_swept.toml`` once triaged.  A failure that is only a
duration-band flip (see ``_duration_flips``) never counts: a baseline
passes when every one of its failures is a flip, and a mutant is recorded
survived, with the flips listed, when no test functionally kills it.
"""

from __future__ import annotations

import argparse
import ast
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
# scripts/ holds the sibling `verify` package.
sys.path.insert(0, str(ROOT / "scripts"))

from verify.failures import (  # noqa: E402
    DURATION_FAILURE,
    failed_ids,
    failure_sections,
    section_matches,
)

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
            if token.type in (tokenize.OP, tokenize.NAME) and old in SWAP:
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
    command = [
        "uv",
        "run",
        "pytest",
        "-q",
        "-n",
        os.environ.get("MUTANTS_WORKERS", "4"),
        "-p",
        "no:cacheprovider",
    ]
    command += ["--tb=short", "-rf", "-m", "not weekly", *(["-x"] if stop else [])]
    # The harness's deadline tests (under tests/, exercising the
    # worker-reaping machinery) can kill no generator mutant, and the
    # substring match drags them into package "line"'s selection ("line"
    # inside "deadline"), where they flake under load.  Exclude that stem
    # outside the language packages, so a package's own deadline-named
    # test still runs.
    keyword = f"({registry_keyword(package)}) and not (deadline and not languages)"
    return [
        *command,
        f"src/esolangs/languages/{package}",
        "tests",
        "-k",
        keyword,
    ]


def _duration_flips(output: str) -> list[str] | None:
    """Return the failed node ids when every failure is a duration-band flip.

    None when anything is unprovable: an ERROR line, no failures at all, no
    FAILURES sections, a section count that disagrees with the summary, a
    section whose body lacks the overrun signature, or a failed id no
    section names.  Callers then keep the plain verdict.
    """
    lines = output.splitlines()
    if any(line.startswith("ERROR ") for line in lines):
        return None
    ids = failed_ids(lines)
    if not ids:
        return None
    sections = failure_sections(output)
    if sections is None or len(sections) != len(ids):
        return None
    if not all(DURATION_FAILURE.search(body) for _, body in sections):
        return None
    titles = [title for title, _ in sections]
    if not all(
        any(section_matches(title, nodeid) for title in titles) for nodeid in ids
    ):
        return None
    return ids


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
            flips = _duration_flips(output) if status == "killed" else None
            if status != "survived" and flips is None:
                print(
                    f"{package}: baseline {status}\n{output[-2000:]}", file=sys.stderr
                )
                return 1
            if flips:
                print(
                    f"{package}: baseline passed; {len(flips)} duration-only "
                    "failure(s) tolerated",
                    flush=True,
                )
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
                flips = _duration_flips(output) if status == "killed" else None
                if flips is not None:
                    status = "survived"
                streak = streak + 1 if status == "timeout" else 0
                failed = sorted(set(re.findall(r"^FAILED (\S+)", output, re.MULTILINE)))
                line = original.split("\n")[mutant["line"] - 1].strip()
                record = mutant | {"package": package, "status": status}
                if flips:
                    record |= {"duration_flips": flips}
                sink.write(
                    json.dumps(record | {"failed": failed[:3], "code": line}) + "\n"
                )
                sink.flush()
                print(
                    package,
                    status + (" (duration-only)" if flips else ""),
                    mutant["file"],
                    mutant["line"],
                    mutant["old"],
                    "->",
                    mutant["new"],
                    flush=True,
                )
    _clear_bytecode()
    return 0


def _code(source: str) -> str:
    """Return ``source``'s syntax tree without docstrings, as text."""
    tree = ast.parse(source)
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def changed_since(package: str, commit: str) -> bool:
    """Whether the package's generator code differs from ``commit``'s.

    Docstrings are ignored: ``Size:`` anchors move with every size change.
    """
    root = (LANGUAGES / package).relative_to(ROOT)
    paths = _git("ls-tree", "-r", "--name-only", commit, f"{root}/generator.py")
    paths += _git("ls-tree", "-r", "--name-only", commit, f"{root}/generator/")
    old = {
        path: _code(_git("show", f"{commit}:{path}"))
        for path in paths.split()
        if path.endswith(".py") and "/tests/" not in path
    }
    new = {
        str(f.relative_to(ROOT)): _code(f.read_text(encoding="utf-8"))
        for f in generator_files(package)
    }
    return old != new


def rank(count: int) -> list[str]:
    """Return the ``count`` largest unswept generators, by source lines."""
    swept = tomllib.loads(SWEPT.read_text(encoding="utf-8"))["swept"]
    sizes = []
    for package in sorted(p.name for p in LANGUAGES.iterdir() if p.is_dir()):
        files = generator_files(package)
        if files and (package not in swept or changed_since(package, swept[package])):
            lines = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)
            sizes.append((lines, package))
    return [package for _, package in sorted(sizes, reverse=True)[:count]]


def main(argv: list[str] | None = None) -> int:
    """Parse the subcommand and run it."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    ranked = commands.add_parser(
        "rank", help="largest generators unswept since their last change"
    )
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
