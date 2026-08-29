r"""Search for a table using the displacement-neutral ``12``/``21`` setter.

``setter2.py`` shows this setter keeps every row at the same pointer
position, so the shared suffix acts on all four rows in lockstep and they
differ only in tape contents -- which is what the earlier ``1``/``2`` setter
could not provide, since its members displace the pointer oppositely.

Rows print together under this setter, so the answer must be carried by the
*bits*: a row prints its byte when the shared walk brings the common
pointer to the write position, and the byte differs per row because
different cells were flipped during the embed.
"""

import sys
from collections import deque

from gen import _Joint
from search import ANSWER, viable

NAMES = {
    "0001": "AND", "0111": "OR", "0110": "XOR", "1110": "NAND",
    "1000": "NOR", "1001": "XNOR", "0011": "b0", "0101": "b1",
    "1100": "NOT b0", "1010": "NOT b1", "0000": "const0", "1111": "const1",
    "0100": "b1 AND NOT b0", "0010": "b0 AND NOT b1",
    "1011": "NOT b1 OR b0", "1101": "NOT b0 OR b1",
}

FILLERS = ["", "2", "22", "222", "1", "12", "21", "121", "212"]


def embeds(n=2):
    """Yield joints for paired-setter embeds, clear of the IO positions."""
    for lead in range(6, 13):
        for mid in FILLERS:
            for post in FILLERS:
                j = _Joint(n)
                j.emit("2" * lead)
                j.emit_pair(0)
                if mid:
                    j.emit(mid)
                j.emit_pair(1)
                if post:
                    j.emit(post)
                if any(m.dead or m.out for m in j.ms):
                    continue
                yield j


def search(j0, want, max_len):
    """BFS over 1/2 suffixes for one printing the table."""
    queue = deque([(j0, "")])
    seen = set()
    while queue:
        j, suffix = queue.popleft()
        if all(m.out == [ANSWER[w]]
               for m, w in zip(j.ms, want, strict=True)):
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


def main():
    """Search every table with the paired setter."""
    max_len = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    pool = list(embeds())
    lines = [f"{len(pool)} paired-setter embeds, suffix limit {max_len}"]

    def log(text):
        """Print and persist progress."""
        print(text, flush=True)
        lines.append(text)
        with open("pair_results.txt", "w") as handle:
            handle.write("\n".join(lines) + "\n")

    log(lines[0])
    found = {}
    for tbl in sorted(NAMES):
        want = [int(c) for c in tbl]
        for j in pool:
            suffix = search(j.fork(), want, max_len)
            if suffix is not None:
                found[tbl] = j.template() + suffix
                break
        mark = f"<- {found[tbl]!r}" if tbl in found else "-- not found"
        log(f"  {tbl} {NAMES[tbl]:14} {mark}")
    log(f"reached {len(found)}/16")


if __name__ == "__main__":
    main()
