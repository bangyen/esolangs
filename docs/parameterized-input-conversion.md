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

> **This program is contract-invalid**, and the XNOR claim above needs that
> caveat: it emits three bytes including `\x10`/`\x11` junk, and the XNOR only
> appears if you post-select the last one. The boolean contract wants the
> program's whole output to be `"0"` or `"1"` exactly. Every `.` firing on a
> nonzero pool prints, so a valid program may use only `[` and `<` between its
> reads and a single final print. This does **not** contradict walls.md's
> Minifuck entry (XNOR unreachable in the read model): that wall is about
> clean-output programs, and its parity constraint lives "at the print stage".
> The working construction below is what actually clears the contract.

The banking question is **resolved, and the answer is that no banking is
needed**: across all 27 uniform two-read programs of the `[<..` shape, nothing
in cells >= 8 depends on bit 1 (checked directly). Bit 1 is never stored past
cell 7 — read 2 does overwrite cell 7, but bit 1's influence has already been
committed to the *output stream* by then, which read 2 cannot touch. The
earlier worry that bit 1 "must be banked in cells >= 8" assumed the answer had
to survive on the tape; it survives in the output instead.

### A working reading generator (n=1 shipped, n=2 in progress)

The contract-valid construction is a **prologue swap**, not a rewrite. Three
verified pieces, composed once per input:

| piece | code | what it does |
|---|---|---|
| READ | `[<.` | reads one bit, no junk output |
| GADGET | `[[[<[[[[[[[[[[[<<<[<[[[<` | re-zeroes the pool, banks the bit at cells 8/10 |
| SPLIT | `<[<` | turns the banked bit into a ±1 **pointer** offset |

GADGET came from a joint lockstep BFS over state *pairs* (both bits run the
same instruction stream — `[`'s skip diverges state, never the stream), so it
cannot produce the unrunnable paths a single-state BFS did. It leaves the pool
all-zero with the pointer identical for both bits, and the next `.`'s pre-flip
lands on cell 9, which is not the bank — so read 2 does not clobber read 1.

SPLIT is the bridge to the existing machinery: it reproduces `_set_bit`'s ±1
position encoding, so a bit read from stdin lands in the same representation
the embed/tree/endgame already consume. That means the whole downstream
pipeline (`_clamp`, `_try_print`, `_find_column`, `_find_parked`) works
**unchanged** — the only swap is a `_Joint` whose rows are advanced by the
reading prologue instead of by `_embed(n)`.

One gadget is not enough. `GADGET` was found by a BFS from the *blank-tape*
post-read state, so it re-zeroes only the **first** read; once bit 1 is banked
the tape is populated and the same string leaves cell 7 holding bit 2 as
`(0,1,0,1)`. `_endgame` requires all eight pool cells to be input-independent,
so every accumulator was rejected and n=2 came back 0/16. A second BFS
launched from the *actual* post-second-read joint state gives

    GADGET2 = <[[<<<[<<[<[<<<<<<<[

after which the pool is input-independent and the rows stay distinct.

### Results

**n=1 — 4/4.** All four tables build and run correctly on the shipped
interpreter, one read each. The constant tables still consume their input
(const-1 with empty stdin raises `EOFError`), satisfying the uniform-read rule.

**n=2 — 16/16 built, 16/16 verified**, clean `"0"`/`"1"` output and exactly
two reads for every table, constants included. Lengths 88-148; four tables
(`0101`, `0110`, `1001`, `1010`) come out of the cheap scan, the rest via the
column search at ~7s each.

That set includes **XNOR (`1001`), NAND (`1110`) and NOR (`1000`)** — the
tables walls.md records as unreachable in the runtime-read model, where the
model is capped at the 8 zero-preserving tables. No relaxed output convention
was needed: the wall's parity constraint sits at the print stage, and this
construction reaches the print stage with an input-independent pool.

**n=3 — blocked.** The prologue leaves only 4 of 8 rows distinct (the third
bit is lost) and emits a stray `' '`. `GADGET2` was searched from the n=2
frontier and does not generalize; n=3 would need its own frontier-launched
gadget, and possibly a per-level one.

### How to rebuild it

The prototype is not kept (notes/ is for work in progress, per `bc33fa8`), so
the reconstruction recipe is the deliverable:

1. Subclass `_Sim` so `.` on a zero pool consumes a scripted bit instead of
   setting `dead` — that flag exists to stop a *parameterized* program from
   reading, which is exactly what a reading generator must do.
2. Build a `_Joint` whose rows are advanced by
   `READ + GADGET1 + SPLIT` for input 0, then `READ + GADGET2` for each later
   input, each row consuming its own bit.
3. Hand that `_Joint` to the shipped ladder unchanged — `_clamp`,
   `_try_print`, `_find_column`. Nothing downstream needs to know the bits
   came from stdin rather than from `_set_bit`.

The load-bearing invariant is the one `_endgame` checks: all eight pool cells
must be input-independent when the endgame starts. Every failure in this
build traced back to violating it.

### Why the brute-force sweeps were the wrong instrument

Two length-capped sweeps here were dead ends worth recording. A sweep over
`<[.` programs is `3^n` candidates times four interpreter runs — ~6.4M runs at
length 13 — and it can only ever find *bare* programs. The working generator
composes a prologue with the tree and endgame into 88-148 characters, which no
length-capped enumeration reaches. Both real breakthroughs (GADGET, GADGET2)
came from **state BFS launched from the live frontier**, exploring hundreds of
states rather than millions of programs.

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
