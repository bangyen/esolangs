"""Start, check, or finish a new language.

    python scripts/new_language.py start "Name" --category tape_based
    python scripts/new_language.py check "Name"     # what is still missing
    python scripts/new_language.py finish "Name"    # regenerate, then verify
    python scripts/new_language.py remove "Name"    # the inverse of all three
    python scripts/new_language.py bounds "Name"    # worst steps/bits per n

``start`` writes the interpreter, generator and test stubs.  ``check`` lists
every integration point the language still lacks, with the file and entry
to add; ``tests/tooling/test_new_language.py`` runs it over the registry,
so the list cannot drift from what the suite enforces.  Once the list is
empty it runs the seconds-long tests ``finish`` would otherwise fail late.
``bounds`` measures what the proof ledger's cells state and drafts them.
``finish`` regenerates every committed artifact and runs the full
``verify/gate.py`` gate.
``remove`` deletes what ``check`` asks for, regenerates, and lists the
mentions left in prose for a hand edit.
"""

from __future__ import annotations

import argparse
import keyword
import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Container
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[1]
# ``remove``'s half lives beside this file, imported as a sibling whether
# this runs as a script or is imported as ``scripts.new_language``.
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from docs.curation import fragment_row as _curation_fragment  # noqa: E402
from docs.proof_status import load as _proof_status_load  # noqa: E402
from removal import language as removal  # noqa: E402

CATEGORIES = (
    "grid_based",
    "stack_based",
    "queue_based",
    "tape_based",
    "register_based",
    "program_based",
    "variable_based",
    "other",
)


def _category_menu() -> str:
    """Return one line per category with its two best-known members."""
    from esolangs.registry import LANGUAGES

    lines = []
    for category in CATEGORIES:
        members = sorted(
            (n for n, lang in LANGUAGES.items() if lang.category == category),
            key=lambda n: -_curation(n).get("backlinks", 0),
        )
        lines.append(f"  {category:<15} e.g. {', '.join(members[:2]) or '-'}")
    return "\n".join(lines)


def _ask_category() -> str | None:
    """Prompt for a category on a terminal; None when there is none to ask."""
    if not sys.stdin.isatty():
        return None
    print(f"category? (pass --category to skip this)\n{_category_menu()}")
    answer = input("> ").strip()
    return answer if answer in CATEGORIES else None


def _slug(name: str) -> str:
    """Return the registry's id for ``name``, refused unless importable."""
    from esolangs.registry import LANGUAGES, canonical_id

    if name in LANGUAGES:
        return LANGUAGES[name].id
    slug = canonical_id(name)
    taken = {lang.id: other for other, lang in LANGUAGES.items()}
    if slug in taken:
        raise ValueError(f"{name!r} slugs to {slug!r}, {taken[slug]}'s id")
    if not slug.isidentifier() or keyword.iskeyword(slug):
        # ``class`` passed the old check and scaffolded an import line that
        # was a SyntaxError.
        raise ValueError(
            "name must produce a Python identifier beginning with a letter, "
            "and not a Python keyword"
        )
    return slug


#: Left in a stub's docstring until it is written; ``check`` looks for it.
PLACEHOLDER = "<describe"

_GENERATOR = '''"""{name} Boolean program generator: <describe the construction>.

<describe how the program reads its inputs, branches, and answers>

Size:
    <describe the growth in T or n>; n=4 parity: <count> chars

Raises:
    GeneratorCapError: <describe the cap; drop this section without one>

Decisions:
    <describe a rejected alternative and the measurement that rejected it>
"""

from esolangs.registry._language import Language
from esolangs.generation.helpers import _validate_truth_table


def {slug}(truth_table: str) -> str:
    """Build a {name} program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    raise NotImplementedError("{name} generator")


# The registry entry.  Add split=True if run() takes one string per source
# line, contract=BooleanContract(...) if the programs do not read one 0/1
# line per input (docs/CONTRIBUTING.md#the-boolean-io-contract), and
# wrap=wrap_chars (esolangs.generation.wrap) if a newline anywhere is harmless,
# else no_wrap="<why a break changes the program>"; eof="..." if an
# exhausted read has a spec value, empty_program="..." if "" is rejected,
# random=True if an instruction draws at random (run(seed=...) fixes it);
# a generator taking a width needs balance=, picking its squarest regime;
# example=Example(pair=PAIR, expected=...) for a template, or
# Example(expected=...) when the 0,1 row's output is not a bare "0" (a
# trailing newline, a dump).
LANGUAGE = Language("{name}", "{slug}", category="{category}", boolean={slug})
'''

