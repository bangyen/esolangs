"""Programs and templates that carry the language they were generated for."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Self

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    check_setters,
    fill_runs,
    runs,
)

__all__ = ["_Tagged", "_Template"]


class _Tagged(str):
    """A generated program, tagged with the language it is written in.

    :func:`check_program` -- shared by :func:`run` and
    :func:`~esolangs.vm.make_vm` -- refuses it under any other language,
    since a permissive interpreter reads foreign text as no-ops and answers
    plausibly and wrongly.  A hand-written ``str`` is accepted unchecked;
    ``str(program)``, ``==``, ``len``, ``json`` and file writes see the
    text alone.
    """

    language: str

    def __new__(cls, text: str, language: str) -> Self:
        """Return ``text`` tagged as a ``language`` program."""
        program = super().__new__(cls, text)
        program.language = language
        return program

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle as (class, text, language): the tag survives a worker."""
        return (type(self), (str(self), self.language))


class _Template(_Tagged):
    """A parameterized generator's template: the program's shape, plus how to fill it.

    Each input is a run of one character (``$`` unless the language
    declares another) exactly as wide as its setter, so
    ``len(template) == len(program)`` and the k-th run *is* input k.
    ``setters`` is one equal-width ``(zero, one)`` pair per input; a run
    of the wrong length, a run left over, or the character in the program
    text proper all refuse.  The language tag lets
    :func:`esolangs.instantiate` refuse a template under another name --
    filling Minifuck's XOR as RAM0 used to run and answer 0.  A ``str``
    subclass, so the pairs do not survive disk; a plain string is filled
    by :func:`esolangs.registry.recover_setters`.  A width wraps with
    every run kept whole.
    """

    char: str
    setters: Setters

    def __new__(
        cls,
        text: str,
        language: str,
        char: str = TEMPLATE_CHAR,
        setters: Sequence[tuple[str, str]] = (),
    ) -> Self:
        """Return ``text`` tagged as ``language``'s template."""
        template = super().__new__(cls, text, language)
        template.char = char
        template.setters = check_setters(setters)
        runs(text, char, template.setters)
        return template

    @property
    def inputs(self) -> int:
        """How many inputs the template embeds."""
        return len(self.setters)

    def fill(self, bits: Sequence[int]) -> str:
        """Return the program for ``bits``."""
        return fill_runs(str(self), self.char, self.setters, bits)

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle with the character and the setters."""
        return (type(self), (str(self), self.language, self.char, self.setters))
