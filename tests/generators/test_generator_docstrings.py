"""Every generator docstring follows the template, and its claims run.

Each ``Size:`` anchor is regenerated and measured; each ``Raises:`` entry is
rendered from ``[[evidence.raises]]`` in ``language.toml``, whose ``table`` (a
string or an anchor's ``n=14 parity``) must raise it, or whose
``untriggerable`` gives the reason no call reaches it.
"""

import ast
import io
import pathlib
import re
import tokenize
import tomllib

import pytest

import esolangs
from esolangs import exceptions
from esolangs.registry import LANGUAGES
from scripts.docs.ablations import load as load_ablations
from scripts.docs.evidence import (
    GeneratorRaise,
    generator_raises,
    source_anchors,
    update_source_anchors,
)
from scripts.new_language import _GENERATOR, PLACEHOLDER
from tests.generators.generator_sections import (
    SECTIONS,
    anchors,
    figures,
    measured,
    named_table,
)
from tests.interpreters.spec_sections import headers, section

pytestmark = pytest.mark.medium

_LANGUAGES_DIR = pathlib.Path(esolangs.__file__).parent / "languages"


def _generated() -> list[str]:
    """Return every language with a Boolean generator, sorted."""
    return sorted(name for name, lang in LANGUAGES.items() if lang.backend)


def _files(name: str) -> list[pathlib.Path]:
    """Return the generator's files, its docstring's module first."""
    root = _LANGUAGES_DIR / LANGUAGES[name].id
    if (root / "generator.py").exists():
        return [root / "generator.py"]
    package = root / "generator"
    return [package / "__init__.py", *sorted(package.rglob("[!_]*.py"))]


def _doc(name: str) -> str:
    return ast.get_docstring(ast.parse(_files(name)[0].read_text())) or ""


def _capped(name: str) -> bool:
    """Whether the registry or the code says the generator can refuse a table."""
    lang = LANGUAGES[name]
    source = "".join(path.read_text() for path in _files(name))
    return bool(
        lang.backend.max_inputs
        or lang.backend.restrictions
        or "GeneratorCapError" in source
    )


def _doc_issues(doc: str) -> list[str]:
    """Return violations of the generator template."""
    issues = []
    found = headers(doc)
    names = [name for _, name in found]
    if unknown := [name for name in names if name not in SECTIONS]:
        issues.append(f"sections outside the template: {unknown}")
    known = [name for name in names if name in SECTIONS]
    if known != sorted(set(known), key=SECTIONS.index):
        issues.append(f"sections out of order or repeated: {known}")
    lines = doc.splitlines()
    for i, name in found:
        if i + 1 >= len(lines) or not lines[i + 1].startswith("    "):
            issues.append(f"{name}: body is not indented")
    if found and found[0][0] < 2:
        issues.append("no construction prose before the sections")
    if not anchors(doc):
        issues.append("Size: gives no measured anchor (n=8 parity: 1,186 chars)")
    if PLACEHOLDER in doc:
        issues.append("template placeholder left in")
    return issues


_GOOD = "A.\n\nB.\n\nSize:\n    O(T); n=2 parity: 9 chars"


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        (_GOOD + "\n\nNotes:\n    x", "outside the template"),
        (_GOOD + "\n\nDecisions:\n    x\n\nRaises:\n    ArgumentError: y", "order"),
        ("A.\n\nSize:\nn=2 parity: 9 chars", "not indented"),
        ("A.\nSize:\n    n=2 parity: 9 chars", "no construction prose"),
        ("A.\n\nSize:\n    O(T), about 9 chars", "no measured anchor"),
        (_GOOD + "\n\nDecisions:\n    <describe x>", "placeholder"),
    ],
)
def test_the_docstring_check_catches_each_violation(doc: str, expected: str) -> None:
    """Positive control: each rule fires on a docstring that breaks it."""
    assert any(expected in issue for issue in _doc_issues(doc))


