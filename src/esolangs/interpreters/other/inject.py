"""Interpreter for Inject.

Inject has no numbers and no variables.  The whole of its state is the
*text* of its own program: a label ``name;`` written once opens a
label-block and written a second time closes it, and every command reads or
rewrites the lines between some label's two delimiters.  ``send`` writes a
block to stdout, ``readto`` overwrites a block with a line of stdin,
``inject`` rewrites a block by regex substitution, and the three ``skip``
forms are the only control flow.  Blocks may overlap, and a label's own
delimiter lines are not part of the block they delimit.

``skip`` is decided by the program's *nesting*, not by a jump target, and
the spec gives it three clauses in order:

1. if the next line is a label that **begins** a block, don't run that
   block -- continue after the block's closing delimiter;
2. otherwise, if the instruction pointer is inside at least one block, go
   back to the beginning label of the **innermost** enclosing block;
3. otherwise, exit the program.

``skipif X`` and ``skipq X Y`` are that same jump, executed only when their
condition holds: ``X`` has at least one line, and ``X`` and ``Y`` are equal
respectively.  When the condition fails, control simply falls through to
the next line.

Documented decisions for gaps the wiki leaves open:

* **Blocks are lists of lines, and ``send`` terminates each with a
  newline.**  The spec says ``send`` "writes the contents" without fixing a
  terminator.  Lines are the unit everywhere else in the language --
  ``readto`` overwrites a block with *a line*, and ``skipif`` counts lines
  -- and the wiki's cat program only echoes its input faithfully if each
  sent line ends with a newline, so that is the reading taken here.
* **``readto`` at EOF raises :class:`EOFError`**, the suite-wide convention;
  ``io.input_str`` strips the terminator, so the stored line is the raw line
  contents.  An **empty line stores an empty block** -- zero lines, not one
  empty one.  The cat example pins this: it loops on ``skipif`` ("at least
  one line") and is specified to terminate on empty input, which happens
  only if a blank line leaves nothing behind.
* **A label line, a blank line, and any line whose first word is not a
  command all execute as no-ops** when control flows through them.  Both
  the hello-world example (whose block sits inline and is reached only
  because the preceding ``skip`` jumps it) and the truth machine (which
  falls through the ``0`` block's bare ``0``) depend on this.  It is the
  namesake command working as designed: ``readto`` and ``inject`` write
  arbitrary text into blocks that control can later flow through, so the
  dispatch is "a command word runs, everything else is text".
* **Block structure is fixed when the program is parsed.**  ``readto`` and
  ``inject`` can write a label-lookalike such as ``foo;`` into a block, but
  a written-in line neither opens nor closes a block: the spans are
  computed once and thereafter only shifted, so such a line is inert data
  and ``skip``'s first clause does not see it either.
* **The innermost block** is the one with the shortest span containing the
  pointer; a tie is impossible, since two distinct blocks cannot share both
  delimiters' positions.
* **``inject`` uses Python's :mod:`re`**, a superset of the features the
  spec requires.  The replacement is applied with the substitution taken
  literally except for backreferences, and a malformed regex raises
  :class:`~esolangs.exceptions.HaltError` rather than escaping as a
  ``re.error``.
* A program that is structurally malformed -- a label written a third time,
  a label opened and never closed, a command naming an unknown label, or a
  command whose syntax does not parse -- raises :class:`ValueError`.
  Invalid runtime operations raise
  :class:`~esolangs.exceptions.HaltError`.
* **Running off the end of the program halts**, the same as clause 3.

**The wiki's truth-machine example does not match the wiki's own prose.**
Traced under the rules above, ``skipq data 0`` fires exactly when the input
*is* ``0``; the line after it (``loop;``) closes a block rather than opening
one, so clause 1 does not apply and clause 2 loops back -- printing ``0``
forever.  On input ``1`` the condition fails, control falls through to the
bare ``skip``, clause 1 jumps the ``data`` block, and the program halts
after a single print.  That is a truth machine with its two cases
exchanged.  The prose is kept and the example is treated as the error,
because ``skipif`` is specified with the identical "only executes if"
wording and the cat example *does* depend on that wording being literal:
cat loops while its input block is non-empty and stops on an empty line.
One command cannot read its condition forwards and its neighbour's
backwards, so the polarity the cat example pins is the one implemented.
``tests/interpreters/test_inject.py`` runs both: the wiki's program with
its traced (inverted) behaviour asserted, and a corrected truth machine
that halts on ``0`` and loops on ``1``.

**Inject has no text generator.**  ``send`` is the only output command and
it terminates every line it writes, so no Inject program can print text
that does not end in a newline -- which is what the hello-world harness
asks for.  The language is registered with a boolean generator only, the
way Fargo is for its own output-alphabet reason.
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# A label line is exactly a name and a semicolon; the semicolon is not part
# of the name.  Surrounding whitespace is not significant -- the wiki's own
# examples are written flush left, but nothing keys off the indentation.
_LABEL = re.compile(r"(\w+);")


def _spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Return each label's ``(begin, end)`` delimiter line numbers.

    A name's first occurrence opens its block and its second closes it; a
    third is a syntax error, and so is a block left open at the end of the
    program.
    """
    opened: dict[str, int] = {}
    spans: dict[str, tuple[int, int]] = {}
    for i, line in enumerate(lines):
        match = _LABEL.fullmatch(line.strip())
        if match is None:
            continue
        name = match.group(1)
        if name in spans:
            raise ValueError(f"label written more than twice: {name}")
        if name in opened:
            spans[name] = (opened.pop(name), i)
        else:
            opened[name] = i
    if opened:
        raise ValueError(f"unclosed label-block: {sorted(opened)[0]}")
    return spans


