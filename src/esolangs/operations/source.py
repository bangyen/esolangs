"""Acquire runnable source and validate language ownership."""

import re

from esolangs.artifacts import ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText
from esolangs.exceptions import ProgramError, TemplateError
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, resolve, template_char
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource, _FileSource, source_for

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


def _check_runnable(language: str, program: Program) -> None:
    """Reject a program that is a path or an unfilled template.

    Both are valid input to an interpreter and each produced a confident
    wrong answer (an unfilled template can run as nothing).  Shared by
    ``_check_program`` and :func:`make_vm`.
    """
    name = resolve(language)
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
    if not LANGUAGES[name].runtime.path_like_source and _looks_like_a_path(program):
        raise ProgramError(
            f"program looks like a path, not source: {program!r}. "
            f"Read the file first, or pass pathlib.Path({program!r}); "
            f"source that only looks like one runs with a trailing newline"
        )
    char = template_char(LANGUAGES[name].id)
    if char is not None and char in program:
        backend = LANGUAGES[name].backend
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


def _read_source(language: str, program: ProgramSource | _FileSource) -> Program:
    """Load source and check its kind and origin, allowing unfilled templates."""
    name = resolve(language)

    def check_origin(source: object) -> None:
        if isinstance(
            source, (ProgramArtifact, TemplateArtifact, Raster, CompressedText)
        ):
            origin = source.language
            if origin is not None and origin != name:
                raise ProgramError(
                    f"this program was generated for {origin}, so running it as "
                    f"{name} would read it as {name} source -- which may well run, "
                    "and answer nonsense"
                )

    check_origin(program)
    if isinstance(program, (ProgramArtifact, TemplateArtifact)):
        program = program.source
    check_origin(program)
    program = source_for(name, program)
    check_origin(program)
    return program


def _check_program(
    language: str, program: ProgramSource, stdin: InputSource = ""
) -> Program:
    """Return ``program`` as source, having checked what can be checked here.

    Not a load check: it refuses the wrong *kind* of thing (a path as a
    string, an unfilled template, an unsupported container, an unreadable file, an
    unknown name) and type-checks ``stdin``, but ``_check_program("brainfuck",
    "[")`` returns the program and :func:`make_vm` raises ``ProgramError``.
    :func:`make_vm` calls this, so it cannot build a machine to check.
    A :class:`~pathlib.Path`
    is read here with one trailing newline stripped (some readers reject
    one), so the whole call is::

        path = importlib.resources.files("esolangs") / describe(lang)["examples"][0]
        run(lang, path, stdin=encode_inputs(lang, [0, 1]))

    Programs may also be UTF-8 text bytes, PNG bytes, or readable streams.
    The interpreter chooses the decoder. Stdin streams are checked without
    being consumed; execution snapshots their remaining text.
    """
    name = resolve(language)
    if isinstance(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    explicit = isinstance(program, ProgramArtifact)
    program = _read_source(name, program)
    check_input(stdin)
    if not explicit:
        _check_runnable(name, program)
    return program