_GENERATOR_TEST = '''"""Tests for the {name} Boolean generator."""

import pytest

import esolangs


#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{{2**n}}b") for n in (1, 2) for i in range(2 ** 2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("{name}", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("{name}", bits)
        got = esolangs.run("{name}", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("{name}", got) == table[row], (table, row)
'''


def scaffold(name: str, category: str, *, generator: bool = True) -> list[Path]:
    """Create and return the interpreter, generator and test stubs."""
    slug = _slug(name)
    package = ROOT / "src/esolangs/languages" / slug
    files = {
        package / "interpreter.py": _interpreter_stub(name),
        package / "tests" / f"test_{slug}.py": (
            f'"""Tests for the {name} interpreter."""\n\n'
            "import pytest\n\n"
            f"from esolangs.languages.{slug}.interpreter import run\n"
            "from esolangs.runtime.io import ScriptedIO\n\n\n"
            '@pytest.mark.xfail(reason="placeholder: replace with the spec")\n'
            "def test_placeholder_increment_and_write() -> None:\n"
            "    io = ScriptedIO()\n"
            '    run("+.", io)\n'
            '    assert io.getvalue() == "\\x01"\n'
        ),
    }
    if generator:
        fields = {"name": name, "slug": slug, "category": category}
        files[package / "generator.py"] = _GENERATOR.format(**fields)
        files[package / "tests" / f"test_boolean_{slug}.py"] = _GENERATOR_TEST.format(
            **fields
        )
    files[package / "tests/__init__.py"] = '"""Language-specific execution tests."""\n'
    files[package / "__init__.py"] = '"""Language implementation modules."""\n'
    files[package / "language.toml"] = (
        "# Language-owned data, one section per dataset; aggregators read\n"
        "# only their own section and skip this file when it is absent.\n\n"
        "[curation]\nunassessed = true\n"
    )
    namespace = package.parent / "__init__.py"
    if not namespace.exists():
        files[namespace] = '"""Language-owned interpreters and generators."""\n'
    collisions = [path for path in files if path.exists()]
    collisions += [
        path
        for path in (
            package.with_suffix(".py"),
            ROOT / "src/esolangs/runtime" / slug,
            ROOT / "src/esolangs/generation" / slug,
        )
        if path.exists()
    ]

    if collisions:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in collisions)
        raise FileExistsError(f"refusing to overwrite {joined}")
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return list(files)


def _interpreter_stub(name: str) -> str:
    """Return ``_template.py`` named for ``name``, its maintainer comment dropped."""
    template = (ROOT / "src/esolangs/runtime/_template.py").read_text()
    _, doc, body = template.split('"""', 2)
    return '"""' + doc.replace("<Language>", name) + '"""' + body


@dataclass(frozen=True)
class Gap:
    """One missing integration point: where it goes and what to put there."""

    where: str
    fix: str


def _tests_module(module: str, attr: str) -> Container[str]:
    value: Container[str] = removal.tests_attr(module, attr)
    return value


def _source_file(base: Path) -> Path | None:
    """Return ``base.py``, else ``base/__init__.py``, whichever exists."""
    return next(
        (
            path
            for path in (base.with_suffix(".py"), base / "__init__.py")
            if path.exists()
        ),
        None,
    )


def _unregistered(name: str, slug: str) -> list[Gap]:
    package = ROOT / "src/esolangs/languages" / slug / "generator"
    generator = _source_file(package)
    if generator is None:
        return [
            Gap(
                "src/esolangs/registry/_table.py",
                f'add Language("{name}", "{slug}") to _INTERPRETER_ONLY; add '
                "split=True only if run() takes list[str], one string per line, "
                "and random=True if an instruction draws at random",
            )
        ]
    return [
        Gap(
            str(generator.relative_to(ROOT)),
            f'end it with LANGUAGE = Language("{name}", "{slug}", '
            f"boolean={slug}); add split=True only if run() takes list[str], "
            "one string per source line, and contract=BooleanContract(...) if "
            "its programs do not read one 0/1 line per input "
            "(docs/CONTRIBUTING.md#the-boolean-io-contract)",
        )
    ]


def _registered_generator(name: str) -> bool:
    """Whether ``name`` is registered with a Boolean generator."""
    from esolangs.registry import LANGUAGES

    lang = LANGUAGES.get(name)
    return lang is not None and lang.boolean is not None


