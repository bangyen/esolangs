"""Compile a brainfuck program into a Line ``Node`` graph.

This is the bridge that lets this repo's existing brainfuck text/boolean
generators (``esolangs.tools.text.tape.brainfuck``,
``esolangs.tools.boolean.tape.brainfuck``) target Line: build a brainfuck
program with either generator, compile it here into a :class:`render.Node`
graph, hand that to :func:`render.render` for a real Line drawing, and the
result round-trips through :func:`extract.extract`/:func:`simulate.run` back
to the same tape brainfuck would produce.

The mapping is close to 1:1, matching Line's own opcode set to brainfuck's:
``+``/``-``/``<``/``>`` unchanged, ``,`` -> ``i`` (Line's "read a number into
the current cell"), ``.`` -> ``o`` ("print the current cell as a number") --
per :mod:`simulate`'s own module docstring for what each Line opcode does.
Brainfuck's per-character I/O (raw bytes) and Line's per-call I/O (whole
numbers, see :mod:`simulate`'s ``IO``) differ, so a caller comparing output
against a real brainfuck interpreter must compare per-``,``/``.`` numeric
values, not raw bytes -- not a compilation gap, just the two languages'
documented I/O conventions being different in kind.

The one real compilation problem is ``[...]``: brainfuck's loop has no
1:1 Line opcode, since Line only expresses repetition by a drawn stroke
physically reconnecting to an earlier point (see ``render.py``'s ``Node.goto``
and ``WIP.md``'s "Runtime simulation" section for the full backstory of how
that was discovered).  Compiling ``[...]`` is exactly the shape ``Node.goto``
was built for: a ``?`` fork whose ``nonzero`` arm is the loop body ending in
a node whose ``goto`` points back at the fork, and whose ``zero`` arm is
whatever follows the loop.  ``render.py``'s ``_layout`` never uses a ``?``
node's ``.next`` at all (a fork is a terminal in its own straight-through
chain -- the only way past it is through ``.zero``/``.nonzero``, matching
the wiki's real T-branch shape), so :func:`_parse` builds a ``?``'s
continuation as its ``.zero`` child directly rather than chaining through
``.next`` the way every other command does.
"""

from __future__ import annotations

from render import Node

_BF_TO_LINE = {"+": "+", "-": "-", "<": "<", ">": ">", ",": "i", ".": "o"}


def _nop() -> Node:
    """Build a single node whose op has no net effect on tape or pointer.

    Used only as a placeholder to carry a ``goto`` where no real node exists
    to hang it on -- see :func:`_control_tail`.  ``>`` alone would move the
    pointer, so this cannot be a single opcode; instead it is one ``Node``
    whose op is ``>`` immediately followed (via ``.next``) by ``<``, which
    ``render.py`` lays out as two ordinary kinks moving the pointer right
    then back left.  The ``goto`` always attaches to the *second* of the two
    (see call site), so the pointer is back at its original cell by the time
    the jump fires -- net zero effect, matching what "nothing here" should
    mean.
    """
    out = Node(">")
    back = Node("<")
    out.next = back
    return out


def _control_tail(node: Node) -> Node:
    """Find the node where ``node``'s chain falls through to whatever follows it.

    For an ordinary straight-through chain this is just the last node
    reached by ``.next``.  A ``?`` fork is not a dead end for this purpose,
    though, even though ``render.py``'s own ``_layout`` never follows a
    fork's ``.next`` (see module docstring) -- once *entered* on either arm,
    a brainfuck loop's exit path is exactly its ``zero`` arm (the loop runs
    while nonzero and falls through once the cell reads zero), so a nested
    loop's own control flow "continues" through its ``.zero`` child, not
    ``.next``.  Confirmed necessary: without descending into ``.zero`` here,
    the code following a nested loop gets wired as the *inner* fork's own
    ``goto`` target (silently ignored -- ``Node.goto`` is only checked on a
    straight-through node's step, never a ``?`` node's) instead of the
    *outer* loop's, dropping the outer loop-back entirely.

    If this walk bottoms out at a ``?`` node with no ``.zero`` at all (its
    loop is the last thing in its own level, so there is nothing there yet),
    a placeholder :func:`_nop` is installed as that ``.zero`` and its own
    tail returned instead -- a plain ``?`` node cannot carry ``goto`` itself
    (see above), so *some* real node must exist there for the caller to
    attach one to.
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

    Returns ``(head, next_pos)``: ``head`` is the built chain's first node
    (``None`` if this level had no recognized commands at all, e.g. an
    all-comment tail or an empty loop body), and ``next_pos`` is the index
    just past the ``]`` that stopped this call (or ``len(program)`` at top
    level).  A ``[...]`` recurses into its own body first (so an inner loop
    is fully built, including its own ``goto``, before anything past it is
    parsed -- the natural innermost-first order for nested loops), then
    recurses *again* for everything after the matching ``]`` at this same
    level, wiring that second recursion's result as the fork's ``.zero``
    rather than continuing the straight-through chain the way every other
    command does (see module docstring for why ``.next`` cannot carry a
    ``?`` node's continuation).
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

    Raises :class:`ValueError` if brackets are unbalanced (an unmatched
    ``[`` runs off the end of the program with no closing ``]``, or a stray
    ``]`` with no matching ``[``) or if the program contains no recognized
    commands at all (:func:`render.render` requires at least one node to lay
    out; an all-comment program has nothing to compile).
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

    from render import render

    code = sys.argv[1] if len(sys.argv) > 1 else "++++++++[>++++++++<-]>+."
    out_path = sys.argv[2] if len(sys.argv) > 2 else "bf_line_out.png"
    render(bf_to_line(code)).save(out_path)
    print(f"wrote {out_path}")
