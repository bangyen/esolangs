"""Start, check, or finish a new language.

    python scripts/new_language.py start "Name" --category tape_based
    python scripts/new_language.py check "Name"     # what is still missing
    python scripts/new_language.py finish "Name"    # regenerate, then verify
    python scripts/new_language.py remove "Name"    # the inverse of all three
    python scripts/new_language.py bounds "Name"    # worst steps/bits per n

``start`` writes the interpreter, generator and test stubs.  ``check`` lists
every integration point the language still lacks, with the file and entry
to add; ``tests/scripts/test_new_language.py`` runs it over the registry,
so the list cannot drift from what the suite enforces.  Once the list is
empty it runs the seconds-long tests ``finish`` would otherwise fail late.
``bounds`` measures what the proof ledger's cells state.  ``finish``
regenerates every committed artifact and runs the full ``verify.py`` gate.
``remove`` deletes what ``check`` asks for, regenerates, and lists the
mentions left in prose for a hand edit.  The bare ``"Name" --category ...``
form still means ``start``.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import itertools
import json
import keyword
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Container
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[1]
CATEGORIES = tuple(
    sorted(
        path.name
        for path in (ROOT / "src/esolangs/interpreters").iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    )
)
COMMANDS = ("start", "check", "finish", "remove", "bounds")


def _slug(name: str) -> str:
    """Return the registry's id for ``name``, refused unless importable."""
    from esolangs.registry import canonical_id

    slug = canonical_id(name)
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

_GENERATOR = '''"""Boolean program generator for {name}.

<describe the construction: how a node reads its input, branches, and
answers, and the size and build bound (O(T) for a decision tree)>
"""

from esolangs.registry._language import Language
from esolangs.tools.helpers import _validate_truth_table


def {slug}(truth_table: str) -> str:
    """Build a {name} program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    raise NotImplementedError("{name} generator")


# The registry entry.  Add split=True if run() takes one string per source
# line, contract=BooleanContract(...) if the programs do not read one 0/1
# line per input (docs/CONTRIBUTING.md#the-boolean-io-contract), and
# wrap=wrap_chars (esolangs.tools.wrap) if a newline anywhere is harmless,
# else no_wrap="<why a break changes the program>"; eof="..." if an
# exhausted read has a spec value, empty_program="..." if "" is rejected;
# a generator taking a width needs balance=, picking its squarest regime;
# example=Example(pair=PAIR, expected=...) for a template or an answer that
# is not a printed 0/1.
LANGUAGE = Language("{name}", "{category}.{slug}", boolean={slug})
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
        assert got == table[row], (table, row)
'''


def scaffold(name: str, category: str, *, generator: bool = True) -> list[Path]:
    """Create and return the interpreter, generator and test stubs."""
    slug = _slug(name)
    files = {
        ROOT / "src/esolangs/interpreters" / category / f"{slug}.py": (
            _interpreter_stub(name)
        ),
        ROOT / "tests" / "interpreters" / f"test_{slug}.py": (
            f'"""Tests for the {name} interpreter."""\n\n'
            "import pytest\n\n"
            f"from esolangs.interpreters.{category}.{slug} import run\n"
            "from esolangs.interpreters.io import ScriptedIO\n\n\n"
            '@pytest.mark.xfail(reason="placeholder: replace with the spec")\n'
            "def test_placeholder_increment_and_write() -> None:\n"
            "    io = ScriptedIO()\n"
            '    run("+.", io)\n'
            '    assert io.getvalue() == "\\x01"\n'
        ),
    }
    if generator:
        fields = {"name": name, "slug": slug, "category": category}
        files[ROOT / "src" / "esolangs" / "tools" / f"{slug}.py"] = _GENERATOR.format(
            **fields
        )
        files[ROOT / "tests" / "tools" / f"test_boolean_{slug}.py"] = (
            _GENERATOR_TEST.format(**fields)
        )
    collisions = [path for path in files if path.exists()]
    if collisions:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in collisions)
        raise FileExistsError(f"refusing to overwrite {joined}")
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return list(files)


def _interpreter_stub(name: str) -> str:
    template = (ROOT / "src/esolangs/interpreters/_template.py").read_text()
    body = template.split('"""', 2)[2]
    return (
        f'"""Interpreter for {name}.\n\n{PLACEHOLDER} the machine from the wiki '
        "page: memory, pointer, commands>\n\nA malformed program raises "
        ":class:`ValueError`;\nexhausted input raises :class:`EOFError`.\n"
        '"""' + body
    )


