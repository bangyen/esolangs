import sys
from collections import deque

sys.path.insert(
    0,
    "/Users/bangyen/Documents/repos/esolangs/.claude/worktrees/"
    "minifuck-parameterized-boolean/src",
)

ALPHA = "<[x."


class Sim:
    """Replicate _Machine.step without needing code up-front."""

    __slots__ = ("tape", "ptr", "out", "dead", "skip")

    def __init__(self):
        self.tape = [0] * 8
        self.ptr = 0
        self.out = []
        self.dead = False
        self.skip = False

    def copy(self):
        s = Sim.__new__(Sim)
        s.tape = list(self.tape)
        s.ptr = self.ptr
        s.out = list(self.out)
        s.dead = self.dead
        s.skip = self.skip
        return s

    def key(self):
        return (tuple(self.tape), self.ptr, tuple(self.out), self.dead, self.skip)

    def exec(self, ins):
        if self.dead:
            return
        if self.skip:
            self.skip = False
            return
        if ins == "<":
            if self.ptr:
                self.ptr -= 1
        elif ins in ".[":
            self.ptr += 1
            if self.ptr + 1 >= len(self.tape):
                self.tape.append(0)
            self.tape[self.ptr] ^= 1
            if ins == ".":
                n = int("".join(map(str, self.tape[:8])), 2)
                if n:
                    self.out.append(chr(n))
                else:
                    self.dead = True  # would read input -> forbidden
            elif not self.tape[self.ptr]:
                self.tape[self.ptr + 1] ^= 1
                self.skip = True


def setter(bit):
    return "[<" if bit else "xx"


def search(table, n=2, maxlen=24):
    """BFS over suffix programs; prefix is the embed of the bits."""
    rows = []
    for row in range(2**n):
        bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
        s = Sim()
        for b in bits:
            # ``[<``/``xx`` writes the bit at ptr+1 without moving; the two
            # ``[`` step the pointer past the cell just written so the next
            # bit lands in a fresh cell instead of overwriting this one.
            for ch in setter(b) + "[[":
                s.exec(ch)
        rows.append((s, table[row]))
    start = tuple(r[0] for r in rows)
    want = [r[1] for r in rows]
    seen = {tuple(s.key() for s in start)}
    q = deque([(start, "")])
    while q:
        states, prog = q.popleft()
        if len(prog) >= maxlen:
            continue
        for ch in ALPHA:
            new = []
            for s in states:
                c = s.copy()
                c.exec(ch)
                new.append(c)
            if any(s.dead for s in new):
                continue
            k = tuple(s.key() for s in new)
            if k in seen:
                continue
            seen.add(k)
            p = prog + ch
            if all(
                len(s.out) == 1 and s.out[0] == chr(48 + int(w))
                for s, w in zip(new, want)
            ):
                return p, len(seen)
            if all(len(s.out) == 0 for s in new):
                q.append((tuple(new), p))
    return None, len(seen)


if __name__ == "__main__":
    import time

    maxlen = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    tables = {
        "NAND": "1110",
        "NOR": "1000",
        "XNOR": "1001",
        "AND": "0001",
        "OR": "0111",
        "XOR": "0110",
    }
    for name, t in tables.items():
        t0 = time.time()
        r, visited = search(t, maxlen=maxlen)
        print(f"{name} {t}: {r!r}  (visited={visited} {time.time() - t0:.1f}s)")
