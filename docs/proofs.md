# Proofs

Three results, machine-checked in Lean 4 + mathlib and kept here as prose
after the Lean sources (`extra/lean/esolangs`) were removed; recoverable
from git history at commit `528fe2c2`. Each statement is transcribed from
its proof file's docstring, so it says exactly what the theorem said. The
axiom audit under each result names what the theorem ultimately rested
on — `sorryAx` would mark a gap in the proof (never appeared), and
`Lean.ofReduceBool` marks a `native_decide` step (trusts the Lean compiler,
not just the kernel).

Two results are positive correctness properties of shipped generators;
the third is a negative result binding future boolean-generator work on
`%^2^-1`, and the wall entry in [`docs/walls.md`](walls.md) points here for
its argument.

## MAMMALIAN generator totality

**Claim.**  The MAMMALIAN text generator
(`src/esolangs/tools/text/tape.py::slow_acv_mammalian`) is *total* over the
byte range: for every byte-range text it emits a program that prints that
text, and the per-character search never fails — it never reaches its
`ValueError` branch.  (Like the other byte-oriented generators, `mammalian`
rejects codepoints above 255 with a documented `ValueError` before the
search runs, so the byte range is the whole domain.)

Two structural facts make the search always succeed.

**1. Number theory (`even_q_solvable`).**  Every even array `q` has
`gcd (q + 1) 256 = 1`, so the value equation `(q + 1) * final ≡ target`
(mod 256) is solvable for every target.  The reason is immediate: `q` even
makes `q + 1` odd, `256 = 2^8`, and an odd number is coprime to every power
of two — so `q + 1` is a unit in `ZMod 256` and `final = (q+1)⁻¹ * target`
is the solution.  The generator only ever needs an even array, and on one it
can always hit any target byte.

**2. Reachability (`walk_reaches_even`).**  The SPRINT walk from every
pointer reaches an even array in steps 1..46.  The walk is
`sprint q k = (q + ((q + 1) * k) % 256) % 23`.  At SEED count 1 it degenerates
to the affine map `q ↦ 2q + 1 mod 23`, a bijection whose orbits have period
dividing 11; every orbit contains an even array, so every one of the 23
pointers reaches one within 46 SPRINTs even at SEED count 1 alone.  The
start array is deliberately *not* counted as reached — it is only reachable
if the walk returns to it — which matches the Python walk table, where the
recorded steps are `range(1, 47)`.

**Totality (`search_total`).**  The per-character search was formalised as
`searchOne`, mirroring the Python generator: for each candidate array `q` it
takes `g = gcd (q + 1) 256`, checks the target is divisible by `g`, solves
the reduced congruence for a base value, lifts it by each of the `g`
solutions, and asks whether the required SEED count is reachable.  Success
was then verified by computation over the full finite state space — 23
pointers × 256 SEED counts × 256 targets — with a companion check that the
failure count over that space is exactly 0.  Because the reachability table
uses the same step range (1..46) as the Python `_mammalian_walk`, the
theorem certifies the actual generator's search rather than an idealisation
of it.

**Axioms.**  `even_q_solvable`, `walk_reaches_even` and `search_total`
legitimately carried `native_decide` axioms: they are finite exhaustive
checks, which is what `native_decide` is for.  This was the only result of
the three that used it.

## Factor round-trip correctness

**Claim.**  The Factor encoder is total, and decoding recovers the program:
`decode (encode code) = code`.

Factor is brainfuck re-encoded as the prime factorization of a single
integer (`src/esolangs/interpreters/tape_based/factor.py`,
`src/esolangs/tools/text/tape.py::_factor_encode`).  Each distinct
prime factor's residue mod 11 selects a brainfuck instruction and its
exponent is the run length.  The model is a run-length encoding: a program
is a list of `(command, exponent)` runs of identical instructions; the
encoder walks the runs and hands each one the next prime congruent to that
command's residue mod 11, folding `num *= p^e`; the decoder reads the
distinct prime factors ascending, their residues identifying the commands
and their exponents the run lengths.

The eight instructions take residues 1..8 (`>`=1, `<`=2, `+`=3, `-`=4,
`.`=5, `,`=6, `[`=7, `]`=8), and the residue map is injective, so a residue
names its command unambiguously.

