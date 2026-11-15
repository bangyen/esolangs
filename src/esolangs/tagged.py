"""Pickle entry points for the former tagged text wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from esolangs.artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
    _restore_legacy_settings,
)

if TYPE_CHECKING:
    from esolangs._bindings import Setters
    from esolangs.settings import DialectSettings


def _Tagged(  # noqa: N802
    text: str, language: str, settings: DialectSettings | None
) -> ProgramArtifact[str]:
    return ProgramArtifact(
        text, language, settings=_restore_legacy_settings(language, settings)
    )


def _Template(  # noqa: N802
    text: str,
    language: str,
    char: str,
    setters: Setters,
    settings: DialectSettings | None,
) -> TemplateArtifact:
    return TemplateArtifact(
        text,
        language,
        TemplateBindings(char=char, setters=setters),
        settings=_restore_legacy_settings(language, settings),
    )
