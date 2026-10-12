"""Code outside a language's own files names it no more than it did.

A language should be removable by deleting its files.  Each mention of it
elsewhere -- a string equal to its name or id, an import of its modules, an
attribute named after them, a docstring or comment that cites it as an
example -- is coupling that ``remove`` has to chase, so
``tests/support/fixtures/coupling.toml`` records how many each file holds.  The
counts only go down: a new per-language table belongs on the language's
``LANGUAGE`` or in its own test file, and a file that sheds mentions
lowers its count.
"""

import ast
import io
import re
import subprocess
import tokenize
import tomllib
from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES, Language
from tests.support.reference import REFERENCE

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = ROOT / "tests/support/fixtures/coupling.toml"
#: The language shared tests use as their example: naming it is not coupling.
TREES = ("src/", "tests/", "scripts/")
#: Files ``new_language.py remove`` edits, or its own test, which names
#: languages as examples.  The coupling guard does not count them.
MANAGED = frozenset(
    {
        "src/esolangs/registry/_table.py",
        "src/esolangs/languages/generators.py",
        "tests/support/samples.py",
        "tests/generators/test_wrap.py",
        "tests/proofs/test_execution_formulas.py",
        "tests/proofs/test_workspace_formulas.py",
        "tests/proofs/test_schemes.py",
        "tests/api/test_language_coupling.py",
        "tests/api/test_interpreter_only_admissions.py",
        "tests/tooling/test_new_language.py",
        "tests/proofs/test_bands.py",
    }
)


def _mentions(path: str) -> Counter[str]:
    """Count the names a file's code (not its docstrings) spells."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    docs = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    found: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node not in docs:
                found[node.value] += 1
        elif isinstance(node, ast.ImportFrom) and node.module:
            # A module, or a module imported from its package by name.
            found["." + node.module.rsplit(".", 1)[-1]] += 1
            if node.module.startswith(("esolangs.generation", "esolangs.runtime")):
                found.update("." + alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update("." + alias.name.rsplit(".", 1)[-1] for alias in node.names)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"boolean", "tools"}
        ):
            # ``boolean.smu``: a generator reached through the package.
            found["." + node.attr] += 1
    return found


#: Phrases that introduce a second language as an example or comparison.
_CITATION_PHRASES = (
    "as in",
    "unlike",
    "like",
    "such as",
    "à la",
    "cf.",
    "see",
    "duplicating",
    "duplicates",
    "mirroring",
    "mirrors",
)
#: Suffixes that cite a language as a model rather than describe it: a
#: ``-like`` compound after the name.  The phrase list above only catches a
#: citation that comes first, so these slipped through.
_CITATION_SUFFIXES = ("-like", "-based", "-style", "-family")
#: A possessive naming the language's own source cites it as the authority
#: for another language: "X's page says the cell to the left is allowed".
#: A possessive of a property ("X's rotations cost 19") is a fact, not a
#: citation, so only these source nouns count.
_CITATION_SOURCE = re.compile(
    r"(?i)'s\s+(page|spec|specification|documentation|manual|wiki|entry"
    r"|interpreter|implementation|module)\b"
)
#: Prose that records history, not a statement about a live language.
_HISTORY = frozenset({"docs/CHANGELOG.md"})
#: The file kinds whose prose is scanned for citations.
_PROSE = (".py", ".md", ".tex")


def _prose(path: Path, text: str) -> list[str]:
    """Return a file's docstrings and comments, or its lines if it is text."""
    if path.suffix != ".py":
        return text.splitlines()
    lines: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            lines += node.value.value.splitlines()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                lines.append(token.string)
    except tokenize.TokenError:
        pass
    return lines


def _cites(line: str, name: re.Pattern[str], phrase: re.Pattern[str]) -> bool:
    """Whether a prose line cites a language rather than describes one.

    A citation is a phrase before the name ("like a second language"), a
    compound after it ("a second-language-like machine"), or a possessive
    naming its source ("its page says").  A bare mention is not.  The caller
    has already dropped the file's own language.
    """
    return any(
        phrase.search(line[: match.start()])
        or line[match.end() :].startswith(_CITATION_SUFFIXES)
        or _CITATION_SOURCE.match(line[match.end() :])
        for match in name.finditer(line)
    )


