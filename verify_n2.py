"""Build every two-input table and RUN it on the shipped interpreter."""
import sys
import time
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck as interp
from build3 import build


class CountIO(ScriptedIO):
    def __init__(s, t):
        super().__init__(t)
        s.reads = 0

    def input_char(s, p="Input: "):
        s.reads += 1
        return super().input_char(p)


def check(prog, table):
    """Run all four inputs; return (ok, details)."""
    details = []
    ok = True
    for combo, bits in enumerate(["00", "01", "10", "11"]):
        io = CountIO("".join(f"{b}\n" for b in bits))
        m = interp._Machine(prog, io)
        try:
            while not m.halted:
                m.step()
            out = io.getvalue()
        except EOFError:
            out = "<EOF>"
        want = table[combo]
        good = out == want
        ok &= good
        details.append(f"{bits}->{out!r}({'ok' if good else 'WANT ' + want}) r={io.reads}")
    return ok, details


built = passed = 0
for i in range(16):
    t = format(i, "04b")
    t0 = time.time()
    prog, how = build(t)
    dt = time.time() - t0
    if prog is None:
        print(f"  {t}: no program            {dt:5.1f}s", flush=True)
        continue
    built += 1
    ok, details = check(prog, t)
    passed += ok
    print(f"  {t}: len={len(prog):4d} {how:6s} {'PASS' if ok else 'FAIL'} {dt:5.1f}s  "
          + " ".join(details), flush=True)

print(f"\nbuilt {built}/16, verified {passed}/16")
