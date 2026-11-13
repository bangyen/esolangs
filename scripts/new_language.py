"""Start, check, or finish a new language.

    python scripts/new_language.py start "Name" --category tape_based
    python scripts/new_language.py check "Name"     # what is still missing
    python scripts/new_language.py finish "Name"    # regenerate, then verify
    python scripts/new_language.py bounds "Name"    # worst steps/bits per n

``start`` writes the interpreter, generator and test stubs.  ``check`` lists
every integration point the language still lacks, with the file and entry
to add; ``tests/tooling/test_new_language.py`` runs it over the registry,
so the list cannot drift from what the suite enforces.  Once the list is
empty it runs the seconds-long tests ``finish`` would otherwise fail late.
``bounds`` measures resource maxima and their witnesses.
``finish`` regenerates every committed artifact and runs the full
``verify/gate.py`` gate.
"""

from __future__ import annotations

import argparse
import importlib
import keyword
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[1]
# Support direct execution and imports of the development tools.
sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from docs.catalogue import load as _catalogue_load  # noqa: E402
from docs.curation import FAME_BACKLINKS  # noqa: E402
from docs.curation import fragment_row as _curation_fragment  # noqa: E402
from docs.proof_status import load as _proof_status_load  # noqa: E402

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

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def {slug}(truth_table: str) -> str:
    """Build a {name} program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    raise NotImplementedError("{name} generator")


def {slug}_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return {slug}(request.table)


'''

_DESCRIPTOR = '''"""Runtime and compiler capabilities for {name}."""

from esolangs.registry._language import Language
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._operations import OperationRef
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "{name}", RuntimeSpec(
        "{slug}", category="{category}",
        machine_preparation="prepare_machine", completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            completion=Completion.HALTED, debug=DebugSpec(ip="ind")
        ),
    ),
    backend=BooleanBackend(entrypoint=OperationRef[GenerationRequest, Program](
        "esolangs.languages.{slug}.generator", "{slug}_request"
    )),
)
'''

_INTERPRETER_DESCRIPTOR = '''"""Runtime capabilities for {name}."""

from esolangs.registry._language import Language
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language("{name}", RuntimeSpec(
        "{slug}", category="{category}",
        machine_preparation="prepare_machine", completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            completion=Completion.HALTED, debug=DebugSpec(ip="ind")
        ),
    ))
'''

_GENERATOR_TEST = '''"""Tests for the {name} Boolean generator."""

import esolangs
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        n = len(table).bit_length() - 1
        program = esolangs.generate("{name}", table)
        for row in range(len(table)):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            stdin = esolangs.encode_inputs("{name}", bits)
            got = esolangs.run("{name}", program, stdin=stdin, timeout=5).output
            # The answer as the contract reads it, not the raw output.
            assert esolangs.read_answer("{name}", got) == table[row], (table, row)
'''


def scaffold(name: str, category: str, *, generator: bool = True) -> list[Path]:
    """Create and return the interpreter, generator and test stubs."""
    slug = _slug(name)
    package = ROOT / "src/esolangs/languages" / slug
    fields = {"name": name, "slug": slug, "category": category}
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
    files[package / "descriptor.py"] = (
        _DESCRIPTOR if generator else _INTERPRETER_DESCRIPTOR
    ).format(**fields)
    if generator:
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
    descriptor = f"src/esolangs/languages/{slug}/descriptor.py"
    return [
        Gap(
            descriptor,
            f'declare LANGUAGE = Language("{name}", '
            f'runtime=RuntimeSpec("{slug}", ...)) with explicit '
            "machine_preparation, completion_entrypoint and capabilities; "
            "add a BooleanBackend with an OperationRef entrypoint for a generator, "
            "source_policy=LineSourcePolicy() only when run() takes source lines, "
            "and the Boolean I/O contract; "
            "run `python scripts/docs/generate.py docs` to refresh documentation",
        )
    ]


def _registered_generator(name: str) -> bool:
    """Whether ``name`` is registered with a Boolean generator."""
    from esolangs.registry import LANGUAGES

    lang = LANGUAGES.get(name)
    return lang is not None and lang.backend is not None


def _template(section_name: str) -> str:
    """Point at the reference language's filled-in ``section_name`` to copy."""
    from esolangs.registry import LANGUAGES
    from tests.support.reference import REFERENCE

    path = f"src/esolangs/languages/{LANGUAGES[REFERENCE].id}/language.toml"
    return f"; copy its [{section_name}] section from {path} and edit it"


