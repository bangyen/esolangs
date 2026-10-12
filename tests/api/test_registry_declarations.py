"""Only canonical generated declarations populate the registry."""

import runpy
import sys
from dataclasses import replace
from types import SimpleNamespace

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
