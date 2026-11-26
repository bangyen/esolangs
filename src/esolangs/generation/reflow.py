"""Select a catalog's source wrappers for text and compressed programs."""

from math import isqrt
from typing import TYPE_CHECKING

from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import ProgramError
from esolangs.generation.requests import call_backend
from esolangs.generation.token_balance import CELL_ASPECT, balanced_token_width
from esolangs.generation.wrap import (
    TokenWrapper,
    _balance_candidates,
    _balance_character_width,
    _cell_width,
    _span,
    _token_fit,
    _tokens,
    balance_score,
    balance_width,
    wrap_chars,
    wrap_grid,
    wrap_space_delimited,
)
from esolangs.runtime._validate import _has_backing_type

if TYPE_CHECKING:
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._catalog import Catalog
    from esolangs.registry._language import LanguageDeclaration


def _language(
    language_id: str, *, catalog: "Catalog | None" = None
) -> "LanguageDeclaration | None":
    """Look up the declared language for a wrapper's identifier."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    return next(
        (lang for lang in catalog.languages.values() if lang.id == language_id), None
    )


def _backend(
    language_id: str, *, catalog: "Catalog | None" = None
) -> "BooleanBackend | None":
    """Return the registered backend for ``language_id``, if any."""
    language = _language(language_id, catalog=catalog)
    return None if language is None else language.backend


def wrap_program(
    program: str,
    language_id: str,
    width: int | None,
    *,
    catalog: "Catalog | None" = None,
) -> str:
    """Return ``program`` wrapped to ``width`` columns, if that is possible.

    ``None`` means do not wrap (the default).  A language that cannot take
    newlines, and a program already multi-line, are returned unchanged
    rather than raising; a multiline wrapper knows which lines are structural.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if width is None or width <= 0:
        return program
    backend = _backend(language_id, catalog=catalog)
    if backend is None or backend.layout.wrap is None:
        return program
    if "\n" in program and not backend.layout.wrap_multiline:
        return program
    wrapped = call_backend(backend.layout.wrap, program, width)
    return _wrapped_text(wrapped, language_id)


def _wrapped_text(result: object, language_id: str) -> str:
    """Require text from a declared source reflow."""
    if not _has_backing_type(result, str):
        raise ProgramError(f"{language_id}'s wrapper did not return text")
    return str.__str__(result)


def _layout_compressed(
    program: CompressedText,
    language_id: str,
    width: int | None = None,
    *,
    balance: bool = False,
    catalog: "Catalog | None" = None,
) -> CompressedText:
    """Apply text reflow to gzip source while retaining its export budgets."""
    program = _freeze_compressed(program)
    if width is None and not balance:
        return program
    language = _language(language_id, catalog=catalog)
    if language is None or (backend := language.backend) is None:
        return program
    if balance:
        if backend.layout.wrap is None and backend.layout.wrap_balance is None:
            return program
    elif backend.layout.wrap is None:
        return program
    multiline = program._is_multiline()  # noqa: SLF001
    if multiline and (not backend.layout.wrap_multiline or backend.layout.wrap is None):
        return program
    if (
        not multiline
        and backend.layout.wrap is wrap_chars
        and (not balance or backend.layout.wrap_balance is None)
    ):
        size = len(program)
        if language.runtime.compressed_source:
            # Native compressed sources retain their terminal-width break.
            chosen = max(1, isqrt(CELL_ASPECT * size)) if balance else width
            return program.wrapped(chosen)
        chosen = _balance_character_width(size) if balance else width
        assert chosen is not None
        return program._wrap_characters(chosen)  # noqa: SLF001
    source = "".join(program.chunks())
    result = (
        balance_program(source, language_id, catalog=catalog)
        if balance
        else wrap_program(source, language_id, width, catalog=catalog)
    )
    if result == source:
        return program
    return CompressedText.from_chunks((result,), limits=program.limits)


def balance_program(
    program: str, language_id: str, *, catalog: "Catalog | None" = None
) -> str:
    """Balance whole-token fits and term folds; otherwise estimate source area."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if "\n" not in program:
        balanced = _balance_line(program, language_id, catalog=catalog)
        if balanced is not None:
            return balanced
    # Token wrappers break before the width, so a neighbour can tie the side
    # with one row fewer or one column narrower.
    width = balance_width(program)
    candidates = [
        wrap_program(program, language_id, candidate, catalog=catalog)
        for candidate in _balance_candidates(width)
    ]
    return min((program, *candidates), key=balance_score)


def _balance_line(
    program: str, language_id: str, *, catalog: "Catalog | None" = None
) -> str | None:
    """Balance a one-line program by its wrapper's tokens, or None to estimate."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    backend = _backend(language_id, catalog=catalog)
    if backend is None:
        return None
    if backend.layout.wrap_balance is not None:
        balanced = call_backend(backend.layout.wrap_balance, program)
        return _wrapped_text(balanced, language_id)
    wrapper = backend.layout.wrap
    if wrapper is wrap_space_delimited:
        return _token_fit(program, program.split(), " ")
    if isinstance(wrapper, TokenWrapper):
        return _token_fit(program, _tokens(program, wrapper.pattern))
    if wrapper is wrap_grid:
        tokens = program.split()
        if not tokens:
            return program
        cell = _cell_width(tokens)
        aligned = [
            token.rjust(_span(len(token), cell) * (cell + 1) - 1) for token in tokens
        ]
        width = balanced_token_width(aligned, " ", rstrip_rows=True)
        return min(
            program,
            wrap_program(program, language_id, width, catalog=catalog),
            key=balance_score,
        )
    return None