def _common_gaps(name: str, module: str) -> list[Gap]:
    """List the steps every language needs, generator or not."""
    gaps = []
    base = ROOT / "src/esolangs/languages" / module / "interpreter"
    source = _source_file(base)
    if source is None:
        gaps.append(Gap(f"{base.relative_to(ROOT)}.py", "write the interpreter"))
    elif PLACEHOLDER in source.read_text(encoding="utf-8"):
        gaps.append(Gap(str(source.relative_to(ROOT)), "write the docstring"))
    needle = f"esolangs.languages.{module}.interpreter"
    tests = [
        path
        for path in (
            *((ROOT / "tests").rglob("*.py")),
            *((base.parent / "tests").rglob("*.py")),
        )
        if needle in path.read_text(encoding="utf-8")
    ]
    if not tests:
        gaps.append(
            Gap(
                f"src/esolangs/languages/{module}/tests/",
                f"add tests importing {needle}",
            )
        )
    gaps.extend(
        Gap(str(path.relative_to(ROOT)), "replace the placeholder test")
        for path in tests
        if "def test_placeholder_" in path.read_text(encoding="utf-8")
    )
    # tests/support/samples.py derives a generator language's sample itself.
    if not _registered_generator(name) and name not in _tests_module(
        "support.samples", "SAMPLES"
    ):
        gaps.append(
            Gap(
                "tests/support/samples.py",
                f'add "{name}": (<tiny program>, <stdin>) to SAMPLES; the VM '
                "protocol and debugger tests step it",
            )
        )
    if not _curation(name):
        gaps.append(
            Gap(
                f"src/esolangs/languages/{module}/language.toml",
                'add a [curation] section with backlinks = <wiki "What links '
                'here" count> (50+ is the fame route, fewer a first '
                "implementation), plus bf_derivative = true if the wiki tags it "
                "Brainfuck derivatives (see docs/limitations.md#curation); "
                "offline, unassessed = true until the count is recorded",
            )
        )
    return gaps


def _generator_gaps(lang: Language) -> list[Gap]:
    """List the steps a language with a Boolean generator needs."""
    from esolangs.generation.wrap import takes_width
    from esolangs.languages import generators

    assert lang.boolean is not None
    gen = lang.boolean.__name__
    module_rel = lang.boolean.__module__.replace(".", "/")
    base = ROOT / f"src/{module_rel}"
    source = _source_file(base) or base / "__init__.py"
    source_rel = str(source.relative_to(ROOT))
    gaps = []
    if source.exists() and PLACEHOLDER in source.read_text(encoding="utf-8"):
        gaps.append(Gap(source_rel, "write the docstring"))
    if source.exists() and "raise NotImplementedError(" in source.read_text(
        encoding="utf-8"
    ):
        gaps.append(
            Gap(
                source_rel,
                "implement the generator; tests/support/samples.py derives the "
                "language's VM sample from its one-input program",
            )
        )
    if gen not in generators.__all__:
        gaps.append(
            Gap(
                "src/esolangs/languages/generators.py",
                "declare the generator's LANGUAGE and run "
                "`python scripts/docs/generate.py docs` to regenerate the exports",
            )
        )
    width = takes_width(lang.boolean)
    if not width and lang.wrap is None and not lang.no_wrap:
        gaps.append(
            Gap(
                source_rel,
                "add wrap=wrap_chars (from esolangs.generation.wrap, or a wrapper "
                "its syntax needs, keeping a header such as `W,H:` whole) to "
                "its LANGUAGE, take a width parameter, or say why a break "
                'would change the program as no_wrap="..."',
            )
        )
    if width and lang.balance is None:
        gaps.append(
            Gap(
                source_rel,
                "add balance=_balance to its LANGUAGE: a "
                "`_balance(table, default)` returning the squarest of its "
                "width regimes (see src/esolangs/languages/arrowqueue/generator.py)",
            )
        )
    return gaps + _ledger_gaps(lang.name)