@cache
def _citations() -> list[str]:
    """Return each docstring, comment or text line that cites a language.

    A file's own language is skipped: its prose is free to describe its
    dialect.  Only the names it does not own count, which is what lets the
    possessive suffix above stand without flagging every language's own
    documentation.
    """
    langs = sorted(LANGUAGES.values(), key=lambda lang: -len(lang.name))
    phrase = re.compile(
        r"(?i)\b(" + "|".join(re.escape(p) for p in _CITATION_PHRASES) + r")\s*$"
    )
    owned = {lang.name: _own(lang)[1] for lang in langs}
    files = subprocess.run(
        ["git", "ls-files", "*.py", "*.md", "*.tex"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    found: list[str] = []
    for relative in files:
        if relative in _HISTORY:
            continue
        others = [name for name in owned if not relative.startswith(owned[name])]
        if not others:
            continue
        name = re.compile(rf"(?<!\w)(?:{'|'.join(re.escape(n) for n in others)})(?!\w)")
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if not name.search(text):
            continue
        for line in _prose(path, text):
            if _cites(line, name, phrase):
                found.append(f"{relative}: {line.strip()[:100]}")
    return sorted(set(found))


@pytest.mark.medium
def test_no_file_cites_another_language() -> None:
    """A fact about one language does not name a second as its example."""
    found = _citations()
    assert not found, (
        "a shared file cites another language; state the fact without naming a "
        f"second language: {found}"
    )


def test_citation_matching_covers_a_compound() -> None:
    """A suffix after the name cites it; a bare mention does not."""
    name = re.compile(r"(?<!\w)(?:Zork)(?!\w)")
    phrase = re.compile(r"(?i)\b(like)\s*$")
    assert _cites("Zork wraps its bytes", name, phrase) is False
    assert _cites("like Zork, it wraps", name, phrase) is True
    assert _cites("a Zork-like machine", name, phrase) is True
    assert _cites("Zork's page allows it", name, phrase) is True
    assert _cites("Zork's rotations cost 19", name, phrase) is False


def _own(lang: Language) -> tuple[set[str], tuple[str, ...]]:
    """Return a language's spellings and the path prefixes it owns."""
    modules = [f"esolangs.languages.{lang.id}.interpreter"] if lang.interpreter else []
    if lang.boolean is not None:
        modules.append(lang.boolean.__module__.removesuffix(".__init__"))
    canonical = [m for m in modules if m.startswith("esolangs.languages.")]
    stems = {lang.id}
    if lang.boolean is not None:
        stems.add(lang.boolean.__name__)
    prefixes = [f"src/{m.replace('.', '/')}" for m in modules]
    prefixes.append(f"src/esolangs/languages/{lang.id}/")
    prefixes += [f"src/{m.split('.generator')[0].replace('.', '/')}" for m in canonical]
    for stem in stems:
        prefixes += [f"scripts/profile_{stem}", f"scripts/verify_{stem}_"]
    spellings = {lang.name, *lang.aliases, *stems} | {"." + stem for stem in stems}
    return spellings, tuple(prefixes)


@cache
def _counts() -> dict[str, int]:
    """Count, per file, its mentions of languages it does not belong to."""
    files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    owned = [_own(lang) for name, lang in LANGUAGES.items() if name != REFERENCE]
    counts: dict[str, int] = {}
    for path in files:
        if path in MANAGED or not path.startswith(TREES):
            continue
        found = _mentions(path)
        total = sum(
            found[spelling]
            for spellings, prefixes in owned
            if not path.startswith(prefixes)
            for spelling in spellings
            # ``line`` and ``eval`` name a language and a common word: only
            # an import or attribute of the module counts for those.
            if spelling.startswith(".") or spelling not in {"line", "eval", "false"}
        )
        if total:
            counts[path] = total
    return counts


def lower_recorded() -> None:
    """Lower each recorded count to the current one; ``remove`` calls this."""
    text = ALLOWED.read_text(encoding="utf-8")
    header = [line for line in text.splitlines() if line.startswith("#")]
    allowed = tomllib.loads(text)
    _counts.cache_clear()
    now = _counts()
    kept = {
        path: min(count, now[path]) for path, count in allowed.items() if path in now
    }
    body = [f'"{path}" = {count}' for path, count in sorted(kept.items())]
    ALLOWED.write_text("\n".join([*header, "", *body]) + "\n", encoding="utf-8")


@pytest.mark.medium
def test_no_file_names_more_languages_than_recorded() -> None:
    allowed = tomllib.loads(ALLOWED.read_text(encoding="utf-8"))
    grown = {
        path: (count, allowed.get(path, 0))
        for path, count in _counts().items()
        if count > allowed.get(path, 0)
    }
    assert not grown, (
        "new per-language mentions (now, recorded) -- put the fact on the "
        f"language's LANGUAGE or in its own test file instead: {grown}"
    )


@pytest.mark.medium
def test_the_recorded_counts_only_go_down() -> None:
    allowed = tomllib.loads(ALLOWED.read_text(encoding="utf-8"))
    counts = _counts()
    shrunk = {
        path: (counts.get(path, 0), count)
        for path, count in allowed.items()
        if counts.get(path, 0) < count
    }
    assert not shrunk, (
        "fewer mentions than recorded (now, recorded): lower them in "
        f"tests/support/fixtures/coupling.toml: {shrunk}"
    )
