"""Compile a brainfuck program into a Line ``Node`` graph.

Build with ``esolangs.tools.tape.brainfuck``, compile here, render with
:func:`render.render`, and the drawing round-trips through
:func:`extract.extract`/:func:`simulate.run` to the same tape.  The
mapping is 1:1 (``,`` -> ``i``, ``.`` -> ``o``; compare per-call numeric
values, not bytes) except ``[...]``: Line expresses repetition only by a
stroke reconnecting, so a loop is a ``?`` whose ``nonzero`` arm ends in a
``goto`` back to it and whose ``zero`` arm is what follows.  ``_layout``
never follows a ``?``'s ``.next``, so :func:`_parse` builds the
continuation as ``.zero``.
"""

from __future__ import annotations

from .render import Node

_BF_TO_LINE = {"+": "+", "-": "-", "<": "<", ">": ">", ",": "i", ".": "o"}


def _nop() -> Node:
    """Build a single node whose op has no net effect on tape or pointer.

    A ``>`` node followed by ``<``; the ``goto`` attaches to the second, so
    the pointer is back before the jump.
    """
    out = Node(">")
    back = Node("<")
    out.next = back
    return out


def _control_tail(node: Node) -> Node:
    """Find the node where ``node``'s chain falls through to whatever follows it.

    A ``?`` is not a dead end: a loop's exit is its ``zero`` arm, so the walk
    descends there (without this, code after a nested loop was wired as the
    inner fork's ignored ``goto`` and the outer loop-back dropped).  A ``?``
    with no ``.zero`` gets a :func:`_nop` placeholder to carry the ``goto``.
    """
    while True:
        if node.op == "?":
            if node.zero is None:
                node.zero = _nop()
            node = node.zero
        elif node.next is not None:
            node = node.next
        else:
            return node


def _parse(program: str, pos: int) -> tuple[Node | None, int]:
    """Parse brainfuck commands from ``pos`` until ``]`` or end of program.

    Returns ``(head, next_pos)``; ``head`` is ``None`` for a level with no
    commands.  A ``[...]`` recurses into its body first, then for everything
    after the ``]``, wiring that as the fork's ``.zero``.
    """
    if pos >= len(program):
        return None, pos
    ch = program[pos]
    if ch == "]":
        return None, pos + 1
    if ch == "[":
        body_head, pos = _parse(program, pos + 1)
        if body_head is None:
            # An empty loop body ("[]") has no node to hang a `goto` off of
            # -- `Node.goto` is only checked on a straight-through node's own
            # step, after its op runs (see render.py's `_layout`), so a fork
            # with nothing at all between visits has no way to express the
            # reconnection.  Brainfuck's own "[]" is a real infinite spin on
            # a nonzero cell to begin with (not a useful program), so this is
            # rejected rather than forcing degenerate geometry to represent
            # it.
            raise ValueError(
                "an empty loop body ('[]') cannot be compiled to Line: a "
                "loop-back needs at least one node to carry the 'goto' back "
                "to the fork"
            )
        body_tail = _control_tail(body_head)
        fork = Node("?")
        body_tail.goto = fork
        fork.nonzero = body_head
        fork.zero, pos = _parse(program, pos)
        return fork, pos
    op = _BF_TO_LINE.get(ch)
    rest, pos = _parse(program, pos + 1)
    if op is None:
        # A comment character: not itself a node, but the rest of this
        # level still needs parsing and returning.
        return rest, pos
    node = Node(op, next=rest)
    return node, pos


def bf_to_line(program: str) -> Node:
    """Compile a brainfuck ``program`` into a Line :class:`render.Node` graph.

    Raises :class:`ValueError` on unbalanced brackets or a program with no
    recognized commands.
    """
    depth = 0
    for ch in program:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                raise ValueError("unmatched ']' with no matching '['")
    if depth:
        raise ValueError("unmatched '[' with no matching ']'")
    head, _pos = _parse(program, 0)
    if head is None:
        raise ValueError("brainfuck program has no recognized commands to compile")
    return head


if __name__ == "__main__":
    import sys

    from .render import render

    code = sys.argv[1] if len(sys.argv) > 1 else "++++++++[>++++++++<-]>+."
    out_path = sys.argv[2] if len(sys.argv) > 2 else "bf_line_out.png"
    render(bf_to_line(code)).save(out_path)
    print(f"wrote {out_path}")
