"""Catalog validation and artifact overrides for scoped dialect choices."""

from typing import TypedDict

from esolangs._dialect import DialectSchema, Scalar
from esolangs._dialect import DialectSettings as DialectSettings
from esolangs.exceptions import ArgumentError


def settings_for(language: str, **choices: Scalar) -> DialectSettings:
    """Bind validated overrides to the selected language's immutable schema."""
    from esolangs.registry import LANGUAGES, resolve

    name = resolve(language)
    schema = LANGUAGES[name].runtime.dialect_schema or DialectSchema(name, {}, {})
    settings = DialectSettings(schema, **choices)
    dialect_options(name, settings)
    return settings


def dialect_options(
    language: str, settings: DialectSettings | None
) -> dict[str, Scalar]:
    """Validate scope and choices before source or input acquisition."""
    from esolangs.registry import LANGUAGES, resolve

    if settings is None:
        return {}
    if not isinstance(settings, DialectSettings):
        raise ArgumentError(
            f"settings must be a DialectSettings object, got {type(settings).__name__}"
        )
    name = resolve(language)
    runtime = LANGUAGES[name].runtime
    schema = runtime.dialect_schema or DialectSchema(name, {}, {})
    if settings._schema != schema:  # noqa: SLF001 - verify the declared domain schema
        raise ArgumentError(
            f"dialect settings belong to {settings.language}, not {name}"
        )
    values = settings.options(name)
    if runtime.dialect is not None:
        try:
            runtime.dialect(**values)
        except (TypeError, ValueError) as error:
            raise ArgumentError(
                f"invalid dialect settings for {name}: {error}"
            ) from error
    return values


def effective_settings(
    language: str, program: object, settings: DialectSettings | None
) -> DialectSettings | None:
    """Merge explicit choices over retained same-language source provenance."""
    from esolangs.artifacts import ProgramArtifact, TemplateArtifact
    from esolangs.compressed import CompressedText
    from esolangs.raster import Raster
    from esolangs.registry import resolve

    if settings is not None and not isinstance(settings, DialectSettings):
        raise ArgumentError(
            f"settings must be a DialectSettings object, got {type(settings).__name__}"
        )
    dialect_options(language, settings)
    if not isinstance(
        program, (Raster, CompressedText, ProgramArtifact, TemplateArtifact)
    ) or program.language != resolve(language):
        return settings
    retained = program.settings
    dialect_options(language, retained)
    if retained is None:
        return settings
    if settings is None:
        return retained
    # Validate the combined choices after explicit fields replace retained fields.
    merged = settings_for(language, **(dict(retained._items) | dict(settings._items)))  # noqa: SLF001
    dialect_options(language, merged)
    return merged


class DialectOption(TypedDict):
    """A dialect setting's default and its accepted choices."""

    default: int | str
    choices: tuple[int | str, ...]


def dialect_choices(language: str) -> dict[str, DialectOption]:
    """Return fresh choices and explicitly declared defaults."""
    from esolangs.registry import LANGUAGES, resolve

    runtime = LANGUAGES[resolve(language)].runtime
    if runtime.dialect is None:
        return {}
    schema = runtime.dialect_schema
    assert schema is not None
    choices = schema.choices
    return {
        key: {"default": default, "choices": choices[key]}
        for key, default in schema.defaults.items()
    }
