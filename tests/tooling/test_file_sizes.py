"""Cap files, keep tests below their sources, and keep the suite under budget."""

import pathlib
import re
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


#: A per-language helper module under ``src/**/tests`` with a name like this
#: is an independent oracle or accounting model: migration-acceptance evidence
#: with its own ceiling, not regression tests.  ``test_*`` files never match.
_ORACLE = re.compile(
    r"oracle|accounting|workspace_(views|checks)|_model\.py$"
    r"|resource_checks|capture_comparison"
)
#: Oracle line ceiling (user, 2026-11-11); lower it as oracles shrink. 2026-11-08
#: dropped the tests < src rule; oracles then grew 17k lines, the rest 6k.
MAX_ORACLE_LINES = 34_631


def _category(name: str) -> str:
    """Return which line budget the repo-relative ``name`` counts toward."""
    parts = name.split("/")
    if parts[0] == "scripts":
        return "scripts"
    if name.startswith("tests/tooling/"):
        return "tooling"
    if parts[0] == "src" and "tests" not in parts:
        return "source"
    if (
        parts[0] == "src"
        and not parts[-1].startswith("test_")
        and _ORACLE.search(parts[-1])
    ):
        return "oracle"
    return "tests"


def test_tests_stay_below_their_sources() -> None:
    """Test code stays below the code it tests; oracles have their own ceiling.

    ``tests/`` + ``src/**/tests`` < ``src``, and ``tests/tooling`` < ``scripts``.
    """
    lines: dict[str, int] = defaultdict(int)
    for name, count in _sizes().items():
        lines[_category(name)] += count
    assert lines["tests"] > 10_000, "test files were not found"
    assert lines["oracle"] > 1_000, "oracle files were not found"
    assert lines["tests"] < lines["source"], (
        f"tests: {lines['tests']} lines, src: {lines['source']}; prune, don't offset"
    )
    assert lines["oracle"] < MAX_ORACLE_LINES, (
        f"oracles: {lines['oracle']} lines, ceiling {MAX_ORACLE_LINES}; condense"
    )
    assert 0 < lines["tooling"] < lines["scripts"], (
        f"tests/tooling: {lines['tooling']}, scripts: {lines['scripts']}"
    )


#: Shared tests outside the registry contracts (user budget 10,000 on
#: 2026-10-05; split on 2026-11-18, when 2,501 of the 9,999 were shared).
MAX_SHARED_TESTS = 3_000
#: Each language's own ``src/**/tests`` cases, averaged over the registry: a
#: language brings its tests, but the mean may not drift (56.8 on 2026-11-18).
MAX_PACKAGE_TESTS_PER_LANGUAGE = 60
#: No one package may hold more (Line had 352 on 2026-11-18).
MAX_PACKAGE_TESTS = 400
#: A test function whose cases name this many languages is a registry
#: contract: it grows by one case per language by design, so the budget
#: leaves it out.  The narrowest contract sweep names 11.
CONTRACT_LANGUAGES = 10
_PACKAGE = re.compile(r"src/esolangs/languages/([^/]+)/tests/")


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


def _budgets(
    node_ids: list[str], spelling: re.Pattern[str]
) -> tuple[int, dict[str, int]]:
    """Return the shared count and each language package's count, contracts out."""
    packages: dict[str, list[str]] = defaultdict(list)
    shared = []
    for node_id in node_ids:
        match = _PACKAGE.match(node_id)
        (packages[match.group(1)] if match else shared).append(node_id)
    return _uncounted(shared, spelling), {
        name: _uncounted(ids, spelling) for name, ids in packages.items()
    }


def test_the_budgets_split_shared_from_package_tests() -> None:
    """Positive control: a package's cases leave the shared count, by package."""
    spelling = _spelling({"L"})
    ids = ["tests/t.py::test_a[0]", "tests/t.py::test_a[1]"]
    ids += [f"src/esolangs/languages/x/tests/t.py::test_b[{n}]" for n in range(3)]
    ids.append("src/esolangs/languages/y/tests/t.py::test_c")
    assert _budgets(ids, spelling) == (2, {"x": 3, "y": 1})


@pytest.mark.medium
def test_the_suite_stays_under_its_test_budget() -> None:
    """Fewer, sharper tests: a sweep that pushes past a budget is a blocker."""
    # 2026-10-16: 12,170 collected, 3,277 in 38 contract functions.
    node_ids = collect_ids("")
    assert len(node_ids) > 1000, "collection came back nearly empty"
    spellings = {
        spelling
        for language in LANGUAGES.values()
        for spelling in (language.name, language.id, *language.aliases)
    }
    shared, packages = _budgets(node_ids, _spelling(spellings))
    assert len(packages) > 100, "language package tests were not found"
    assert shared < MAX_SHARED_TESTS, (
        f"{shared} shared non-contract tests, budget {MAX_SHARED_TESTS}: "
        "prune, don't re-tag"
    )
    total, cap = sum(packages.values()), MAX_PACKAGE_TESTS_PER_LANGUAGE * len(LANGUAGES)
    assert total <= cap, (
        f"{total} language package tests, budget {cap} "
        f"({MAX_PACKAGE_TESTS_PER_LANGUAGE} per language): prune, don't re-tag"
    )
    over = {name: n for name, n in packages.items() if n > MAX_PACKAGE_TESTS}
    assert not over, f"over {MAX_PACKAGE_TESTS} tests in one package: {over}"