class _Machine:
    """The run state: the program's lines, its label spans, and the pointer.

    The program text *is* the memory here, so ``lines`` is mutated in place
    by ``readto`` and ``inject`` and the spans are recomputed whenever a
    block's length changes.
    """

    def __init__(self, code: str | list[str], io: IO) -> None:
        self.lines = code.split("\n") if isinstance(code, str) else list(code)
        self.spans = _spans(self.lines)
        self.io = io
        self.ind = 0
        self.done = False

    @property
    def halted(self) -> bool:
        return self.done or self.ind >= len(self.lines)

    # The VM's language-shaped view.

    @property
    def ip(self) -> int:
        """The line cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """Each labelled block's line count, in label order.

        Inject has no numbers at all -- its state is the text of its own
        program -- so this is the one numeric view of the state the
        language itself can test, since ``skipif`` asks whether a block has
        at least one line.  A block's size is the gap between its
        delimiters, so the spans alone give it without slicing the lines
        back out.
        """
        return [
            self.spans[name][1] - self.spans[name][0] - 1 for name in sorted(self.spans)
        ]

    @property
    def stack(self) -> list[object]:
        """The labels enclosing the cursor, innermost last.

        ``skip``'s second clause is decided by that nesting, which is what
        makes it the language's stack.
        """
        inside = [
            name for name, (begin, end) in self.spans.items() if begin < self.ind < end
        ]
        ordered = sorted(inside, key=lambda n: self.spans[n][1] - self.spans[n][0])
        return list(reversed(ordered))

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The program text is the memory, so it has to go in whole: a loop
        # that keeps rewriting a block is not a repeat.  The input cursor
        # separates a re-read from a genuine cycle.
        return (self.ind, self.done, tuple(self.lines), self.io.position())

    # -- blocks -------------------------------------------------------

    def _span(self, name: str) -> tuple[int, int]:
        if name not in self.spans:
            raise ValueError(f"unknown label: {name}")
        return self.spans[name]

    def _contents(self, name: str) -> list[str]:
        """Return the lines strictly between a label's two delimiters."""
        begin, end = self._span(name)
        return self.lines[begin + 1 : end]

    def _replace(self, name: str, body: list[str]) -> None:
        """Overwrite a block's contents, moving every later delimiter.

        The program text is also the code being executed, so a rewrite that
        changes a block's length moves every line after it -- including the
        instruction pointer, when the rewritten block sits *before* the
        currently executing line.  Without that the pointer would be left
        pointing at a different line than the one it was on, and a
        ``readto`` into an earlier block would re-execute itself.
        """
        begin, end = self._span(name)
        self.lines[begin + 1 : end] = body
        shift = len(body) - (end - begin - 1)
        if not shift:
            return
        if begin < self.ind:
            self.ind += shift
        # Only positions strictly after the opening delimiter move: an
        # overlapping block that begins earlier keeps its own start and has
        # its end pushed along, which is what keeps the two nestings
        # consistent after a rewrite.
        self.spans = {
            label: (b + shift * (b > begin), e + shift * (e > begin))
            for label, (b, e) in self.spans.items()
        }

    # -- control flow -------------------------------------------------

    def _begins_block(self, index: int) -> str | None:
        """Return the label beginning a block at ``index``, if any."""
        if index >= len(self.lines):
            return None
        match = _LABEL.fullmatch(self.lines[index].strip())
        if match is None:
            return None
        name = match.group(1)
        span = self.spans.get(name)
        return name if span is not None and span[0] == index else None

    def _innermost(self) -> str | None:
        """Return the shortest block strictly containing the pointer."""
        inside = [n for n, (b, e) in self.spans.items() if b < self.ind < e]
        if not inside:
            return None
        return min(inside, key=lambda n: self.spans[n][1] - self.spans[n][0])

    def _skip(self) -> None:
        """Perform the three-clause ``skip`` jump."""
        ahead = self._begins_block(self.ind + 1)
        if ahead is not None:
            self.ind = self.spans[ahead][1] + 1
            return
        inner = self._innermost()
        if inner is not None:
            self.ind = self.spans[inner][0]
            return
        self.done = True

    # -- one command --------------------------------------------------

    def step(self) -> None:
        """Execute one line, advancing the pointer."""
        # A halted machine ignores a further step, so a caller can drive it
        # without checking first.
        if self.halted:
            return
        line = self.lines[self.ind].strip()

        # A blank line and a label line are both no-ops; the hello-world
        # example runs straight through its block's delimiters.
        if not line or _LABEL.fullmatch(line):
            self.ind += 1
            return

        command, _, rest = line.partition(" ")
        rest = rest.strip()

        if command == "send":
            for text in self._contents(rest):
                self.io.print_str(text + "\n")
        elif command == "readto":
            # An empty line stores an *empty* block rather than one empty
            # line: the cat example loops on ``skipif`` ("at least one
            # line") and terminates on empty input, which only happens if
            # a blank line leaves nothing behind.
            value = self.io.input_str()
            self._replace(rest, [value] if value else [])
        elif command == "inject":
            self._inject(rest)
        elif command == "skip":
            if rest:
                raise ValueError(f"skip takes no argument: {line}")
            self._skip()
            return
        elif command == "skipif":
            if len(self._contents(rest)) >= 1:
                self._skip()
                return
        elif command == "skipq":
            left, _, right = rest.partition(" ")
            right = right.strip()
            if not left or not right:
                raise ValueError(f"skipq takes two labels: {line}")
            if self._contents(left) == self._contents(right):
                self._skip()
                return
        # Anything else is a *data* line and executes as a no-op.  This is
        # forced by the wiki's truth machine: on the falling-through branch
        # control jumps the ``data`` block, lands on the ``0`` block's
        # delimiter, and flows through the bare ``0`` inside it.  It is
        # also the language's namesake working as designed -- ``readto``
        # and ``inject`` write arbitrary text into blocks that control can
        # later flow through, so the dispatch is "a command word runs,
        # everything else is text".

        self.ind += 1

    def _inject(self, rest: str) -> None:
        """Run ``inject X=S/R``: substitute ``S`` with ``R`` in block ``X``."""
        name, sep, expression = rest.partition("=")
        if not sep:
            raise ValueError(f"inject needs a label and a regex: {rest}")
        # The pattern cannot contain a slash, so the *first* slash is the
        # separator and everything after it is the replacement -- which
        # may itself contain slashes.
        pattern, sep, replacement = expression.partition("/")
        if not sep:
            raise ValueError(f"inject needs a replacement: {rest}")
        try:
            body = [
                re.sub(pattern, replacement, text)
                for text in self._contents(name.strip())
            ]
        except re.error as err:
            raise HaltError(f"invalid regex: {pattern}") from err
        self._replace(name.strip(), body)


def run(code: str | list[str], io: IO) -> None:
    """Run an Inject program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