def _ledger_gaps(name: str) -> list[Gap]:
    """List the ledger row and the formula tests its stated bounds need."""
    rows, _ = _proof_status_load()
    row = next((item for item in rows if item.generator == name), None)
    toml = f"src/esolangs/languages/{_slug(name)}/language.toml"
    if row is None:
        return [
            Gap(
                toml,
                "add a [proof_status] section: "
                f"`just bounds {shlex.quote(name)}` measures the worst cases "
                "and prints one to paste; replace each FILL",
            )
        ]
    if "FILL" in repr(row):
        return [Gap(toml, "replace each FILL in [proof_status]")]
    if not row.execution.split(": ", 1)[-1].startswith(("worst ", "at most ")):
        return []
    gaps = []
    for cell in ("execution", "workspace"):
        stated = getattr(row, cell).split(": ", 1)[-1]
        table = f"test_{cell}_formulas"
        if cell == "workspace" and "bits" not in stated:
            continue
        if name not in _tests_module(f"proofs.{table}", "FORMULAS"):
            gaps.append(
                Gap(
                    f"tests/proofs/{table}.py",
                    f"the ledger's {cell} cell does not parse as a formula: "
                    f"{stated}; write its bound with n, T, L, integers, bl, "
                    "max, min, ⌈⌉ and ⌊⌋ before the unit (tests/proofs/"
                    f"_formula.py), or declare proof_{cell}=(callable, "
                    "exact, (lo, hi)) on the Language with the callable "
                    "in the package's proof_formulas.py (taglate is the "
                    "example)",
                )
            )
    return gaps


def check(name: str) -> list[Gap]:
    """Return every integration point ``name`` still lacks, in order."""
    from esolangs.registry import LANGUAGES, canonical_id

    lang = LANGUAGES.get(name)
    if lang is None:
        return _unregistered(name, canonical_id(name))
    gaps = _common_gaps(name, lang.interpreter or "")
    if lang.boolean is not None:
        gaps += _generator_gaps(lang)
    return gaps


def _escaped(nodes: list[str]) -> list[str]:
    r"""Return ``nodes`` with non-ASCII escaped, as pytest spells its ids.

    ``Forþ``'s ids read ``For\xfe``: unescaped, pytest found none of them.
    """
    return [node.encode("unicode_escape").decode("ascii") for node in nodes]


def quick_tests(name: str) -> list[str]:
    """Return the seconds-long tests that ``finish`` would otherwise fail late.

    The language's own files, the ledger's prose limits and fold measure,
    its formula rows at their smallest arity, and the docstring conventions.
    """
    from esolangs.registry import LANGUAGES, example_stems
    from esolangs.registry._language import Shape

    lang = LANGUAGES[name]
    nodes = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(
            (ROOT / "src/esolangs/languages" / lang.id / "tests").rglob("test_*.py")
        )
    ]
    nodes += [
        "tests/interpreters/test_interpreter_conventions.py"
        "::test_interpreter_docstrings_follow_the_template",
        "tests/interpreters/test_interpreters_robustness.py"
        f"::test_empty_program_terminates[{name}]",
        # Whole modules or functions: each runs the registry in ~1-4 s, and
        # Kiss/SwitchCase first failed all of these inside finish's
        # 250 s gate (2026-10-21).
        "tests/interpreters/test_spec_triggers.py",
        "tests/api/test_catalog_contracts.py::TestTheSpecIsReachable",
        "tests/interpreters/test_transition_purity.py"
        f"::test_interpreter_core_is_pure_for_its_sample[{name}]",
    ]
    if lang.boolean is None:
        return _escaped(nodes)
    nodes += [
        "tests/proofs/test_ledger.py",
        "tests/proofs/test_schemes.py",
        "tests/generators/test_boolean_sharing_catalogue.py",
        "tests/generators/test_generator_docstrings.py"
        "::test_the_size_anchor_is_what_generate_emits",
        "tests/generators/test_boolean_contract.py"
        "::test_every_table_reads_the_same_number_of_inputs",
        "tests/generators/test_boolean_canonical_catalogue.py"
        "::test_native_mechanisms_are_referenced",
        "tests/runtime/test_answer_plumbing.py::TestWhatHappensWhenAProgramIsUnderfed",
    ]
    catalogue = "tests/generators/test_boolean_canonical_catalogue.py::"
    folding = removal.tests_attr(
        "generators.test_boolean_canonical_catalogue", "_folding"
    )
    nodes.append(catalogue + "test_the_catalogue_covers_exactly_the_exceptions")
    if name not in folding("constant"):
        nodes.append(catalogue + f"test_a_constant_table_folds[{name}]")
    if name not in folding("ignored") | folding("ignored_read"):
        nodes.append(
            catalogue + f"test_an_ignored_input_costs_under_half_a_real_one[{name}]"
        )
    if lang.shape is not Shape.LOOKUP:
        # A tree generator must fold an input the table ignores.
        nodes.append(
            "tests/generators/test_boolean_contract.py"
            f"::test_generator_shape_is_what_the_catalogue_says[{name}]"
        )
    stem = example_stems().get(lang.id, "")
    if stem:
        nodes.append(f"tests/tooling/test_examples.py::test_boolean_example[{stem}]")
    if (
        stem
        in removal.tests_attr(
            "interpreters.test_input_convention", "_reading_languages"
        )()
    ):
        nodes.append(
            "tests/interpreters/test_input_convention.py"
            f"::test_running_out_of_input_reaches_the_caller[{stem}]"
        )
    arities = []
    for table in ("execution", "workspace"):
        formulas = removal.tests_attr(f"proofs.test_{table}_formulas", "FORMULAS")
        if name in formulas:
            arities.append(min(formulas[name][2]))
    if arities:
        nodes.append(
            "tests/proofs/test_workspace_formulas.py::"
            f"test_execution_and_workspace_formulas_hold[{name}-{min(arities)}]"
        )
    return _escaped(nodes)


