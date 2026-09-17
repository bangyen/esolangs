"""Programs and templates that carry the language they were generated for."""

from __future__ import annotations

from collections.abc import Sequence

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

    :func:`generate` and :func:`instantiate` return one, and
    :func:`check_program` -- the entry check :func:`run` and
    :func:`~esolangs.vm.make_vm` share -- refuses it under any other
    language.  A program generated for one interpreter and run on another
    is not a syntax error most of the time: a permissive interpreter reads
    the foreign text as no-ops and answers, plausibly and wrongly.

    Permissive by design, like the template tag below: a hand-written
    program is a plain ``str`` -- every interpreter test, every example file
    read back from disk -- and is accepted unchecked.  The check catches the
    mistake on the library's own path and does not pretend to cover text
    that left it.  ``str(program)``, ``==``, ``len``, ``json`` and file
    writes see the text alone.
    """

    language: str

    def __new__(cls, text: str, language: str) -> _Tagged:
        """Return ``text`` tagged as a ``language`` program."""
        program = super().__new__(cls, text)
        program.language = language
        return program

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle as (class, text, language): the tag survives a worker."""
        return (type(self), (str(self), self.language))


class _Template(_Tagged):
    """A parameterized generator's template: the program's shape, plus how to fill it.

    The text is the program with each input spelled as a run of one
    character (``$`` unless the language declares another) exactly as long
    as that input's setter, so ``len(template) == len(program)`` for every
    row it fills to and consecutive inputs need no separator: the setter
    widths say where one run ends.  ``setters`` is one ``(zero, one)`` pair
    per input, in order -- the k-th run *is* input k, there is no index to
    keep in step with anything -- and the constructor holds the
    conventions: every pair equal width (or the program's length would
    carry the bit), the runs accounting for every occurrence of the
    character (a run of the wrong length, a run left over, or the character
    in the program text proper all refuse).

    The language tag is what lets :func:`esolangs.instantiate` refuse a
    template under another name.  Filling one language's template as
    another was not an error and not obviously wrong -- it ran, and
    answered::

        mf = generate("Minifuck", "0110")     # XOR
        instantiate("RAM0", mf, [0, 1])       # wrong language, no complaint
        # ... and the program answers 0, where XOR of 0 and 1 is 1.

    The tag is an attribute on a ``str`` subclass rather than a wrapper type,
    so a template stays a string everywhere else -- written to files,
    printed, sliced.  Which means the pairs do not survive a round trip
    through disk; a plain string is filled by recovering them from the
    language's own setters (:func:`esolangs.registry.recover_setters`),
    which the runs' total length determines.

    A template is never wrapped: it is the shape of its programs, and a
    width applies when it is filled.
    """

    char: str
    setters: Setters

    def __new__(
        cls,
        text: str,
        language: str,
        char: str = TEMPLATE_CHAR,
        setters: Sequence[tuple[str, str]] = (),
    ) -> _Template:
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
