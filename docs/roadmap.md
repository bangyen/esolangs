# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

## Conditional follow-up

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length.  For each remaining generator, either add a
  loop-less O(T) construction and an executed scaling regression, or record a
  structural proof that the language or required encoding forces super-linear
  output and continue with the next generator.  Generation time includes
  choosing an input order and writing the result.

  A language stays if its generator is O(T) on all four axes, its row has a
  proved language lower bound, or tests pin a semantic obstruction broken by
  every attempted construction. A syntax-level lookup table is not a
  generator. After one more executed round without a construction or bound,
  that language and row leave. An unproved wall is not a lookup table.

  The audit covers totality, generation time, output size, and execution time.
  `proofs/index.md` defines totality; `tests/proofs/deep/linearity.py` measures
  size by same-parity successive differences through n=12. Timings use the
  top five arities, best of three, and exclude loading; runs under 10 ms do not
  establish an exponent. Closure requires a language-wide lower bound, not a
  sample ratio. The live audit is:

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | Factor | Total | Language lower bound | Language lower bound | Linear |
  | Malbolge | Exception | Open | Linear | Linear |
  | Polynomial | Cap | Language lower bound | Language lower bound | Linear |

  Malbolge ships through sixteen inputs; finite source space excludes some
  18-input tables, leaving generation time at seventeen open. Its fixed
  59,049-character source makes output `O(1)`, while set cells grow linearly;
  see [malbolge-scaling](proofs/malbolge-scaling.md#the-emitted-size-law).

  Factor's worst-case encoding and language floor are `Theta(T log T)`;
  [factor](proofs/factor.md) gives the totality and generation bounds.
  Polynomial's language-level text complexity is `Theta(T**2 / log T)` and
  its generation time is super-linear; [polynomial](proofs/polynomial.md)
  proves both bounds and the parser's totality.

  At the top arities, B-tapemark, 6-5, Forth, Circuit Diagram after its n=8
  route change, and Vandevelo grow x2.0--2.2 per added input. This straddles
  the size contract's x2.15 and remains linear pending wider measurements.
  Vandevelo is x2.0 over n=11..15 and takes 0.31 s at n=12.

## Open problems

Research questions the proofs leave open.  Each names the first executable
step; an answer lands in the paper it extends, and the row leaves.

- **Brainfuck behaviour count.**  [brainfuck-count](proofs/brainfuck-count.md)
  brackets the growth rate of distinct behaviours (input-output maps on all
  inputs, repo model: clipped tape, `,` at EOF an error) of `C`-character
  programs: `4.1858 <= liminf B(C)**(1/C) <= limsup <= 7.0601`, from
  `[2.414, 7.388]`.  Upper: behaviour-preserving shortlex rewriting (dead
  loops, clears, diverging bodies, excursion commutation) and an exactly
  certified Perron bound on the irreducible words; the old `7.388` counted
  `[]` as removable, which is unsound when programs may diverge.  Lower:
  token families decodable from their event sequences, with reads sent to
  the nearest cell whose value is never printed again and nested loops
  attached to prints (four local rules make brackets decodable; the fourth, a
  read in every loop body, closes a gap where a read-free loop diverges and
  hides its output, lowering the old 4.1963), certified by a Collatz-Wielandt vector; loop-free programs alone
  lie in `[4.061, 2 + sqrt 5 = 4.236]`.  A single fixed input gives `>= 3.366`.
  Open: the limit.  Local rules have saturated near 7.06, so the upper side
  needs a global equivalence argument; the lower side needs a decodable
  loop gadget beating `4.236`; the nested family without the local rules
  certifies 4.2418 at `W = 6` and shows no collisions by brute force, so a
  decoding proof for it would settle that loops raise the rate.

- **Malbolge's first unreachable arity.**  Counting proves some 18-input
  table has no Malbolge program; 17 needs the program count a further
  `2**46076` down, and the length and alphabet cuts are dead
  ([limitations](limitations.md), Malbolge).  The live route is a dependence
  cut over the 24,434-cell threshold (the largest `K` with
  `C(59049, K) * 8**K < 2**131072`), but NOT per program: `'o'*59046 +
  '/<v'` computes the one-input identity and every one of its cells flips
  it, so some program for a table can depend on all 59,049.  With full
  stores a cell's first access is always a read, so dependent cells are
  touched cells; in the shipped constructions every sampled touched cell
  is dependent (3,416 at `n = 4`, 9,308 at 10, 16,650 at 11, at least
  19,007 at 12).  What survives is a cut over ONE program per table -- a
  normal form that strips nop runs and padding -- or a count of
  descriptions rather than of flip-sensitive cells.  Either way it is a
  density lemma: 17 inputs need 2.22 bits a cell against the 3 a cell
  holds, so every program must waste 0.78 bits a cell (the sixteen-input
  build stores 1.11).  Directly sampling scaled stores cannot measure this:
  at `3**6` cells the threshold is 1,618 bits, so even the first expected
  collision needs about `2**809` programs (`2**2428` at `3**7`).  In 10,000
  random legal programs, 234 at `3**6` and 246 at `3**7` computed a total
  one-input table, but the sample itself caps any distinct-table estimate at
  0.0183 and 0.0061 bits a cell.  Next step: define a canonical nop/padding
  normal form and bound its descriptions analytically; empirical entropy
  cannot supply the needed upper bound.  The shipped
  constructions reach 16 inputs (a positional address, one cell per row
  pair), so 17 is the only arity whose status is unknown: a build would
  need more than two table bits in nearly every cell, and a proof that one
  table is unreachable needs the density lemma above.

- **Polynomial's constant.**  `prop:bracket` in
  [polynomial](proofs/polynomial.tex) brackets `C_P n / T**2` explicitly:
  both limits in `[13/4 log10(2), 325/8 log10(2)]`, a factor 12.5 (down
  from 211).
  Lower side: counting with the relabelling symmetry (`lem:gapauto`,
  `prop:counting`) forces `T/(n+4)` input values for every `n >= 7`.
  Upper side: embedded automaton programs with an additive decoder
  (`lem:adddec`, `prop:embprog`, effective profile `325/8` per state
  squared, `lem:effprofile`) on a trie-banded automaton (`lem:trieband`,
  `lem:bandtrie`) with `(1 + o(1)) T/n` states for every `n`, so levels
  are CLOSED.  Open: profile (`325/8` against mass `13/4`).  Sources neither
  even nor odd pay mass `4` (`rem:parity`), even or odd ones `3`
  (`lem:evensigns`, both-signs rows on `E` with `f = x^e E(x**2)`), plus
  `1/4` for every large `n` by counting sign skeletons
  (`lem:evencount`, `cor:evenhard`; even or odd sources add and subtract
  only right after a read, `lem:symruns`; exact register arithmetic, the
  float `**` is a caveat).  The register and real roots are not
  charged, see the complex-roots row of the
  [coefficient-mass roadmap](https://github.com/bangyen/coefficient-mass/blob/main/ROADMAP.md).