@dataclass(frozen=True)
class Gap:
    """One missing integration point: where it goes and what to put there."""

    where: str
    fix: str


def _tests_attr(module: str, attr: str) -> Any:
    """Read ``attr`` from ``tests.<module>``, which needs the repo on the path."""
    sys.path.insert(0, str(ROOT))
    try:
        return getattr(importlib.import_module(f"tests.{module}"), attr)
    finally:
        sys.path.remove(str(ROOT))


def _tests_module(module: str, attr: str) -> Container[str]:
    value: Container[str] = _tests_attr(module, attr)
    return value


def _unregistered(name: str, slug: str) -> list[Gap]:
    found = sorted((ROOT / "src/esolangs/interpreters").glob(f"*/{slug}.py"))
    module = f"{found[0].parent.name}.{slug}" if found else f"<category>.{slug}"
    generator = ROOT / f"src/esolangs/tools/{slug}.py"
    if not generator.exists():
        return [
            Gap(
                "src/esolangs/registry/_table.py",
                f'add Language("{name}", "{module}") to _INTERPRETER_ONLY; add '
                "split=True only if run() takes list[str], one string per line",
            )
        ]
    return [
        Gap(
            str(generator.relative_to(ROOT)),
            f'end it with LANGUAGE = Language("{name}", "{module}", '
            f"boolean={slug}); add split=True only if run() takes list[str], "
            "one string per source line, and contract=BooleanContract(...) if "
            "its programs do not read one 0/1 line per input "
            "(docs/CONTRIBUTING.md#the-boolean-io-contract)",
        )
    ]


def _common_gaps(name: str, module: str) -> list[Gap]:
    """List the steps every language needs, generator or not."""
    gaps = []
    base = ROOT / "src/esolangs/interpreters" / module.replace(".", "/")
    source = next(
        (p for p in (base.with_suffix(".py"), base / "__init__.py") if p.exists()),
        None,
    )
    if source is None:
        gaps.append(Gap(f"{base.relative_to(ROOT)}.py", "write the interpreter"))
    elif PLACEHOLDER in source.read_text(encoding="utf-8"):
        gaps.append(Gap(str(source.relative_to(ROOT)), "write the docstring"))
    needle = f"esolangs.interpreters.{module}"
    tests = [
        path
        for path in (ROOT / "tests").rglob("*.py")
        if needle in path.read_text(encoding="utf-8")
    ]
    if not tests:
        gaps.append(Gap("tests/interpreters/", f"add tests importing {needle}"))
    gaps.extend(
        Gap(str(path.relative_to(ROOT)), "replace the placeholder test")
        for path in tests
        if "def test_placeholder_" in path.read_text(encoding="utf-8")
    )
    if name not in _tests_module("samples", "SAMPLES"):
        gaps.append(
            Gap(
                "tests/samples.py",
                f'add "{name}": (<tiny program>, <stdin>) to SAMPLES; the VM '
                "protocol and debugger tests step it (a generator language "
                "gets its own one-input program once the generator runs)",
            )
        )
    curation = tomllib.loads((ROOT / "tests/fixtures/curation.toml").read_text())
    if name not in curation["languages"]:
        gaps.append(
            Gap(
                "tests/fixtures/curation.toml",
                f'add "{name}" = {{ backlinks = <wiki "What links here" count>, '
                'route = "fame" | "first implementation" }} under [languages] (see '
                'docs/limitations.md#curation); offline, {{ route = "unassessed" }} '
                "until the count is recorded",
            )
        )
    return gaps