def test_the_docstring_check_passes_the_template_shape() -> None:
    """Negative control: a conforming docstring raises nothing."""
    doc = _GOOD + "\n\nRaises:\n    GeneratorCapError: x\n\nDecisions:\n    y"
    assert _doc_issues(doc) == []


def test_the_stub_is_the_template() -> None:
    """``new_language.py``'s stub fails only for what a writer must fill in."""
    stub = _GENERATOR.format(name="X", slug="x", category="c")
    issues = _doc_issues(ast.get_docstring(ast.parse(stub)) or "")
    assert [issue.split(" ")[0] for issue in issues] == ["Size:", "template"]


def test_generator_docstrings_follow_the_template() -> None:
    """Every registered generator's module docstring is checked."""
    failures = {name: _doc_issues(_doc(name)) for name in _generated()}
    assert {name: issues for name, issues in failures.items() if issues} == {}
    # A generator that can refuse a table declares the refusal it raises.
    undeclared = [
        name
        for name in _generated()
        if _capped(name)
        and "GeneratorCapError" not in {r.error for r in generator_raises(name)}
    ]
    assert undeclared == []
    # Rendered ``Size:`` figures and ``Raises:`` entries match their records.
    assert not update_source_anchors(check=True), "run `just docs`"
    for name in _generated():
        text = " ".join(" ".join(section(_doc(name), "Size")).split()).replace(",", "")
        for anchor in source_anchors(name):
            assert anchor.text.replace(",", "") in text, (name, anchor.text)


def _notes(source: str) -> list[tuple[int, str]]:
    """Return ``(line, text)`` for each function/class docstring and comment."""
    found = [
        (node.lineno, doc)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and (doc := ast.get_docstring(node))
    ]
    found += [
        (tok.start[0], tok.string)
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT
    ]
    return found


def _repeats(module_doc: str, sources: dict[str, str]) -> list[str]:
    """Return ``path:line figure`` for each module-docstring figure said again."""
    told = measured(module_doc)
    return sorted(
        f"{path}:{line} {figure}"
        for path, source in sources.items()
        for line, text in _notes(source)
        for figure in figures(text) & told
    )


def test_the_repeat_check_catches_a_figure_said_twice() -> None:
    """Positive control, and a short integer or other figure does not count."""
    source = 'def f():\n    """Saves 9.61% at n=10."""\n    # 1,186 chars\n'
    assert _repeats("A.\n\nDecisions:\n    9.61%, 1186 chars", {"g.py": source}) == [
        "g.py:1 9.61%",
        "g.py:3 1186",
    ]
    assert _repeats("A.\n\nSize:\n    n=10, 7.5%", {"g.py": source}) == []
    # An anchor's size, a prose constant and the 10% bar are not restatements.
    assert (
        _repeats("A 9.61% prose.\n\nSize:\n    n=2 and: 1,186 chars", {"g.py": source})
        == []
    )
    assert measured("A.\n\nDecisions:\n    10% bar, 4.8%") == {"4.8%"}


def test_a_module_docstring_figure_is_said_once() -> None:
    """A measurement lives in one place, so an update cannot miss its twin."""
    repeats = {}
    for name in _generated():
        root = _LANGUAGES_DIR / LANGUAGES[name].id
        paths = (
            [root / "generator.py"]
            if (root / "generator.py").exists()
            else [*sorted((root / "generator").rglob("*.py"))]
        )
        sources = {
            path.relative_to(root).as_posix(): path.read_text() for path in paths
        }
        if found := _repeats(_doc(name), sources):
            repeats[name] = found
    # A bare dict compare truncates in pytest's diff; list every hit.
    assert repeats == {}, (
        "the module docstring states these figures; drop the repeat at "
        f"each path:line -- {repeats}"
    )


_SAVING = re.compile(r"\d+\.\d+%")
_CITED = re.compile(r"\[ablations\.(\w+)\]")


