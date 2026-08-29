"""Run the generated reading programs on the SHIPPED interpreter."""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck as interp

from reading_gen import reading_joint  # noqa: E402


def build(t):
    n = M._validate_truth_table(t)
    frontier = M._BASE + n * M._SPAN + 6
    base = reading_joint(n)
    M._clamp(base)
    for acc in range(9, frontier):
        hit = M._try_print(base, t, acc)
        if hit is not None:
            return hit.template()
    return None


class CountIO(ScriptedIO):
    def __init__(s, t):
        super().__init__(t)
        s.reads = 0

    def input_char(s, p="Input: "):
        s.reads += 1
        return super().input_char(p)


print("n=1, run on the real interpreter:")
allok = True
for t in ["01", "10", "00", "11"]:
    prog = build(t)
    if prog is None:
        print(f"  {t}: NO PROGRAM")
        allok = False
        continue
    row = []
    for bit in "01":
        io = CountIO(f"{bit}\n")
        m = interp._Machine(prog, io)
        try:
            while not m.halted:
                m.step()
            out = io.getvalue()
        except EOFError:
            out = "<EOF>"
        want = t[int(bit)]
        ok = out == want
        allok &= ok
        row.append(f"in={bit} out={out!r} want={want} reads={io.reads} {'OK' if ok else 'FAIL'}")
    print(f"  table {t}: " + " | ".join(row))
print()
print("all correct:", allok)