def _workspace_row(name: str) -> list[Gap]:
    """The workspace ledger row the runtime tests require of every language."""
    import csv

    ledger = ROOT / "tests/runtime/workspace_models.csv"
    if not ledger.exists():  # a scaffold-only tree, as the tooling tests build
        return []
    with ledger.open(encoding="utf-8") as source:
        if any(row["language"] == name for row in csv.DictReader(source)):
            return []
    backend = "yes" if _registered_generator(name) else "no"
    return [
        Gap(
            str(ledger.relative_to(ROOT)),
            f"add the row {name},{backend},owned-adapter,<model>: <model> is the "
            "name its interpreter passes to workspace_model(...), and "
            "inherited-adapter replaces owned-adapter if it reuses another "
            "language's",
        )
    ]


def _common_gaps(name: str, module: str) -> list[Gap]:
    """List the steps every language needs, generator or not."""
    gaps = []
    base = ROOT / "src/esolangs/languages" / module / "interpreter"
    source = _source_file(base)
    if source is None:
        gaps.append(Gap(f"{base.relative_to(ROOT)}.py", "write the interpreter"))
    elif PLACEHOLDER in source.read_text(encoding="utf-8"):
        gaps.append(Gap(str(source.relative_to(ROOT)), "write the docstring"))
    elif not hasattr(
        importlib.import_module(f"esolangs.languages.{module}.interpreter"),
        "_Machine",
    ):
        gaps.append(
            Gap(
                str(source.relative_to(ROOT)),
                "expose the stepping machine as _Machine (an interpreter that "
                "reuses another's subclasses or aliases it); the runtime and "
                "lifecycle tests step it",
            )
        )
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
    if (
        not _registered_generator(name)
        and name not in importlib.import_module("tests.support.samples").SAMPLES
    ):
        gaps.append(
            Gap(
                "tests/support/samples.py",
                f'add "{name}": (<tiny program>, <stdin>) to SAMPLES; the VM '
                "protocol and debugger tests step it",
            )
        )
    row = _curation(name)
    if not row:
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
    elif (
        "admitted" not in row and row.get("backlinks", FAME_BACKLINKS) < FAME_BACKLINKS
    ):
        gaps.append(
            Gap(
                f"src/esolangs/languages/{module}/language.toml",
                "a first implementation records admitted = <the admitting "
                "commit's offset datetime> in [curation], and any outside "
                "implementation as outside_implementation = { date, source }",
            )
        )
    return gaps + _workspace_row(name)


def _generator_gaps(lang: Language) -> list[Gap]:
    """List the steps a language with a Boolean generator needs."""
    from docs.ablations import parse_audits
    from docs.evidence import parse_anchors
    from docs.fragments import section

    assert lang.backend is not None
    module_rel = lang.backend.generate.__module__.replace(".", "/")
    base = ROOT / f"src/{module_rel}"
    source = _source_file(base) or base / "__init__.py"
    source_rel = str(source.relative_to(ROOT))
    gaps = []
    metadata = ROOT / f"src/esolangs/languages/{lang.id}/language.toml"
    try:
        parse_anchors(lang.name, section(metadata, "evidence") or {})
    except (ValueError, FileNotFoundError) as error:
        gaps.append(
            Gap(
                str(metadata.relative_to(ROOT)),
                f"record source evidence: {error}{_template('evidence')}",
            )
        )
    try:
        parse_audits(lang.name, "ablations", section(metadata, "ablations") or {})
    except (ValueError, FileNotFoundError) as error:
        gaps.append(
            Gap(
                str(metadata.relative_to(ROOT)),
                f"record measured audit evidence: {error}{_template('ablations')}",
            )
        )
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
    width = lang.backend.layout_width
    if not width and lang.backend.wrap is None and not lang.backend.no_wrap:
        gaps.append(
            Gap(
                source_rel,
                "add wrap=wrap_chars (from esolangs.generation.wrap, or a wrapper "
                "its syntax needs, keeping a header such as `W,H:` whole) to "
                "its LANGUAGE, take a width parameter, or say why a break "
                'would change the program as no_wrap="..."',
            )
        )
    if width and lang.backend.balance is None:
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
    try:
        rows, _ = _proof_status_load()
    except ValueError as error:
        return [
            Gap(
                f"src/esolangs/languages/{_slug(name)}/language.toml",
                f"complete resource evidence before rendering proof status: {error}",
            )
        ]
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
    from docs.fragments import section
    from docs.resource_evidence import parse_bounds

    try:
        parse_bounds(name, section(ROOT / toml, "resource_evidence") or {})
    except (ValueError, FileNotFoundError, ImportError) as error:
        return [Gap(toml, f"record resource evidence: {error}")]
    return []