def _dirty() -> set[str]:
    """Return the paths git reports as changed or untracked."""
    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line[3:] for line in status.splitlines()}


def sources(name: str) -> list[str]:
    """Return the language's interpreter and generator source paths."""
    from esolangs.registry import LANGUAGES

    lang = LANGUAGES[name]
    modules = [f"esolangs.languages.{lang.id}.interpreter"] if lang.interpreter else []
    if lang.boolean is not None:
        modules.append(lang.boolean.__module__)
    found = []
    for module in dict.fromkeys(modules):
        base = ROOT / "src" / module.replace(".", "/")
        # A module is ``base.py``; a package is its directory.
        found += [
            str(path.relative_to(ROOT))
            for path in (base.with_suffix(".py"), base)
            if path.is_file() or (path / "__init__.py").is_file()
        ]
    return found


def bounds(name: str, arities: range) -> list[tuple[int, int, int, int, str, str]]:
    """Return ``(n, worst steps, worst bits, size, steps' table, bits' table)``.

    Over the tables the formula tests use, so a stated bound that matches
    these is one they accept, and the tables are the witnesses a ``worst``
    bound needs.  Size is characters per table row: flat for an O(T)
    generator, growing for one that is not.
    """
    import esolangs

    tables = removal.tests_attr("proofs.test_execution_formulas", "_tables")
    measure = removal.tests_attr("proofs.test_execution_formulas", "_measure")
    rows = []
    for n in arities:
        worst = {t: measure(name, t, written=True) for t in tables(name, n)}
        size = max(len(str(esolangs.generate(name, t))) for t in tables(name, n))
        steps = max(worst, key=lambda t: worst[t][0])
        bits = max(worst, key=lambda t: worst[t][1])
        # Mean program size per row: ``size`` covers 2**n rows.
        rows.append((n, worst[steps][0], worst[bits][1], size >> n, steps, bits))
    return rows


#: Terms a fitted cell may combine, as the ledger's notation spells them.
_TERMS: dict[str, Callable[[int], int]] = {
    "T": lambda n: 2**n,
    "n^2": lambda n: n * n,
    "n": lambda n: n,
    "bl(n)": int.bit_length,
}
#: Fewest terms first, so the simplest exact formula wins.
_BASES = (
    ("n",),
    ("bl(n)",),
    ("T",),
    ("T", "n"),
    ("n", "bl(n)"),
    ("T", "bl(n)"),
    ("n^2", "n"),
    ("T", "n", "bl(n)"),
)


def _solve(rows: list[list[Fraction]], *, spare: bool = True) -> list[Fraction] | None:
    """Return the unique exact solution of the augmented ``rows``, or None.

    With ``spare``, None too when no row is left over to confirm it: k + 1
    unknowns fit any k + 1 points, so an exact fit is evidence only past that.
    """
    unknowns = len(rows[0]) - 1
    rows = [row[:] for row in rows]
    for col in range(unknowns):
        pivot = next((r for r in range(col, len(rows)) if rows[r][col]), None)
        if pivot is None:
            return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        rows[col] = [x / rows[col][col] for x in rows[col]]
        for r, row in enumerate(rows):
            if r != col and row[col]:
                rows[r] = [
                    x - row[col] * y for x, y in zip(row, rows[col], strict=True)
                ]
    if (spare and len(rows) == unknowns) or any(row[-1] for row in rows[unknowns:]):
        return None
    return [row[-1] for row in rows[:unknowns]]


