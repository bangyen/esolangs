"""Exact printability of each byte by a 1/2-only 123 program, via state BFS.

Enumerating programs by length cannot settle printability -- ``docs/walls.md``
stopped at length 8 and concluded no program prints exactly ``'0'``, but such
programs exist at length 14.  Searching *machine states* instead settles it
exactly.

With no ``3`` in the program there is no control flow, so a 1/2-only program
is a straight-line walk and the reachable configurations form a finite graph:
the state is the pointer position together with the eight bits at locations
0-7.  Locations outside 0-7 are inert for output (``byte()`` reads only 0-7)
but the pointer must be tracked over them, so positions are tracked over the
range the walk can actually occupy before returning.

A ``2`` at -2 prints ``byte()``; the question "which bytes can be printed as
a program's *only* output, then halt cleanly" is then reachability of a state
whose pointer is -2 with the desired byte, plus a tail that halts.
"""

from collections import deque

# The pointer lives in [-3, PMAX]; a 1 at -3 wraps (-4 -> 0).  Walking right
# past 7 is allowed (that is how high-order bits get set), but a walk that
# never comes back cannot print, so the range is capped generously.
PMAX = 16


def step_states(state):
    """Yield ``(next_state, printed_byte)`` for commands ``1`` and ``2``."""
    pos, bits = state
    # command '1': flip the bit under the pointer, then move left (wrap -4->0)
    if -3 <= pos <= PMAX:
        new_bits = bits
        if 0 <= pos <= 7:
            new_bits = bits ^ (1 << (7 - pos))
        npos = pos - 1
        if npos == -4:
            npos = 0
        yield (npos, new_bits), None
    # command '2': read at -3, write at -2, else move right
    if pos == -2:
        yield (0, bits), bits  # prints byte(), resets pointer to 0
    elif pos == -3:
        pass  # a read; excluded from the 1/2-only *constant* question
    elif pos < PMAX:
        yield (pos + 1, bits), None


def main():
    """BFS from the blank tape; report which bytes are printable exactly once."""
    start = (0, 0)
    seen = {start}
    queue = deque([start])
    printable = {}
    while queue:
        state = queue.popleft()
        for nxt, out in step_states(state):
            if out is not None and out not in printable:
                printable[out] = True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    print(f"reachable states: {len(seen)}")
    print(f"printable bytes: {len(printable)}")
    for name, byte in (("'0' (48)", 48), ("'1' (49)", 49)):
        print(f"  {name}: {'PRINTABLE' if byte in printable else 'NO'}")
    missing = [b for b in range(256) if b not in printable]
    print(f"bytes never printable: {len(missing)}", missing[:20])


if __name__ == "__main__":
    main()
