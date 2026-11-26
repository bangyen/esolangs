"""Read and update the native PNG source metadata chunk."""

from __future__ import annotations

import re
import struct
import zlib
from collections.abc import Buffer
from json import JSONDecoder
from json.encoder import encode_basestring_ascii
from typing import TYPE_CHECKING, Any

from esolangs._dialect import DialectSettings
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.raster._png_chunks import _SIGNATURE, _backing_bytes, _chunks
from esolangs.runtime._json import check_record_utf8, record_dumps, record_loads
from esolangs.runtime._validate import _has_backing_type, check_input_arity, check_scale
from esolangs.runtime.source_hints import display_label, program_error_context

if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


_METADATA_CHUNK = b"esOL"
_METADATA_LIMIT = 16_384
_JSON_TOKEN = re.compile(r"[^ \r\n\t]")
_JSON_ASCII_ESCAPE = re.compile(rb"[\x7f-\xff]+")


class SourceMetadataSizeError(ProgramError):
    """Source metadata exceeds the native PNG chunk budget."""


def _decode_metadata(body: bytes) -> dict[str, Any]:
    if len(body) > _METADATA_LIMIT:
        raise ValueError("duplicate or oversized esolangs PNG metadata")
    decoded = record_loads(body.decode("utf-8-sig"))
    if not isinstance(decoded, dict):
        raise ValueError("esolangs PNG metadata must be an object")
    try:
        check_record_utf8(decoded)
    except UnicodeEncodeError as error:
        raise ProgramError(f"PNG metadata is not valid UTF-8 text: {error}") from error
    return decoded


def _check_version(metadata: dict[str, Any]) -> None:
    version = metadata.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("invalid esolangs PNG metadata version")
    if version != 1:
        raise ValueError("unsupported esolangs PNG metadata version")


def check_source_fields(metadata: dict[str, Any]) -> None:
    """Require the claims present on every source tag, including null values."""
    if not {"language", "settings", "scale"} <= metadata.keys():
        raise ValueError("esolangs PNG metadata requires language, settings and scale")


def read_metadata(data: Buffer) -> dict[str, Any] | None:
    """Read bounded UTF-8 version-one source metadata."""
    found: dict[str, Any] | None = None
    for kind, body in _chunks(_backing_bytes(data)):
        if kind != _METADATA_CHUNK:
            continue
        if found is not None:
            raise ValueError("duplicate or oversized esolangs PNG metadata")
        found = _decode_metadata(body)
    if found is not None:
        _check_version(found)
    return found


def write_metadata(data: Buffer, metadata: dict[str, Any]) -> bytes:
    """Append source metadata before IEND; image editors may discard it."""
    body = _encode_metadata(metadata)
    data = _backing_bytes(data)
    position, end = _metadata_span(data, locate_existing=False)
    return _write_metadata_chunk(data, body, position, end)


def _encode_metadata(metadata: dict[str, Any]) -> bytes:
    utf8 = _utf8_metadata(metadata)
    if len(utf8) > _METADATA_LIMIT:
        raise SourceMetadataSizeError("oversized esolangs PNG metadata")
    # Characters requiring ASCII escapes occur only inside JSON strings.
    # Escape this validated snapshot without reading caller containers again.
    body = _JSON_ASCII_ESCAPE.sub(
        lambda run: encode_basestring_ascii(run[0].decode())[1:-1].encode("ascii"),
        utf8,
    )
    return body if len(body) <= _METADATA_LIMIT else utf8


def _metadata_span(data: bytes, *, locate_existing: bool) -> tuple[int, int]:
    """Find the existing chunk or the insertion point before IEND."""
    # A PNG datastream can end before the last byte of its enclosing file.
    position = len(_SIGNATURE)
    previous = None
    for kind, contents in _chunks(data):
        if kind == b"IEND":
            break
        end = position + 12 + len(contents)
        if locate_existing and kind == _METADATA_CHUNK:
            if previous is not None:
                raise ProgramError("duplicate esolangs PNG metadata")
            previous = position, end
        position = end
    return (position, position) if previous is None else previous


