# brainfuck -> Streetcode: what is built and what is open

This records an attempt at a total `brainfuck -> Streetcode` transpiler under
the admission contract in `src/esolangs/tools/transpilers.py`. The I/O half is
fully solved; the geometry half reduces to one open sub-problem, stated below
with a construction that works for a large sub-class and a witness for what it
does not reach.

## No residues (criterion 3 is vacuous here)

An earlier reading held that bf and Streetcode disagree on a blank input line
(bf's `,` -> 10, Streetcode's `I` -> 0), which would have been an admissible
residue. That split was removed at `a8c2ec4b`: `io.input_char` now returns 0
for a blank line, matching `input_str`. So bf and Streetcode agree on every
observable:

- a blank input line reads 0 through both;
- exhausted input raises `EOFError` in both;
- `,` / `I` on a code point above U+00FF is reduced mod 256 in both;
- `.` / `O` print `chr(cell)`.

A total transpiler therefore needs **no** divergence clause.

## The intermediate language, and why it is total (verified)

bf lowers cleanly to an IL over Streetcode's cell model. Streetcode cells are
unbounded signed integers, so a bf cell (0-255, wrapping) is emulated as a
canonical cell plus a scratch cell:

- bf cell `i` maps to Streetcode cell `2i`; cell `2i+1` is its scratch.
- Invariant at every bf-op boundary: even cells hold `[0,255]`, odd cells 0,
  and `cp = 2 * bf_ptr`.

Op lowering:

- `>` -> `==`, `<` -> `__` (Streetcode `_` clamps at 0, composing with bf's
  own left-clamp), `.` -> `O`.
- a maximal run of `+`/`-` with net delta `d` -> `^` * (d mod 256) when
  `d != 0 (mod 256)`, followed by one canonicalizer.
- `,` -> `I` followed by one canonicalizer (Streetcode's `I` already stores a
  whole code point; the canonicalizer reduces it mod 256).

The canonicalizer reduces the cell under `cp` to `[0,255]` using its scratch,
with a `while`/`if`:

    s = 256; while x { x--; s--; if s == 0 { s += 256 } }; x = 256; while s { s--; x-- }

This is one uniform macro; it is position-relative (`=`/`_` park), so it needs
no static knowledge of where `cp` sits.

`[` / `]` lower to a `while cell != 0 { body }`.

A plain-Python IL simulator under Streetcode cell semantics was fuzzed
differentially against the repo brainfuck interpreter: over a seeded corpus of
random programs (sizes 1-30, mixed comment/bracket/IO, six input shapes
including blank, ASCII, and above-U+00FF lines), every program that halts in
bf's own step budget produced identical output, identical tape (even cells vs
bf cells, odd cells 0), and `cp == 2 * ptr`. The IL layer is total and
equivalent; the code is `notes/bf2sc_il.py` (untracked per repo convention).

## The geometry: solved for the countdown class, open in general

Streetcode has no indirect dispatch: `cp` moves one cell per glyph and control
flow is one zero-test per wall gap. A `while` is a junction the car laps.

Confirmed by tracing the reference counting-loop grid (see
`tests/interpreters/test_streetcode.py::TestStreetcodeCountingLoop`) and
grids built for this attempt:

- **Entry polarity.** A two-wide mouth (a gap with `+` tips) in the street's
  south wall, met eastbound, reads the cell: zero -> continue East (skip),
  nonzero -> dive South. This is exactly bf `[`.
- **The lap closes.** A hollow-island lap re-tests the cell each time round
  and drains it; `while cell != 0` terminates.
- **Exit is clean.** At zero the car climbs an east shaft that lands it back
  on the street's eastbound lane heading East, past a head-on crossing it
  takes because `cp` is parked on a nonzero scratch there.
- **Skip is clean.** With the cell 0 at entry, the car drives straight East
  across both the entry mouth and the exit gap (both read 0 -> East) to the
  continuation, tape untouched.

All four were traced on `[-]`-shaped rooms that validate, drain from a preset,
and skip when zero. The room is a working
`while cell != 0 { cell -= 1; scratch += k }` — the countdown/multiplier
class.

### The open sub-problem: body cp-movement across lap gaps

Every wall gap the lap crosses reads the cell under `cp` as the car arrives
(`streetcode-gap-junction-law`). The island keeps its steering gaps reading a
known-nonzero scratch by parking `cp` there with a fixed `=`/`_` pair. That
park is **relative to the current `cp`**, so it only re-finds the value cell
if the body's net `cp` displacement is a fixed constant.

A general bf body moves `cp` by a data-dependent amount: a nested loop
`[>...]` whose trip count depends on cell contents leaves `cp` displaced by a
runtime-variable offset by the time control reaches the enclosing `]`. No
fixed glyph sequence restores `cp` to the tested cell across the lap's
steering gaps, so the lap's mid-gaps read an uncontrolled cell and steer the
car out of the island.

This is the same barrier the roadmap files under **"Lower drawn control
flow"** (`docs/roadmap.md`): the construction is a compiler / source-machine
problem, not command transliteration, and it needs the reference
interpreter's junction and post-corner semantics pinned before a general
lowering. The countdown room above is the reachable fragment; the general
`while` with cp-moving, nesting bodies is not yet constructed.

## Status

Not registered in `TRANSPILERS`: registering a transpiler that is total over
the source is the contract, and the geometry is total only over the countdown
class, not over all bf. Per the admission bar, a partial transpiler is not
carried. The IL layer and the traced room components are recorded here and in
`notes/` so a later attempt at the general lowering starts from proven pieces
rather than re-deriving them.
