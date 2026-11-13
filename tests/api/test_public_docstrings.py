"""The exported functions document their errors, and each is shown by a call.

Docstrings use Google sections (ruff's pydocstyle convention checks their
form); this checks their content against what the calls actually raise.
Languages are chosen by trait, not name, so any one stays removable.
"""

import inspect
import json
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

import esolangs
import esolangs.raster.png as png
from esolangs import exceptions as x
from esolangs.registry._describe import interpreter_module
from tests.interpreters.spec_sections import section
from tests.support.reference import REFERENCE
from tests.support.spec_triggers import all_triggers, run_trigger

#: Exported functions with no ``Raises:``, each with the reason.
RAISE_FREE = {"list_languages": "returns the registry's names"}

_MISSING = Path("/nonexistent/program.b")


def _functions() -> dict[str, Callable[..., object]]:
    """Return every function ``esolangs.__all__`` exports."""
    return {
        name: obj
        for name in esolangs.__all__
        if inspect.isfunction(obj := getattr(esolangs, name))
    }


def _raises(name: str) -> set[str]:
    """Return the exception names a function's ``Raises:`` lists."""
    doc = inspect.getdoc(_functions()[name]) or ""
    return {
        m[1] for line in section(doc, "Raises") if (m := re.match(r"^    (\w+):", line))
    }


@cache
def _first(trait: str) -> str:
    """Return the first language with ``trait``, read off ``describe``."""
    tests = {
        "parameterized": lambda d: d["parameterized"],
        "no generator": lambda d: not d["boolean_generator"],
        "termination": lambda d: d["answer_mode"] == "termination",
        "raster": lambda d: d["source_kind"] == "raster" and d["boolean_generator"],
    }
    return next(
        n for n in esolangs.list_languages() if tests[trait](esolangs.describe(n))
    )


def _over_cap(generate=esolangs.generate) -> object:
    """Generate one input past the smallest declared arity cap."""
    cap, name = min(
        (d["generator_max_inputs"], n)
        for n in esolangs.list_languages()
        if (d := esolangs.describe(n))["generator_max_inputs"]
    )
    return generate(name, "01" * 2**cap)


def _halting_trigger() -> str:
    """Run the first spec trigger documented to raise HaltError."""
    name, trigger = next(
        (n, t) for n, t in all_triggers() if t["expect"] == "HaltError"
    )
    return run_trigger(name, trigger)


def _template() -> esolangs.Artifact:
    return esolangs.generate(_first("parameterized"), "0110")


def _raster_png() -> bytes:
    raster = esolangs.generate(_first("raster"), "01")
    return raster.source.to_png()  # type: ignore[union-attr]


def _without_pillow(call: Callable[[], object]) -> object:
    saved, png.Image = png.Image, None
    try:
        return call()
    finally:
        png.Image = saved


def _run_png_without_pillow() -> object:
    data = _raster_png()
    return _without_pillow(lambda: esolangs.run(_first("raster"), data).output)


def _load_png_without_pillow(load=esolangs.load_program) -> object:
    document = esolangs.dump_program(_first("raster"), _raster_png())
    return _without_pillow(lambda: load(_first("raster"), document))


def _no_docstrings(monkeypatch: pytest.MonkeyPatch) -> None:
    # What ``python -OO`` does to every interpreter (checked under -OO too).
    monkeypatch.setattr(interpreter_module(REFERENCE), "__doc__", None)


def _portable(settings: dict[str, object]) -> str:
    document = json.loads(esolangs.dump_program(REFERENCE, "+."))
    document["settings"] = settings
    return json.dumps(document)


R = REFERENCE
type _Setup = Callable[[pytest.MonkeyPatch], None]
type _Probe = tuple[Callable[[], object], _Setup | None]