**Totality is Dirichlet.**  The encoder's search for "the least prime
`p ≥ candidate` with `p % 11 = res c`" terminates because each residue 1..8
is coprime to 11 — 11 is prime and the residues sit strictly below it — and
Dirichlet's theorem on primes in arithmetic progressions
(mathlib's `Nat.forall_exists_prime_gt_and_modEq`) gives a prime in every
reduced residue class above any bound.  So the search is well-defined at
every run, at every candidate, and the encoder never gets stuck.

**The round-trip.**  Decoding recovers each run
(`decodeRuns_encodeRuns`, hence `decode_encode`) because the sorted distinct
prime factors of the encoded integer are precisely the primes the encoder
chose, in order, with the right exponents.  The pieces:

- Each next prime is searched strictly above the previous one, so the chosen
  primes are pairwise distinct and strictly increasing
  (`encodePairs_primes_nodup`, `encodePairs_pairwise_lt_fst`) — which is why
  reading them back in ascending order recovers the run order.
- The factorization of the encoded number at a prime `q` is exactly the
  exponent that `q` received across the chosen pairs
  (`encodeRuns_factorization_at`, `encodeRuns_factorization_one`), since
  distinct primes contribute nothing to each other's exponents.
- That exponent is positive exactly at the chosen primes
  (`chosenExp_pos_iff`), so the distinct prime factors of the encoded number
  are the chosen primes and nothing else (`primeFactors_encodeRuns`).
- Expanding the run decomposition recovers the flat program
  (`expand_runGroup`), and every run `runGroup` produces has positive length
  (`runGroup_pos`), so no run vanishes in the encoding.

**Axioms.**  Kernel-only — `propext`, `Classical.choice`, `Quot.sound`.  No
`sorryAx`, no `native_decide`: the prime search rests on Dirichlet, not on
computation.

## The %^2^-1 boolean-generator wall

**Claim (`computes_ignores`, and its corollaries `no_xor` / `no_and`).**
`%^2^-1` has no two-input boolean generator, *at any program length*.  Every
program meeting the boolean contract computes a function that ignores one of
its two inputs, so XOR and AND — which depend on both — are unreachable.

The scope matters: the claim quantifies over programs of unbounded length,
and non-termination of a `t` loop is not decidable by simulation, so this is
an induction on the execution and **not** a bounded search.  No amount of
enumeration would have established it.

### The machine

`%^2^-1` (`src/esolangs/interpreters/register_based/pct_squared_minus_one.py`)
has a single accumulator and nine commands: `s` (acc -= 2), `i` (acc -= 3),
`m` (acc *= 2), `p` (acc *= -1), `l` (print the magnitude in decimal), `e`
(print the low byte), `n` (read one input byte into the accumulator), `'`
(acc := 0), and `t` — the only control flow, which rewinds the cursor to
*the start of the program* when the accumulator is nonzero.  There is no
forward jump, no skip, and no way to branch over code.

The model was faithful to the interpreter's `_Machine.step`: the `acc > 3003`
reset fires *before* the command, a taken `t` sets the cursor to 0 with no
increment, `e` prints the low byte (Python's `& 0xFF`), and every other
command advances the cursor by one.  Output was kept out of the machine
state — the run returns what it emitted — which makes "the tail of a run
depends only on the state it starts from" hold definitionally.

**The contract.**  A boolean program for two inputs must, on each of the four
bit combinations, halt cleanly having consumed both bits and printed exactly
one character: the table's entry, as the byte `'0'` (48) or `'1'` (49).

### Two structural facts

**1. A read erases the past (`read_erases`).**  `n` overwrites the
accumulator and advances the cursor by one, so immediately after a read at
position `i` the state is `⟨i + 1, byte read, rest⟩` — no component mentions
anything the machine computed before.  Two states at the same cursor with
the same remaining input land, after a read, in *identical* states whatever
their accumulators were (`read_erases_pair`).  Nothing the earlier bit
computed survives, and no branch exists that could have routed the cursor
elsewhere on the strength of it.

**2. Reads cannot be skipped (`count_le_of_halts`).**  Let `countN code i`
be the number of `n` commands at positions `≥ i`.  Because `t` jumps only to
position 0, a run that reaches the end of the program crosses every read
ahead of it — so a clean halt from a state needs at least as much input
remaining as there are reads at or ahead of the cursor.  The proof is an
induction on fuel: a non-read command advances one position leaving the
input untouched, a read pays one input byte for the one read it crosses, and
a taken rewind restarts at 0, where the count is at least the count at the
current cursor.

That second fact is what forbids the two runs from diverging at a `t`: the
branch that rewinds must pay for the reads it re-crosses.  Two consequences
carry the argument.

- *With no input left, a taken `t` is fatal* (`rewind_fatal_of_empty`): it
  returns to position 0, and any contract-satisfying program has a read
  there to re-cross, so the counting lemma refutes a clean halt.  Hence once
  the input is exhausted, the accumulator can no longer change the control
  flow of a cleanly-halting run — every `t` it meets is untaken and the
  cursor walks straight to the end.  The runs visit the same commands, and
  the only outputs that can differ are those of `l`/`e`, which read the
  accumulator (`tail_determined`).
- *With one byte left and two or more reads in the program, a `t` is never
  taken* (`rewind_not_taken`): the rewind would land at position 0 and need
  `countN code 0 ≥ 2` bytes when only one is left.

### The canonical split

To compare two runs, the position at which they split must be the *same* —
a function of the program, not of the accumulator.  Define `firstReadFrom
code i` as the least position `≥ i` holding a read.  Two structural cases:

- **Two or more reads.**  A `t` can never be taken while one byte remains
  (above), so the cursor advances one step at a time and stops exactly at
  `firstReadFrom code i`.
- **Exactly one read.**  A `t` *may* be taken — this is the
  single-`n`-read-twice shape — but then the read that eventually fires is
  the unique one, whatever path reached it (`read_pos_unique`,
  `unique_read_pos`).

Either way the split position does not depend on the accumulator
(`run_splits`, `run_splits_pos`).  Before the first read, only `read`
inspects the input, so two runs at the same cursor with the same accumulator
take exactly the same branches — including every `t` test — regardless of
what the input *contains* (`lockstep_two`, `lockstep_first`).  After the
first read both runs hold the same accumulator, since the byte read is the
same, so the lemma applies a second time.

### The wall

Putting those together, a program meeting the contract prints
`A b₁ ++ B b₂` (`computes_splits`): a prefix determined by the first bit,
then a suffix determined by the second.  The split is at the canonical read
positions — the first read from 0, and the read reached after it — which are
functions of the program alone.  That is what makes `B` independent of `b₁`:
the tail run starts from a state naming only `b₂`.

Now take lengths.  The contract prints exactly one character, so
`1 = |A b₁| + |B b₂|` on all four combinations, forcing `|B 48| = |B 49|`
and the whole character to come from exactly one side:

- `|B| = 1` forces every `A b₁ = []`, so the character is `B b₂` — the first
  bit is ignored;
- `|B| = 0` forces `B ≡ []`, so the character is `A b₁` — the second bit is
  ignored.

Either way a two-input program ignores one of its inputs.  XOR and AND
depend on both, so neither is computable (`no_xor`, `no_and`,
`no_two_input_generator`).

The theorems are stated for the byte-valued encoding a program prints with
`e`, but a program answering with `l` instead (printing the decimal digits
`0`/`1`) is covered too: `computes_ignores` quantifies over *every*
function, so the `l`-valued XOR falls to the same theorem.

### Scope: the wall is exactly at n ≥ 2

The `n == 1` case is *not* walled.  All four one-input functions are
expressible: identity is `ne`; NOT is `nss` followed by 31 `i`s then `pe`,
computing `x ↦ -x + 97`, which sends 48 ↦ 49 and 49 ↦ 48 — verified to map
`'0'` ↔ `'1'`.

The wall also has a documented escape at `n ≥ 2`, which is why the shipped
generator exists: parameterizing voids the proof's hypothesis.  No `n` ever
runs, so nothing overwrites the accumulator and the "state at the last read
depends on the last bit alone" step has no object to apply to.  See the
`%^2^-1` entry in [`docs/walls.md`](walls.md) for that construction.

**Axioms.**  Kernel-only, for every theorem in the chain
(`count_le_of_halts`, `lockstep_first`, `lockstep_two`, `computes_splits`,
`computes_ignores`, `no_xor`, `no_and`, `no_two_input_generator`): `propext`,
`Classical.choice`, `Quot.sound`.  No `sorryAx`, no `Lean.ofReduceBool` —
nothing here rested on `native_decide`, as befits a claim over unbounded
program length.
