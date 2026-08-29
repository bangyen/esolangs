# Which parameterized boolean generators could read real input?

Method: decide from the **interpreter's op set**, not generator docstrings.
All 14 parameterized generators were mapped to their registry interpreter and
grepped for the exact input methods in `interpreters/io.py`
(`input_str` / `input_char` / `input_num`).

**Result: 12 of 14 make no input call at all. Two do — COD and Minifuck.**

| generator | interpreter | input call |
|---|---|---|
| `cod` | `grid_based.cod` | `input_num` |
| `minifuck` | `tape_based.minifuck` | `input_char` |
| the other 12 | (respective) | none |

The other 12 (`a_painter_ant`, `arrowqueue`, `back`, `bfpda`, `bio`,
`bitdeque`, `eval`, `lamfunc`, `minsky_swap`, `nocomment`, `ram0`, `wii2d`)
have no input mechanism, so the parameterized convention is the correct
design for them, not a workaround.

## COD — convertible (strongest candidate)

`tools/boolean/cod.py` says "COD has no input command". That is **factually
wrong** about the shipped interpreter: `...` — a vertical run of exactly three
dots touching the top or bottom edge — executes `cod.value = io.input_num()`.

Verified read-once-and-print program (a working COD cat):

```
~~.~~~~~~
~~.~~~~~~
>.....---
~~~~~~~~~
```

stdin `0` / `1` / `7` prints `0` / `1` / `7`, with exactly **1** read each.

**This is wiki-spec conformant**, verified against
<https://esolangs.org/wiki/COD>. The spec's prose: the `...` (three periods)
command "must be touching either the top or bottom edge of the program,
without any waves or other characters in between, otherwise it will be
completely ignored" — exactly what `_edge_dot_cells` enforces. Output `---`
is likewise spec'd as three dashes touching the left or right edge.

Geometry rules established empirically:

- the dot run must be **exactly 3** and capped by a wall; a 4th dot voids it
  (`_edge_dot_cells`) — this is the spec's "without any waves or other
  characters in between"
- a cod **crossing horizontally** reads exactly once. Note this interpreter
  treats each of the three dot cells as a read cell, so a cod entering more
  than one of them reads more than once; the spec describes `...` as a
  *single* command, so the per-cell behaviour is implementation detail rather
  than spec, and a generator should not lean on it
- extra reads come from the cod bouncing in dead ends; an unbroken corridor
  into an edge `---` printer terminates cleanly after one read

### Stale caveat in the interpreter docstring

`interpreters/grid_based/cod.py` states the wiki's truth-machine example
"uses a single `.` for input rather than `...`" and so "does not read input as
written". That is **wrong about the example it cites**: the wiki's
truth-machine has a genuine three-dot run in column 2, rows 0-2, touching the
top edge, and this interpreter's own `_edge_dot_cells` detects it as a valid
input command. Worth correcting alongside the `cod.py` generator docstring.

COD's value is an unbounded signed integer, so the existing gauntlet /
fork-box decision-tree machinery has a real value to branch on, and
"each input read exactly once" is satisfiable by giving each input its own
crossing.

## Minifuck — convertible, with a storage question

`.` reads a byte, but only when cells 0–7 are all zero **after** its flip.

- One bit: `[<.` reads a bit with no spurious output and lands it in **cell 7**
  (ASCII `'0'`=00110000, `'1'`=00110001) — the cell the existing notes already
  call the print-orientation cell.
- Two bits: reading `'1'` leaves cell 7 set, so a naive second `.` prints
  instead of reading. The way through is the `[`-cascade: flipping cell 2 to 0
  triggers the bonus flip of cell 3, clearing **both** ASCII bits and
  re-zeroing the pool.

**27 programs read twice on a uniform, input-independent schedule** for all
four 2-bit inputs, e.g. `[<..[<[<[<..` (length 12). The final tape depends on
both bits, so bit 1's information survives read 2.

Open question before building: read 2 overwrites cells 0–7, and bit 1 lives in
cell 7, so bit 1 likely has to be banked in cells >= 8 first (per the
rightward-flow constraint). That is the design problem — not a wall.

> Caution: an earlier sweep here concluded "no program reads twice, exhaustive
> to length 13". That was a **harness artifact** — `input_char` reads a whole
> *line*, so `ScriptedIO("01")` supplied one line and every genuine two-read
> program EOF'd and was discarded. Feed one bit per line (`"0\n1\n"`), and
> count reads by subclassing `input_char`. The uniform two-read programs also
> start at length 12, just past a length-11 sweep.

## Second tier — unresolved

`docs/wiki-specs.json` stores only content hashes, not spec text, so "does a
language's wiki spec define an input command the interpreter never
implemented?" cannot be answered from this repo. Answering it needs the wiki
pages themselves.

## Doc fix, independent of any conversion

`src/esolangs/tools/boolean/cod.py` line 3 claims "COD has no input command",
contradicting its own interpreter. Worth correcting even if the generator
stays parameterized.
