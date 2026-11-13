"""Only canonical generated declarations populate the registry."""

import runpy
import sys
from dataclasses import replace
from types import SimpleNamespace

from esolangs import ExecutionLimits
from esolangs.registry import LANGUAGES, _table


def test_imported_incidental_declarations_do_not_register(monkeypatch) -> None:
    incidental = replace(next(iter(LANGUAGES.values())), name="Incidental declaration")
    monkeypatch.setitem(
        sys.modules,
        "esolangs.languages.incidental.generator",
        SimpleNamespace(LANGUAGE=incidental),
    )
    rebuilt = runpy.run_path(_table.__file__)["LANGUAGES"]
    assert rebuilt == LANGUAGES
    assert incidental.name not in rebuilt
    _check_scoped_catalogs()


def _check_scoped_catalogs():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    import pytest

    import esolangs
    import esolangs.operations.execution as execution
    from esolangs.registry import CATALOG
    from esolangs.runtime._definition import VerbatimSourcePolicy
    from esolangs.runtime.io import ScriptedIO
    from tests.support.execution import run_observed

    records = list(LANGUAGES.values())
    snapshot = esolangs.Catalog(records)
    records.clear()
    assert len(snapshot.languages) == len(LANGUAGES) > 100
    for index in (
        snapshot.languages,
        snapshot._by_id,
        snapshot._by_folded,
        snapshot._by_boolean,
        snapshot._runners,
        snapshot._interpreters,
    ):
        with pytest.raises(TypeError):
            index["unregistered"] = None
    original = LANGUAGES["brainfuck"]
    with pytest.raises(esolangs.ArgumentError, match="unique"):
        esolangs.Catalog([original, original])
    with pytest.raises(esolangs.ArgumentError, match="identifiers"):
        esolangs.Catalog([original, replace(original, name="second owner")])
    scoped = snapshot.with_language(
        replace(
            original,
            aliases=(*original.aliases, "scoped-bf"),
            runtime=replace(original.runtime, source_policy=VerbatimSourcePolicy()),
        )
    )
    bound = scoped.bind("scoped-bf")
    assert bound.catalog is scoped
    assert replace(bound, name="Brainfuck").catalog is scoped
    assert bound.run("input.bf", limits=ExecutionLimits(max_steps=10)).output == "\x00"
    with pytest.raises(esolangs.UnknownLanguageError):
        CATALOG.resolve("scoped-bf")
    assert (
        snapshot.bind("Brainfuck")
        .run("input.bf", limits=ExecutionLimits(max_steps=10))
        .output
        == "\x00"
    )

    class Unreadable:
        def read(self):
            raise AssertionError("invalid scope must be rejected before reading")

    with pytest.raises(esolangs.ArgumentError, match="catalog must"):
        esolangs.run("brainfuck", Unreadable(), catalog={})
    with pytest.raises(esolangs.ArgumentError, match="installed catalog"):
        bound.run(Unreadable(), stdin=Unreadable(), isolated=True)

    barrier = Barrier(2)

    def factory(label):
        class TaggedIO(ScriptedIO):
            def _write(self, value):
                super()._write(label + str(value))

        def create(stdin):
            barrier.wait(timeout=2)
            return TaggedIO(stdin)

        return create

    def call(catalog, label, stdin):
        return run_observed(
            "brainfuck",
            ",.",
            stdin=stdin,
            max_steps=2,
            catalog=catalog,
            io_factory=factory(label),
        ).output

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(call, snapshot, "A:", "x")
        second = pool.submit(call, scoped, "B:", "y")
        assert first.result(timeout=5) == "A:x"
        assert second.result(timeout=5) == "B:y"
    assert (
        esolangs.run(
            "brainfuck", ",.", stdin="z", limits=ExecutionLimits(max_steps=2)
        ).output
        == "z"
    )
    assert not hasattr(execution, "io_factory")
