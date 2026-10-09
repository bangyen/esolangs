"""Shared rules for previewing keyword corrections in a language's source.

An interpreter module offers ``suggest_corrections(source)`` to
``esolangs suggest``; these are the pieces those functions share.
"""

from collections.abc import Iterable
from typing import NamedTuple


class Correction(NamedTuple):
    """One proposed edit: ``source[start:end]`` from ``before`` to ``after``."""

    start: int
    end: int
    before: str
    after: str
    reason: str


def one_edit(word: str, candidate: str) -> bool:
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


def keyword_correction(
    word: str,
    start: int,
    known: Iterable[str],
    *,
    case_reason: str = "keyword spelling is case-sensitive",
) -> Correction | None:
    """Return one unique case or spelling edit from the supplied vocabulary."""
    vocabulary = tuple(known)
    if word in vocabulary:
        return None
    folded = word.casefold()
    candidates = [name for name in vocabulary if name.casefold() == folded]
    reason = case_reason
    if not candidates:
        candidates = [name for name in vocabulary if one_edit(folded, name.casefold())]
        reason = "one spelling edit from a unique command keyword"
    if len(candidates) != 1:
        return None
    return Correction(start, start + len(word), word, candidates[0], reason)