def _spelled(terms: tuple[str, ...], coefficients: list[int]) -> str:
    """Return ``3T + n - 2`` for ``(T, n)`` and ``[3, 1, -2]``."""
    parts: list[str] = []
    for term, c in zip((*terms, ""), coefficients, strict=True):
        if not c:
            continue
        magnitude = f"{'' if abs(c) == 1 and term else abs(c)}{term}"
        sign = "-" if c < 0 else "+"
        parts.append(f"{sign} {magnitude}" if parts else f"{'-' * (c < 0)}{magnitude}")
    return " ".join(parts) or "0"


def _fit(values: list[tuple[int, int]], unit: str) -> str:
    """Return the simplest exact ``worst`` cell through ``values``, else FILL.

    Integer combinations of ``_TERMS`` plus a constant, from n = 3 (where
    the formula tests start), each confirmed by a point it was not solved
    from and re-read through the tests' own parser.
    """
    parse = removal.tests_attr("proofs._formula", "parse")
    values = [(n, v) for n, v in values if n >= 3]
    for terms in _BASES:
        rows = [
            [Fraction(_TERMS[t](n)) for t in terms] + [Fraction(1), Fraction(v)]
            for n, v in values
        ]
        solution = _solve(rows)
        # Determined without n = 3 too: over 3..6 bl(n) is 2, 3, 3, 3, a
        # free value at n = 3, and its 5 such fits on the ledger all missed
        # n = 7; the 47 that survive this held.
        if (
            solution is None
            or _solve(rows[1:], spare=False) is None
            or any(c.denominator != 1 for c in solution)
        ):
            continue
        coefficients = [int(c) for c in solution]
        clause = f"worst {_spelled(terms, coefficients)} {unit}"
        formula = parse(clause)[0]
        if all(formula(n, "") == v for n, v in values):
            grows = "T" in terms and coefficients[terms.index("T")]
            return f"{'linear' if grows else 'poly n'}: {clause}"
    return (
        f"FILL: at most <formula in n, T, L> {unit}"
        "  # more points (--max-n) fit more terms"
    )


def size_anchors(name: str) -> list[str]:
    """Return one line per ``Size:`` anchor in the generator's docstring.

    Each is re-measured as ``test_the_size_anchor_is_what_generate_emits``
    does; SwitchCase's went stale twice while being built.
    """
    import importlib
    import inspect

    import esolangs
    from esolangs.registry import LANGUAGES

    boolean = LANGUAGES[name].boolean
    if boolean is None:
        return []
    doc = inspect.cleandoc(importlib.import_module(boolean.__module__).__doc__ or "")
    sections = "generators.generator_sections"
    named_table = removal.tests_attr(sections, "named_table")
    lines = []
    for n, table, size, unit in removal.tests_attr(sections, "anchors")(doc):
        program = esolangs.generate(name, named_table(n, table))
        got = (
            len(program)
            if isinstance(program, (str, esolangs.CompressedText))
            else sum(len(row) for row in program.rows)
        )
        verdict = "ok" if got == size else f"STALE: emits {got:,}"
        lines.append(f"  n={n} {table}: {size:,} {unit}  {verdict}")
    return lines


def _print_bounds(name: str, max_n: int) -> None:
    """Print the worst cases per arity and the ledger cells they support."""
    # Steps feed the ledger's Execution cell, bits its Workspace cell
    # (peak written state); chars/row stays flat for an O(T) generator.
    rows = bounds(name, range(1, max_n + 1))
    print("n  Execution  Workspace  chars/row  witness tables (steps, bits)")
    for n, steps, bits, per_row, by_steps, by_bits in rows:
        print(f"{n:<2} {steps:>9}  {bits:>9}  {per_row:>9}  {by_steps} {by_bits}")
    print('"worst" must equal these columns from n = 3; otherwise write "at most"')
    print(
        "measured on the interpreter and generator as they stand: re-run after "
        "changing either, then just finish-language to refresh the example "
        "and [generator_sizes]"
    )
    if anchors := size_anchors(name):
        print("docstring Size: anchors", *anchors, sep="\n")
    cells = [
        f'execution = "{_fit([(r[0], r[1]) for r in rows], "commands")}"'
        "  # or steps, rewrites: the interpreter's unit",
        f'workspace = "{_fit([(r[0], r[2]) for r in rows], "bits")}"',
    ]
    rows_, _ = _proof_status_load()
    if any(row.generator == name for row in rows_):
        print("\n".join(cell for cell in cells if "FILL" not in cell))
        return
    ledger = "proofs._ledger"
    labels = sorted(removal.tests_attr(ledger, "SCHEME_LABELS").values())
    scaling = sorted(removal.tests_attr(ledger, "SCALING_CLASSES"))
    print(
        f"\n# append to src/esolangs/languages/{_slug(name)}/language.toml and "
        "replace each FILL;\n# docs/proofs/index.md defines the labels under "
        '"Proof schemes" and the ledger rows show the style',
        "[proof_status]",
        f'labels = ["FILL: {", ".join(labels)}"]  # plus "cap" or "exception"',
        'qualification = "FILL: how the program computes the table, one sentence"',
        f'scaling = "FILL: {" | ".join(scaling)}: in at most '
        f'{removal.tests_attr(ledger, "LINEAR_CLAUSE_WORDS")} words"',
        *cells,
        sep="\n",
    )


