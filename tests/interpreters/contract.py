"""Shared bodies for the per-language tests whose *data* is the only thing
that differs between files.

The registry-wide sweep in ``tests/test_vm_protocol.py`` handles the checks
that need no per-language knowledge at all.  Two families resisted it, and
for the same reason: their answers are genuinely language-specific.  An
empty program prints nothing in brainfuck, prints ``o`` in A Painter Ant,
and is a ``ValueError`` in Dig -- and a program that loops forever cannot
be derived from a registry entry, it has to be written by someone who knows
the language.

So the split here is the other way round from the sweep: the *body* is
shared and the *data* is supplied per file.  A language's test file names
its own runner and its own programs, and inherits the assertions:

    class TestContract(EmptyProgramContract):
        run = staticmethod(run_and_capture)
        empty_program = ""
        empty_output = ""

Anything the language does on top of the shared shape -- Between also
checking ``"\\n\\n"``, Dig also rejecting blank-only programs -- stays a
normal test in that file.  The contract replaces the copied shape, not the
language's own coverage.
"""

import re
from typing import Any, ClassVar

import pytest


class EmptyProgramContract:
    """What a language does with a program containing no instructions.

    A language either runs the empty program to some output (nearly always
    ``""``, though A Painter Ant still prints its ant) or refuses it as
    malformed.  That is the whole of the variation across the forty-odd
    copies this replaces, so setting :attr:`empty_raises` is what picks the
    second branch and everything else defaults to the first.
    """

    # The file's own helper -- run_and_capture, _run, run_program.  It
    # already knows whether the language wants a string or a list of lines,
    # and carries any limit the language needs, so the contract does not
    # have to model either.
    run: ClassVar[Any]

    # The empty program in this language's shape: "" or [].
    empty_program: ClassVar[Any] = ""

    # What running it prints, for the languages that accept it.  Almost
    # always "", so that is the default and only the exceptions say so.
    empty_output: ClassVar[str] = ""

    # Set instead by the languages that refuse an empty program: the exact
    # message, which is what decides between the two branches below.
    empty_raises: ClassVar[str | None] = None

    def test_empty_program(self) -> None:
        """An empty program either produces its output or is refused."""
        if self.empty_raises is not None:
            # The message is matched in full rather than as a `match=`
            # substring, which would also accept a message that had grown a
            # wider or wrong claim around the expected text.  `match=` still
            # gets the escaped message, since the lint rule wants
            # `pytest.raises(ValueError)` narrowed by something.
            expected = re.escape(self.empty_raises)
            with pytest.raises(ValueError, match=expected) as caught:
                type(self).run(self.empty_program)
            assert str(caught.value) == self.empty_raises
        else:
            assert type(self).run(self.empty_program) == self.empty_output


class CycleContract:
    """What the hang detector concludes about two of a language's programs.

    ``run_until_halt_or_cycle`` returns True when a machine reaches its
    halt and False when it proves a hang by revisiting a snapshot.  Both
    halves matter: without the halting program the detector could return
    False for everything, and without the looping one it could return True.

    The looping program has to *revisit a snapshot*, not merely fail to
    halt.  A loop that grows its state on every pass -- a counter climbing
    forever -- never repeats one, so the detector runs until something else
    stops it.  That is why these programs are written per language by
    someone who knows it, rather than derived from the registry.
    """

    # The language's steppable class and the IO it takes, as
    # ``machine(program)`` -- a small function in the file supplies the IO,
    # since which of IO/ScriptedIO a language wants is its own business.
    machine: ClassVar[Any]

    halting_program: ClassVar[Any]

    # None where no existing test had a looping program for this language.
    # Writing one takes knowing which of its loops repeats a snapshot rather
    # than growing its state forever, so the gap is left visible as a skip
    # instead of being filled with a guess that would hang the suite.
    looping_program: ClassVar[Any] = None

    def test_halting_program_is_detected(self) -> None:
        """A program that reaches its halt is reported as halting."""
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(type(self).machine(self.halting_program))

    def test_loop_is_detected_as_a_cycle(self) -> None:
        """A program that revisits a snapshot is proven to hang."""
        from esolangs.vm import run_until_halt_or_cycle

        if self.looping_program is None:
            pytest.skip("no looping program written for this language yet")
        assert not run_until_halt_or_cycle(type(self).machine(self.looping_program))
