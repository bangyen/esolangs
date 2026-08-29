"""Is the answer at a FIXED position, the way run_back's cell n is?

Extraction is legitimate in this repo when the generator determines where the
answer sits (run_back: "the generator puts the answer in cell n").  It would
NOT be legitimate to scan the output for whatever looks like the answer.

So: for the length-13 XNOR program, does every input emit the same NUMBER of
bytes, with the answer always last?  If the length varies by input, the
"last byte" is still well defined, but the output length itself leaks the
input -- worth knowing either way.
"""
import sys
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck

CODE = "[<..[<[<[<..."
TABLE = "1001"  # XNOR, indexed by the two bits

print(f"program {CODE!r}")
lengths = set()
for combo, bits in enumerate(["00", "01", "10", "11"]):
    io = ScriptedIO("".join(f"{b}\n" for b in bits))
    m = minifuck._Machine(CODE, io)
    while not m.halted:
        m.step()
    out = io.getvalue()
    lengths.add(len(out))
    want = TABLE[combo]
    print(f"  {bits}: {len(out)} bytes {[hex(ord(c)) for c in out]} "
          f"last={out[-1]!r} want={want} {'OK' if out[-1] == want else 'MISMATCH'}")

print()
print("  output length constant across inputs?", len(lengths) == 1, lengths)
print("  -> if False, the byte COUNT leaks the input even though the")
print("     last byte is the answer.")
