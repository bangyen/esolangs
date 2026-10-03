"""Preview spelling edits without executing or rewriting a program."""

import re
from typing import NamedTuple, cast

from esolangs.cli_args import _check_count, _errors, _fail, _split_positional
from esolangs.cli_io import _read_program
from esolangs.registry import LANGUAGES, resolve


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
        if word in _DISPATCH:
            continue
        if word.upper() in _DISPATCH:
            candidate = word.upper()
            reason = "command keywords are uppercase"
        else:
            candidates = [name for name in _DISPATCH if _one_edit(word.upper(), name)]
            if len(candidates) != 1:
                continue
            candidate = candidates[0]
            reason = "one spelling edit from a unique command keyword"
        start = token.start(1) + keyword.start(1)
        corrections.append(
            _Correction(start, start + len(word), word, candidate, reason)
        )
    return tuple(corrections)


def _suggest(rest: list[str]) -> None:
    """Print located corrections; leave the file and stdin untouched."""
    rest = _split_positional(rest, set())
    _check_count("suggest", rest, 2)
    with _errors():
        language = resolve(rest[0])
    if LANGUAGES[language].id != "modulous":
        _fail("source correction previews currently support Modulous only")
    source = _read_program(rest[1], language=language)
    source = cast(str, source)
    try:
        corrections = _modulous_corrections(source)
    except ValueError as exc:
        _fail(exc)
        raise  # pragma: no cover - _fail exits
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
