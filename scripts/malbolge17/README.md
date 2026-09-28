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