def _ablation_repeats(verdicts: dict[str, str], sources: dict[str, str]) -> list[str]:
    """Return ``path:line figure`` for each nonzero verdict saving said again.

    A citation names a key that is not in ``verdicts`` reports as ``key?``.
    """
    told = {
        figure
        for verdict in verdicts.values()
        for figure in _SAVING.findall(verdict)
        if float(figure[:-1])
    }
    found = []
    for path, source in sources.items():
        doc = ast.get_docstring(ast.parse(source))
        for line, text in [*_notes(source), *([(1, doc)] if doc else [])]:
            found += [f"{path}:{line} {f}" for f in set(_SAVING.findall(text)) & told]
            found += [
                f"{path}:{line} {key}?"
                for key in _CITED.findall(text)
                if key not in verdicts
            ]
    return sorted(found)


def test_the_ablation_check_catches_a_saving_said_twice() -> None:
    """Positive control; a zero saving and a cited key do not count."""
    source = (
        '"""Saves 9.61%."""\n# 0.0% here; see [ablations.fold]\n# [ablations.gone]\n'
    )
    assert _ablation_repeats(
        {"fold": "kept: 9.61%, 0.0% on AND"}, {"g.py": source}
    ) == [
        "g.py:1 9.61%",
        "g.py:3 gone?",
    ]


def test_an_ablation_saving_is_said_once() -> None:
    """A source line cites ``[ablations.<key>]`` instead of restating its figure."""
    repeats = {}
    for name in _generated():
        root = _LANGUAGES_DIR / LANGUAGES[name].id
        audit = load_ablations(name)
        assert audit is not None
        verdicts = {key: entry.verdict for key, entry in audit.records.items()}
        sources = {
            path.relative_to(root).as_posix(): path.read_text() for path in _files(name)
        }
        # A figure that matches a verdict but measures something else.
        distinct = set(audit.unrelated)
        if found := [
            f
            for f in _ablation_repeats(verdicts, sources)
            if f.split()[1] not in distinct
        ]:
            repeats[name] = found
    assert repeats == {}, (
        "cite [ablations.<key>] at each path:line instead of restating its "
        f"saving ('key?' is a citation of an unknown key) -- {repeats}"
    )


def _size(program: esolangs.Program) -> tuple[int, str]:
    """Return the emitted size as ``scripts/benchmark.py`` counts it."""
    if isinstance(program, (str, esolangs.CompressedText)):
        return len(program), "chars"
    return sum(len(row) for row in program.rows), "codels"


_ANCHORS = [
    (name, anchor.witness.arity, anchor.witness.name, anchor.size, anchor.unit)
    for name in _generated()
    for anchor in source_anchors(name)
]


@pytest.mark.parametrize(
    ("name", "n", "table", "size", "unit"),
    _ANCHORS,
    ids=[f"{a[0]}-n{a[1]}-{a[2]}" for a in _ANCHORS],
)
def test_the_size_anchor_is_what_generate_emits(
    name: str, n: int, table: str, size: int, unit: str
) -> None:
    """A documented size is regenerated, so an optimization must update it."""
    # Both raster names count emitted color cells at the generator's default scale.
    measured_unit = "codels" if unit == "pixels" else unit
    assert _size(esolangs.generate(name, named_table(n, table)).source) == (
        size,
        measured_unit,
    )