#: ``(function, exception, call, setup)``: ``call`` must raise ``exception``.
TRIGGERS: list[tuple[str, type[Exception], Callable[[], object], _Setup | None]] = [
    (
        "save_program",
        x.UnknownLanguageError,
        lambda: esolangs.save_program("No Such Language", "", "."),
        None,
    ),
    (
        "save_program",
        x.TemplateError,
        lambda: esolangs.save_program(
            _first("parameterized"),
            esolangs.generate(_first("parameterized"), "0110"),
            _MISSING,
        ),
        None,
    ),
    (
        "save_program",
        x.ProgramNotFoundError,
        lambda: esolangs.save_program("Brainfuck", _MISSING, _MISSING),
        None,
    ),
    (
        "save_program",
        x.ArgumentError,
        lambda: esolangs.save_program("Brainfuck", "", ".", gzip=1),
        None,
    ),
    (
        "save_program",
        x.ProgramError,
        lambda: esolangs.save_program("Brainfuck", "+.", _MISSING),
        None,
    ),
    (
        "save_program",
        x.MissingDependencyError,
        lambda: _without_pillow(
            lambda: esolangs.save_program(
                _first("raster"), esolangs.generate(_first("raster"), "01"), _MISSING
            )
        ),
        None,
    ),
    (
        "generate",
        x.UnknownLanguageError,
        lambda: esolangs.generate("Nolang", "01"),
        None,
    ),
    ("generate", x.TruthTableError, lambda: esolangs.generate(R, "012"), None),
    (
        "generate",
        x.ArgumentError,
        lambda: esolangs.generate(R, "01", balance=True, width=5),
        None,
    ),
    (
        "generate",
        x.ArgumentError,
        lambda: esolangs.generate(R, "01", scale=2),
        None,
    ),
    (
        "generate",
        x.ArgumentError,
        lambda: esolangs.generate(_first("no generator"), "01"),
        None,
    ),
    ("generate", x.GeneratorCapError, _over_cap, None),
    (
        "instantiate",
        x.UnknownLanguageError,
        lambda: esolangs.instantiate("Nolang", "x", [1]),
        None,
    ),
    (
        "instantiate",
        x.TemplateError,
        lambda: esolangs.instantiate(R, esolangs.generate(R, "01"), [1]),
        None,
    ),
    (
        "instantiate",
        x.ArgumentError,
        lambda: esolangs.instantiate(_first("parameterized"), _template(), [1]),
        None,
    ),
    (
        "instantiate",
        x.ArgumentError,
        lambda: esolangs.instantiate(_first("parameterized"), _template(), [1, 2]),
        None,
    ),
    ("run", x.UnknownLanguageError, lambda: esolangs.run("Nolang", "").output, None),
    (
        "run",
        x.ArgumentError,
        lambda: esolangs.run(R, "", max_steps=-1).output,
        None,
    ),
    ("run", x.ArgumentError, lambda: esolangs.run(R, "", seed=1).output, None),
    ("run", x.ProgramError, lambda: esolangs.run(R, "[").output, None),
    ("run", x.ProgramNotFoundError, lambda: esolangs.run(R, _MISSING).output, None),
    (
        "run",
        x.TemplateError,
        lambda: esolangs.run(_first("parameterized"), _template()).output,
        None,
    ),
    ("run", x.InputExhaustedError, lambda: esolangs.run(R, ",").output, None),
    (
        "run",
        x.ExecutionTimeoutError,
        lambda: esolangs.run(R, "+[]", timeout=0.2).output,
        None,
    ),
    (
        "run",
        x.ExecutionTimeoutError,
        lambda: esolangs.run(R, "+[]", max_steps=100).output,
        None,
    ),
    (
        "run",
        x.InterpreterLimitError,
        lambda: esolangs.run(R, "+[.]", isolated=True, timeout=5, max_output=10).output,
        None,
    ),
    ("run", x.HaltError, _halting_trigger, None),
    ("run", x.MissingDependencyError, _run_png_without_pillow, None),
    ("describe", x.UnknownLanguageError, lambda: esolangs.describe("Nolang"), None),
    ("describe", x.ProgramError, lambda: esolangs.describe(R), _no_docstrings),
    (
        "encode_inputs",
        x.UnknownLanguageError,
        lambda: esolangs.encode_inputs("Nolang", [1]),
        None,
    ),
    (
        "encode_inputs",
        x.ArgumentError,
        lambda: esolangs.encode_inputs(_first("parameterized"), [1]),
        None,
    ),
    (
        "encode_inputs",
        x.ArgumentError,
        lambda: esolangs.encode_inputs(_first("no generator"), [1]),
        None,
    ),
    ("encode_inputs", x.ArgumentError, lambda: esolangs.encode_inputs(R, [2]), None),
    (
        "encode_inputs",
        x.ArgumentError,
        lambda: esolangs.encode_inputs(R, [1], truth_table="0110"),
        None,
    ),
    (
        "encode_inputs",
        x.TruthTableError,
        lambda: esolangs.encode_inputs(R, [1], truth_table="012"),
        None,
    ),
    (
        "read_answer",
        x.UnknownLanguageError,
        lambda: esolangs.read_answer("Nolang", "1"),
        None,
    ),
    (
        "read_answer",
        x.ArgumentError,
        lambda: esolangs.read_answer(_first("termination"), ""),
        None,
    ),
    ("read_answer", x.ProgramError, lambda: esolangs.read_answer(R, "x"), None),
    (
        "dump_program",
        x.UnknownLanguageError,
        lambda: esolangs.dump_program("Nolang", ""),
        None,
    ),
    (
        "dump_program",
        x.ArgumentError,
        lambda: esolangs.dump_program(
            R, "+.", settings=esolangs.Language("brainfuck").settings(nonsense_key=1)
        ),
        None,
    ),
    (
        "dump_program",
        x.ProgramNotFoundError,
        lambda: esolangs.dump_program(R, _MISSING),  # type: ignore[arg-type]
        None,
    ),
    (
        "dump_program",
        x.MissingDependencyError,
        lambda: _without_pillow(
            lambda: esolangs.dump_program(
                _first("raster"), esolangs.generate(_first("raster"), "01")
            )
        ),
        None,
    ),
    (
        "load_program",
        x.UnknownLanguageError,
        lambda: esolangs.load_program("Nolang", "{}"),
        None,
    ),
    (
        "load_program",
        x.ArgumentError,
        lambda: esolangs.load_program(R, b"{}"),  # type: ignore[arg-type]
        None,
    ),
    (
        "load_program",
        x.ProgramError,
        lambda: esolangs.load_program(R, "{}"),
        None,
    ),
    (
        "load_program",
        x.ProgramError,
        lambda: esolangs.load_program(R, _portable({"nonsense_key": 1})),
        None,
    ),
    ("load_program", x.MissingDependencyError, _load_png_without_pillow, None),
]


