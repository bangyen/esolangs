"""Extract concrete 1/2-only programs printing exactly '0' and exactly '1'.

``bfs.py`` settles *that* every byte is printable; this reconstructs the
command string for a given byte and checks it against the shipped
interpreter, so the witness is executed rather than argued.
"""

from collections import deque

from lib import run

PMAX = 16


def moves(state):
    """Yield ``(command, next_state, printed)`` from ``state``."""
    pos, bits = state
    if -3 <= pos <= PMAX:
        nb = bits ^ (1 << (7 - pos)) if 0 <= pos <= 7 else bits
        npos = pos - 1
        if npos == -4:
            npos = 0
        yield "1", (npos, nb), None
    if pos == -2:
        yield "2", (0, bits), bits
    elif pos != -3 and pos < PMAX:
        yield "2", (pos + 1, bits), None


def shortest_printer(target):
    """Return the shortest 1/2-only program printing ``target`` then halting.

    After the print the pointer sits at 0, so the program still has to reach a
    negative position to halt cleanly at the end of the code; a single ``1``
    moves 0 -> -1, which is below zero and halts.
    """
    start = (0, 0)
    seen = {start: ""}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        code = seen[state]
        for cmd, nxt, out in moves(state):
            if out == target:
                return code + cmd + "1"  # print, then step below 0 to halt
            if nxt not in seen:
                seen[nxt] = code + cmd
                queue.append(nxt)
    return None


def main():
    """Print and verify a witness for each ASCII digit."""
    for ch in ("0", "1"):
        code = shortest_printer(ord(ch))
        out, status = run(code, "", limit=100000)
        ok = "OK" if (out == ch and status == "halt") else "MISMATCH"
        print(f"{ch!r}: len={len(code)} {code!r}")
        print(f"     interpreter -> output={out!r} status={status} [{ok}]")


if __name__ == "__main__":
    main()