def _write_metadata_chunk(data: bytes, body: bytes, start: int, end: int) -> bytes:
    if len(body) > _METADATA_LIMIT:
        raise SourceMetadataSizeError("oversized esolangs PNG metadata")
    chunk = _METADATA_CHUNK + body
    return (
        data[:start]
        + struct.pack(">I", len(body))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        + data[end:]
    )


def _utf8_metadata(metadata: dict[str, Any]) -> bytes:
    """Validate the same Unicode scalar values as portable metadata."""
    try:
        return record_dumps(metadata, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProgramError(f"PNG metadata is not valid UTF-8 text: {error}") from error


def _token_offset(text: str, position: int) -> int:
    match = _JSON_TOKEN.search(text, position)
    assert match is not None  # the complete object has already been decoded
    return match.start()


def _update_metadata_body(
    body: bytes,
    stored: dict[str, Any],
    additions: dict[str, Any],
    *,
    ensure_ascii: bool,
) -> bytes:
    """Edit only claim values, preserving legal extension numbers and spelling."""
    text = body.decode("utf-8")
    decoder = JSONDecoder(parse_int=str, parse_float=str)
    position = text.index("{") + 1
    start = 0
    parts = []
    for key in stored:
        _, key_end = decoder.raw_decode(text, _token_offset(text, position))
        value_start = _token_offset(text, _token_offset(text, key_end) + 1)
        _, value_end = decoder.raw_decode(text, value_start)
        position = _token_offset(text, value_end) + 1
        if key in additions:
            parts.append(text[start:value_start])
            parts.append(record_dumps(additions[key], ensure_ascii=ensure_ascii))
            start = value_end
    close = position - 1
    parts.append(text[start:close])
    new_fields = {key: value for key, value in additions.items() if key not in stored}
    if new_fields:
        parts.extend((",", record_dumps(new_fields, ensure_ascii=ensure_ascii)[1:-1]))
    parts.append(text[close:])
    return "".join(parts).encode("utf-8")


def _retained_owner(
    owner: Any, requested: str | None, *, catalog: Catalog | None
) -> str | None:
    if owner is None:
        return None
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("stored PNG language must be a nonblank string")
    if catalog is None:
        if requested is None or requested == owner:
            return owner
        from esolangs.registry._catalog import _same_origin_spelling

        if _same_origin_spelling(owner, requested):
            return owner
    else:
        from esolangs.registry._catalog import resolve_origin

        canonical = resolve_origin(owner, catalog=catalog)
        if canonical is None:
            raise ValueError(f"stored PNG language {owner!r} is not a catalog owner")
        if requested in (None, canonical):
            _check_png_owner(canonical, catalog, error_type=ValueError)
            return canonical
    raise ValueError(f"conflicting PNG language {owner!r} and {requested!r}")


def _check_png_owner(
    owner: str, catalog: Catalog, *, error_type: type[ValueError]
) -> None:
    from esolangs.runtime._definition import SourceKind

    if catalog.languages[owner].runtime.source_kind is not SourceKind.RASTER:
        raise error_type(
            f"{display_label(owner)} requires text source, but the program is a PNG"
        )


def _check_retained_settings(
    saved: Any, requested: Any, owner: str | None, *, catalog: Catalog | None
) -> None:
    from esolangs.settings import _decode_settings_choices, _settings_for

    if owner is None:
        raise ValueError("stored PNG settings need a language to apply to")
    choices = _decode_settings_choices(saved)
    if any(type(value) not in (int, str) for value in choices.values()):
        raise ValueError("stored PNG settings must be integer or string choices")
    if requested is not None and choices == _decode_settings_choices(requested):
        # Explicit settings already passed the catalog validator.
        return
    if catalog is not None:
        schema = catalog.languages[owner].runtime.dialect_schema
        if schema is not None and requested is None:
            _settings_for(owner, choices, catalog=catalog)
        elif schema is not None:
            schema.validate(choices)
        elif choices:
            raise ValueError(f"{display_label(owner)} declares no PNG dialect settings")
    if requested is not None:
        raise ValueError("conflicting PNG settings")


def _missing_claims(
    stored: dict[str, Any], requested: dict[str, Any], *, catalog: Catalog | None
) -> dict[str, Any]:
    owner = _retained_owner(
        stored.get("language"), requested["language"], catalog=catalog
    )
    for key in ("scale", "input_arity"):
        value = stored.get(key)
        if value is None and (key == "scale" or key not in stored):
            continue
        if type(value) is not int or value < 1:
            raise ValueError(f"stored PNG {key} must be a positive integer")
        if requested.get(key) not in (None, value):
            raise ValueError(f"conflicting PNG {key}")
    if (settings := stored.get("settings")) is not None:
        _check_retained_settings(
            settings, requested["settings"], owner, catalog=catalog
        )
    return {
        key: value
        for key, value in requested.items()
        if value is not None and stored.get(key) is None
    }


def _attach_metadata(
    data: Buffer, metadata: dict[str, Any], *, catalog: Catalog | None
) -> bytes:
    data = _backing_bytes(data)
    start, end = _metadata_span(data, locate_existing=True)
    if start == end:
        return _write_metadata_chunk(data, _encode_metadata(metadata), start, end)
    body = data[start + 8 : end - 4]
    with _track_acquisition_failures():
        try:
            stored = _decode_metadata(body)
            _check_version(stored)
            check_source_fields(stored)
            additions = _missing_claims(stored, metadata, catalog=catalog)
        except ProgramError:
            raise
        except (ValueError, RecursionError) as error:
            if _is_acquisition_failure(error):
                raise
            raise program_error_context(f"cannot tag PNG: {error}", error) from error
    if not additions:
        return data
    _utf8_metadata(additions)
    updated = _update_metadata_body(body, stored, additions, ensure_ascii=True)
    if len(updated) > _METADATA_LIMIT:
        updated = _update_metadata_body(body, stored, additions, ensure_ascii=False)
    return _write_metadata_chunk(data, updated, start, end)


def attach_source_metadata(
    data: Buffer,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None = None,
    catalog: Catalog | None = None,
) -> bytes:
    """Add absent source claims to PNG, checking settings in a supplied catalog."""
    claims = _source_claims(
        language, settings, scale, input_arity=input_arity, catalog=catalog
    )
    if claims is None:
        return _backing_bytes(data)
    return _attach_metadata(data, claims, catalog=catalog)


def _source_claims(
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None,
    catalog: Catalog | None,
) -> dict[str, Any] | None:
    """Validate incoming claims before acquiring image support or scanning PNG."""
    if catalog is not None:
        from esolangs.registry._catalog import get_catalog

        catalog = get_catalog(catalog)
    if language is None and settings is None and scale is None and input_arity is None:
        return None
    if language is not None:
        if not _has_backing_type(language, str):
            raise ArgumentError("PNG language must be a string")
        language = str.__str__(language)
        if not language.strip():
            raise ArgumentError("PNG language must be nonblank")
    if settings is not None:
        if not _has_backing_type(settings, DialectSettings):
            raise ArgumentError("settings must be a DialectSettings or None")
        owner = settings._schema.language  # noqa: SLF001
        spelling = owner if language is None else language
        if catalog is not None or spelling != owner:
            # An alias outside the owner's spelling needs its declared catalog.
            from esolangs.registry._catalog import _folded_spelling, get_catalog

            claimed = (
                owner
                if catalog is None
                and _folded_spelling(spelling) == _folded_spelling(owner)
                else get_catalog(catalog).resolve(spelling)
            )
            if claimed != owner:
                raise ArgumentError(
                    f"dialect settings belong to {display_label(owner)}, "
                    f"not {display_label(claimed)}"
                )
        language = owner
    elif catalog is not None and language is not None:
        language = catalog.resolve(language)
    metadata: dict[str, Any] = {
        "version": 1,
        "language": language,
        "settings": None
        if settings is None
        else {
            key: {"integer": hex(value)} if type(value) is int else value
            for key, value in settings._items  # noqa: SLF001
        },
        "scale": None if scale is None else check_scale(scale),
    }
    if input_arity is not None:
        metadata["input_arity"] = check_input_arity(input_arity)
    if catalog is not None and language is not None:
        _check_png_owner(language, catalog, error_type=ArgumentError)
        if settings is not None:
            from esolangs.settings import dialect_options

            dialect_options(language, settings, catalog=catalog)
    return metadata