def finish(name: str) -> int:
    """Regenerate every committed artifact, then run the full gate.

    Several minutes on a laptop: run it in the background.
    """
    gaps = check(name)
    if gaps:
        _report(name, gaps)
        print("running the gate anyway, to list every other failure")
    gate = _gate()
    if _curation(name).get("unassessed"):
        print(
            f"{name}: curation unassessed; before merging, replace "
            "`unassessed = true` in its language.toml with backlinks = <the "
            'wiki\'s "What links here" count>'
        )
    return 1 if gaps else gate


def _curation(name: str) -> dict[str, Any]:
    """Return ``name``'s row in its package's curation section, or {}."""
    path = ROOT / "src/esolangs/languages" / _slug(name) / "language.toml"
    return _curation_fragment(path)


#: The gate's CI-only checks (MANUAL_ONLY); the
#: size baseline is left out because ``_gate`` has just re-recorded it.
#: Without them a green finish could still fail CI.
_CI_ONLY = (
    "generated docs",
    "dead definitions",
    "exception leaks",
    "deep proofs (verify band)",
)


def _ci_only() -> int:
    """Run the checks the gate leaves to CI; return the exit status."""
    cmd = ["scripts/verify/gate.py", "--quiet", "--only", ",".join(_CI_ONLY)]
    print("+", " ".join(cmd), flush=True)
    return subprocess.run([sys.executable, *cmd], cwd=ROOT, check=False).returncode


