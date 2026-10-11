"""Compile a brainfuck program into a Line ``Node`` graph.

The drawing round-trips through :func:`extract.extract`/:func:`simulate.run`
to the same tape.  The mapping is 1:1 (``,`` -> ``i``, ``.`` -> ``o``;
compare per-call numeric values, not bytes) except ``[...]``: a loop is a
``?`` whose ``nonzero`` arm ends in a ``goto`` back to it and whose ``zero``
arm is what follows (``_layout`` never follows a ``?``'s ``.next``).
"""

from __future__ import annotations

from esolangs.tools.line.render import Node

_BF_TO_LINE = {"+": "+", "-": "-", "<": "<", ">": ">", ",": "i", ".": "o"}


def _nop() -> Node:
    """Build a two-node chain whose ops has no net effect on tape or pointer.

    A ``>`` node followed by ``<``; the ``goto`` attaches to the second, so
    the pointer is back before the jump.
    """
    out = Node(">")
    back = Node("<")
    out.next = back
    return out


def _control_tail(node: Node) -> Node:
    """Find the node where ``node``'s chain falls through to whatever follows it.

    The walk descends a ``?``'s ``zero`` arm, since the loop exits there; one
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
            # "[]" has no node to carry the `goto`, which `_layout` checks
            # only on a straight-through node's own step.  It is an infinite
            # spin on a nonzero cell anyway, so it is rejected.
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
        # A comment character is not a node.
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
