"""Catalog validation and artifact overrides for scoped dialect choices."""

from typing import TYPE_CHECKING, Any, TypedDict

from esolangs._dialect import DialectSchema, Scalar
from esolangs._dialect import DialectSettings as DialectSettings
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError
from esolangs.outcomes import _remember_acquisition_failure
from esolangs.runtime._validate import _argument_repr, _has_backing_type

if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


def _settings_record(
    name: str, choices: dict[str, Scalar], *, catalog: "Catalog"
) -> DialectSettings:
    """Check decoded choices against the schema before invoking runtime hooks."""
    schema = catalog.languages[name].runtime.dialect_schema or DialectSchema(
        name, {}, {}
    )
    return DialectSettings(schema, **choices)


def _decode_settings(
    value: Any,
    language: str | None,
    *,
    catalog: "Catalog",
    checked_settings: DialectSettings | None = None,
) -> DialectSettings | None:
    """Restore saved choices against a schema without calling its dialect."""
    if value is None:
        return None
    choices = _decode_settings_choices(value)
    if language is None:
        raise ValueError("settings need a language to apply to")
    if (
        checked_settings is not None
        and checked_settings._schema.language == language  # noqa: SLF001
        and all(type(item) in (int, str) for item in choices.values())
        and choices == DialectSettings.options(checked_settings)
    ):
        return checked_settings
    return _settings_record(catalog.resolve(language), choices, catalog=catalog)


def _decode_settings_choices(value: Any) -> dict[str, Any]:
    """Decode settings payloads without binding or invoking a dialect."""
    if not isinstance(value, dict):
        raise ValueError("settings must be an object or null")
    choices: dict[str, Any] = {}
    for key, saved in value.items():
        if type(saved) is int:
            raise ValueError("integer settings need a hexadecimal string")
        item = saved
        if isinstance(item, dict):
            if set(item) != {"integer"} or not isinstance(item["integer"], str):
                raise ValueError("integer settings need a hexadecimal string")
            literal = item["integer"]
            if not literal.startswith(("0x", "-0x")):
                raise ValueError("integer settings need a hexadecimal string")
            item = int(literal, 16)
        choices[key] = item
    return choices


def _settings_for(
    language: str, choices: dict[str, Scalar], *, catalog: "Catalog | None" = None
) -> DialectSettings:
    """Bind validated overrides to the selected language's immutable schema."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    name = catalog.resolve(language)
    settings = _settings_record(name, choices, catalog=catalog)
    dialect_options(name, settings, catalog=catalog)
    return settings


def dialect_options(
    language: str,
    settings: DialectSettings | None,
    *,
    catalog: "Catalog | None" = None,
    validate_defaults: bool = False,
    _sparse_validated: bool = False,
) -> dict[str, Scalar]:
    """Validate sparse choices and, when requested, their effective defaults."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    if settings is None and not validate_defaults:
        return {}
    if settings is not None and not _has_backing_type(settings, DialectSettings):
        raise ArgumentError(
            f"settings must be a DialectSettings object, got {type(settings).__name__}"
        )
    name = catalog.resolve(language)
    runtime = catalog.languages[name].runtime
    if settings is None and runtime.dialect_schema is None:
        return {}
    schema = runtime.dialect_schema or DialectSchema(name, {}, {})
    if settings is not None and settings._schema != schema:  # noqa: SLF001
        owner = settings._schema.language  # noqa: SLF001
        if owner == name:
            raise ArgumentError(
                f"dialect settings for {name} use a different schema from this catalog"
            )
        raise ArgumentError(f"dialect settings belong to {owner}, not {name}")
    values = {} if settings is None else DialectSettings.options(settings)
    if runtime.dialect is not None:
        checked = schema.defaults | values if validate_defaults else values
        if _sparse_validated and settings is not None and checked == values:
            return values
        try:
            runtime.dialect(**checked)
        except EsolangError as error:
            _remember_acquisition_failure(error)
            raise
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
    from esolangs.artifacts import ProgramArtifact, TemplateArtifact
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)

    explicit_options = dialect_options(language, settings, catalog=catalog)
    if not (
        _has_backing_type(program, ProgramArtifact)
        or _has_backing_type(program, TemplateArtifact)
    ) or resolve_origin(program.language, catalog=catalog) != catalog.resolve(language):
        return settings
    retained = program.settings
    if retained is settings:
        return retained
    if (
        settings is not None
        and _has_backing_type(retained, DialectSettings)
        and retained._schema == settings._schema  # noqa: SLF001
    ):
        if DialectSettings.options(retained) == explicit_options:
            return retained
        _check_dialect_conflicts(retained, settings)
    dialect_options(language, retained, catalog=catalog)
    return _merge_settings(language, retained, settings, catalog=catalog)


def _check_dialect_conflicts(
    retained: DialectSettings,
    settings: DialectSettings,
) -> None:
    """Refuse overriding a concrete retained choice before invoking its hook."""
    retained_values = dict(retained._items)  # noqa: SLF001
    # A retained choice is how the source was written; contradicting it reads
    # the same text as a different program, the refusal check_origin makes for
    # a foreign language.  Explicit choices may only add what was not retained.
    conflicts = sorted(
        (key, value)
        for key, value in settings._items  # noqa: SLF001
        if key in retained_values and retained_values[key] != value
    )
    if conflicts:
        detail = ", ".join(
            f"{key}={_argument_repr(retained_values[key])}, not {_argument_repr(value)}"
            for key, value in conflicts
        )
        raise ProgramError(
            f"this program was written with {detail}; reading it otherwise "
            "may well run, and answer nonsense -- pass its .source to drop "
            "the retained settings"
        )


def _merge_settings(
    language: str,
    retained: DialectSettings | None,
    settings: DialectSettings | None,
    *,
    catalog: "Catalog",
) -> DialectSettings | None:
    """Combine validated, nonconflicting choices for one language."""
    if retained is None:
        return settings
    if settings is None or settings is retained:
        return retained
    retained_values = dict(retained._items)  # noqa: SLF001
    explicit_values = dict(settings._items)  # noqa: SLF001
    merged = retained_values | explicit_values
    if merged == retained_values:
        return retained
    if merged == explicit_values:
        return settings
    return _settings_for(language, merged, catalog=catalog)


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