def check(name: str) -> list[Gap]:
    """Return every integration point ``name`` still lacks, in order."""
    from esolangs.registry import LANGUAGES, canonical_id

    lang = LANGUAGES.get(name)
    if lang is None:
        return _unregistered(name, canonical_id(name))
    gaps = _common_gaps(name, lang.runtime.interpreter or "")
    from docs.semantic import load as semantic_evidence

    try:
        semantic_evidence(name)
    except (ValueError, FileNotFoundError) as error:
        gaps.append(
            Gap(
                f"src/esolangs/languages/{lang.id}/language.toml",
                "record bounded independent semantic checks: "
                f"{error}{_template('semantic_evidence')}",
            )
        )
    if lang.backend is not None:
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
    from esolangs.registry._backend import Shape

    lang = LANGUAGES[name]
    nodes = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(
            (ROOT / "src/esolangs/languages" / lang.id / "tests").rglob("test_*.py")
        )
    ]
    nodes += [
        f"tests/generators/test_ablation_evidence.py::test_audit_evidence[{name}]",
        f"tests/interpreters/test_semantic_admission.py::test_semantic_evidence[{name}]",
        "tests/interpreters/test_interpreter_conventions.py"
        "::test_interpreter_docstrings_follow_the_template",
        "tests/interpreters/test_interpreters_robustness.py"
        f"::test_empty_program_terminates[{name}]",
        # Whole modules or functions: each runs the registry in ~1-4 s, and
        # Kiss/Sonata/SwitchCase first failed all of these inside finish's
        # 250 s gate (2026-10-21).
        "tests/interpreters/test_spec_triggers.py",
        "tests/api/test_language_coupling.py::test_no_file_cites_another_language",
        "tests/api/test_catalog_contracts.py::TestTheSpecIsReachable",
        "tests/interpreters/test_transition_purity.py"
        f"::test_interpreter_core_is_pure_for_its_sample[{name}]",
    ]
    if lang.backend is None:
        return _escaped(nodes)
    nodes += [
        "tests/proofs/test_ledger.py",
        "tests/proofs/test_schemes.py",
        "tests/generators/test_boolean_sharing_catalogue.py",
        "tests/generators/test_generator_docstrings.py"
        "::test_the_size_anchor_is_what_generate_emits",
        "tests/generators/test_boolean_canonical_catalogue.py"
        "::test_native_mechanisms_are_referenced",
        "tests/runtime/test_answer_plumbing.py::TestWhatHappensWhenAProgramIsUnderfed",
    ]
    if not lang.parameterized:
        nodes.append(
            "tests/generators/test_reads_every_input.py"
            f"::test_every_input_is_read[{name}-{{}}]"
        )
    catalogue = "tests/generators/test_boolean_canonical_catalogue.py::"
    folding = _catalogue_load()["folding"]
    nodes.append(catalogue + "test_the_catalogue_covers_exactly_the_exceptions")
    if name not in set(folding["constant"]):
        nodes.append(catalogue + f"test_a_constant_table_folds[{name}]")
    if name not in set(folding["ignored"]) | set(folding["ignored_read"]):
        nodes.append(
            catalogue + f"test_an_ignored_input_costs_under_half_a_real_one[{name}]"
        )
    if lang.backend.shape is not Shape.LOOKUP:
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
        in importlib.import_module("tests.support.input_convention").reading_languages()
    ):
        nodes.append(
            "tests/interpreters/test_input_convention.py"
            f"::test_running_out_of_input_reaches_the_caller[{stem}]"
        )
    arities = []
    for table in ("execution", "workspace"):
        formulas = importlib.import_module(f"tests.proofs.{table}").FORMULAS
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
    modules = (
        [f"esolangs.languages.{lang.id}.interpreter"]
        if lang.runtime.interpreter
        else []
    )
    if lang.backend is not None:
        modules.append(lang.backend.generate.__module__)
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
    bound needs. Size is characters or raster pixels per table row: flat for an O(T)
    generator, growing for one that is not.
    """
    from source_units import source_units

    import esolangs

    measurement = importlib.import_module("tests.proofs.measurement")
    tables, measure = measurement.tables, measurement.measure
    rows = []
    for n in arities:
        worst = {t: measure(name, t, written=True) for t in tables(name, n)}
        size = max(
            source_units(esolangs.generate(name, t).source) for t in tables(name, n)
        )
        steps = max(worst, key=lambda t: worst[t][0])
        bits = max(worst, key=lambda t: worst[t][1])
        # Mean program size per row: ``size`` covers 2**n rows.
        rows.append((n, worst[steps][0], worst[bits][1], size >> n, steps, bits))
    return rows


def size_anchors(name: str) -> list[str]:
    """Return one line per ``Size:`` anchor in the generator's docstring.

    Each is re-measured as ``test_the_size_anchor_is_what_generate_emits``
    does; Sonata's and SwitchCase's went stale twice while being built.
    """
    from docs.evidence import source_anchors

    import esolangs
    from esolangs.registry import LANGUAGES

    backend = LANGUAGES[name].backend
    if backend is None:
        return []
    lines = []
    try:
        anchors = source_anchors(name)
    except (KeyError, FileNotFoundError):
        return []
    for anchor in anchors:
        program = esolangs.generate(name, anchor.witness.table()).source
        got = (
            len(program)
            if isinstance(program, (str, esolangs.CompressedText))
            else sum(len(row) for row in program.rows)
        )
        verdict = "ok" if got == anchor.size else f"STALE: emits {got:,}"
        lines.append(f"  {anchor.text}  {verdict}")
    return lines


def _print_bounds(name: str, max_n: int) -> None:
    """Print measured resource maxima, witnesses and size anchors."""
    import esolangs

    # Steps feed the ledger's Execution cell, bits its Workspace cell
    # (peak written state); chars/row stays flat for an O(T) generator.
    rows = bounds(name, range(1, max_n + 1))
    units = "pixels" if esolangs.describe(name)["source_kind"] == "raster" else "chars"
    print(f"n  Execution  Workspace  {units}/row  witness tables (steps, bits)")
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
    """Regenerate, then run the full gate and CI-only checks."""
    python = [sys.executable]
    for cmd in (
        [*python, "scripts/docs/generate.py", "examples"],
        [*python, "scripts/docs/generate.py", "docs"],
        [*python, "checks/check_generator_sizes.py", "--update"],
    ):
        print("+", " ".join(cmd[1:]), flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
            return 1
    cmd = [*python, "scripts/verify/gate.py", "--full", "--quiet"]
    print("+", " ".join(cmd[1:]), flush=True)
    if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
        return 1
    return _ci_only()


def _registered_name(name: str) -> str:
    """Return ``name`` as the registry spells it, or unchanged if new.

    Raises :class:`UnknownLanguageError` for a never-started name close to a
    registered one: a typo must not be treated as a new language.
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


