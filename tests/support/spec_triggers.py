"""Reusable spec triggers helpers."""

from __future__ import annotations

import esolangs
from esolangs.registry import LANGUAGES
from tests.support.cases import cases
from tests.support.execution import run_observed


def _interpreted() -> list[str]:
    """Return every language with an interpreter, sorted."""
    return sorted(name for name, lang in LANGUAGES.items() if lang.runtime.interpreter)


def triggers_of(name: str) -> dict[str, object]:
    """Return ``name``'s triggers and untriggerable entries."""
    data = cases(LANGUAGES[name].id)
    return {
        "triggers": data.get("spec_triggers", []),
        "untriggerable": data.get("spec_untriggerable", {}),
    }


def all_triggers() -> list[tuple[str, dict[str, object]]]:
    """Return ``(language, trigger)`` for every language's triggers."""
    return [
        (name, trigger)
        for name in _interpreted()
        for trigger in triggers_of(name)["triggers"]  # type: ignore[attr-defined]
    ]


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
    chosen = (
        esolangs.Language(name).settings(**settings)
        if isinstance(settings, dict)
        else None
    )
    return run_observed(
        name,
        _program(name, trigger),
        stdin=str(trigger.get("stdin", "")),
        timeout=5,
        settings=chosen,
    ).output