def test_every_exported_function_lists_its_errors() -> None:
    """A ``Raises:`` section, or a recorded reason there is none."""
    missing = [
        name for name in _functions() if name not in RAISE_FREE and not _raises(name)
    ]
    assert missing == []
    assert set(RAISE_FREE) <= set(_functions())


def test_raises_names_only_package_exceptions() -> None:
    """A typo or a builtin under ``Raises:`` is not what a caller catches."""
    unknown = {
        name: sorted(n for n in _raises(name) if not hasattr(x, n))
        for name in _functions()
    }
    assert {name: found for name, found in unknown.items() if found} == {}


def test_every_raises_entry_has_a_trigger() -> None:
    """A new ``Raises:`` line cannot land without a call that shows it.

    A subclass's trigger covers its base (``ProgramNotFoundError`` shows
    ``ProgramError``), as the docstrings say.
    """
    missing = {
        (name, entry)
        for name in _functions()
        for entry in _raises(name)
        if not any(
            fn == name and issubclass(exc, getattr(x, entry))
            for fn, exc, _, _ in TRIGGERS
        )
    }
    assert missing == set()


def _grouped_triggers() -> list[object]:
    groups: dict[tuple[str, type[Exception]], list[_Probe]] = {}
    for function, exception, call, setup in TRIGGERS:
        groups.setdefault((function, exception), []).append((call, setup))
    return [
        pytest.param(function, exception, probes, id=f"{function}-{exception.__name__}")
        for (function, exception), probes in groups.items()
    ]


@pytest.mark.medium
@pytest.mark.parametrize(("function", "exception", "probes"), _grouped_triggers())
def test_the_documented_error_is_raised(
    function: str,
    exception: type[Exception],
    probes: list[_Probe],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each trigger raises the exception its function's ``Raises:`` names."""
    assert exception.__name__ in _raises(function)
    for call, setup in probes:
        with monkeypatch.context() as patch:
            if setup is not None:
                setup(patch)
            with pytest.raises(exception):
                call()


def test_describe_returns_documents_every_key() -> None:
    """``describe``'s ``Returns:`` names each key the dict carries."""
    doc = inspect.getdoc(esolangs.describe) or ""
    named = set(re.findall(r"``(\w+)``", "\n".join(section(doc, "Returns"))))
    assert set(esolangs.describe(REFERENCE)) - named == set()
