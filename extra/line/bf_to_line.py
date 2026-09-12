r"""Compile a brainfuck program into a Line ``Node`` graph."""

from __future__ import annotations

from render import Node

_BF_TO_LINE = {"+": "+", "-": "-", "<": "<", ">": ">", ",": "i", ".": "o"}


def _nop() -> Node:
    r"""Build a single node whose op has no net effect on tape or pointer."""
    out = Node(">")
    back = Node("<")
    out.next = back
    return out


def _control_tail(node: Node) -> Node:
    r"""Find the node where ``node``'s chain falls through to whatever."""
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
    r"""Parse brainfuck commands from ``pos`` until ``]`` or end of program."""
    if pos >= len(program):
        return None, pos
    ch = program[pos]
    if ch == "]":
        return None, pos + 1
    if ch == "[":
        body_head, pos = _parse(program, pos + 1)
        if body_head is None:
            # An empty loop body ("[]") has.
            # -- `Node.goto` is only.
            # step, after its op runs (see.
            # with nothing at all between.
            # reconnection.
            # a nonzero cell to begin with.
            # rejected rather than forcing.
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
        # A comment character: not.
        # level still needs parsing and.
        return rest, pos
    node = Node(op, next=rest)
    return node, pos


def bf_to_line(program: str) -> Node:
    r"""Compile a brainfuck ``program`` into a Line :class:`render.Node`."""
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
