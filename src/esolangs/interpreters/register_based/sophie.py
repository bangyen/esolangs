"""Sophie interpreter implementation.

Esoteric language equivalent to a Finite State Automaton.
Single accumulator with basic control flow operations.

`*` breaks out of the nearest enclosing loop. A single-branch `@c{}` skips
its block when the condition fails. `&` halts. Unmatched structural brackets
raise :class:`ValueError`; a `*` break with no enclosing loop is an
invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the code, accumulator, loop
stack, and skip flag), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once ``&`` fires or the cursor reaches the
end of the code.
"""

import re
from collections.abc import Iterator

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import format_integer, parse_integer
from esolangs.interpreters.source_hints import syntax_error


def _brackets(code: str) -> Iterator[tuple[int, str]]:
    """Yield structural brackets, skipping literal data in loads and guards."""
    for token in re.finditer(r"\#(?:\$\d+|\$?.)|@(?:\$\d+|\$?.)\{|[\[\]{}]", code):
        glyph = token[0]
        if glyph.startswith("#"):
            continue
        if glyph.startswith("@"):
            yield token.end() - 1, "{"
        else:
            yield token.start(), glyph


def matches(code: str) -> None:
    """Reject unmatched structural brackets; loaded and tested brackets are data."""
    brackets = list(_brackets(code))
    for opener, closer in (("[", "]"), ("{", "}")):
        depth = 0
        for index, glyph in brackets:
            if glyph == opener:
                depth += 1
            elif glyph == closer:
                if depth == 0:
                    raise syntax_error(
                        f"unmatched '{closer}' at position {index}",
                        "put the matching opener before this closing delimiter",
                    )
                depth -= 1
        if depth:
            raise syntax_error(
                f"unmatched '{opener}'",
                "close this opening delimiter with its matching partner",
            )


def _partners(code: str) -> dict[int, int]:
    """Return literal-aware partners for code already accepted by matches."""
    table: dict[int, int] = {}
    brackets = list(_brackets(code))
    for opener, closer in (("[", "]"), ("{", "}")):
        stack: list[int] = []
        for index, glyph in brackets:
            if glyph == opener:
                stack.append(index)
            elif glyph == closer and stack:
                table[stack.pop()] = index
    return table


def find(code: str, ind: int) -> int:
    """Return the literal-aware closing position, or source length if unmatched."""
    opener = code[ind]
    closer = chr(ord(opener) + 2)
    depth = 1
    for index, glyph in _brackets(code):
        if index <= ind:
            continue
        depth += (glyph == opener) - (glyph == closer)
        if not depth:
            return index
    return len(code)


#: One instant of a run: ``(acc, ind, skp, stk, halted)`` -- the
#: accumulator, the cursor, the break flag, the stack of loop-entry
#: positions, and whether ``&`` fired.  A value :func:`_advance` maps
#: forward, with the stack as a ``tuple`` for the same reason.
#:
#: ``skp`` remains a compatibility view, always false. Break jumps directly
#: past its own loop: propagating a skip flag wrongly skipped later loops.
type _State = tuple[int, int, bool, tuple[int, ...], bool]


def _advance(
    state: _State,
    code: str,
    partners: dict[int, int],
    value: int | None = None,
) -> _State:
    """Return the state after executing the command under the cursor.

    Pure: it reads ``state`` and returns a new one.  The four I/O commands
    are the caller's -- ``.`` and ``,`` print the accumulator this carries
    forward unchanged, and ``:``/``;`` arrive as ``value``, already read
    and already rejected if the input did not qualify, in which case it is
    ``None`` and the accumulator stands.

    ``]`` returns to one before its loop's ``[`` to re-read it; ``*``
    jumps past that loop's close. A
    conditional that fails jumps to its block's ``}`` -- or to the ``{`` of
    an else-block if one follows, so the trailing advance enters it.
    """
    acc, ind, skp, stk, halted = state

    if (c := code[ind]) == "[":
        stk = (*stk, ind)
    elif c in "]*":
        if not stk:
            raise HaltError(
                f"{c!r} at position {ind} closes a loop that never opened",
                hint="add the matching loop opener before this closing instruction",
            )
        opener = stk[-1]
        stk = stk[:-1]
        ind = opener - 1 if c == "]" else partners[opener]
    elif c in ".,":
        pass  # printed by the caller; the accumulator is unchanged
    elif c in ":;":
        if value is not None:
            acc = value
    elif c == "{":
        ind = partners[ind]
    elif c == "&":
        return (acc, ind, skp, stk, True)
    else:
        val = code[ind:]
        if m := re.match(r"@\$(\d+){", val):
            ind = _branch(
                code, partners, ind, m.end() - 1, taken=acc == parse_integer(m[1])
            )
        elif m := re.match(r"@\$?(.){", val):
            ind = _branch(code, partners, ind, m.end() - 1, taken=acc == ord(m[1]))
        elif m := re.match(r"#\$(\d+)", val):
            acc = parse_integer(m[1])
            ind += m.end() - 1
        elif m := re.match(r"#\$?(.)", val):
            acc = ord(m[1])
            ind += m.end() - 1

    return (acc, ind + 1, skp, stk, halted)


def _branch(
    code: str, partners: dict[int, int], ind: int, width: int, *, taken: bool
) -> int:
    """Return the cursor for a conditional, entered or skipped.

    A taken branch steps over the ``@c`` header onto its block.  A failed
    one jumps to the block's close, and one place further when an
    else-block starts there, so the trailing advance lands inside it.
    """
    if taken:
        return ind + width
    end = partners[ind + width]
    if end + 1 < len(code) and code[end + 1] == "{":
        return end + 1
    return end


class _Machine:
    """Per-run Sophie state: the code, accumulator, loop stack, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Validate ``code``'s brackets and start with a zero accumulator.

        Unbalanced brackets are a malformed program, raised eagerly before
        any command runs.
        """
        matches(code)
        # Where each bracket's partner is, matched once rather than
        # rescanned from the bracket on every loop skip and block entry.
        self._partners = _partners(code)
        self.io = io
        self.code = code
        self.acc = self.ind = 0
        self.skp = False
        self.stk: tuple[int, ...] = ()
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        """Whether ``&`` fired or the cursor reached the end of the code."""
        return self._halted_by_command or self.ind >= len(self.code)

    # The VM's language-shaped view: Accumulator + loop stack; ip the cursor, memory
    # the acc.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.stk)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.acc,
            self.skp,
            self.stk,
            self._halted_by_command,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.acc, self.ind, self.skp, self.stk, self._halted_by_command)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- the VM's views and
        the tests read them -- so they stay; the one assignment a step
        makes is here rather than scattered through the rules above.
        """
        self.acc, self.ind, self.skp, self.stk, self._halted_by_command = state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor.

        The four I/O commands live here rather than in the transition: this
        is the shell.  ``.`` and ``,`` print the accumulator the transition
        carries forward unchanged, and ``:``/``;`` read here -- including
        the test that decides whether the input counts, since an input that
        does not qualify must leave the accumulator alone rather than
        writing a zero over it.
        """
        if self.halted:
            return
        c = self.code[self.ind]

        value: int | None = None
        if c == ".":
            self.io.print_str(format_integer(self.acc))
        elif c == ",":
            self.io.print_char(chr(self.acc))
        elif c == ":":
            num = self.io.input_token()
            if num.isdigit():
                value = parse_integer(num)
        elif c == ";":
            value = self.io.input_char()

        self._restore(_advance(self._state, self.code, self._partners, value))


def run(code: str, io: IO) -> None:
    """Execute Sophie program code."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
