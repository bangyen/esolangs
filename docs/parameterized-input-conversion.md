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
- **the approach angle decides the read count.** This interpreter treats each
  of the three dot cells as its own read cell, so:

  | approach | reads |
  |---|---|
  | crossing horizontally (one cell entered) | 1 |
  | turning *into* the column, then exiting to a printer | **3** |
  | turning in with a dead end above | loops until EOF |

  The spec describes `...` as a **single** input command, so three reads for
  one command is an interpreter artifact, not COD semantics. A generator must
  therefore route every input crossing **horizontally** — "each input read
  exactly once" is satisfiable, but only under that discipline, and it is a
  constraint on the layout rather than something COD gives for free.
- extra reads come from the cod bouncing in dead ends; an unbroken corridor
  into an edge `---` printer terminates cleanly after one read
- **whitespace is open water.** `_is_open` is `cell != "~"`, so spaces used as
  visual padding are navigable, not walls. The wiki truth-machine relies on
  this (column 1 is spaces at rows 4-7). Any generated grid must pad with `~`,
  not spaces, or cods will swim through the margins.

### Stale caveat in the interpreter docstring

`interpreters/grid_based/cod.py` states the wiki's truth-machine example
"uses a single `.` for input rather than `...`" and so "does not read input as
written". That is **wrong about the example it cites**: the wiki's
truth-machine has a genuine three-dot run in column 2, rows 0-2, touching the
top edge, and this interpreter's own `_edge_dot_cells` detects it as a valid
input command. Worth correcting alongside the `cod.py` generator docstring.

There *are* dots in the columns either side of the run, but the spec's
"without any waves or other characters in between" constrains the run along
its own column; column 2 reads `. . . ~ ~ ~ ~ ~`, and the verdict is stable
whether the ragged rows are padded with spaces or with `~`.

COD's value is an unbounded signed integer, so the existing gauntlet /
fork-box decision-tree machinery has a real value to branch on, and
"each input read exactly once" is satisfiable by giving each input its own
crossing.

## Minifuck — convertible, verified end to end

`.` reads a byte, but only when cells 0–7 are all zero **after** its flip.

**Wiki-spec conformant**, verified against <https://esolangs.org/wiki/Minifuck>.
The spec's own command list matches the interpreter on every op relied on here:

- `.` — "Move to next bit and invert it and output letter stored in first 8
  bits, **if none then input**" — i.e. print when the pool holds something,
  read when it is empty. That is exactly the pool-is-zero read condition.
- `[` — "Move to next bit and invert it, skip next instruction and invert next
  bit if zero" — the `[`-cascade used below to clear both ASCII bits.
- `<` — "Same as Brainfuck" (move left); storage is a right-infinite tape of
  binary bits.

The spec's example program `<[<.[<.` runs correctly on this interpreter
(reads one bit, echoes it), so the shipped implementation agrees with the
wiki on its own sample.

- One bit: `[<.` reads a bit with no spurious output and lands it in **cell 7**
  (ASCII `'0'`=00110000, `'1'`=00110001) — the cell the existing notes already
  call the print-orientation cell.
- Two bits: reading `'1'` leaves cell 7 set, so a naive second `.` prints
  instead of reading. The way through is the `[`-cascade: flipping cell 2 to 0
  triggers the bonus flip of cell 3, clearing **both** ASCII bits and
  re-zeroing the pool.

**54 programs read twice on a uniform, input-independent schedule** at length
12, e.g. `[<..[<[<[<..`, and at length 13 **54 of them separate all four
2-bit inputs by output alone** — the property a boolean generator actually
needs, since it must *print* the answer.

Worked example, `[<..[<[<[<...` (length 13):

| input | output bytes | last byte |
|---|---|---|
| `00` | `10 31 31` | `'1'` |
| `01` | `10 30 30` | `'0'` |
| `10` | `11 01 30` | `'0'` |
| `11` | `11 01 31` | `'1'` |

The final byte is clean ASCII and is exactly **XNOR** of the two input bits.
So Minifuck computes a real two-input boolean function from actual stdin.

The banking question is **resolved, and the answer is that no banking is
needed**: across all 27 uniform two-read programs of the `[<..` shape, nothing
in cells >= 8 depends on bit 1 (checked directly). Bit 1 is never stored past
cell 7 — read 2 does overwrite cell 7, but bit 1's influence has already been
committed to the *output stream* by then, which read 2 cannot touch. The
earlier worry that bit 1 "must be banked in cells >= 8" assumed the answer had
to survive on the tape; it survives in the output instead.

Remaining work for a real generator is scale, not feasibility: these are
n=2 results, and whether the read schedule stays uniform and
output-separating for n>=3 is unmeasured.

> Caution: an earlier sweep here concluded "no program reads twice, exhaustive
> to length 13". That was a **harness artifact** — `input_char` reads a whole
> *line*, so `ScriptedIO("01")` supplied one line and every genuine two-read
> program EOF'd and was discarded. Feed one bit per line (`"0\n1\n"`), and
> count reads by subclassing `input_char`. The uniform two-read programs also
> start at length 12, just past a length-11 sweep, and the *output-separating*
> ones start at length 13 — two separate off-by-one cliffs, each of which
> would have produced a false wall on its own.

## Second tier — unresolved

`docs/wiki-specs.json` stores only content hashes, not spec text, so "does a
language's wiki spec define an input command the interpreter never
implemented?" cannot be answered from this repo. Answering it needs the wiki
pages themselves.

## Doc fix, independent of any conversion

`src/esolangs/tools/boolean/cod.py` line 3 claims "COD has no input command",
contradicting its own interpreter. Worth correcting even if the generator
stays parameterized.
