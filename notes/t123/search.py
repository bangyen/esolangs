r"""Search for an embed + common suffix that prints a two-input table.

Every instantiation runs the *same* code, so a parameterized program cannot
branch on its inputs the way a reading one would: the rows must already
differ in (pointer, tape) after the embed, and one shared suffix must carry
each row to its own answer byte.

The search is breadth-first over suffixes in ``1``/``2``, with three
pruning rules:

* a row that touches the read position is dead (a parameterized program
  must not consume stdin);
* a row that prints anything other than its table entry is dead;
* a row that has already printed its entry must print nothing further.

``3`` is left out of the suffix alphabet.  It is genuinely useful -- the
length-7 selector needs it -- but its jump target depends on the positions
of every other ``3``, so it cannot be appended one character at a time
against a fixed simulation.  A ``3``-bearing search would need
whole-template re-simulation against the shipped interpreter, which is not
done here.
"""

from collections import deque

from gen import _Joint

ANSWER = {0: "0", 1: "1"}


def embed_layouts(n, extras):
    """Yield layouts placing each ``{Xi}`` once, with optional filler."""
    if n == 2:
        for pre in extras:
            for mid in extras:
                for post in extras:
                    yield [pre, 0, mid, 1, post] if pre else [0, mid, 1, post]
    else:
        raise ValueError("only n == 2 is explored here")


def build(n, layout):
    """Emit a layout, returning the joint or None if a row died."""
    j = _Joint(n)
    for item in layout:
        if isinstance(item, int):
            j.emit_setter(item)
        elif item:
            j.emit(item)
    if any(m.dead for m in j.ms):
        return None
    return j


def solved(j, want):
    """Whether every row has printed exactly its answer."""
    return all(m.out == [ANSWER[w]] for m, w in zip(j.ms, want, strict=True))


def viable(j, want):
    """Whether every row is still consistent with its answer."""
    for m, w in zip(j.ms, want, strict=True):
        if m.dead:
            return False
        if len(m.out) > 1:
            return False
        if m.out and m.out[0] != ANSWER[w]:
            return False
    return True


def search_suffix(j0, want, max_len):
    """Breadth-first search over 1/2 suffixes for one that prints the table."""
    queue = deque([(j0, "")])
    seen = set()
    while queue:
        j, suffix = queue.popleft()
        if solved(j, want):
            return suffix
        if len(suffix) >= max_len:
            continue
        for ch in "12":
            nxt = j.fork()
            nxt.emit(ch)
            if not viable(nxt, want):
                continue
            key = tuple((m.pos, m.byte(), tuple(m.out)) for m in nxt.ms)
            if key in seen:
                continue
            seen.add(key)
            queue.append((nxt, suffix + ch))
    return None
