"""Code outside a language's own files does not name it.

A language should be removable by deleting its files.  Each mention of it
elsewhere -- a string equal to its name or id, an import of its modules, an
attribute named after them, a docstring or comment that cites it as an
example -- is coupling that manual removal has to chase.  None is left, so none may
come back: a per-language fact belongs on the language's ``LANGUAGE`` or in
its own test file.
"""

import ast
import io
import re
import subprocess
import tokenize
from collections import Counter
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES, LanguageDeclaration
from tests.support.reference import REFERENCE

ROOT = Path(__file__).resolve().parents[2]
#: The language shared tests use as their example: naming it is not coupling.
TREES = ("src/", "tests/", "scripts/")
#: Existing shared fixtures and integration tests that name languages.
#: The coupling guard does not count them.
MANAGED = frozenset(
    {
        "src/esolangs/registry/_table.py",
        "tests/support/samples.py",
        "tests/generators/test_wrap.py",
        "tests/proofs/measurement.py",
        "tests/proofs/_witnesses.py",
        "tests/proofs/test_workspace_formulas.py",
        "tests/api/test_language_coupling.py",
        "tests/tooling/test_new_language.py",
        "tests/proofs/test_bands.py",
        "tests/cli/test_cli_messages.py",
    }
)


def _mentions(tree: ast.AST) -> Counter[str]:
    """Count the names a file's code (not its docstrings) spells."""
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
            if node.module != "esolangs.cli.help":
                found["." + node.module.rsplit(".", 1)[-1]] += 1
            if node.module.startswith(("esolangs.generation", "esolangs.runtime")):
                found.update("." + alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(
                "." + alias.name.rsplit(".", 1)[-1]
                for alias in node.names
                if alias.name != "esolangs.cli.help"
            )
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


def _python_prose(tree: ast.AST, text: str) -> list[str]:
    """Return Python docstrings and comments using the shared parse."""
    lines: list[str] = []
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


def test_citation_matching_covers_a_compound() -> None:
    """A suffix after the name cites it; a bare mention does not."""
    name = re.compile(r"(?<!\w)(?:Zork)(?!\w)")
    phrase = re.compile(r"(?i)\b(like)\s*$")
    assert _cites("Zork wraps its bytes", name, phrase) is False
    assert _cites("like Zork, it wraps", name, phrase) is True
    assert _cites("a Zork-like machine", name, phrase) is True
    assert _cites("Zork's page allows it", name, phrase) is True
    assert _cites("Zork's rotations cost 19", name, phrase) is False


def _own(lang: LanguageDeclaration) -> tuple[set[str], tuple[str, ...]]:
    """Return a language's spellings and the path prefixes it owns."""
    modules = (
        [f"esolangs.languages.{lang.id}.interpreter"]
        if lang.runtime.interpreter
        else []
    )
    if lang.backend is not None:
        modules.append(lang.backend.generate.__module__.removesuffix(".__init__"))
    canonical = [m for m in modules if m.startswith("esolangs.languages.")]
    stems = {lang.id}
    if lang.backend is not None:
        stems.add(lang.backend.generate.__name__)
    prefixes = [f"src/{m.replace('.', '/')}" for m in modules]
    prefixes.append(f"src/esolangs/languages/{lang.id}/")
    prefixes += [f"src/{m.split('.generator')[0].replace('.', '/')}" for m in canonical]
    for stem in stems:
        prefixes += [f"scripts/profile_{stem}", f"scripts/verify_{stem}_"]
    spellings = {lang.name, *lang.aliases, *stems} | {"." + stem for stem in stems}
    return spellings, tuple(prefixes)


def _foreign_mentions(
    tree: ast.AST, relative: str, owned: dict[str, tuple[set[str], tuple[str, ...]]]
) -> int:
    found = _mentions(tree)
    return sum(
        found[spelling]
        for name, (spellings, prefixes) in owned.items()
        if name != REFERENCE and not relative.startswith(prefixes)
        for spelling in spellings
        # Some language IDs are common words or argument names, and
        # FALSE is also GridScript's BOOL literal. Their module imports
        # and attributes still count as coupling.
        if spelling.startswith(".")
        or spelling not in {"line", "eval", "false", "FALSE"}
    )


def _scan() -> tuple[dict[str, int], list[str]]:
    """Find foreign code mentions and prose citations in one source scan."""
    langs = sorted(LANGUAGES.values(), key=lambda lang: -len(lang.name))
    owned = {lang.name: _own(lang) for lang in langs}
    phrase = re.compile(
        r"(?i)\b(" + "|".join(re.escape(p) for p in _CITATION_PHRASES) + r")\s*$"
    )
    files = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "*.py", "*.md", "*.tex"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    counts: dict[str, int] = {}
    citations: list[str] = []
    for relative in files:
        path = ROOT / relative
        python = path.suffix == ".py"
        check_names = python and relative not in MANAGED and relative.startswith(TREES)
        others = [
            name
            for name, (_, prefixes) in owned.items()
            if relative not in _HISTORY and not relative.startswith(prefixes)
        ]
        if not (check_names or others):
            continue
        text = path.read_text(encoding="utf-8")
        name = (
            re.compile(rf"(?<!\w)(?:{'|'.join(re.escape(n) for n in others)})(?!\w)")
            if others
            else None
        )
        check_prose = name is not None and name.search(text) is not None
        tree = None
        if python and (check_names or check_prose):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                if check_names:
                    raise
                continue
        if check_names:
            assert tree is not None
            if total := _foreign_mentions(tree, relative, owned):
                counts[relative] = total
        if name is not None and check_prose:
            lines = _python_prose(tree, text) if tree is not None else text.splitlines()
            citations.extend(
                f"{relative}: {line.strip()[:100]}"
                for line in lines
                if _cites(line, name, phrase)
            )
    return counts, sorted(set(citations))


@pytest.mark.medium
def test_no_file_names_or_cites_another_language() -> None:
    counts, citations = _scan()
    errors = []
    if counts:
        errors.append(
            "per-language mentions outside the language's own files -- put the "
            f"fact on the language's LANGUAGE or in its own test file instead: {counts}"
        )
    if citations:
        errors.append(
            "a shared file cites another language; state the fact without naming a "
            f"second language: {citations}"
        )
    assert not errors, "\n".join(errors)