def _gate() -> int:
    """Regenerate, run the gate and CI's checks, and rerun failures alone."""
    python = [sys.executable]
    for cmd in (
        [*python, "scripts/docs/generate.py", "examples"],
        [*python, "scripts/docs/generate.py", "docs"],
        [*python, "checks/check_generator_sizes.py", "--update"],
    ):
        print("+", " ".join(cmd[1:]), flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
            return 1
    print("+ scripts/verify/gate.py --full --quiet", flush=True)
    failed = []
    with subprocess.Popen(
        [*python, "scripts/verify/gate.py", "--full", "--quiet"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as gate:
        assert gate.stdout is not None
        for line in gate.stdout:
            print(line, end="", flush=True)
            if line.startswith("FAILED "):
                failed.append(line[7:].split(" - ")[0].strip())
    if not gate.returncode:
        return _ci_only()
    if not failed:
        return 1  # not a pytest failure
    # A loaded machine pushes borderline tests past their duration band.
    # Rerunning only the failures, serially, separates those from real ones.
    # The ids come from this run's output: pytest's own --lf record can
    # hold tests since deleted, and then reruns the whole suite.
    print("+ rerunning the failed tests alone", flush=True)
    rerun = [*python, "-m", "pytest", "-q", "-n", "0", "-m", "", *failed]
    if subprocess.run(rerun, cwd=ROOT, check=False).returncode:
        return 1
    print(
        "every failed test passed alone: the failures were load, not the "
        "language; rerun the gate on a quiet machine before pushing"
    )
    return 0


def _registered_name(name: str) -> str:
    """Return ``name`` as the registry spells it, or unchanged if new.

    Raises :class:`UnknownLanguageError` for a never-started name close to a
    registered one: a typo otherwise reads as a new language, and ``check
    "Brainfuk"`` asked to register it in ``_INTERPRETER_ONLY``.
    """
    from esolangs.exceptions import UnknownLanguageError
    from esolangs.registry import canonical_id, resolve

    try:
        return resolve(name)
    except UnknownLanguageError as exc:
        started = (ROOT / "src/esolangs/languages" / canonical_id(name)).exists()
        if exc.suggestions and not started:
            raise
        return name


def _report(name: str, gaps: list[Gap]) -> None:
    print(f"{name}: {len(gaps)} step(s) left")
    for gap in gaps:
        print(f"- {gap.where}: {gap.fix}")
    print(f"after fixing these: just check-language {shlex.quote(name)}")


def _regenerate() -> bool:
    """Refresh the tested generated totals and examples; False on failure."""
    before = _dirty()
    for target in ("examples", "docs"):
        regenerate = ["scripts/docs/generate.py", target]
        if subprocess.run(
            [sys.executable, *regenerate],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
        ).returncode:
            # Its own error is above; a CalledProcessError trace buried it.
            print(f"regenerating failed; rerun: python {' '.join(regenerate)}")
            return False
    for changed in sorted(_dirty() - before):
        print(f"regenerated {changed}")
    return True


def main(argv: list[str] | None = None) -> int:
    """Dispatch ``start``, ``check``, ``finish`` or ``remove``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="write the stubs")
    start.add_argument("name")
    start.add_argument("--category", choices=CATEGORIES, help="asked if omitted")
    start.add_argument(
        "--interpreter-only",
        action="store_true",
        help="no generator: only for a famous language whose spec precludes one",
    )
    for command in ("check", "finish", "remove"):
        sub.add_parser(command).add_argument("name")
    measure = sub.add_parser("bounds", help="worst steps and bits per arity")
    measure.add_argument("name")
    measure.add_argument("--max-n", type=int, default=6)
    args = parser.parse_args(argv)
    if args.command in {"check", "finish", "bounds", "remove"}:
        # A new LANGUAGE is registered by the export this writes, but
        # docs.generate imports the package first, so its registry predates
        # the export: rerun on the new one.  The first check after `start`
        # otherwise asked for the LANGUAGE the stub already had, and `remove`
        # of a stub never checked raised KeyError.
        sys.path.insert(0, str(ROOT / "scripts"))
        from docs.generate import update_exports

        if update_exports(ROOT, ROOT):
            os.execv(sys.executable, [sys.executable, __file__, *argv])
        try:
            args.name = _registered_name(args.name)
        except ValueError as exc:
            if args.command == "remove":
                parser.error(str(exc))
            parser.error(f"{exc}; a new one starts with: just new-language")
    if args.command == "bounds":
        try:
            _print_bounds(args.name, args.max_n)
        except NotImplementedError:
            print(f"{args.name}: implement the generator first", file=sys.stderr)
            return 1
        return 0
    if args.command == "check":
        gaps = check(args.name)
        if gaps:
            # A to-do list, not a failure: nonzero is for failing tests.
            _report(args.name, gaps)
            return 0
        if not _regenerate():
            return 1
        quick = [sys.executable, "-m", "pytest", "-q", "-n", "0", "-m", ""]
        tests = quick_tests(args.name)
        print("+ pytest", " ".join(tests), flush=True)
        failed = subprocess.run([*quick, *tests], cwd=ROOT)
        if failed.returncode:
            print(f"{args.name}: integrated, but fix the failures above first")
            return 1
        print(
            f"{args.name}: integrated; next: "
            f"just finish-language {shlex.quote(args.name)}"
        )
        return 0
    if args.command == "finish":
        return finish(args.name)
    if args.command == "remove":
        try:
            leftover = removal.remove(args.name)
        except ValueError as exc:
            parser.error(str(exc))
        except KeyError:
            parser.error(f"{args.name} is not registered; nothing to remove")
        print(f"removed {args.name}; {len(leftover)} mention(s) to review")
        print("\n".join(leftover))
        return 0
    args.category = args.category or _ask_category()
    if args.category is None:
        parser.error(f"--category is one of:\n{_category_menu()}")
    try:
        paths = scaffold(args.name, args.category, generator=not args.interpreter_only)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    for path in paths:
        print(f"created {path.relative_to(ROOT)}")
    implementation = (
        "interpreter" if args.interpreter_only else "interpreter and generator"
    )
    print(f"next: implement the {implementation} in the created source files")
    print("conventions: docs/CONTRIBUTING.md#interpreter-conventions")
    # Registration happens there, not here: until then `bounds`, `esolangs`
    # and the registry raise UnknownLanguageError for the new name.
    print(f"then: just check-language {shlex.quote(args.name)} (registers it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