def _generator_gaps(lang: Language) -> list[Gap]:
    """List the steps a language with a Boolean generator needs."""
    from esolangs import tools
    from esolangs.tools.wrap import takes_width

    assert lang.boolean is not None
    gen = lang.boolean.__name__
    gaps = []
    source = ROOT / f"src/esolangs/tools/{gen}.py"
    if source.exists() and PLACEHOLDER in source.read_text(encoding="utf-8"):
        gaps.append(Gap(str(source.relative_to(ROOT)), "write the docstring"))
    if gen not in tools.__all__:
        gaps.append(
            Gap(
                "src/esolangs/tools/__init__.py",
                f'add `from esolangs.tools.{gen} import {gen}` and "{gen}" to __all__',
            )
        )
    width = takes_width(lang.boolean)
    if not width and lang.wrap is None and not lang.no_wrap:
        gen_module = lang.boolean.__module__.replace(".", "/")
        gaps.append(
            Gap(
                f"src/{gen_module}.py",
                "add wrap=wrap_chars (from esolangs.tools.wrap, or a wrapper "
                "its syntax needs, keeping a header such as `W,H:` whole) to "
                "its LANGUAGE, take a width parameter, or say why a break "
                'would change the program as no_wrap="..."',
            )
        )
    if width and lang.balance is None:
        gen_module = lang.boolean.__module__.replace(".", "/")
        gaps.append(
            Gap(
                f"src/{gen_module}.py",
                "add balance=_balance to its LANGUAGE: a "
                "`_balance(table, default)` returning the squarest of its "
                "width regimes (see tools/arrowqueue.py)",
            )
        )
    return gaps + _ledger_gaps(lang.name)


def _ledger_gaps(name: str) -> list[Gap]:
    """List the ledger row and the formula tests its stated bounds need."""
    data = tomllib.loads((ROOT / "src/esolangs/proof_status.toml").read_text())
    row = next((row for row in data["ledger"] if row["generator"] == name), None)
    if row is None:
        return [
            Gap(
                "src/esolangs/proof_status.toml",
                f'add a [[ledger]] block: generator = "{name}", labels = ["tree"], '
                "qualification, scaling, execution, workspace and evidence = "
                '"docs/proofs/index.md#generator-ledger"; copy a block with the '
                "same construction and see Symbols in docs/proofs/index.md; "
                'each cell is "<class>: <clause>", e.g. "linear: ..." or '
                '"poly n: worst 7n + 3 commands ..."; '
                "a clause after `worst`/`at most` takes at most "
                f"{_tests_attr('proofs._ledger', 'FORMULA_CLAUSE_WORDS')} words, "
                f"any other {_tests_attr('proofs._ledger', 'LINEAR_CLAUSE_WORDS')}; "
                f"`python scripts/new_language.py bounds {name!r}` measures the "
                "worst steps and bits to state",
            )
        ]
    if not row["execution"].split(": ", 1)[-1].startswith(("worst ", "at most ")):
        return []
    gaps = []
    for cell in ("execution", "workspace"):
        stated = row[cell].split(": ", 1)[-1]
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
                    f'_formula.py), or add "{name}": (lambda n, _: ..., '
                    "exact, (lo, hi)) to _HAND for a case split or definition",
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


def quick_tests(name: str) -> list[str]:
    """Return the seconds-long tests that ``finish`` would otherwise fail late.

    The language's own files, the ledger's prose limits and fold measure,
    its formula rows at their smallest arity, and the docstring conventions.
    """
    from esolangs.registry import LANGUAGES, example_stems

    lang = LANGUAGES[name]
    nodes = [
        path
        for path in (
            f"tests/interpreters/test_{lang.id}.py",
            f"tests/tools/test_boolean_{lang.id}.py",
        )
        if (ROOT / path).exists()
    ]
    nodes += [
        "tests/test_interpreter_conventions.py"
        "::test_interpreter_docstrings_follow_the_template",
        f"tests/fuzz/test_interpreters_robustness.py"
        f"::test_empty_program_terminates[{name}]",
    ]
    if lang.boolean is None:
        return nodes
    nodes += ["tests/proofs/test_ledger.py", "tests/proofs/test_schemes.py"]
    stem = example_stems().get(lang.id, "")
    if (
        stem
        in _tests_attr("interpreters.test_input_convention", "_reading_languages")()
    ):
        nodes.append(
            "tests/interpreters/test_input_convention.py"
            f"::test_running_out_of_input_reaches_the_caller[{stem}]"
        )
    arities = [
        min(formulas[name][2])
        for table in ("execution", "workspace")
        for formulas in (_tests_attr(f"proofs.test_{table}_formulas", "FORMULAS"),)
        if name in formulas
    ]
    if arities:
        nodes.append(
            "tests/proofs/test_workspace_formulas.py::"
            f"test_execution_and_workspace_formulas_hold[{name}-{min(arities)}]"
        )
    return nodes


