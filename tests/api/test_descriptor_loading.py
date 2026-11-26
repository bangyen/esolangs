"""Catalog operations leave implementations unloaded until selected."""

import dataclasses
import inspect
import json
import subprocess
import sys

import pytest

import esolangs
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import TemplateLayout
from esolangs.generation.wrap import wrap_chars
from esolangs.registry import LANGUAGES, _functions
from esolangs.registry._backend import TemplateSpec
from esolangs.registry._certification import load as load_certification
from esolangs.registry._functions import FunctionRef
from esolangs.registry._operations import OperationRef
from tests.support.reference import REFERENCE


@pytest.mark.medium
def test_catalog_does_not_import_generators():
    code = """
import esolangs, json, sys, typing
assert 'esolangs.registry' not in sys.modules
from esolangs._dialect import DialectSchema
schema = DialectSchema('detached_scope', {'mode': ('a', 'b')}, {'mode': 'a'})
settings = esolangs.DialectSettings(schema, mode='b')
values = [
    esolangs.ProgramArtifact('', 'detached_scope', settings=settings),
    esolangs.Raster((((0, 0, 0),),)),
    esolangs.CompressedText.from_chunks(['x']),
    esolangs.TemplateArtifact('$', 'detached_scope',
        esolangs.TemplateBindings(setters=(('0','1'),)), spans=((0,1),)),
]
assert values[-1].fill([1]).source == '1'
for value in values:
    typing.get_type_hints(type(value))
assert 'esolangs.registry' not in sys.modules, 'value model loaded the catalog'
from esolangs.generation import examples
assert 'esolangs.registry._table' not in sys.modules, 'examples loaded the catalog'
assert 'BOOLEAN_EXAMPLES' not in vars(examples), 'example import built the index'
names = esolangs.list_languages()
assert 'esolangs.registry._table' in sys.modules, 'catalog control did not fire'
for name in names:
    esolangs.describe(name)
    esolangs.Language(name).settings().options()
def loaded():
    return sorted(m for m in sys.modules
                  if m.startswith("esolangs.languages.") and ".generator" in m)
assert examples.BOOLEAN_EXAMPLES, 'example index did not build on access'
assert examples.BOOLEAN_EXAMPLES is vars(examples)['BOOLEAN_EXAMPLES']
assert not loaded(), loaded()
esolangs.generate(sys.argv[1], "01")
assert loaded(), "positive control did not load a generator"
print(json.dumps(names))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, REFERENCE],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(completed.stdout) == sorted(LANGUAGES)


def test_declared_callable_parameters_match_implementations():
    def check(value):
        if isinstance(value, OperationRef):
            assert not hasattr(value, "parameters")
            assert tuple(inspect.signature(value.load()).parameters) == ("request",)
        elif isinstance(value, FunctionRef):
            assert not hasattr(value, "__signature__")
            target = value.load()
            assert callable(target)
            assert tuple(inspect.signature(target).parameters) == value.parameters, (
                value
            )
        elif dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                check(getattr(value, field.name))

    for language in LANGUAGES.values():
        check(language)
        check(load_certification(language))


def test_callable_references_observe_mutation(monkeypatch):
    reference = LANGUAGES[REFERENCE].backend.entrypoint
    assert isinstance(reference, OperationRef)
    original = reference.load()
    module = sys.modules[reference.module]
    monkeypatch.setattr(module, reference.name, lambda _table: "fault")
    assert reference(GenerationRequest("01")) == "fault"
    monkeypatch.setattr(module, reference.name, original)
    assert reference.load() is original


@pytest.mark.parametrize(
    ("field", "reference", "options", "message"),
    [
        ("entrypoint", OperationRef("esolangs", "_missing"), {}, r"esolangs\._missing"),
        ("balance", OperationRef("esolangs", "__all__"), {"balance": True}, "callable"),
        ("wrap", FunctionRef("esolangs", "__all__"), {"width": 1}, "callable"),
        ("entrypoint", OperationRef("esolangs.absent", "emit"), {}, "esolangs.absent"),
    ],
)
def test_scoped_generator_hooks_raise_program_errors(
    field, reference, options, message
) -> None:
    record = LANGUAGES[REFERENCE]
    backend = dataclasses.replace(record.backend, **{field: reference})
    bound = esolangs.Catalog([dataclasses.replace(record, backend=backend)]).bind(
        REFERENCE
    )
    with pytest.raises(esolangs.ProgramError, match=message):
        bound.generate("01", **options)


@pytest.mark.parametrize(
    ("hook", "table", "options"),
    [
        ("entrypoint", "01", {}),
        ("wrap", "01", {"width": 1}),
        ("wrap", "01", {"balance": True}),
        ("wrap_balance", "01", {"balance": True}),
        ("balance", "01", {"balance": True}),
        ("arity_guard", "0110", {}),
    ],
)
@pytest.mark.parametrize("declared", [False, True])
def test_generation_hooks_share_typed_value_errors(hook, table, options, declared):
    original = LANGUAGES[REFERENCE]
    fault = (
        esolangs.TemplateError("backend refused request")
        if declared
        else ValueError("backend refused request")
    )

    def refuse(*_args):
        raise fault

    backend = dataclasses.replace(original.backend, max_inputs=1, **{hook: refuse})
    bound = esolangs.Catalog([dataclasses.replace(original, backend=backend)]).bind(
        REFERENCE
    )
    error = esolangs.TemplateError if declared else esolangs.ArgumentError
    with pytest.raises(error, match="backend refused request") as caught:
        bound.generate(table, **options)
    assert (caught.value if declared else caught.value.__cause__) is fault


def test_plain_reflow_keeps_the_declared_source_kind() -> None:
    original = LANGUAGES[REFERENCE]
    backend = dataclasses.replace(
        original.backend, wrap=lambda *_args: esolangs.Raster((((0, 0, 0),),))
    )
    bound = esolangs.Catalog([dataclasses.replace(original, backend=backend)]).bind(
        REFERENCE
    )
    for options in ({"width": 1}, {"balance": True}):
        with pytest.raises(esolangs.ProgramError, match="wrapper did not return text"):
            bound.generate("01", **options)


def test_template_hooks_validate_bindings_and_rows() -> None:
    original = LANGUAGES[REFERENCE]
    calls = []

    def emit(request):
        calls.append(request.table)
        return TemplateLayout("$.", ((0, 1),))

    def refuse(*_args):
        raise ValueError("template hook refused request")

    backend = dataclasses.replace(
        original.backend,
        entrypoint=emit,
        wrap=None,
        same_layout=refuse,
        template=TemplateSpec(setters=lambda *_args: (("+", "-"),)),
    )
    declaration = dataclasses.replace(original, backend=backend)
    bound = esolangs.Catalog([declaration]).bind(REFERENCE)
    with pytest.raises(esolangs.ProgramError, match="bind all 2 inputs"):
        bound.generate("0110")
    template = bound.generate("01")
    calls.clear()
    for bits in ([0, 1], [2]):
        with pytest.raises(esolangs.ArgumentError, match=r"bits|inputs"):
            bound.instantiate(template, bits, truth_table="01")
    assert not calls
    different = dataclasses.replace(template, source="$+.")
    with pytest.raises(esolangs.ArgumentError, match="template hook refused request"):
        bound.instantiate(different, [0], truth_table="01")

    broken = dataclasses.replace(backend, template=TemplateSpec(setters=refuse))
    bound = esolangs.Catalog([dataclasses.replace(declaration, backend=broken)]).bind(
        REFERENCE
    )
    with pytest.raises(esolangs.ArgumentError, match="template hook refused request"):
        bound.generate("01")
    _check_template_hooks_require_real_layouts(declaration, backend, emit)


def _check_template_hooks_require_real_layouts(declaration, backend, emit) -> None:
    class ClaimedLayout:
        @property
        def __class__(self) -> type:
            return TemplateLayout

    for hook, options in (("entrypoint", {}), ("balance", {"balance": True})):
        valid = dataclasses.replace(backend, **{hook: emit})
        bound = esolangs.Catalog(
            [dataclasses.replace(declaration, backend=valid)]
        ).bind(REFERENCE)
        template = bound.generate("01", **options)
        assert bound.run(bound.instantiate(template, [0])).unwrap().output == "\x01"

        invalid = dataclasses.replace(backend, **{hook: lambda _: ClaimedLayout()})
        bound = esolangs.Catalog(
            [dataclasses.replace(declaration, backend=invalid)]
        ).bind(REFERENCE)
        with pytest.raises(esolangs.ProgramError, match="did not return slots"):
            bound.generate("01", **options)

    for layout, diagnostic in (
        (TemplateLayout(0, ((0, 1),)), "text source"),
        (TemplateLayout("$.", (0,)), "pairs of offsets"),
    ):
        invalid = dataclasses.replace(
            backend, wrap=wrap_chars, entrypoint=lambda _, layout=layout: layout
        )
        bound = esolangs.Catalog(
            [dataclasses.replace(declaration, backend=invalid)]
        ).bind(REFERENCE)
        for width in (None, 1):
            with pytest.raises(esolangs.TemplateError, match=diagnostic):
                bound.generate("01", width=width)


def test_scoped_dialect_keeps_declared_hook_errors() -> None:
    record = LANGUAGES[REFERENCE]
    schema = esolangs.DialectSchema(REFERENCE, {"mode": (0, 1)}, {"mode": 0})
    runtime = dataclasses.replace(
        record.runtime,
        dialect=FunctionRef("esolangs", "_missing", ("mode",)),
        dialect_schema=schema,
    )
    bound = esolangs.Catalog([dataclasses.replace(record, runtime=runtime)]).bind(
        REFERENCE
    )
    with pytest.raises(esolangs.ProgramError, match=r"esolangs\._missing"):
        bound.settings(mode=1)


@pytest.mark.parametrize("reference", [FunctionRef, OperationRef])
def test_callable_references_distinguish_missing_dependencies(monkeypatch, reference):
    def importer(module):
        assert module == "declared.target"
        raise ModuleNotFoundError(name="unavailable_dependency")

    monkeypatch.setattr(_functions, "import_module", importer)
    with pytest.raises(esolangs.MissingDependencyError, match="unavailable_dependency"):
        reference("declared.target", "emit").load()


@pytest.mark.parametrize(
    "parameters", [[], ("width", "width"), ("bad-name",), ("class",), (None,)]
)
def test_callable_parameter_declarations_are_validated(parameters):
    with pytest.raises(ValueError, match="distinct identifiers"):
        FunctionRef("unloaded.module", "emit", parameters)


def test_backend_options_are_declared_without_loading():
    from esolangs.registry._backend import BooleanBackend

    plain = BooleanBackend(str, balance=str)
    assert not plain.layout_width
    assert not hasattr(plain, "balance_parameters")
    declared = BooleanBackend(
        OperationRef("unloaded.module", "emit"),
        layout_width=True,
        balance=OperationRef("unloaded.module", "balance"),
    )
    assert declared.layout_width
    assert not hasattr(declared.entrypoint, "parameters")
    with pytest.raises(TypeError, match="typed request"):
        BooleanBackend(FunctionRef("unloaded.module", "emit", ("table",)))
    assert "unloaded.module" not in sys.modules
