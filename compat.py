"""What does the embed leave, and can a read-gadget prologue reproduce it?

The parameterized path writes each bit with `_set_bit` ("[<" for 1, "xx" for
0) at `_BASE`-ish cells, then the tree+endgame reads them back.  A reading
generator must arrive at the SAME joint state, but with the bits having come
from stdin instead of from the program text.
"""
import sys
sys.path.insert(0, "src")
from esolangs.tools.boolean.minifuck import _embed, _BASE, _SPAN

for n in (1, 2):
    j = _embed(n)
    tpl = "".join(j.parts)
    print(f"n={n} template={tpl!r}")
    print(f"   length {len(tpl)}")
    for row, m in zip(j.rows, j.ms):
        cells = m.tape[_BASE - 2:_BASE + n * _SPAN + 2]
        print(f"   row {row} ptr={m.ptr} cells[{_BASE-2}:{_BASE+n*_SPAN+2}]={cells}")
    print()