def bounds(name: str, arities: range) -> list[tuple[int, int, int, int]]:
    """Return ``(n, worst steps, worst written bits, largest size)`` per arity.

    Over the tables the formula tests use, so a stated bound that matches
    these is one they accept.  Size is characters per table row: flat for
    an O(T) generator, growing for one that is not.
    """
    import esolangs

    tables = _tests_attr("proofs.test_execution_formulas", "_tables")
    measure = _tests_attr("proofs.test_execution_formulas", "_measure")
    rows = []
    for n in arities:
        worst = [measure(name, table, written=True) for table in tables(name, n)]
        size = max(len(str(esolangs.generate(name, t))) for t in tables(name, n))
        rows.append((n, max(s for s, _ in worst), max(b for _, b in worst), size >> n))
    return rows


def finish(name: str) -> int:
    """Regenerate every committed artifact, then run the full gate.

    Several minutes on a laptop: run it in the background.
    """
    gaps = check(name)
    if gaps:
        _report(name, gaps)
        print("running the gate anyway, to list every other failure")
    gate = _gate()
    if _curation(name).get("route") == "unassessed":
        print(f"{name}: curation unassessed; record its backlinks before merging")
    return 1 if gaps else gate


def _curation(name: str) -> dict[str, Any]:
    """Return ``name``'s row in the curation fixture, or {}."""
    text = (ROOT / "tests/fixtures/curation.toml").read_text(encoding="utf-8")
    return dict(tomllib.loads(text)["languages"].get(name, {}))


