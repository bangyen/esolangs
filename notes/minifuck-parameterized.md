# Minifuck: parameterizing the boolean generator breaks the documented wall

`docs/walls.md` records Minifuck as reaching only the four one-input
functions plus the eight 0-preserving two-input tables, with XNOR, NAND, NOR,
NOT-b0, NOT-b1 and const-1 unreachable.  **That characterization is about the
runtime-read model and is still true as stated.**  It does not transfer to a
*parameterized* generator, where the inputs are embedded in the program
rather than read with `.`.

## The wall does not survive parameterization

Found by joint-state BFS over the four instantiations and **verified on the
shipped interpreter** (`src/esolangs/interpreters/tape_based/minifuck.py`),
answer read from a scratch cell:

| table | program after the embed prefix |
| --- | --- |
| AND `0001` | `[<<<<<[x[<` |
| NAND `1110` | `[<<<<<[x[<<[x` |
| NOR `1000` | `[x<<<<[<[<[<[<` |
| XNOR `1001` | `<<<[[[[[x[[[[` |
| OR `0111` | `<<[[[x<<<<[x[[[[<` |
| XOR `0110` | `<<[[[x<<<<[<[[[[<` |

NAND, NOR and XNOR are exactly the tables the original analysis could not
reach.  All six nontrivial two-input tables are reachable with embedded bits.

## Verified primitives

Each was checked against the real interpreter or an interpreter-faithful
simulator, not argued from the spec.

* **Setter.** `[<` writes a 1 at `ptr+1`, `xx` writes a 0; equal width, no net
  pointer motion.  This is the `{Xi}` fill and it keeps every instantiation
  the same length (the leak invariant `instantiate` documents).
* **Skip reconvergence.** `[` on a 1-cell clears it, XORs into `ptr+1`, and
  skips one instruction; control flow rejoins after that single slot, so only
  *state* diverges, never the instruction stream.
* **`[x` is position-safe.** It advances the pointer exactly one cell
  whatever the crossed cell holds (2000/2000 single steps, 500/500 multi-step
  walks over random tapes).  Junk threatens reads and carries, never
  navigation.
* **Prefix-XOR law.** A `[x`-walk leaves `cell_i = NOT(old_i XOR w_{i-1})`,
  i.e. the complement of the running prefix-XOR of everything crossed
  (6000/6000 random tapes, including nonzero carry-in).  The transform is
  affine and invertible, so re-crossing a stored bit region loses nothing.
* **Deposit.** `[x` entered at `E+s` with acc at `E+2` computes `acc ^= s`.
* **Reconvergence.** `<` never writes and clamps at 0, so a long enough run
  of `<` converges every path for free.
* **Relay and output.** `[<` at `acc-1` leaves `ptr = (acc-1) + value`; a
  constant walk lands `ptr` on 6 or 7; `[x.` then prints one ASCII digit.
  Which digit each position yields depends on cell 7 at print time, so the
  generator *runs the endgame in a copy and checks the printed output*
  rather than assuming an orientation.

## What ships in the prototype

`minifuck-boolean-prototype.py` builds a template around a joint simulator:
every emitted fragment is executed against all `2**n` rows as it is emitted,
so the affine bookkeeping is never hand-tracked, and the generator raises
rather than emitting a program it has not verified.

It currently covers the tables whose answer appears directly in a tape cell
after the embed — at `n == 2` that is `0000`, `1000`, `1100`, `1110`, `1111`
(5/16), each verified end-to-end through the real interpreter with equal
instantiation lengths.  The embed's carry chain computes AND, NOR and XOR as
a byproduct, which is why the scan finds anything at all.

## The open obstruction

A total generator needs the minterm loop, and that is blocked on one point:

* Only `s AND (cell == 0)` exists as a literal stage.  The `== 1` form is
  **unreachable** — exhaustive over all 113 distinct pointer patterns in the
  131k reachable joint states, not a bounded-search miss.
* One-sided tests constrain prefix parities to 1 only, so they isolate just
  one row of `2**n`.  Every input needs both polarities.
* The complement is derivable at runtime (`[x` leaves `NOT b` in the tested
  cell — this is the `nocomment` pattern, and it does **not** need a `{Ci}`
  embed), but the current embed does not leave both polarities standing in
  the region at the same time.  Greedy isolation reaches 4/4 rows at
  `n == 2`, 6/8 at `n == 3` (rows 5 and 6 resist), and 3/16 at `n == 4`.

Re-crossing the region to refresh the columns helps but does not close the
gap.  The next step is a layout that keeps a companion complement cell alive
per input across passes, so both polarities are testable at every pass.

## Dead ends worth not repeating

* **Searching on blank scratch.** Pointer spread is pinned at 1 on an
  all-zero tape (exhaustive to length 10), so a width-doubling stage looks
  structurally impossible.  It is not — with the scratch pattern as a free
  parameter, stages are found readily.  A negative result on blank scratch
  proves nothing.
* **Fixed width-2 stage chains.** Even with perfect gadgets these reach only
  88/256 tables at `n == 3` (majority-of-3 is unreachable) and 520/65536 at
  `n == 4`.  Width-2 branching programs cannot be total; do not polish them.
* **Harvesting.** Sweeping embed variants finds all 16 tables at `n == 2` but
  105/256 at `n == 3`.  It is per-table search with no termination guarantee —
  a shortcut, not a totality argument.
* **Demanding too much of one gadget.** A "converging deposit" (acc ^= s with
  the pointer converged *and* clean residue) does not exist, across ~2400
  states achieving the deposit.  Neither condition is actually needed: `<`
  reconverges for free afterwards.
