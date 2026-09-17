"""Programs and templates that carry the language they were generated for."""

from __future__ import annotations

from collections.abc import Sequence

from esolangs.tools.helpers import Setters, check_setters, check_slots

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
    """A parameterized generator's template, tagged with the language.

    A template is otherwise an ordinary string of source with ``{Xi}`` slots
    in it, and that is the whole problem: :func:`instantiate` had no way to
    tell whose it was, so it accepted any name and substituted *that*
    language's setter code into another language's program.  The result was
    not an error and not obviously wrong -- it ran, and answered::

        mf = generate("Minifuck", "0110")     # XOR
        instantiate("RAM0", mf, [0, 1])       # wrong language, no complaint
        # ... and the program answers 0, where XOR of 0 and 1 is 1.

    Syntax cannot catch that; the mismatched program was well-formed. So the
    template carries its language and :func:`instantiate` compares.

    The tag is an attribute on a ``str`` subclass rather than a wrapper type,
    so a template stays a string everywhere else -- written to files,
    printed, sliced.  Which means it does not survive a round trip through
    disk, so a plain ``str`` is accepted unchecked: the check catches the
    mistake where it is made and does not pretend to cover the file the CLI
    wrote an hour ago.
    """

    unwrapped: str
    setters: Setters | None

    def __new__(
        cls,
        text: str,
        language: str,
        unwrapped: str = "",
        setters: Sequence[tuple[str, str]] | None = None,
    ) -> _Template:
        """Return ``text`` tagged as ``language``'s template.

        ``unwrapped`` is the same template before a width was applied, kept
        because :func:`instantiate` cannot recover it: a reflow wrapper
        leaves ordinary newlines behind and there is no way to tell the ones
        it inserted from ones the generator meant.  Without it a width on
        ``instantiate`` was a no-op for every parameterized language --
        ``wrap_program`` declines to reflow a program that already has
        newlines, which after ``generate(table, width)`` it always does.
        """
        template = super().__new__(cls, text, language)
        template.unwrapped = unwrapped or text
        template.setters = None
        if setters is not None:
            # The conventions, held by the object rather than by every
            # caller: one equal-width pair per input, and the slots are
            # exactly ``{X0}``..``{Xn-1}`` once each in order, so the k-th
            # slot is input k and there is one width to check.
            template.setters = check_setters(setters)
            check_slots(template.unwrapped, len(template.setters))
        return template

    def __reduce__(self) -> tuple[object, ...]:
        """Pickle with the unwrapped source and the setters as well."""
        return (type(self), (str(self), self.language, self.unwrapped, self.setters))