def test_the_named_tables_are_the_functions_they_name() -> None:
    """Positive control for the anchor vocabulary, MSB-first rows."""
    assert [named_table(2, t) for t in ("parity", "and", "or", "majority", "zero")] == [
        "0110",
        "0001",
        "0111",
        "0001",
        "0000",
    ]
    assert named_table(3, "majority") == "00010111"
    assert len(named_table(4, "random 7")) == 16
    assert anchors("A.\n\nSize:\n    n=2 parity: 4 pixels") == [
        (2, "parity", 4, "pixels")
    ]
    from scripts.docs.evidence import SourceAnchor, TableWitness, render_source_anchors

    anchor = SourceAnchor(TableWitness(2, "parity"), 9, "chars", "control")
    source = '"""A.\n\nSize:\n    n=2 parity: 4 chars\n"""\nvalue = 4\n'
    rendered = render_source_anchors(source, (anchor,))
    assert rendered == source.replace("parity: 4 chars", "parity: 9 chars")
    assert render_source_anchors(rendered, (anchor,)) == rendered
    for broken in (
        source.replace("n=2", "n=3"),
        source.replace("4 chars", "4 chars; n=2 parity: 4 chars"),
        "value = 4\n",
    ):
        with pytest.raises(ValueError, match="anchor"):
            render_source_anchors(broken, (anchor,))
    from scripts.docs.evidence import parse_anchors
    from tests.support.reference import REFERENCE

    language = LANGUAGES[REFERENCE]
    data = tomllib.loads((_LANGUAGES_DIR / language.id / "language.toml").read_text())[
        "evidence"
    ]
    assert parse_anchors(REFERENCE, data) == source_anchors(REFERENCE)
    base = data["anchors"][0]
    for changes in (
        {"arity": True},
        {"arity": 0},
        {"rule": "unknown"},
        {"rule": "random", "seed": True},
        {"rule": "parity", "seed": 7},
        {"size": -1},
        {"size": True},
        {"unit": "bytes"},
        {"unit": "pixels"},
        {"scale": 2},
        {"construction": "other:generate"},
        {"unexpected": 0},
    ):
        with pytest.raises(ValueError, match=r"witness|anchor|evidence|schema"):
            parse_anchors(REFERENCE, {"version": 1, "anchors": [base | changes]})
    for broken in (
        {"version": True, "anchors": [base]},
        {"version": 2, "anchors": [base]},
        {"version": 1, "anchors": []},
        {"version": 1, "anchors": [base, base]},
        {
            "version": 1,
            "anchors": [
                {k: v for k, v in (base | {"rule": "random"}).items() if k != "seed"}
            ],
        },
    ):
        with pytest.raises(ValueError, match=r"witness|anchor|evidence|schema"):
            parse_anchors(REFERENCE, broken)
    from scripts.docs.evidence import parse_raises, render_raises

    good = {"error": "GeneratorCapError", "when": "x", "table": "0110"}
    assert parse_raises([good]) == (GeneratorRaise("GeneratorCapError", "x", "0110"),)
    for rows in (
        {},
        [good, good],
        [good | {"error": "ValueError"}],
        [good | {"when": " "}],
        [good | {"untriggerable": "y"}],
        [{k: v for k, v in good.items() if k != "table"}],
        [good | {"unexpected": "z"}],
    ):
        with pytest.raises(ValueError, match="raise"):
            parse_raises(rows)
    declared = parse_raises([good])
    with pytest.raises(ValueError, match="Raises: section"):
        render_raises('"""A.\n\nSize:\n    y\n"""\n', declared)
    with pytest.raises(ValueError, match="declared raises"):
        render_raises('"""A.\n\nRaises:\n    GeneratorCapError: y\n"""\n', ())
    assert (
        render_raises('"""A.\n\nRaises:\n    ArgumentError: old\n"""\n', declared)
        == '"""A.\n\nRaises:\n    GeneratorCapError: x\n"""\n'
    )


def _table(spec: str) -> str:
    """Return a trigger's table: literal, or an anchor's ``n=14 parity``."""
    if m := re.fullmatch(r"n=(\d+) (.+)", spec):
        return named_table(int(m[1]), m[2])
    return spec


_TRIGGERS = [
    (name, declared)
    for name in _generated()
    for declared in generator_raises(name)
    if declared.table is not None
]


@pytest.mark.parametrize(
    ("name", "declared"),
    _TRIGGERS,
    ids=[f"{name}-{d.error}" for name, d in _TRIGGERS],
)
def test_the_declared_table_raises_what_the_docstring_says(
    name: str, declared: GeneratorRaise
) -> None:
    """The declared exception is what ``generate`` raises on its table."""
    assert declared.table is not None
    with pytest.raises(getattr(exceptions, declared.error)):
        esolangs.generate(name, _table(declared.table))
