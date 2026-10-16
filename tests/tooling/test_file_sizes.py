"""Cap files, keep tests below their sources, and keep the suite under budget."""

import pathlib
import re
import subprocess
from collections import defaultdict

import pytest

from esolangs.registry import LANGUAGES
from scripts.ci.shard import collect_ids

#: The most lines a file may have before it has to be split.
MAX_LINES = 1200

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_TREES = ("src", "tests", "scripts")


def _sizes() -> dict[str, int]:
    """Return every checked file's line count, keyed by repo-relative path."""
    return {
        path.relative_to(_ROOT).as_posix(): path.read_text().count("\n")
        for tree in _TREES
        for path in sorted((_ROOT / tree).rglob("*.py"))
    }


def test_no_file_is_over_the_cap() -> None:
    """A file over the cap must be split."""
    over = {name: lines for name, lines in _sizes().items() if lines > MAX_LINES}
    assert not over, f"over {MAX_LINES} lines: {over}. Split the file."


def _tracked_lines(
    tree: str, *, exclude: str | None = None, tests: bool | None = None
) -> int:
    """Count the lines of ``tree/*.py`` files git sees, as ``wc -l`` does.

    ``tests`` keeps only files under a ``tests`` directory (True) or only
    files outside one (False).
    """
    # Untracked files count too: a new language's tests are untracked until
    # committed, and a file only staged for deletion does not.
    listed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            f"{tree}/*.py",
        ],
        cwd=_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    names = [name.decode() for name in listed.split(b"\0") if name]
    paths = [_ROOT / name for name in names]
    return sum(
        path.read_bytes().count(b"\n")
        for path in paths
        if path.exists()
        and (exclude is None or not path.is_relative_to(_ROOT / exclude))
        and (tests is None or ("tests" in path.relative_to(_ROOT).parts) == tests)
    )


@pytest.mark.parametrize(
    ("tests", "source", "exclude"),
    [
        ("tests", "src", "tests/tooling"),
        ("tests/tooling", "scripts", None),
    ],
)
def test_test_budgets(tests, source, exclude) -> None:
    test_lines = _tracked_lines(tests, exclude=exclude)
    source_lines = _tracked_lines(source)
    assert source_lines > 0
    assert test_lines < source_lines, (
        f"{tests}: {test_lines} lines, {source}: {source_lines}"
    )


def test_language_tests_count_as_tests() -> None:
    """``src/**/tests`` is test code: count it against the code it tests."""
    # The row above counts it as source, so it passed at 1:5.8 while the
    # user's rule (tests/ + src/**/tests < src) stood at 93% (2026-10-16).
    test_lines = _tracked_lines("tests", exclude="tests/tooling") + _tracked_lines(
        "src", tests=True
    )
    source_lines = _tracked_lines("src", tests=False)
    assert test_lines > 10_000, "test files were not found"
    assert test_lines < source_lines, (
        f"tests/ + src/**/tests: {test_lines} lines, src: {source_lines}; prune"
    )


#: Collected tests outside the registry contracts (user budget, 2026-10-05).
MAX_TESTS = 10_000
#: A test function whose cases name this many languages is a registry
#: contract: it grows by one case per language by design, so the budget
#: leaves it out.  The narrowest contract sweep names 11.
CONTRACT_LANGUAGES = 10


def _spelling(spellings: set[str]) -> re.Pattern[str]:
    """Match one of ``spellings`` as a whole part of a pytest case id."""
    # Longest first, so a name is not read as a prefix of a longer one; ids
    # join params with "-" and paths with "/".
    alternatives = "|".join(map(re.escape, sorted(spellings, key=len, reverse=True)))
    return re.compile(rf"(?:^|[-/])({alternatives})(?:$|[-/.])")


def _uncounted(node_ids: list[str], spelling: re.Pattern[str]) -> int:
    """Return how many of ``node_ids`` are not registry-contract cases."""
    cases: dict[str, list[str]] = defaultdict(list)
    for node_id in node_ids:
        function, _, case = node_id.partition("[")
        cases[function].append(case.removesuffix("]"))
    contract = sum(
        len(ids)
        for ids in cases.values()
        if len({m.group(1) for m in map(spelling.search, ids) if m})
        >= CONTRACT_LANGUAGES
    )
    return len(node_ids) - contract


def test_the_contract_rule_exempts_only_sweeps_over_languages() -> None:
    """Positive control: a sweep over enough languages is exempt, a big one is not."""
    names = [f"L{i}" for i in range(CONTRACT_LANGUAGES)]
    spelling = _spelling(set(names))
    ids = [f"t.py::test_a[{name}-{n}]" for name in names for n in range(3)]
    ids.append("t.py::test_a[unnamed]")
    ids += [f"t.py::test_b[{n}]" for n in range(50)]
    ids += [f"t.py::test_c[{name}]" for name in names[1:]]
    ids.append("t.py::test_d[L10]")
    assert _uncounted(ids, spelling) == 50 + CONTRACT_LANGUAGES - 1 + 1


@pytest.mark.medium
def test_the_suite_stays_under_its_test_budget() -> None:
    """Fewer, sharper tests: a sweep that pushes past the budget is a blocker."""
    # 2026-10-16: 12,170 collected, 3,277 in 38 contract functions.
    node_ids = collect_ids("")
    assert len(node_ids) > 1000, "collection came back nearly empty"
    spellings = {
        spelling
        for language in LANGUAGES.values()
        for spelling in (language.name, language.id, *language.aliases)
    }
    count = _uncounted(node_ids, _spelling(spellings))
    assert count < MAX_TESTS, (
        f"{count} non-contract tests, budget {MAX_TESTS}: prune, don't re-tag"
    )
