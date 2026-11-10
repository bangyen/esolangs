"""Acquire runnable source and validate language ownership."""

import re

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText
from esolangs.exceptions import MissingDependencyError, ProgramError, TemplateError
from esolangs.raster import Raster, png
from esolangs.registry import template_char
from esolangs.registry._catalog import Catalog
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._program import Program
from esolangs.runtime._source import (
    ProgramSource,
    _FileSource,
    _read_container,
    source_for,
)
from esolangs.runtime._validate import check_scale
from esolangs.settings import dialect_options

#: Characters a filename is made of, and a program mostly is not.
_PATH_CHARS = re.compile(r"^[\w./\\~-]+$")

#: A short extension, which is what makes a bare name look like a file.
_PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _looks_like_a_path(program: Program) -> bool:
    """Whether ``program`` is a filename someone meant to open.

    A path is legal text in most of these languages
    (``run("brainfuck", "prog.bf")`` returns a null byte).  Shape-based: one
    line of path characters, rooted (``/``, ``./``, ``../``, ``~/``) or ending
    in a short extension, naming something (a letter).  ``.``, ``..``,
    ``~~`` and Befunge's ``/`` are accepted as programs.
    """
    if not isinstance(program, str):
        return False
    if "\n" in program or not _PATH_CHARS.match(program):
        return False
    if not re.search("[A-Za-z]", program):
        return False
    rooted = program.startswith(("/", "./", "../", "~/"))
    return rooted or bool(_PATH_EXTENSION.search(program))


def _check_runnable(
    language: str, program: Program, *, catalog: "Catalog | None" = None
) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are valid input to an interpreter and each produced a confident
    wrong answer (an unfilled template can run as nothing).  Shared by
    ``_check_program`` and :func:`make_vm`.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, (Raster, CompressedText)):
        return
    if not isinstance(program, str):
        # A non-source value otherwise fell through: an ``int`` leaked a
        # ``TypeError`` from ``char in program`` for a template language and
        # was silently accepted by every other one.
        raise ProgramError(
            f"program must be a string of source or a Raster, got "
            f"{type(program).__name__}"
        )
    if not catalog.languages[name].runtime.path_like_source and _looks_like_a_path(
        program
    ):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r}); "
            f"source that only looks like one runs with a trailing newline"
        )
    char = template_char(catalog.languages[name].id, catalog=catalog)
    if char is not None and char in program:
        backend = catalog.languages[name].backend
        assert backend is not None
        spec = backend.template
        assert spec is not None  # template_char uses the same declaration
        unfilled = spec.unfilled
        if unfilled is not None and not unfilled(program):
            return
        raise TemplateError(
            f"{name}'s generator returns a template, and this one still has "
            f"unfilled runs of {char!r} ({program.count(char)} characters); "
            f"fill them with esolangs.instantiate({name!r}, program, bits)"
        )


def check_origin(
    language: str, origin: object, *, catalog: "Catalog | None" = None
) -> None:
    """Reject known foreign provenance before reading a payload."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if origin is None:
        return
    if not isinstance(origin, str):
        raise ProgramError("source language must be a string")
    canonical = catalog.resolve(origin)
    if canonical != language:
        raise ProgramError(
            f"this program was generated for {canonical}, so running it as "
            f"{language} would read it as {language} source -- which may well run, "
            "and answer nonsense"
        )


def read_png_artifact(
    language: str, data: bytes, *, catalog: "Catalog | None" = None
) -> ProgramArtifact[Raster]:
    """Decode native metadata into its owning artifact, leaving pixels untagged."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.portable import decode_settings

    name = catalog.resolve(language)
    try:
        metadata = png.read_metadata(data)
        settings = None
        scale = None
        if metadata is not None:
            origin = metadata.get("language")
            if origin is not None and not isinstance(origin, str):
                raise ValueError("PNG language must be a string")
            check_origin(name, origin, catalog=catalog)
            settings = decode_settings(
                metadata.get("settings"), origin, catalog=catalog
            )
            scale = metadata.get("scale")
            if scale is not None:
                check_scale(scale)
        raster = Raster.from_png(data)
        return ProgramArtifact(raster, name, settings, scale)
    except (ProgramError, MissingDependencyError):
        raise
    except Exception as error:
        raise ProgramError(f"not a readable PNG: {error}") from error


def read_artifact(
    language: str,
    program: ProgramSource | _FileSource,
    *,
    catalog: "Catalog | None" = None,
) -> Artifact:
    """Acquire source once, retaining native metadata only in an explicit record."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, (ProgramArtifact, TemplateArtifact)):
        check_origin(name, program.language, catalog=catalog)
        dialect_options(name, program.settings, catalog=catalog)
        source = source_for(name, program.source, catalog=catalog)
        if source is program.source and program.language == name:
            return program
        if isinstance(program, TemplateArtifact):
            if not isinstance(source, str):
                raise TemplateError("template source must be text")
            return TemplateArtifact(source, name, program.bindings, program.settings)
        return ProgramArtifact(source, name, program.settings, program.scale)
    value, file = _read_container(program)
    if isinstance(value, bytes) and value.startswith(b"\x89PNG\r\n\x1a\n"):
        record = read_png_artifact(name, value, catalog=catalog)
        # Source-kind checking still belongs to the selected language's loader.
        source = source_for(name, record.source, catalog=catalog)
        return ProgramArtifact(source, name, record.settings, record.scale)
    snapshot: Program | bytes | _FileSource
    if file:
        assert isinstance(value, bytes)
        snapshot = _FileSource(str(program), value)
    else:
        snapshot = value
    source = source_for(name, snapshot, catalog=catalog)
    return ProgramArtifact(source, name)


def _read_source(
    language: str,
    program: ProgramSource | _FileSource,
    *,
    catalog: "Catalog | None" = None,
) -> Program:
    """Project source for callers that explicitly need only the payload."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return read_artifact(language, program, catalog=catalog).source


def _check_program(
    language: str,
    program: ProgramSource | _FileSource,
    stdin: InputSource = "",
    *,
    catalog: "Catalog | None" = None,
) -> ProgramArtifact[Program]:
    """Acquire a runnable record without consuming stdin or parsing commands."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    explicit = isinstance(program, ProgramArtifact)
    record = read_artifact(name, program, catalog=catalog)
    assert isinstance(record, ProgramArtifact)
    check_input(stdin)
    if not explicit:
        _check_runnable(name, record.source, catalog=catalog)
    return record
