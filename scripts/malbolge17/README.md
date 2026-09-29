# Seventeen-input Malbolge: research artifacts

Supporting files for the "Seventeen" sections of
[docs/proofs/malbolge-scaling.md](../../docs/proofs/malbolge-scaling.md).
None of this is wired into the generator.

- `msim.c`, `tables.h` -- a C Malbolge simulator matching
  `esolangs.interpreters.other.malbolge` (checked against it). Build with
  `gcc -O2 -o msim msim.c`; `msim PROGRAM NBITS [stride] [offset]` feeds each
  row's bits as `0`/`1` lines and prints its output. It runs every row of a
  sixteen-input program in about 2.5 s, and found no wrong row in the shipped
  sixteen-input build on a seeded random table or the parity table.
- `decoder_s6_norepeat.p` -- six shared states decode a group of three cells
  (seven meanings each) for eight rows, realising all 256 answer vectors with
  no row reading a cell twice.
- `decoder_s5_norepeat.p` -- five shared states with no re-read, the
  minimum (four are excluded by exhaustive search).
- `decoder_s5_repeats.p` -- five states, but 462 paths re-read a cell, which a
  destructive read forbids.
- `decoder_s13_fixed_order.txt` -- the earlier thirteen-state decoder in which
  each state reads one fixed cell (a different file format).
- `verify_decoder.py` -- checks a `.p` decoder: `verify_decoder.py FILE
  [--no-repeat]`.
- `sweep17.py` -- builds a valid seventeen-input program (prints input 2)
  whose first reads weigh 164,965 bits, refuting the per-program form of the
  read-count bound: `uv run python scripts/malbolge17/sweep17.py OUT.mb`.
- `trace.c` -- `trace PROGRAM NBITS [stride]`: per cell, how many rows first
  touch it by execution (split by whether `A` holds `'0'`/`'1'`) or as data.
- `slack.c` -- `slack PROGRAM NBITS CELLFILE [full]`: which other characters
  at each listed cell leave every row's output unchanged (256-row screen, or
  every row with `full`).
- `outputs.py` -- exhaustive checks on the printed word (plain operands,
  residues, landing addresses) behind "Seventeen: straight-line programs".
- `readers.c` -- `gcc -O2 -o readers readers.c && ./readers`: the most
  cleanly printing admissible triples for every lockstep way of reading a
  three-cell group (at most 137 of 512).
- `prototype/five_esc.py.txt` -- the same decoder with the dense-table
  escape and five-base parity views; also 2,744 of 2,744. Build `msim.c` as
  `/private/tmp/malbolge17-msim` before running it.
- `prototype/five_lab.py.txt`, `prototype/chain_k.py.txt` -- the scratch
  prototype of the five-state group decoder that runs 2,744 of 2,744 cases
  on real sources (see the doc). Kept as text: it hard-codes `/tmp` paths
  (`chain_k.py` is exec'd for its helpers) and is not written to the repo's
  lint standard. To rerun `five_lab.py`, copy both into a scratch directory
  as `.py`, fix its paths, build `msim`, and run with `PYTHONPATH=src`.
- `fold_classes.py` -- the 272 triple classes that no `p p p` fold separates
  at the worst residue.
- `fold.c`, `fold2s.c` -- anneal the stateless fold decoder's row windows (best
  measured cover 20,364 of 24,064 residue/vector pairs).
- `tiling_runs.py` -- free cells in long runs under every digit-local
  six-slab tiling (best 5,127 in runs of 200 or more); needs numpy.
- `address17.py` -- word-level model of the seventeen-input address fold
  (16,384 groups, cells `0..6561` free, no wrap to cell 0).
- `address_gadget.py` -- emits the first three-bit address slot as real source
  and checks all eight inputs against `address17.py`.
- `parity_views.py` -- exact five-base factorization of the ten view constants,
  its three consumable parity words and one-trit toggle, and emitted setup
  measurements.
- `address_parity.py` -- exhaustive certificate for the straight-line reducer
  from the computed group pointer to the parity toggle operand.