def _lint(name: str) -> bool:
    """Run ruff over the language's package, as ``finish``'s pre-commit will."""
    package = f"src/esolangs/languages/{_slug(name)}"
    for args in (["check"], ["format", "--check"]):
        cmd = [sys.executable, "-m", "ruff", *args, package]
        print("+ ruff", " ".join(args), package, flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
            print(f"{name}: fix the lint above (`ruff format {package}` formats)")
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Dispatch ``start``, ``check``, ``finish`` or ``bounds``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="write the stubs")
    start.add_argument("name")
    start.add_argument("--category", choices=CATEGORIES, required=True)
    start.add_argument(
        "--interpreter-only",
        action="store_true",
        help="no generator: only for a famous language whose spec precludes one",
    )
    for command in ("check", "finish"):
        sub.add_parser(command).add_argument("name")
    measure = sub.add_parser("bounds", help="worst steps and bits per arity")
    measure.add_argument("name")
    measure.add_argument("--max-n", type=int, default=6)
    args = parser.parse_args(argv)
    if args.command in {"check", "finish", "bounds"}:
        try:
            args.name = _registered_name(args.name)
        except ValueError as exc:
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
        if not _lint(args.name):
            return 1
        quick = [sys.executable, "-m", "pytest", "-q", "-n", "0", "-m", ""]
        tests = quick_tests(args.name)
        print("+ pytest", " ".join(tests), flush=True)
        failed = subprocess.run([*quick, *tests], cwd=ROOT, check=False)
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
