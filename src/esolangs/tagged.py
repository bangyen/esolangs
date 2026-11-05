"""Programs and templates that carry the language they were generated for."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Self

from esolangs.generation.helpers import TEMPLATE_CHAR, Setters
from esolangs.runtime._artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings

__all__ = ["_Tagged", "_Template"]


class _Tagged(str):
    """A generated program, tagged with the language it is written in.

    :func:`_check_program` -- shared by :func:`run` and
    :func:`~esolangs.vm.make_vm` -- refuses it under any other language,
    since a permissive interpreter reads foreign text as no-ops and answers
    plausibly and wrongly.  A hand-written ``str`` is accepted unchecked;
    ``str(program)``, ``==``, ``len``, ``json`` and file writes see the
    text alone.
    """

    language: str
    settings: DialectSettings | None

    def __new__(
        cls, text: str, language: str, settings: DialectSettings | None = None
    ) -> Self:
        """Return ``text`` tagged as a ``language`` program."""
        program = super().__new__(cls, text)
        object.__setattr__(program, "language", language)
        object.__setattr__(program, "settings", settings)
        return program

    @property
    def _artifact(self) -> ProgramArtifact[str] | TemplateArtifact:
        """Convert at the boundary; retaining a record doubles stored text."""
        return ProgramArtifact(str(self), self.language, self.settings)

    def __setattr__(self, name: str, value: object) -> None:
        """Refuse: a retag (``p.language = "Brainfuck"``) changed what ran."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        """Refuse, as :meth:`__setattr__` does."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle with language and dialect provenance for workers."""
        return (type(self), (str(self), self.language, self.settings))


class _Template(_Tagged):
    """A parameterized generator's template: the program's shape, plus how to fill it.

    Each input is a run of one character (``$`` unless the language
    declares another) exactly as wide as its setter, so
    ``len(template) == len(program)`` and the k-th run *is* input k.
    ``setters`` is one equal-width ``(zero, one)`` pair per input; a run
    of the wrong length, a run left over, or the character in the program
    text proper all refuse.  The language tag lets
    :func:`esolangs.instantiate` refuse a template under another name --
    filling an XOR as another language used to run and answer 0.  A ``str``
    subclass, so the pairs do not survive disk; a plain string is filled
    by :func:`esolangs.registry.recover_setters`.  A width wraps with
    every run kept whole.
    """

    _bindings: TemplateBindings

    def __new__(
        cls,
        text: str,
        language: str,
        char: str = TEMPLATE_CHAR,
        setters: Sequence[tuple[str, str]] = (),
        settings: DialectSettings | None = None,
    ) -> Self:
        """Return ``text`` tagged as ``language``'s template."""
        artifact = TemplateArtifact(
            str(text), language, TemplateBindings(char, tuple(setters)), settings
        )
        template = super().__new__(cls, artifact.source, language, settings)
        object.__setattr__(template, "_bindings", artifact.bindings)
        return template

    @property
    def char(self) -> str:
        """The character marking input runs."""
        return self._bindings.char

    @property
    def setters(self) -> Setters:
        """Ordered zero/one bindings."""
        return self._bindings.setters

    @property
    def _artifact(self) -> TemplateArtifact:
        """Recover the explicit record from the legacy source adapter."""
        return TemplateArtifact(str(self), self.language, self._bindings, self.settings)

    @property
    def inputs(self) -> int:
        """How many inputs the template embeds."""
        return self._bindings.inputs

    def fill(self, bits: Sequence[int]) -> str:
        """Return the program for ``bits``; the wrong count is a TemplateError."""
        return self._bindings.fill(str(self), bits)

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle with the character and the setters."""
        return (
            type(self),
            (str(self), self.language, self.char, self.setters, self.settings),
        )
