"""Preview spelling edits without executing or rewriting a program."""

import re
from collections.abc import Iterable
from typing import NamedTuple, cast

from esolangs._execution import interpreter_errors
from esolangs.cli_args import _check_count, _errors, _split_positional
from esolangs.cli_io import _read_program
from esolangs.registry import LANGUAGES, SourceKind, resolve


class _Correction(NamedTuple):
    start: int
    end: int
    before: str
    after: str
    reason: str


def _one_edit(word: str, candidate: str) -> bool:
    """Return whether one insertion, deletion, substitution or swap connects them."""
    if len(word) == len(candidate):
        different = [
            i for i, (a, b) in enumerate(zip(word, candidate, strict=True)) if a != b
        ]
        if len(different) == 1:
            return True
        if len(different) == 2:
            left, right = different
            return (
                right == left + 1
                and word[left] == candidate[right]
                and word[right] == candidate[left]
            )
        return False
    shorter, longer = sorted((word, candidate), key=len)
    return len(longer) == len(shorter) + 1 and any(
        longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer))
    )


def _keyword_correction(
    word: str,
    start: int,
    known: Iterable[str],
    *,
    case_reason: str = "keyword spelling is case-sensitive",
) -> _Correction | None:
    """Return one unique case or spelling edit from the supplied vocabulary."""
    vocabulary = tuple(known)
    if word in vocabulary:
        return None
    folded = word.casefold()
    candidates = [name for name in vocabulary if name.casefold() == folded]
    reason = case_reason
    if not candidates:
        candidates = [name for name in vocabulary if _one_edit(folded, name.casefold())]
        reason = "one spelling edit from a unique command keyword"
    if len(candidates) != 1:
        return None
    return _Correction(start, start + len(word), word, candidates[0], reason)


def _modulous_corrections(source: str) -> tuple[_Correction, ...]:
    """Return unique one-edit command corrections in balanced Modulous source."""
    from esolangs.interpreters.stack_based.modulous import (
        _DISPATCH,
        _TOKEN,
        _reject_stray_text,
    )

    _reject_stray_text(source)
    corrections = []
    for token in _TOKEN.finditer(source):
        keyword = re.match(r"\s*([A-Za-z]+)(?=\s|$)", token.group(1))
        if keyword is None:
            continue
        word = keyword.group(1)
        start = token.start(1) + keyword.start(1)
        correction = _keyword_correction(
            word, start, _DISPATCH, case_reason="command keywords are uppercase"
        )
        if correction is not None:
            corrections.append(correction)
    return tuple(corrections)


def _bitdeque_corrections(source: str) -> tuple[_Correction, ...]:
    """Return command edits, skipping the token consumed as each GOTO target."""
    from esolangs.interpreters.queue_based.bitdeque import _COMMANDS

    corrections = []
    target = False
    for token in re.finditer(r"\S+", source):
        word = token.group()
        if target:
            target = False
            continue
        correction = None
        if word.isalpha() and word.isascii():
            correction = _keyword_correction(
                word,
                token.start(),
                _COMMANDS,
                case_reason="command keywords are uppercase",
            )
        if correction is not None:
            corrections.append(correction)
        target = (correction.after if correction is not None else word) == "GOTO"
    return tuple(corrections)


def _packlang_corrections(source: str) -> tuple[_Correction, ...]:
    """Return edits only where Packlang's parser requires a keyword."""
    from esolangs.interpreters.other._packlang_lex import (
        _TOKEN,
        _strip_comments,
        _tokenize,
    )
    from esolangs.interpreters.other.packlang import (
        _DATATYPES,
        _parse_packages,
        _Parser,
        _Type,
    )

    masked = _strip_comments(source, preserve_positions=True)
    tokens = _tokenize(masked)
    positions = [match.start() for match in _TOKEN.finditer(masked)]
    corrections: list[_Correction] = []

    class PreviewParser(_Parser):
        _speculating = False

        def correct(self, vocabulary: Iterable[str]) -> None:
            word = self.peek()
            if word is None or self._speculating:
                return
            correction = _keyword_correction(word, positions[self.pos], vocabulary)
            if correction is not None:
                self.tokens[self.pos] = correction.after
                corrections.append(correction)

        def package_kind(self) -> str:
            self.correct(("Package", "Dependency"))
            return super().package_kind()

        def parse_type(self) -> _Type:
            self.correct(_DATATYPES)
            return super().parse_type()

        def expect(self, word: str) -> None:
            if word in ("Then", "Do"):
                self.correct((word,))
            super().expect(word)

        def is_declaration(self) -> bool:
            # Array(Integer, n) can also be a call; speculative parsing
            # must not rewrite identifiers in its arguments.
            previous = self._speculating
            self._speculating = True
            try:
                return super().is_declaration()
            finally:
                self._speculating = previous

    _parse_packages(PreviewParser(tokens))
    return tuple(sorted(corrections, key=lambda correction: correction.start))


def _suggest(rest: list[str]) -> None:
    """Print located corrections; leave the file and stdin untouched."""
    rest = _split_positional(rest, set())
    _check_count("suggest", rest, 2)
    with _errors():
        language = resolve(rest[0])
    handlers = {
        "modulous": _modulous_corrections,
        "bitdeque": _bitdeque_corrections,
        "packlang": _packlang_corrections,
    }
    handler = handlers.get(LANGUAGES[language].id)
    source = _read_program(rest[1], language=language)
    if handler is None:
        reason = (
            "raster source has no command spellings to correct"
            if LANGUAGES[language].source_kind == SourceKind.RASTER
            else "no safe keyword correction rules are available for this language"
        )
        print(f"{language}: {reason}; the program is not validated")
        return
    source = cast(str, source)
    with (
        _errors(),
        interpreter_errors(
            "source preview exceeds parser recursion depth", language=language
        ),
    ):
        corrections = handler(source)
    line, column, cursor = 1, 1, 0
    for correction in corrections:
        prefix = source[cursor : correction.start]
        newlines = prefix.count("\n")
        line += newlines
        column = len(prefix) - prefix.rfind("\n") if newlines else column + len(prefix)
        cursor = correction.start
        print(
            f"{rest[1]}:{line}:{column}: {correction.before!r} -> "
            f"{correction.after!r}; {correction.reason}"
        )
    if not corrections:
        print("no unambiguous command corrections found; the program is not validated")
