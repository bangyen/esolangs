"""Shared bracket-matching helper for the interpreters.

Every interpreter that rejects an unbalanced program *statically* reports it
the same way: ``unmatched '<char>' at position <i>``, as a
:class:`ValueError`.  The wording is one string built here rather than a
sentence each interpreter spells for itself, so a reader who has seen one
rejection has seen them all and a test can assert the whole message instead
of the word "unmatched" inside it.

The characters are a parameter because the languages disagree about which
glyphs open and close a loop -- ``[``/``]`` for the brainfuck family, ``l``
for Home Row, ``{``/``}`` for BIO -- while agreeing about everything else.

Two kinds of interpreter deliberately do *not* come through here:

- those that scan for the partner at *run* time (Circlefuck walks the ring,
  bit~ walks the pool), which have no position to name when the walk falls
  off the end -- the scan knows only that it failed; and
- those for which an unmatched bracket is not an error at all.  Painfuck's
  unmatched ``a`` on a zero cell skips to the end and halts, Rotfuck's
  unbalanced source is legal as long as it never runs, and Unsquare raises
  its ``HaltError`` mid-run.  Rejecting those statically would change which
  programs are valid, which is a language change and not a message one.
"""

from __future__ import annotations


def unmatched(char: str, position: int) -> ValueError:
    """Build the rejection every static bracket scan raises.

    Spelled once so the interpreters cannot drift apart in wording; the
    scans that find their own unbalanced bracket raise this rather than
    formatting a near-identical sentence each.
    """
    return ValueError(f"unmatched {char!r} at position {position}")


def match_brackets(
    code: str, open_char: str = "[", close_char: str = "]"
) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Raises :class:`ValueError` if the brackets are unbalanced.  An
    unmatched closer is reported at its own position and an unmatched
    opener at the *last* one still waiting, which is the innermost
    unclosed loop.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == open_char:
            stack.append(i)
        elif char == close_char:
            if not stack:
                raise unmatched(close_char, i)
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise unmatched(open_char, stack[-1])
    return res