def _gate() -> int:
    """Regenerate, run the gate, and rerun its failures alone."""
    python = [sys.executable]
    for cmd in (
        [*python, "scripts/generate.py", "examples"],
        [*python, "scripts/generate.py", "docs"],
        [*python, "scripts/check_generator_sizes.py", "--update"],
    ):
        print("+", " ".join(cmd[1:]), flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
            return 1
    print("+ scripts/verify.py --quiet", flush=True)
    failed = []
    with subprocess.Popen(
        [*python, "scripts/verify.py", "--quiet"],
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
        return 0
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


def _whole_statement(
    node: ast.AST, named: Callable[[ast.AST | None], bool], modules: set[str]
) -> bool:
    """Whether ``node`` is a statement that exists only for the language.

    ``X["Name"] = ...``, ``run_x = _runner("module")``, and an import from
    the language's own interpreter or generator module.
    """
    if isinstance(node, ast.ImportFrom):
        return node.module in modules
    if not isinstance(node, ast.Assign):
        return False
    if any(isinstance(t, ast.Subscript) and named(t.slice) for t in node.targets):
        return True
    call = node.value
    return isinstance(call, ast.Call) and [*map(named, call.args)] == [True]


def _drop_entries(path: Path, keys: set[str], modules: set[str]) -> int:
    """Delete every dict entry, list item or ``X[key] = ...`` keyed by ``keys``.

    Located by AST and cut by line, so an entry must own its lines; one
    sharing a line with another is left for the leftover report.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []

    def named(node: ast.AST | None) -> bool:
        return isinstance(node, ast.Constant) and node.value in keys

    def own(first: ast.expr, last: ast.expr) -> None:
        """Take an entry's lines only if nothing else shares them."""
        before = lines[first.lineno - 1][: first.col_offset]
        after = lines[last.end_lineno - 1][last.end_col_offset :]  # type: ignore[operator]
        if not before.strip() and after.strip() in {"", ","}:
            lo, hi = first.lineno, last.end_lineno or last.lineno
            # Its comment goes too, unless a sibling below still sits under it.
            following = lines[hi].strip() if hi < len(lines) else ""
            if not following or following[0] in "#)]}":
                while lo > 1 and lines[lo - 2].strip().startswith("#"):
                    lo -= 1
            spans.append((lo, hi))

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if key is not None and named(key):
                    own(key, value)
        elif isinstance(node, ast.List | ast.Set | ast.Tuple):
            for item in node.elts:
                # A bare key, or a ``Language("Name", ...)`` naming it.
                first = (
                    item.args[0] if isinstance(item, ast.Call) and item.args else None
                )
                if named(item) or named(first):
                    own(item, item)
        elif isinstance(node, ast.stmt) and _whole_statement(node, named, modules):
            spans.append((node.lineno, node.end_lineno or node.lineno))
    # An import another language still uses stays (Cyclic tag reuses BCT's
    # PAIR); judged on the source with every other cut already made.
    imports = {
        (node.lineno, node.end_lineno or node.lineno): node
        for node in ast.parse(source).body
        if isinstance(node, ast.ImportFrom)
    }
    kept = [*lines]
    for lo, hi in sorted(set(spans), reverse=True):
        del kept[lo - 1 : hi]
    used = {
        node.id
        for node in ast.walk(ast.parse("".join(kept)))
        if isinstance(node, ast.Name)
    }
    spans = [
        span
        for span in spans
        if span not in imports
        or not {a.asname or a.name for a in imports[span].names} & used
    ]
    for lo, hi in sorted(set(spans), reverse=True):
        del lines[lo - 1 : hi]
    if spans:
        path.write_text("".join(lines), encoding="utf-8")
    return len(spans)


def _drop_json(path: Path, prune: Callable[[object], object]) -> None:
    """Rewrite ``path`` through ``prune``, keeping its indent and escaping."""
    text = path.read_text(encoding="utf-8")
    indent = len(text.split("\n", 2)[1]) - len(text.split("\n", 2)[1].lstrip())
    pruned = prune(json.loads(text))
    out = json.dumps(pruned, indent=indent, ensure_ascii=text.isascii())
    path.write_text(out + "\n" * text.endswith("\n"), encoding="utf-8")


def _drop_toml(path: Path, name: str) -> None:
    """Drop ``name``'s ``[[...]]`` block and ``"name" = ...`` lines from ``path``.

    Text, not a parse and rewrite, so the file's comments and folding stay.
    """
    text = path.read_text(encoding="utf-8")
    # Each block runs from its header to the next; the head has none.
    blocks = re.split(r"\n(?=\[)", text)
    kept = []
    for block in blocks:
        if (
            block.startswith("[[")
            and tomllib.loads(block.split("\n", 1)[1]).get("generator") == name
        ):
            continue
        lines = block.split("\n")
        kept.append(
            "\n".join(
                line
                for line in lines
                if not re.match(
                    rf"({re.escape(json.dumps(name))}|{re.escape(name)}) =", line
                )
            )
        )
    path.write_text("\n".join(kept), encoding="utf-8")


def _drop_bullets(path: Path, name: str) -> None:
    """Drop each ``- name ...`` bullet, with its indented lines, from ``path``."""
    text = path.read_text(encoding="utf-8")
    bullet = rf"(?m)^- {re.escape(name)}\b.*\n(?:  .*\n)*"
    path.write_text(re.sub(bullet, "", text), encoding="utf-8")


def remove(name: str) -> list[str]:
    """Delete ``name`` everywhere ``check`` looks; return the leftover mentions."""
    from esolangs.registry import LANGUAGES, example_stems

    lang = LANGUAGES[name]
    module = lang.interpreter or ""
    gen = lang.boolean.__name__ if lang.boolean else lang.id
    stem = example_stems().get(lang.id, "")
    doomed = [
        ROOT / "src/esolangs/interpreters" / f"{module.replace('.', '/')}.py",
        ROOT / f"src/esolangs/tools/{gen}.py",
        ROOT / f"tests/interpreters/test_{lang.id}.py",
        ROOT / f"tests/tools/test_boolean_{gen}.py",
        ROOT / f"tests/fixtures/wiki_examples/{lang.id}.toml",
        *(ROOT / "src/esolangs/examples").glob(f"{stem}.*" if stem else "-"),
    ]
    # ``git rm``, not unlink: tests read ``git ls-files``, which would still
    # list a file deleted only from disk.
    subprocess.run(
        ["git", "rm", "-q", "-r", "--ignore-unmatch", *map(str, doomed)],
        cwd=ROOT,
        check=True,
    )
    keys = {name, module, lang.id, gen, stem} - {""}
    modules = {f"esolangs.interpreters.{module}", f"esolangs.tools.{gen}"}
    for relative in (
        "src/esolangs/registry/_table.py",
        "src/esolangs/tools/__init__.py",
        "tests/samples.py",
        "tests/tools/boolean_runners.py",
        "tests/tools/test_wrap.py",
        "tests/proofs/test_execution_formulas.py",
        "tests/proofs/test_workspace_formulas.py",
        "tests/proofs/test_schemes.py",
    ):
        _drop_entries(ROOT / relative, keys, modules)

    def prune(node: object) -> object:
        if isinstance(node, dict):
            return {k: prune(v) for k, v in node.items() if k != name}
        if isinstance(node, list):
            return [
                prune(item)
                for item in node
                if not (isinstance(item, dict) and item.get("generator") == name)
            ]
        return node

    _drop_json(ROOT / "tests/fixtures/generator_sizes.json", prune)
    for relative in ("tests/fixtures/curation.toml", "src/esolangs/proof_status.toml"):
        _drop_toml(ROOT / relative, name)
    _drop_bullets(ROOT / "docs/limitations.md", name)
    kept = []
    for module_name in sorted(modules):
        users = subprocess.run(
            ["git", "grep", "-l", "-F", f"from {module_name} import", "--", "*.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        path = f"src/{module_name.replace('.', '/')}.py"
        if users and (ROOT / path).parent.exists():
            # Another language imports from it: restore it rather than break.
            subprocess.run(
                ["git", "checkout", "HEAD", "--", path], cwd=ROOT, check=True
            )
            kept.append(f"{path}: kept, still imported by {', '.join(users)}")
    for target in ("docs", "examples"):
        subprocess.run(
            [sys.executable, "scripts/generate.py", target],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    grep = subprocess.run(
        ["git", "grep", "-n", "-I", "-w", "-e", name, "-e", lang.id, "-e", module],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return kept + grep.stdout.splitlines()


def _report(name: str, gaps: list[Gap]) -> None:
    print(f"{name}: {len(gaps)} step(s) left")
    for gap in gaps:
        print(f"- {gap.where}: {gap.fix}")
    print(f"rerun: python scripts/new_language.py check {name!r}")


def main(argv: list[str] | None = None) -> int:
    """Dispatch ``start``, ``check``, ``finish`` or ``remove``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        argv.insert(0, "start")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="write the stubs")
    start.add_argument("name")
    start.add_argument("--category", choices=CATEGORIES, required=True)
    start.add_argument(
        "--interpreter-only",
        action="store_true",
        help="no generator: only for a famous language whose spec precludes one",
    )
    for command in ("check", "finish", "remove"):
        sub.add_parser(command).add_argument("name")
    measure = sub.add_parser("bounds", help="worst steps and bits per arity")
    measure.add_argument("name")
    measure.add_argument("--max-n", type=int, default=5)
    args = parser.parse_args(argv)
    if args.command == "bounds":
        print("n  worst steps  worst bits  chars/row")
        rows = bounds(args.name, range(1, args.max_n + 1))
        for n, steps, bits, per_row in rows:
            print(f"{n:<2} {steps:>11}  {bits:>10}  {per_row:>9}")
        for column, label in ((1, "steps"), (2, "bits")):
            slopes = {b[column] - a[column] for a, b in itertools.pairwise(rows)}
            if len(slopes) == 1:
                (slope,) = slopes
                base = rows[0][column] - slope * rows[0][0]
                print(f"{label} fit exactly: lambda n, _: {slope} * n + {base}")
        return 0
    if args.command in {"check", "finish"}:
        # Before anything imports the package: a new LANGUAGE is registered
        # by the export this writes.
        sys.path.insert(0, str(ROOT / "scripts"))
        from generate_exports import update as update_exports

        update_exports(ROOT, ROOT)
    if args.command == "check":
        gaps = check(args.name)
        if gaps:
            # A to-do list, not a failure: nonzero is for failing tests.
            _report(args.name, gaps)
            return 0
        # Generated totals (the ledger's row count) are tested; refresh them.
        subprocess.run(
            [sys.executable, "scripts/generate.py", "docs"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        quick = [sys.executable, "-m", "pytest", "-q", "-n", "0", "-m", ""]
        print("+ pytest", " ".join(quick_tests(args.name)), flush=True)
        if subprocess.run([*quick, *quick_tests(args.name)], cwd=ROOT).returncode:
            print(f"{args.name}: integrated, but fix the failures above first")
            return 1
        print(
            f"{args.name}: integrated; next: "
            f"python scripts/new_language.py finish {args.name!r}"
        )
        return 0
    if args.command == "finish":
        return finish(args.name)
    if args.command == "remove":
        leftover = remove(args.name)
        print(f"removed {args.name}; {len(leftover)} mention(s) left to edit by hand")
        print("\n".join(leftover))
        return 0
    try:
        paths = scaffold(args.name, args.category, generator=not args.interpreter_only)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    for path in paths:
        print(f"created {path.relative_to(ROOT)}")
    print(
        "next: implement the interpreter (see docs/CONTRIBUTING.md#interpreter-"
        "conventions) and generator, then run "
        f"`python scripts/new_language.py check {args.name!r}` for the rest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
