"""Rank generator ``Decisions:`` and comment figures by code churn since.

No harness can re-run them: each describes a rejected option that would have
to be rebuilt.  This lists every docstring ``Decisions:`` line and comment
carrying a measured figure, with the number of later commits that touched its package
(``git blame`` dates the line), most-changed first.  A figure whose package
has moved on is the one to re-measure.  A changed figure is re-dated by its
edit; ``--confirm path:line`` re-dates one that held, recording ``HEAD`` in
``figures_confirmed.toml`` against the line's text.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tokenize
import tomllib
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "esolangs" / "languages"
CONFIRMED = Path(__file__).parent / "baselines/figures_confirmed.toml"
#: A measured figure: a percentage, a decimal, or an integer of 3+ digits.
#: Shorter integers (``n=10``, ``2**n``) recur legitimately.
FIGURE = re.compile(r"\d+(?:\.\d+)?%|\d+\.\d+|\d{1,3}(?:,\d{3})+|\d{3,}")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def _decision_lines(path: Path) -> list[int]:
    """Return 1-based lines of the module docstring's ``Decisions:`` section."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    doc = tree.body[0] if tree.body else None
    if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)):
        return []
    lines = source.splitlines()
    found, inside = [], False
    for number in range(doc.lineno, (doc.end_lineno or doc.lineno) + 1):
        text = lines[number - 1]
        if text.strip() == "Decisions:":
            inside = True
        elif inside and text and not text.startswith(" "):
            inside = False
        elif inside and FIGURE.search(text):
            found.append(number)
    return found


#: A lint code (``SLF001``) is no figure; a comment measures only beside a
#: percentage, decimal, ``->`` or unit, not a constant like ``256``.
_LINT = re.compile(r"\b[A-Z]+\d+\b")
_MEASURE = re.compile(
    r"%|\d\.\d|->|\b\d[\d,]*\s*(?:chars?|characters|cells|pixels|codels|"
    r"steps|commands|instructions|rows|MB|ms|s)\b|\d+x\b"
)


def _comment_lines(path: Path) -> list[int]:
    """Return 1-based lines of comments carrying a measured figure."""
    found = []
    with path.open("rb") as source:
        for token in tokenize.tokenize(source.readline):
            if token.type != tokenize.COMMENT:
                continue
            text = _LINT.sub("", token.string)
            if FIGURE.search(text) and _MEASURE.search(text):
                found.append(token.start[0])
    return found


def _blame(path: Path) -> dict[int, str]:
    """Map each line of ``path`` to the commit that last wrote it."""
    shas, line = {}, 0
    for row in _git("blame", "--porcelain", str(path)).splitlines():
        head = row.split()
        if len(head) >= 3 and len(head[0]) == 40 and head[1].isdigit():
            line = int(head[2])
            shas[line] = head[0]
    return shas


@cache
def _later(sha: str, package: Path) -> int:
    """Count commits after ``sha`` that touched ``package``; 0 if uncommitted."""
    if not sha.strip("0"):
        return 0
    return len(_git("rev-list", f"{sha}..HEAD", "--", str(package)).split())


def _confirmed() -> dict[str, dict[str, str]]:
    """Map ``rel`` path to confirmed line text and the commit that confirmed it."""
    if not CONFIRMED.exists():
        return {}
    return tomllib.loads(CONFIRMED.read_text(encoding="utf-8"))


def _confirm(where: str) -> None:
    """Record ``HEAD`` as the date of the figure at ``rel:line``."""
    rel, _, number = where.rpartition(":")
    text = (LANGUAGES / rel).read_text(encoding="utf-8").splitlines()[int(number) - 1]
    table = _confirmed()
    table.setdefault(rel, {})[text.strip()] = _git("rev-parse", "HEAD").strip()
    out = ["# Decisions: figures re-measured and found to hold; see stale_figures.py."]
    for path in sorted(table):
        out += ["", f"[{json.dumps(path)}]"]
        out += [
            f"{json.dumps(k)} = {json.dumps(v)}" for k, v in sorted(table[path].items())
        ]
    CONFIRMED.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    """Print figures as ``changes  path:line  text``, most-changed first."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--top", type=int, default=0, help="print only N rows")
    parser.add_argument("--confirm", nargs="+", default=[], metavar="PATH:LINE")
    args = parser.parse_args()
    for where in args.confirm:
        _confirm(where)
    confirmed = _confirmed()
    rows = []
    for package in sorted(p for p in LANGUAGES.iterdir() if p.is_dir()):
        sources = [package / "generator.py", *package.glob("generator/*.py")]
        for path in (p for p in sources if p.exists()):
            numbers = sorted({*_decision_lines(path), *_comment_lines(path)})
            if not numbers:
                continue
            shas = _blame(path)
            source = path.read_text(encoding="utf-8").splitlines()
            for number in numbers:
                rel = path.relative_to(LANGUAGES).as_posix()
                text = source[number - 1].strip()
                sha = confirmed.get(rel, {}).get(text, shas[number])
                changes = _later(sha, package)
                rows.append((changes, f"{rel}:{number}", text))
    rows.sort(key=lambda row: (-row[0], row[1]))
    for changes, where, text in rows[: args.top or None]:
        print(f"{changes:4d}  {where}  {text}")
    print(f"{len(rows)} figure lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
