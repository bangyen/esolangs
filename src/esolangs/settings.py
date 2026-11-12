"""Catalog validation and artifact overrides for scoped dialect choices."""

from typing import TYPE_CHECKING, TypedDict

from esolangs._dialect import DialectSchema, Scalar
from esolangs._dialect import DialectSettings as DialectSettings
from esolangs.exceptions import ArgumentError, ProgramError

if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


def _settings_for(
    language: str, choices: dict[str, Scalar], *, catalog: "Catalog | None" = None
) -> DialectSettings:
    """Bind validated overrides to the selected language's immutable schema."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    name = catalog.resolve(language)
    schema = catalog.languages[name].runtime.dialect_schema or DialectSchema(
        name, {}, {}
    )
    settings = DialectSettings(schema, **choices)
    dialect_options(name, settings, catalog=catalog)
    return settings


def dialect_options(
    language: str, settings: DialectSettings | None, *, catalog: "Catalog | None" = None
) -> dict[str, Scalar]:
    """Validate scope and choices before source or input acquisition."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    if settings is None:
        return {}
    if not isinstance(settings, DialectSettings):
        raise ArgumentError(
            f"settings must be a DialectSettings object, got {type(settings).__name__}"
        )
    name = catalog.resolve(language)
    runtime = catalog.languages[name].runtime
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
    language: str,
    program: object,
    settings: DialectSettings | None,
    *,
    catalog: "Catalog | None" = None,
) -> DialectSettings | None:
    """Merge explicit choices over retained same-language source provenance."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.artifacts import ProgramArtifact, TemplateArtifact

    if settings is not None and not isinstance(settings, DialectSettings):
        raise ArgumentError(
            f"settings must be a DialectSettings object, got {type(settings).__name__}"
        )
    dialect_options(language, settings, catalog=catalog)
    if not isinstance(program, (ProgramArtifact, TemplateArtifact)) or catalog.resolve(
        program.language
    ) != catalog.resolve(language):
        return settings
    retained = program.settings
    dialect_options(language, retained, catalog=catalog)
    if retained is None:
        return settings
    if settings is None:
        return retained
    retained_values = dict(retained._items)  # noqa: SLF001
    explicit_values = dict(settings._items)  # noqa: SLF001
    # A retained choice is how the source was written; contradicting it reads
    # the same text as a different program, the refusal check_origin makes for
    # a foreign language.  Explicit choices may only add what was not retained.
    conflicts = sorted(
        key
        for key, value in explicit_values.items()
        if key in retained_values and retained_values[key] != value
    )
    if conflicts:
        detail = ", ".join(
            f"{key}={retained_values[key]!r}, not {explicit_values[key]!r}"
            for key in conflicts
        )
        raise ProgramError(
            f"this program was written with {detail}; reading it otherwise "
            "may well run, and answer nonsense -- pass its .source to drop "
            "the retained settings"
        )
    merged = _settings_for(language, retained_values | explicit_values, catalog=catalog)
    dialect_options(language, merged, catalog=catalog)
    return merged


class DialectOption(TypedDict):
    """A dialect setting's default and its accepted choices."""

    default: int | str
    choices: tuple[int | str, ...]


def dialect_choices(
    language: str, *, catalog: "Catalog | None" = None
) -> dict[str, DialectOption]:
    """Return fresh choices and explicitly declared defaults."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    runtime = catalog.languages[catalog.resolve(language)].runtime
    if runtime.dialect is None:
        return {}
    schema = runtime.dialect_schema
    assert schema is not None
    choices = schema.choices
    return {
        key: {"default": default, "choices": choices[key]}
        for key, default in schema.defaults.items()
    }


def settings_for(language: str, **choices: Scalar) -> DialectSettings:
    """Bind dialect choices against the installed catalog."""
    return _settings_for(language, choices)
