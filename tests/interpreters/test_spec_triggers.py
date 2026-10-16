"""Every interpreter spec's ``Errors:`` entry is shown by running a program.

Each language keeps its triggers in ``languages/<id>/tests/spec_triggers.json``
(so they leave with it): a program (source, hex bytes, or a generated table),
stdin, optional dialect settings, and the exception -- or exact output --
``esolangs.run`` must produce.  ``untriggerable`` maps an entry no ``run``
call reaches to the reason.
"""

import ast
import inspect
import json
import pathlib

import pytest

import esolangs
from esolangs import DialectSettings, exceptions
from esolangs.registry import LANGUAGES
from esolangs.registry._describe import interpreter_module
from tests.interpreters.spec_sections import error_entries

pytestmark = pytest.mark.medium

_LANGUAGES_DIR = pathlib.Path(esolangs.__file__).parent / "languages"


def _interpreted() -> list[str]:
    """Return every language with an interpreter, sorted."""
    return sorted(name for name, lang in LANGUAGES.items() if lang.interpreter)


def triggers_of(name: str) -> dict[str, object]:
    """Return ``name``'s trigger file, or an empty one."""
    path = _LANGUAGES_DIR / LANGUAGES[name].id / "tests/spec_triggers.json"
    if not path.exists():
        return {"triggers": []}
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def all_triggers() -> list[tuple[str, dict[str, object]]]:
    """Return ``(language, trigger)`` for every language's triggers."""
    return [
        (name, trigger)
        for name in _interpreted()
        for trigger in triggers_of(name)["triggers"]  # type: ignore[attr-defined]
    ]


def _entries(name: str) -> set[str]:
    source = pathlib.Path(inspect.getfile(interpreter_module(name))).read_text()
    return error_entries(ast.get_docstring(ast.parse(source)) or "")


def _program(name: str, trigger: dict[str, object]) -> esolangs.ProgramSource:
    """Return the trigger's program in the form ``run`` takes."""
    if "generate" in trigger:
        return esolangs.generate(name, str(trigger["generate"]))
    if "program_hex" in trigger:
        return bytes.fromhex(str(trigger["program_hex"]))
    return str(trigger["program"])


def run_trigger(name: str, trigger: dict[str, object]) -> str:
    """Run one trigger; settings are built here, since they validate."""
    settings = trigger.get("settings")
    chosen = DialectSettings(**settings) if isinstance(settings, dict) else None
    return esolangs.run(
        name,
        _program(name, trigger),
        stdin=str(trigger.get("stdin", "")),
        timeout=5,
        settings=chosen,
    )


_ALL = all_triggers()


@pytest.mark.parametrize(
    ("name", "trigger"),
    _ALL,
    ids=[f"{name}-{t['expect']}-{i}" for i, (name, t) in enumerate(_ALL)],
)
def test_the_trigger_does_what_the_spec_says(
    name: str, trigger: dict[str, object]
) -> None:
    """The documented exception, or exact output, is what ``run`` gives."""
    if trigger["expect"] == "output":
        assert run_trigger(name, trigger) == trigger["output"]
    else:
        with pytest.raises(getattr(exceptions, str(trigger["expect"]))):
            run_trigger(name, trigger)


def test_every_errors_entry_has_a_trigger() -> None:
    """A new ``Errors:`` line cannot land without a program that shows it."""
    missing = {}
    for name in _interpreted():
        data = triggers_of(name)
        covered = {t["expect"] for t in data["triggers"]}  # type: ignore[attr-defined]
        covered |= set(data.get("untriggerable", {}))  # type: ignore[call-overload]
        if gaps := _entries(name) - covered:
            missing[name] = sorted(gaps)
    assert missing == {}


def test_untriggerable_entries_are_still_documented() -> None:
    """An exemption leaves with its entry, so it cannot go stale."""
    stale = {
        name: sorted(set(data.get("untriggerable", {})) - _entries(name))  # type: ignore[call-overload]
        for name in _interpreted()
        if (data := triggers_of(name)).get("untriggerable")
    }
    assert {name: found for name, found in stale.items() if found} == {}
