# Brainfuck behaviour count

We bound the growth rate of distinct behaviours of `C`-character Brainfuck
programs. The earlier interval `[1 + sqrt 2, 1 + lambda]` came from the Factor
constant work removed in `e5276dc` (`lem:draw`, `prop:reduced`,
`prop:drawing`, `rem:gap` of the old `factor.tex`).

## Status

The limit remains open. Exact rational certificates narrow the former
`[1 + sqrt 2, 1 + lambda] = [2.414, 7.388]` interval:

| model (section 1) | lower bound on `liminf B(C)^(1/C)` | upper bound on `limsup B(C)^(1/C)` |
|---|---|---|
| clipped tape, `,` at EOF is an error, all inputs | 4.24200 (Thm 4) | 7.0347 (Thm 1) |
| clipped tape, EOF stores a constant, all inputs | 3.79003 (Thm 4) | 7.0347 (Thm 1) |
| clipped tape, EOF leaves the cell, all inputs | 3.79003 (Thm 4) | 7.3339 (Thm 1) |
| repo model: bi-infinite tape, EOF error / keep | **4.24200** / 3.79003 | **6.9133** / 7.1949 (Thm 1) |
| any fixed nonempty finite input set `I`, any EOF, any tape | **3.36614** (Thm 5) | as for all inputs |
| only the empty input (clipped tape, EOF error) | 3.36614 | 6.3218 (Thm 1) |
| loop-free programs, EOF error | **4.06124** (Thm 3) | **2 + sqrt 5 = 4.23607** (Thm 3) |
| loop-free programs, EOF constant / keep | 3.79003 | 4.23607 / 4.72458 |

For the repository model: **`4.2420 <= liminf B(C)^(1/C) <= limsup B(C)^(1/C) <= 6.9133`**,
from `[2.414, 7.388]`.  In bits per character: `[2.085, 2.789]`, from `[1.272, 2.885]`.
The repository tape clipped at cell 0 until 2026-10-06; on that tape the bracket is
`[4.2420, 7.0347]`.
The lower bound uses nested loops (section 5c) and exceeds the loop-free upper bound
`2 + sqrt 5 = 4.23607`.  Loops therefore strictly raise the growth rate.

Two corrections to the old statement:

* `B(C) <= (1 + lambda)^C` with `lambda = 6.388` was not proved for behaviours of arbitrary
  programs.  Of the five adjacencies, `[]` can be deleted only from a program that terminates
  on every input (as the Factor setting had).  In a model where a program may diverge, `[]`
  is the shortest diverging loop and cannot be removed.  The four sound adjacencies give
  `7.4979`.  Theorem 1 replaces both by `7.0347`.
* The drawing floor `(1 + sqrt 2)^C` is far from the truth.  Loop-free programs with I/O
  already have `4.061^C` behaviours on all inputs and `3.366^C` distinct outputs on a single
  input.

## 1. Model

A *program* is a word over `+ - < > . , [ ]` with balanced brackets; `|P|` is its length (every
character is an instruction).  Cells hold bytes (`+`,`-` wrap mod 256), all 0 at the start; the pointer
starts at cell 0.

* Tape: **clip**: cells `0, 1, 2, ...`, `<` at cell 0 does nothing.  Variant **bi** (the repository
  interpreter, `src/esolangs/interpreters/tape_based/brainfuck.py`, since 2026-10-06): cells indexed by `Z`.
* Input: a finite byte string `w`, read left to right by `,`.  At end of input: **err** (the repository
  interpreter: the run stops with result `(eof, o)`, `o` the output so far), **const** (the cell is set
  to 0), **keep** (the cell is unchanged).
* The *result* of a run on `w` is `(halt, o)`, `(eof, o)` (err only), or `BOTTOM` if the run is infinite
  (its output is not observed).
* The *behaviour* `[[P]]` is the map `w -> result` on all `w in {0..255}*`; for a set `I` of inputs,
  `[[P]]_I` is its restriction.  `B(C) = #{[[P]] : |P| <= C}`, `B_I(C) = #{[[P]]_I : |P| <= C} <= B(C)`.

Exact length versus `<= C` does not matter: appending `.` maps distinct behaviours to distinct
behaviours (a halting output gains one byte, `eof` and `BOTTOM` results are unchanged), so the number of
behaviours of programs of length exactly `C` is nondecreasing in `C` and lies between `B(C)/(C+1)` and
`B(C)`.

## 2. Results

**Theorem 1 (upper bound).**  In clip/err and clip/const, `B(C) <= K * 7.0347^C`.  For
clip/keep `7.3339`, bi/err (the repo model) `6.9133`, bi/keep `7.1949`.  With only the
empty input (clip/err), `B_{{eps}}(C) <= K * 6.3218^C`.

**Theorem 2 (the old five adjacencies).**  Words avoiding `+- -+ >< ][ []` grow as `7.38776` (Perron
root of `J - F`, as in `prop:reduced`), but only the four without `[]` are sound here, growth `7.49791`.

**Theorem 3 (loop-free programs).**  Let `L(C)` count behaviours (on all inputs) of bracket-free
programs of length `<= C`.  For EOF err or const and either tape,

    L(C) <= F_{3C+1}   (Fibonacci numbers), so  limsup L(C)^(1/C) <= phi^3 = 2 + sqrt 5 = 4.23607;

for EOF keep, `limsup <= 4.72458`, the reciprocal of the root of `2x^3 + 3x^2 + 4x - 1`.
Conversely `liminf L(C)^(1/C) >= 4.06124` (err) and `>= 3.79003` (every EOF convention),
by the dead-cell families of section 5b.  These replace `3.87513` and `3.68909`, the limits of
the pointer-read families of section 5.

**Theorem 4 (lower bound, all inputs).**  `B(C) >= c * (2121/500)^C / C` with EOF err on the
clip tape and on the bi tape (the repo model), using the nested-loop family `A_err` of section 5c.  (The family
`D^L_err` of section 5b gives 4.06834.)  `B(C) >= L(C)`, so for const and keep
`B(C) >= c * 3.79003^C / C`.  Hence `liminf B(C)^(1/C) >= 2121/500 = 4.242` (err) and `>= 3.79003`
(const, keep).

**Theorem 5 (one input).**  For every nonempty input set `I`, every EOF convention and either tape,
`B_I(C) >= c * 3.36614^C`: programs without `,` have at least that many distinct outputs.  (The
unconfined value of this construction is `3.38298`, root of `x^3 + x^2 + 3x - 1`.)

## 3. Upper bound (Theorem 1)

**Rewriting.**  A rule `l -> r` replaces a factor `l` of a program by `r`.  Every rule below preserves
the behaviour in every context and makes the program strictly smaller in *shortlex* order (length first,
then lexicographic with letter order `. , - + < > [ ]`).  Shortlex is a well-order, so rewriting
terminates at an *irreducible* program no longer than the start and with the same behaviour.  Hence
`B(C) <= sum_{n <= C} N_n`, `N_n` the number of words of length `n` containing no left-hand side.

**Block lemma.**  If `f` and `g` are both bracket-free or both balanced and, run from any configuration
(tape, pointer, remaining input, output), they either both diverge, or both stop with the same `eof`
result, or both exit with the same configuration, then `u f v` and `u g v` have the same behaviour.
*Proof:* a jump from a bracket outside a balanced (or bracket-free) `f` never lands strictly inside `f`
and no jump from inside leaves it, so every run of `u f v` is a sequence of complete passes through `f`
interleaved with steps outside it.  (Divergence inside `f` is divergence of the run, whose output is not
observed, so `f` and `g` need not agree on output before diverging.)

Let `D_L` be the nonempty words over `+ - < > .` of length `<= L` whose pointer path never goes left of
its start (clip; any path for bi), ends at the start, and changes the start cell by 0 mod 256.  An
*excursion* is `>X<` with `X` over `+ - < >` (or also `. ,`) whose path, started at 1, stays `>= 1` and
ends at 1 (bi: also the mirror `<X>`).  The rules (larger
family sizes, used for the headline numbers, in brackets):

| rule | why it is sound |
|---|---|
| `+-`, `-+`, `><` -> empty (bi: also `<>`) | cancellation; `>` always moves right |
| `] S [G]` -> `] S` for `S` in `D_L` or empty (the `[G]` group deleted) | after `]` the cell is 0 (it was left or skipped at 0); `S` leaves pointer and cell unchanged; the `[` is only reached by falling through `S`, so `[G]` is always skipped |
| `[S]` -> `[]`, `S` in `D_L` | entered at a nonzero cell, `S` returns to it unchanged: both diverge; at 0 both skip |
| `[S[T]X]` -> `[]`, `S, T` in `D_L` or empty | entered at a nonzero cell, `S` keeps it and the inner loop diverges |
| `[[Y]]` -> `[Y]`, `Y` balanced, `|Y| <= 3 [4]` | the inner loop runs to a 0 cell, which the outer `]` then tests |
| `[+^k]` -> `[-^k]`, `k <= 4` | both halt iff `gcd(k,256)` divides the cell, then at 0, nothing else changes |
| `+[-]`, `-[-]` -> `[-]` | dead store before a clear |
| `+,`, `-,`, `[-],` -> `,` (err, const only) | `,` overwrites the cell or ends the run, whose tape is not observed |
| `[].` -> `.[]` | at a nonzero cell both diverge (output unobserved); at 0 both print 0 |
| `[]S` -> `S[]` for `S` in `D_L` (`L <= 6`) | `S` returns to the tested cell without changing it; at 0 both run `S` and skip, and at nonzero both diverge |
| `>[]<W>` -> `W>[]`, `W` a sequence of `+ - . [] [-]` | after `>` the loop tests the right cell while `W` acts only on the left one; at 0 both run `W`, and at nonzero both diverge |
| `[]>W<` -> `>W<[]`, `W` over `+ - .` | the excursion returns without touching the tested cell; at 0 both run it, and at nonzero both diverge |
| `[-]>W<` -> `>W<[-]`, `W` over `+ - . ,` | the clear and excursion act on different cells and commute, including when the excursion reaches EOF |
| `>[-]<W>` -> `W>[-]`, `W` over `+ - . ,` | after the leading `>`, the clear and left block act on different cells and commute |
| `E Y` -> `Y E` for an excursion `E` over `+-<>` (`|X| <= 4 [6]`), `Y` in `. , + -`; `[-]E` -> `E[-]` | `E` neither touches nor clips at the current cell and does no I/O; with err an EOF in `,` happens with the same output either way |
| `E Y` -> `Y E` for an excursion over `+-<>.,` (`|X| <= 4 [5]`), `Y` in `+ -`; `[-]E` -> `E[-]` | the increment or clear does not interact with `E`'s I/O |
| `> Y <>` -> `> Y` (clip), `Y` over `+-<>.,` never left of its start, `|Y| <= 3 [4]` | after `>` the pointer is `>= 1`, so `<>` is the identity |

Each same-length rule goes to a lexicographically smaller word (checked by assertion),
the others shorten.  A word is irreducible exactly when it contains none of the left-hand factors
`+-, ..., ]S[, [S[T], [[Y]], ...` (for `]S[` and `[S[T]` the group to delete or collapse always exists in
a balanced word).  Words avoiding a finite factor set are paths in the Aho-Corasick automaton of the
set; with transfer matrix `M`, `N_n = e_root^T M^n 1 <= (v_root / min v) * rho^n` for any rational
`v > 0` with `M v <= rho v`.  The check builds such a `v` from the numerical Perron vector and checks
`max_i (Mv)_i / v_i` exactly with `fractions.Fraction`:

| model | patterns | states | `rho` certified `<=` |
|---|---|---|---|
| clip/err, five old adjacencies (unsound `[]`) | 5 | 6 | 7.3877553 |
| clip/err, four sound adjacencies | 4 | 5 | 7.4979068 |
| clip/err, + `+, -, [-],` | 7 | 8 | 7.2356196 |
| clip/err and clip/const, all rules (`--big`) | 5793 | 8634 | **7.0600257** |
| clip/err and clip/const, local subset + extended regular families | 15619 + 15 regular families | 11673 minimized | **7.0347** |
| withdrawn: finite global bodies, `len(Y) <= 7` | 723653 | 1358980 | 7.0341 (unsound rule) |
| withdrawn: unrestricted global bodies | 4354 + regular families | 744 minimized | 7.0194 (unsound rule) |
| clip/keep, all rules | 7379 | 10410 | 7.3338896 |
| bi/err, all rules | 9969 | 14814 | 6.9132619 |
| bi/keep, all rules | 12759 | 17946 | 7.1948872 |
| clip/err, empty input only, + `,c -> ,` for `c != ]` | 3940 | 6273 | 6.3217970 |

The last row: on the empty input `,` ends the run, so any instruction after it other than a closing
`]` is dead.  Weighting `[` by `t` and `]` by `1/t` (a Chernoff bound for balanced words) gives no gain:
the optimum is `t = 1`.

The new regular-family row is independent of the withdrawn grammar below. Its definitions are:
`S(A) = (A | [A*])*`, `F(A) = (A | [A*] | >A*<)*`, and
`H = (+ | - | [-] | >(+ | -)*<)*`. Here an alphabet denotes a choice of letters.
Every `S` block stays on one cell; every `F` block returns without going left of its start.
`H` always terminates without I/O. Write `F0 = F(+-.)`, `F1 = F(+-.,)`,
`N = F(+-)`, and `Pj = (. | >Fj<)*`. The four earlier commute monitors use
`S(+-.)`, `F0`, `F1`, and `S(+-.,)` respectively instead of their smaller alphabets.
Their proofs still apply, including divergence and EOF.

The other eleven regular families are:

| left-hand factor | replacement and proof |
| --- | --- |
| `>N<c`, `c` in `.+-` | `c>N<`: disjoint cells, no I/O in `N`; either `N` returns or both runs diverge |
| `>H<,` | `,>H<`: the silent excursion always terminates; EOF therefore agrees |
| `>F1<c`, `c` in `+-` | `c>F1<`: disjoint cells; neither increment affects the excursion's output or EOF |
| `[A[-]B]`, `A,B` over `+-` | `[-]` if `B` has net increment 0 mod 256, otherwise `[]`: each returning iteration ends at that fixed residue |
| `L>H<`, `L = [V]`, `V` over `+-.,` | `>H<L`: `L` stays on the tested cell; `H` is silent and terminating |
| `>L<W>`, `W` over `+-` | `W>L`: the right-cell loop and the silent left-cell block commute |
| `[W[Z]D]`, `D = .*(+|-).*` | `[]`: read-free balanced `W,Z` cannot reach EOF; every returning iteration ends at 1 or 255, so the outer loop cannot exit |
| `>F1<>` | `>F1`: the last `<>` runs at a positive pointer |
| `]P1[G]` | `]P1`: `P1` leaves the zero tested cell unchanged, so `[G]` skips |
| `[P0[]G]` | `[]`: `P0` preserves the nonzero tested cell or diverges; the empty loop cannot return |
| `[.Y].` | `.[Y.]`: rotation preserves the event sequence; the moved print leaves the loop test unchanged |

For the last five monitors, `W,Z` have bracket nesting depth at most one and contain no read;
`Y` has depth at most one and may read. `G` is arbitrary balanced text: the monitor rejects the
prefix before `G` because its matching group can be deleted or collapsed. The forced-divergence
rule observes no output from infinite runs, as required by the model. `D` consists of prints,
one increment or decrement, and more prints. Print rotation runs the same
sequence of `.` and `Y` blocks: at zero both print once; at nonzero both run `. Y . Y ... .`,
ending on the same zero cell or at the same EOF.

The exported certificate now includes its finite factors and regular monitors.
`scripts/perron_certificate.py --check-grammar` reconstructs acceptance with
failure links for finite factors and first/last/follow position automata for
regular factors, independently of the builder's Thompson construction and
minimization. Both use Python's regex parser. Exhausting the reachable product
checks both inclusions across 135,576 state pairs for the 11,673-state matrix;
the exact spectral certificate remains `70347/10000`. The checker rejects a
spectrally valid matrix with a different factor language and aborts if its
150,000-pair budget is exhausted.

Execution controls instantiate all fifteen regular families with six body
variants each, plus 79 local-rule witnesses, at four byte configurations,
two pointer positions and two remaining-input configurations. They compare
halting tape, pointer, consumed input and output, EOF output, and divergence
proved by repeated complete state. Negative controls preserve the distinctions
between EOF and divergence, cell preservation and merely read-free bodies,
and clipped and unclipped pointer cancellation. These finite controls check
the stated side conditions; the general soundness arguments remain above.
The rotation and forced-divergence rules are also executed with
bracket-depth-two and depth-three bodies at the same configurations, including
divergence as the observation and reads that reach EOF
(`test_depth_two_and_three_side_conditions_execute`,
`test_depth_bodies_agree_on_read_positions`). The depth-one bound is therefore
not a soundness boundary.

Each replacement shortens the program or decreases lexicographic order under `. , - + < > [ ]`. The checker rebuilds the finite factors with `L = 6`, excursion-body limits 6 (silent) and
5 (I/O), and clipped-cancellation limit 4. It intersects their avoidance DFA with the fifteen
regular monitors and minimizes after each intersection. This gives 11,673 states, not a frozen
transition table. A positive integer vector checks `10000 M v <= 70347 v` at every state, hence
`B(C) <= K * 7.0347**C`.

The local method has saturated: doubling every family size moves the third decimal (smaller families
7.0632, larger 7.0600), and a heuristic search over all balanced fragments of length `<= 4`
finds no further candidate that survives better contexts. The identity `[[Y]] -> [Y]`
holds for every balanced `Y`: if the inner loop exits, it leaves the cell tested by the outer `]`
at zero; otherwise both sides already have the same result.

The 7.0341 and 7.0194 rows are withdrawn. Both used `[Y[] -> []` for arbitrary balanced,
read-free `Y`, which is unsound: `+[-[]].` halts with output NUL, but `+[].` diverges.
The prefix `Y = -` makes the tested cell zero, so the empty loop skips. Read-freedom
alone does not prevent this. The local rules with `S` in `D_L` retain the missing
cell-preservation hypothesis and are unaffected.

The unrestricted matrix grammar also excluded every empty-loop atom before a read in a
loop body. The counterexample invalidates that exclusion. Keeping only `[[Y]] -> [Y]`
gives the following candidate grammar; no numerical upper bound is claimed for it.
Let `O` be a read-free instruction, `C` a read, `E = []`, `L0` a nonempty read-free loop,
and `L1` a read-containing loop. The read-free sequence series `R` must include `E`:

    B0 = I + O R + (E + L0) (R - I),
    B1 = R C P + (R - I) L1 P + L1 (P - I),
    L0 = [ (B0 - I) ],   L1 = [ B1 ],
    R = (I - O - E - L0)^-1,
    P = (I - O - C - E - L0 - L1)^-1.

These bodies exclude a sole loop, but permit an empty loop after a prefix that may
zero the tested cell. The executed counterexample is pinned in
`tests/proofs/test_brainfuck_count.py`.

No finite monitor counts the unrestricted bodies. A regular class needs finite,
depth-agnostic forbidden factors, but `[.Y].` with `Y` balanced pairs its `[`
with the matching `]` across arbitrary depth. The 11,673-state monitor accepts
`[.[[--]]].` and, for every `k >= 2`, the word `[.` + `[`^k + `--` + `]`^k +
`].`, and it accepts the forced-divergence word `[[` + `[`^k + `--` + `]`^k +
`]--]`; each is a sound left-hand side, so the class is uncounted. The balanced
avoidance specification is not a finite right congruence: Moore refinement gives
15, 39, 86, 173 classes at observation windows 4, 6, 8, 10. The next model is the
context-free/algebraic system `B0, B1, L0, L1, R, P` above, or a depth-indexed
transfer matrix, not a larger finite-factor monitor.
`test_unbounded_body_classes_are_not_regular` pins the accepted families and the
class counts through window 8.

## 4. Loop-free programs (Theorem 3)

**Upper bound.**  Run a bracket-free program `w`; its I/O instructions execute once each, in order,
as events `e_1, ..., e_m` at cells `q_1, ..., q_m` (actual, clipped positions).  Record for each event
its type, `delta_i = q_i - q_{i-1}` (`q_0 = 0`) and, for a print, `A_i` = the net increment (mod 256)
applied to cell `q_i` since the previous event at `q_i`.

* The data determine the behaviour (EOF err or const): the value printed at `e_i` is the value left at
  `q_i` by its previous event (an input byte, the EOF constant, or 0 initially) plus `A_i`; a read
  overwrites the cell (or ends the run), so increments before it are irrelevant; increments after a
  cell's last event are never observed.
* Weight: `|w| >= sum_i (1 + |delta_i|) + sum_{prints} |A_i|`, where `|A| = min(A, 256 - A)`: one
  character per event, each move changes the position by at most 1, and the `+`/`-` characters counted
  in different `A_i` are distinct.
* With `mu(x) = sum_{d in Z} x^|d| = (1+x)/(1-x)`, one event contributes at most
  `F(x) = x mu (mu + 1) = 2x(1+x)/(1-x)^2` to the generating function, so the number of data of weight
  `<= C` is at most `[x^C] 1/((1-x)(1-F)) = [x^C] (1-x)/(1-4x-x^2) = F_{3C+1}` (Fibonacci).  Growth
  `phi^3 = 2 + sqrt 5`.
* EOF keep: a read keeps the old value at EOF, so reads carry an `A_i` too; `F = 2x mu^2`, growth
  `4.72458` (root of `2x^3 + 3x^2 + 4x - 1`).

**Lower bound.**  The families of sections 5 and 5b are loop-free, except `D^L_err`.

Census (exact enumeration, clip/err, `S(n)` = loop-free behaviours of length `<= n`):

| n | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S(n) | 3 | 9 | 28 | 89 | 290 | 962 | 3243 | 11077 | 38252 | 133320 | 468397 | 1657471 |
| ratio | 3.00 | 3.00 | 3.11 | 3.18 | 3.26 | 3.32 | 3.37 | 3.42 | 3.45 | 3.49 | 3.51 | 3.54 |
| `F_{3n+1}` | 3 | 13 | 55 | 233 | 987 | 4181 | 17711 | 75025 | 317811 | 1346269 | 5702887 | 24157817 |

The ratios still climb.  The limit lies in `[4.061, 4.236]`.

## 5. Lower bounds on all inputs (Theorems 3, 4)

Fix a window of `W` cells.  The prefix `,>,>...>,` (`W` reads, cost `2W - 1`) puts the fresh inputs
`x_1, ..., x_W` into cells `0..W-1`.  Tokens (the pointer is at `p`):

* `P(d, D)`: move by `d` to a window cell `p + d`, add `D in (-128, 128]` (`+^D` or `-^-D`), print.
  Cost `1 + |d| + |D|`.
* `R`: `,` (read into the current cell).  Cost 1.
* `Q(k, D)`: `,^k`, add `D`, print.  Cost `k + 1 + |D|`.

Family **F_err** = prefix followed by any word in `P, R`; family **F_any** = prefix followed by any word
in `P, Q`.  Invariant: every window cell holds `x_j + d` for its own index `j` (reads bring a fresh
input into one cell; nothing copies), so every print outputs `x_j + d` for a formal pair `(j, d)`.

**Decoding, F_any (every EOF convention).**  On inputs longer than the number of reads no EOF occurs,
so the output is the formal list `((j_i, d_i))` evaluated at `x`.  Two different formal lists differ as
functions (at the first difference: equal `j` and different `d`, or different `j` and a choice of
`x_j, x_j'`, or different lengths).  The list determines the tokens: with the pointer `p` and the cell
contents known, an output `(j, d)` with `j` already read is `P(d', D)` with `p + d'` the cell holding
`x_j` and `D = d - ` its old offset; `j > r` (reads so far) is `Q(j - r, d)`.

**Decoding, F_err (the repo convention).**  On an input of length `l`, a loop-free program stops with
`(eof, o)` exactly when it reads more than `l` times, `o` being the output before read `l + 1`.  So the
behaviour determines the *event sequence*: the reads and prints in order, each print as a formal pair.
Now an `R` event is the token `R` at the known pointer, and a print event is `P(d', D)` as above.

**Counting lemma.**  Let tokens with costs `c(t) >= 1` act on a finite state set, finitely many from
each state, and let `phi > 0`, `x0 in (0,1)` satisfy `sum_t x0^c(t) phi(s.t) >= phi(s)` for every state.
Then the number of token words of cost `<= n` from `s` is at least `kappa phi(s) x0^-n` with
`kappa = x0^{c_max}/max phi` (induction on `n`: for `n < c_max` the empty word suffices; otherwise split
off the first token).  Here the state is the pointer, and `M_W(x)_{pq} = x^{1+|p-q|} mu_D(x) + [p=q] g(x)`
with `mu_D(x) = sum_{D in (-128,128]} x^|D|`, `g = x` (F_err) or `g = x^2 mu_D (1-x^60)/(1-x)` (F_any,
`k <= 60`).  The check takes `phi` = the rounded Perron vector of `M_W(x0)` and checks the
inequality exactly:

| window `W` | 8 | 16 | 32 | 64 | `-> oo` |
|---|---|---|---|---|---|
| F_err: growth `>=` | 3.798532 | 3.851902 | 3.868702 | 3.873437 | 3.875130 |
| F_any: growth `>=` | 3.620805 | 3.668180 | 3.683282 | 3.687561 | 3.689095 |

As `W -> oo`, `lambda_max(M_W(x)) -> x mu(x) mu_D(x) + g(x)` (above by row sums; below by the Rayleigh
quotient of the all-ones vector, the matrix being symmetric), so `sup_W` of the certified rates is the
root of `x mu mu_D + g = 1`, which agrees with the cubics of Theorem 3 to 60 digits (`mu_D` differs from
`mu` by `O(x^128)`).  Distinct token words are distinct programs with distinct behaviours, of length
`2W - 1 + cost`, which proves Theorem 4.  A brute-force check confirms pairwise distinctness by brute
force on small windows (and, as a negative control, that bare reads are not decodable under keep).

## 5b. Dead-cell families (Theorems 3, 4)

The families of section 5 read only at the pointer, so every read destroys the value just
used.  A read may go anywhere, provided the decoder can work out where it went.  It can if the
read goes to **the nearest cell whose current value is never printed again**: the decoder sees
the whole event sequence, so it knows the future.

**Family `D_err`.**  Same prefix and window as `F_err`.  The state is `(p, m)`, with `p` the
pointer and `m ⊆ [0, W)` the *live set*.  Tokens:

* `P(q, D, f)` with `q in m`: move to `q`, add `D in (-128, 128]`, print; then keep `q` in `m`
  or kill it.  Cost `1 + |q - p| + |D|`.
* `R(f)`, only if some cell is not in `m`: move to the nearest such cell `r` (ties to the
  left), `,`.  Then `r` is live (`f = live`) or not.  Cost `1 + |r - p|`.

A word from `(W - 1, m0)`, for any `m0`, is *valid* if it ends with `m = ∅`.

*Decoding.*  Window cells hold `x_j + d`, with each variable in at most one cell.  In a valid
word, `m` is at every point exactly the set of cells whose current variable is printed at a
later event.  A cell leaves `m` only by a kill-print and comes back only by a read, which
replaces its variable, and the final set is empty.  So the event sequence (section 5) determines
`m0`, each print token (the cell holding `x_j`, the offset, `f = kill` iff `x_j` is not printed
later), the target of each read (the nearest cell not in `m`) and its flag.  Distinct valid
words therefore have distinct behaviours.

*Counting.*  Every word becomes valid when `P(q, 0, kill)` is appended for each `q in m`
(extra cost `<= W^2`), and each valid word arises from at most (its length + 1) words.  The
counting lemma applied to the transfer matrix on the `W 2^W` states `(p, m)` then gives
`#{valid words of cost <= n} >= c x0^-n / n`.

**Family `D_any`** (every EOF convention).  The read token is `Q(k, D, f)`: move to the nearest
cell not in `m`, `,^k` (`k <= 60`), add `D`, print, keep or kill.  Cost `|r - p| + k + 1 + |D|`.
Decoding works on inputs longer than the number of reads: a pair `(j, d)` with `j` beyond the
reads so far is a `Q` with `k = j - ` (reads so far).

**Family `D^L_err`** (loops).  This is `D_err` plus the top-level gadget `P(t, D, kill) [ B , ]`,
where:

* `t` is the *marked* cell.  A top-level read (or a prefix cell) may be marked, but only when
  no live cell is marked.  The marked cell is killed only by the gadget, whose `P` is its last
  top-level print.
* `B` is a possibly empty word of prints `P'(u, D')` with `u` live at top level or `u = t`.
* The `,` reads at the pointer.  Nesting depth is 1, and after the gadget the top-level state is
  `(t, m)` with no mark.

*Decoding.*

* (i) The only tests are gadget entries (each marked variable is tested once) and exit reads.
* (ii) Every iteration reads, so no run diverges.
* (iii) Top-level tokens run on every path, so the shortest halting inputs `H*` are exactly the
  runs that skip every loop.  The coordinates that are constant on `H*` are therefore the marked
  variables, and those constants are their skip values.
* (iv) Walk the all-skip run as for `D_err`, counting only top-level prints as uses.  A constant
  print is a print of the marked variable read most recently, because marked lifetimes do not
  overlap.  So every print is identified, and each gadget follows the last print of its
  variable.
* (v) For a gadget on `x_a`, move `x_a` off its skip value and keep the other marked variables
  at theirs.  The run prints `B`, whose targets hold unmarked variables or `x_a`, all formal,
  and then reads.  So `B` is determined.

Without the one-mark rule, several pinned variables could print as equal constants, and no
complete decoding argument is known for that family.

The state is `(p, m, mark)` at top level and `(t, m, q)` inside a body.  The certificates, all
exact:

| family | window `W` | states | `x0` | growth `>=` |
|---|---|---|---|---|
| `D_err` | 12 | 49152 | 246760799/10^9 | 4.052507 |
| `D_err` | 14 | 229376 | 24623/10^5 | **4.061243** |
| `D_any` | 12 | 49152 | 264354129/10^9 | 3.782804 |
| `D_any` | 14 | 229376 | 26385/10^5 | **3.790032** |
| `D^L_err` | 12 | 638976 | 1229/5000 | **4.068348** |

Numerical growth rates of `D_err` for W = 4, 6, 8, 10, 12, 14 are 3.849, 3.961, 4.011, 4.038,
4.053, 4.062.  The limit appears to be about 4.07 to 4.08.  At W = 8 and 10 the loop gadget
adds about 0.017.  None of the families moves left of cell 0, so they work on both tapes.
A brute-force check confirms pairwise distinctness on small windows: `D_err` (W = 3, 4),
`D_any` under err, const and keep, and `D^L_err` (W = 2, 3, up to 39001 programs, 2403 of them
with loops, on inputs that make loop tests zero).  As a negative control, reads to *any* dead
cell do collide.

## 5c. Nested loops (Theorem 4)

The family `N_err(W, K)` extends `D_err` with nested loops that can be placed almost anywhere.
Brackets attach to prints, and each test reads the value that was just printed.

*Prefix* `>,>,...>,`: `W` reads.  Cell `i` (for `1 <= i <= W`) holds `x_i`, and the pointer is at `W`.
Cell 0 is never visited.  A window cell is *dead*, *live*, or *tested* (live and already tested).
The tokens are `P(q, D, f)` for a live or tested `q`, and `R(f)` at the nearest dead cell, as in
`D_err`.

* A print of a **live** cell may be followed by `[` when the depth is below `K`.  A keep print
  makes the cell tested; a kill print makes it dead.
* A **kill** print of a live cell may be followed by `]` when the depth is positive.

Four local rules apply:

* **N1.**  The token after `[` (the body's first token `g`) is a print.
* **N2.**  Let `tau(g) = 1` when `g` prints the cell the `[` tested.  At depth 1 `tau` is free, and
  a loop directly inside another loop has the opposite `tau`.
* **N3.**  The token after `]` is a read.  It is the single character `,`, because the exit cell
  is dead and nearest.
* **N4.**  Every loop body contains a read at its own top level, that is, not inside a nested
  loop.  A loop opens a child only after such a read.

A word is *valid* if it ends at depth 0, with no live or tested cell, and not with `]`.

*Termination.*  With N4, every run on every finite input ends, with a halt or an EOF.  Suppose a
run is infinite.  It reads only finitely often, so some `]` jumps back infinitely often.  Take
such a loop `L` of maximal depth.  After some time no loop inside `L` jumps back, so each later
pass through `L`'s body executes its top-level tokens in order, including the read.  That gives
infinitely many reads, a contradiction.  So every result below lists all outputs of its run.

N4 is needed.  Without it a displaced repeat can run forever without reading, and its output is
never observed.  An example is `>,>,<.[.>+.],<.` with `x2 != 255`: each pass moves right over a
fresh cell, adds 1 and tests it.

*Once-run.*  Each variable carries at most one bracket.  An *exit variable* is one whose print
carries `]`; it takes the value that makes that print 0.  Every other variable is generic.  An
entry variable avoids the one value that would zero its `[`-print.  On these inputs every `[` is
entered and every `]` exits.  The text therefore runs in order, each body once, and liveness has
the same meaning as in `D_err`.

*Decoding.*  It suffices to recover the once-run's event sequence together with the brackets that
follow each print.  The `D_err` argument then gives the tokens.  Suppose `e_1, ..., e_{k-1}` and
their brackets are known, and let `r` be the number of reads among them.

* Pin the exit variables seen so far and leave every other variable generic.  Truncate the input
  after `r` values.  The run follows the once-run through `e_k`, because no test lies between
  `e_{k-1}`'s bracket and `e_k`, and then it ends.  If `e_k` is a read the result is `(eof, o)`.
  If the text has ended it is `(halt, o)`.  Otherwise the run has one more output, the value of
  `e_k`, and varying the generic variables gives it as a formal pair.
* Let `e_k` print a live variable `x`.  Compare two runs: `G`, with `x` generic, and `Z`, with `x`
  set so that `e_k` prints 0.  Both runs end.
  * With no bracket, both runs execute the same next token.
  * With `[`, `G` enters and its next event is a print (N1).  `Z` skips and its next event is a
    read (N3).
  * With `]`, `G` jumps back and its next event is a print (N1).  `Z` exits and its next event is
    a read (N3).
* So a bracket is present exactly when the two next events differ in type.  Only one kind of
  bracket is possible at depth 0 or `K`.  At any other depth, ask whether `G`'s next print depends
  on `x`:
  * Under `[`, it does exactly when `tau(g_new) = 1`.
  * Under `]`, `G` re-runs the current body's `g` from `x`'s cell, and the print depends on `x`
    exactly when `g`'s move is empty, that is, when `tau(g_cur) = 1`.  A clipped left move lands
    on cell 0, which holds 0.
  * The decoder knows `tau(g_cur)` from the loop's first body event, and N2 makes the two
    hypotheses differ.

*Counting.*  The transfer matrix has these states: cell statuses, pointer, depth, a
just-after-bracket flag, the `tau` of the current depth-1 loop, and whether the innermost open
loop has read yet.  It is restricted to states that can still reach the final state, so every
prefix completes at bounded cost.  The weights are:

* `P`: `x^{1+dist} mu_D`;
* a print followed by a bracket: `x^{2+dist} mu_D`;
* `R`: `x^{1+dist}`.

The check is the one used in section 9 (`phi = round(10^17 v)`, weights `floor(w 2^62)`,
128-bit integers):

| window `W` | depth `K` | states | `x0` | min ratio | growth `>=` |
|---|---|---|---|---|---|
| 8 | 4 | 1311992 | 2398/10^4 | 1.000448 | 4.170141 |
| 9 | 4 | 4428441 | 2389/10^4 | 1.000254 | **4.185851** |

N4 costs about 0.01.  Without it the same windows give 4.182 (W = 8) and 4.196 (W = 9).  Going to
`K = 6` adds about 0.003.  The limit appears to be about 4.22, just below `2 + sqrt 5`.
Counting the words with `D = 0` from the matrix gives the same totals as the brute force below:
748715 at W = 2, K = 3, cost <= 14, and 993648 at W = 1, K = 3, cost <= 18.

A brute-force check confirms pairwise distinctness on small windows (clip/err).  It detects
divergence exactly, by a repeated state at a backward jump, and it tests each class of candidates
on up to 91578 inputs, biased to zeros.  The runs were W = 2 with cost <= 11 and `|D| <= 1`,
W = 3 with cost <= 11 and `|D| <= 1`, W = 1 with cost <= 23 (`D = 0`), and W = 2 with cost <= 17
(`D = 0`).  About 66 million programs were tested, 36 million of them with loops and 263 with
nested loops.  There are no collisions.  As a negative control, dropping the tested status and
N4 gives collisions, for example `,.[...],` against `,.[.],`.

**Without N1-N3.**  Call the family without N1-N3 `T`.  Its rates at `K = 4` are 4.2420
(W = 6), 4.2700 (W = 7) and 4.2898 (W = 8), numerically, and an exact check at W = 6 gives
`>= 4.241781`.  Adding N4 costs 0.008 to 0.013.  Brute force finds no collisions in `T`: 20.7
million programs at W = 1 with cost <= 21 (1.2 million nested), 2.9 million at W = 2 with
cost <= 15, and 2.4 million at W = 3 with cost <= 12.  A decoding proof for `T` would show that
loops raise the growth rate.  The argument above extends as follows (with N4).

* With no bracket, `G` and `Z` agree up to the value of `x`.
* With either bracket, `G` runs the loop's `g` and `Z` runs the token `z` after `]`, both from
  `x`'s cell.  Every cell then holds a variable at a known offset, or 0.  So two consistent
  prints must have equal adds, and they must print the same cell or two cells holding 0.
* The add of `G`'s token can be read off, so the kind of bracket is decided by the signature
  (type, whether it prints `x`'s cell, add) of the current loop's `g`.

Local rules that force a difference within one or two tokens therefore suffice.  They are: `g`
and `z` are not two prints with equal adds, and not two reads unless the next pair differs in the
same way; a child's `g` has a signature different from its parent's.  But these rules need
memory for every open loop, and each tested version costs 0.01 to 0.04.  Examples at W = 6 are
4.203 when `g` and `z` may not both be reads, 4.208 or 4.218 for the parent/child rule, and
0.06 to 0.09 for the combinations that can be proved.  That exceeds the headroom of `T`.  The
configurations that force the cost are those where the loop body and the code after `]` (or a
parent body and a child body) agree for several tokens, such as `.[,.` against `.],.`.  After two
reads into different cells the two tapes differ in two places, and the comparison no longer
reduces to comparing texts.

**Alternating first events.**  The decodable subfamily `A_err(W, K)` keeps N4 and replaces
N1--N3 by one rule: the first events of directly nested loop bodies have opposite types, print
versus read.  The first event at depth 1 is free, so its type and the depth determine every
deeper body's required type.  A word is valid as above.

Termination is the N4 argument.  For decoding, first recover the once-run events inductively as
above.  At an eligible print of a variable `x`, compare runs in which that print is zero and
nonzero, choosing all other tests to make each entered body run once.  With no bracket, changing
`x` cannot change the later event types: a kept `x` is tested and cannot carry another bracket,
and a killed `x` is dead.  With either bracket, one run executes one extra body traversal before
the runs rejoin.  N4 puts a top-level read in that traversal, so EOF truncation observes the
extra interval.  This decides whether a bracket is present.

At depth 0 it must be `[`, and at depth `K` it must be `]`.  At an intermediate depth, the
nonzero run starts the child body after `[` or repeats the current body after `]`.  Their first
event types are opposite by the rule, and the current body's first type is already known.  This
decides the bracket direction.  The recovered event sequence and brackets determine every token
by the `D_err` argument, so distinct valid words have distinct behaviours.

The transfer state is (cell statuses, pointer, depth, the depth-1 first-event type, a
first-event-pending flag, and whether the current body has read at top level).  The weights are
the three classes above.  At `W = 9`, `K = 4` there are 3,122,541 reachable, completable states.
For `x0 = 500/2121`, round the positive left Perron vector at scale `10^17` and replace every
transition weight by its lower bound `floor(w 2^62) / 2^62`.  The exact integer check gives
`(M phi)_s >= 2^62 phi_s` at every state; the minimum ratio is 1.0000577.  The counting lemma
therefore gives growth at least `1/x0 = 2121/500 = 4.242`, strictly greater than
`2 + sqrt 5 = 4.236068`.  The numerical root is 4.242137.

## 6. One input (Theorem 5)

Programs without `,` behave the same on every input, so it suffices to count distinct outputs.  Take
`K = 9`, `h = 4`, `V = 28` (`K V <= 256`) and a window of 64 cells; cell `i` keeps its value in the
interval `J_{i mod 9} = [28 (i mod 9), 28 (i mod 9) + 28)`.  A prefix of constant cost sets cell `i` to
the middle of its interval.  Tokens `P(d, D)` with `|d| <= 4`, target in the window, new value in the
target's interval.  **Decoding:** an output `v` lies in exactly one interval `J_m`; among the 9
consecutive cells `p-4..p+4` exactly one is `= m mod 9`, so the output string determines every token.
**Counting:** with `phi(p, u) = a(p) prod_i b(u_i - base_i)`, `a` and `b` the Perron vectors of the
kernels `x^|p-q|` (`|p-q| <= 4`, on 64 cells) and `x^|u-u'|` (on 28 values),
`sum_t x^c(t) phi(s.t)/phi(s) >= x lambda_a lambda_b`, checked exactly: growth `>= 3.366148`
(`K = 9`; `K = 7, 11` give 3.3574, 3.3654).  Without the interval constraint the rate would be the
root of `x mu^2 = 1`, `3.38298`.

## 7. Census with loops (guidance only)

Enumeration of all balanced words avoiding `+- -+ >< ][ +, -,` of length `<= C`, repo model, run on
the empty input and on the 13 inputs of length `<= 2` over bytes `{0,1,7}`, divergence detected exactly
by state repetition at backward jumps (fallback step limit `3 * 10^6`).  Distinct behaviour vectors of
programs of length `<= C`:

| C | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|
| empty input | 42 | 106 | 282 | 795 | 2377 | 7522 | 24979 | 87303 |
| ratio | 2.33 | 2.52 | 2.66 | 2.82 | 2.99 | 3.16 | 3.32 | 3.50 |
| 13 inputs | 96 | 333 | 1191 | 4431 | 17038 | 67235 | 271782 | 1125532 |
| ratio | 3.20 | 3.47 | 3.58 | 3.72 | 3.85 | 3.95 | 4.04 | 4.14 |

These are behaviours on finite input sets, so they are lower estimates of `B(C)`; the 13-input ratios (4.14 at `C = 11`) are well above the loop-free census
(3.51 at `C = 11`) and still rising; the empty-input ratio (3.50 at `C = 11`) already exceeds the proved 3.366.

## 7b. Bounded-input upper bound (Theorem 6)

For a finite input set `I`, put `R(I) = sum_(x in I) (len(x)+1)`.
Every program has an equivalent source on `I` with at most `R(I)` commas:
on input `x`, a run visits at most `len(x)` successful reads and one
failing read. This holds for divergent runs too; infinitely many successful
reads are impossible on finite input. Delete comma locations visited by
none of these runs. Bracket matching remains valid, and every run has the
same transitions, outputs and outcome after source positions are relabelled.
The pruning is existential; it is not a halting-decision algorithm.

Next cancel `+-`, `-+` and `><` to a fixed point. These preserve the full
machine state, introduce no reads, and never increase length. `<>` is
excluded because the left boundary is clipped. The comma-free segments
are words over seven commands avoiding those three pairs. Their adjacency
matrix has characteristic polynomial

    x**3 (x-1) (x**3 - 6x**2 - 4x + 1).

It is irreducible and aperiodic. Its Perron root is
`lambda_I = 6.584428340...`, so segments of length `l` number at most
`K*lambda_I**l` for a fixed `K`. Inserting at most `R` commas into words
of length at most `C` gives at most

    (C+1) sum_(r=0..min(R,C)) binom(C,r) K**(r+1) lambda_I**(C-r).

Consequently, for every fixed nonempty finite input set,

    3.366148 <= liminf B_I(C)**(1/C)
             <= limsup B_I(C)**(1/C) <= 6.584428341.

The lower bound is Theorem 5's read-free output family, which is
distinguishable on any one input. The upper bound preserves even partial
output at EOF, so it also holds when buffered error output is discarded.
The limit and sharp rate remain unproved.

The upper bound also holds for varying sets `I_C` whenever `R(I_C)=o(C)`:
the binomial term and `K**R` then contribute `exp(o(C))`. For all byte inputs
of length at most `m`, it suffices that `(m+1)*256**m=o(C)`; in particular
`m <= (1-eps)*log_256(C)` for fixed positive `eps`.

For `R=pC`, fixed `p in (0,1]`, the same bound is still finite, with
exponential rate `f(min(p,t*))` where
`f(t) = K^t lambda_I^(1-t) / (t^t (1-t)^(1-t))` and `t* = K/(K+lambda_I)`
maximizes `f` at `f(t*)=K+lambda_I`; `f` increases on `[0,t*]`, so
`rate(p)=f(p)` for `p<=t*` and `rate(p)=K+lambda_I` afterwards. Every `p>0`
gives `rate(p)>lambda_I`, so proportional reads do not preserve `6.584428341`;
`lambda_I` returns only as `p->0`. The proof leaves `K` only "a fixed"
constant; the exact right Perron vector of the segment matrix (entries
`(lambda_I-1)/lambda_I`, `1`, `(lambda_I^2-5lambda_I+1)/(2lambda_I)` repeated)
certifies `K=7/(lambda_I-1)<=1.25349`, so `rate(p)<=7.8380`. The empty
segment forces `K>=1`, hence the saturation `K+lambda_I>=1+lambda_I=7.58443`
is above the all-input `7.0347`: the proportional extension cannot beat
Theorem 1, and it beats the fixed-set bound for no `p>0` (it improves on
Theorem 1 only while `p<~0.021`). This is a rate of the summed expression, an
upper bound only. `test_proportional_read_budget_rate` checks the rate, the
`p->0` control against `lambda_I`, and the exact sum through `C=200`.

`tests/proofs/test_research_tracks.py` checks the exact matrix polynomial
and a rational Perron upper certificate at `1317/200`. Executed pruning
controls cover all loop-free sources through length four on seven binary
inputs, plus halting, EOF and divergent loops. The control `,[,]` prunes
to `,[]` on input zero but changes EOF to divergence on input one: the
equivalence is confined to the chosen input set.

## 8. What is not settled

* **The limit.**  The repo-model interval is `[4.2420, 7.0347]`.  Nested loops raise the
  certified lower bound above the loop-free upper bound `4.236` (section 5c), so loops strictly
  raise the growth rate.  The
  idealised grammar explains why loops must nest.  Take prints of weight `x mu^2`, reads of
  weight `x`, and brackets after prints with no decodability constraint.  Depth 1 then gives
  exactly `2 + sqrt 5`, since `x^4 + 4x^3 + 4x - 1 = (x^2+1)(x^2+4x-1)`.  Depths 2, 4 and 8
  give 4.365, 4.459 and 4.507.  On the dead-cell base the unconstrained nested family `T` of
  section 5c already reaches 4.242 at W = 6 and 4.290 at W = 8, and brute force finds no
  collisions in it.  Its injectivity remains open, but the alternating-first-event subfamily
  already clears the loop-free ceiling.
* **Loop-free rate.**  It lies in `[4.061, 4.236]`.  The upper bound gives each read a free
  position.  Behaviourally a read only kills a value that is never printed again, and the
  dead-cell families suggest a limit near 4.08.  An encoding that drops the positions of
  dead-at-birth reads needs an extra type and gets worse (`x mu^2 + x mu + x`).  Whether a
  read could be moved depends on the future, so no local rule captures it.
* **Upper bound.** Extended regular rules certify 7.0347. The 7.0341 and 7.0194 improvements
  used the unsound read-free-prefix rule above. The unrestricted sound print rotation and
  forced-divergence bodies are not regular (section 3): a finite-factor monitor accepts
  depth-`k` left-hand sides for every `k >= 2`, and the balanced avoidance specification
  has unbounded Moore class count. Next: the context-free/algebraic system `B0, B1, L0, L1,
  R, P` (section 3), or a depth-indexed transfer matrix. A potentially diverging excursion
  cannot commute across a read at EOF; excursions with output cannot commute across prints.
  Two tried and dead: (i) the event encoding of section 4 applied to each bracket-free segment between
  brackets must also charge the positions of the segment's final increments, and the resulting series
  is worse than counting words (radius near `1/8`); (ii) the segment-quotient transfer matrix of the
  old roadmap (`7.371`), which our rules subsume.
* **Model dependence.**  Bounds using `+,` need EOF err/const; the `F_err` lower bound needs the error
  convention (it reads the timing of reads from where the run stops); the rules `[S] -> []` with `.` in
  `S`, `[S[T]X] -> []` and `[]. -> .[]` need that a diverging run's output is not observed.
* **Finite input sets.** Theorem 6 brackets every fixed nonempty finite
  `I` between `3.366148` and `6.584428341`. The limit and sharp rate remain
  open. For input length proportional to source length, `R=pC`, Theorem 6's
  own bound has rate `f(min(p,t*))`, already `>lambda_I` for `p>0` and
  `>=1+lambda_I>7.0347` at `p>=t*~0.1599`, so that counting method cannot
  sharpen the all-input bound (section 7b).

## 9. Reproduction

The certificates are finite exact checks, reproducible from the descriptions
above: the rule families of section 3 fed to an Aho-Corasick automaton and a
Collatz-Wielandt vector checked in `fractions.Fraction` (Theorem 1); the
matrices `M_W(x0)` of section 5 and the product kernel of section 6, checked
the same way (Theorems 4, 5); the generating function of section 4
(Theorem 3).  The soundness of each rule rests on its proof in the table of section 3.
A randomised test against a reference interpreter on random contexts and
inputs is a counterexample search only; it carries negative controls (`[] -> empty`,
`<> -> empty` on the clipped tape, `+, -> ,` under keep, `<+>. -> .<+>`) that
the tests do catch.

The former 7.0341 Perron certificate and 7.0194 matrix certificate count languages
that exclude the counterexample `[-[]]`. Their arithmetic checks do not certify a
behaviour bound: a certificate cannot repair an unsound rewrite.

The replacement 7.0347 certificate is reproducible with
`uv run python -m tests.proofs._brainfuck_count`. The helper builds the factors and regular
monitors, computes a candidate vector by power iteration, rounds it at scale `10**12`, and
checks the displayed Perron inequality using integers only. Floating-point accuracy is not a
hypothesis of the certificate. `tests/proofs/test_brainfuck_count.py` checks the automata against
an independent regex oracle, executes 2,944 contextual rewrite pairs, and rejects the unsafe
read/print commutations with positive counterexamples. The invalid `[-[]]` body remains accepted.

The dead-cell certificates of section 5b come from the transfer matrices on `(p, m)`, and on
`(c, m, q)` for the gadget.  A numerical Perron vector at the rational `x0` is rounded to
integers `phi` (scale `10^17`).  The token weights are replaced by the exact lower bounds
`floor(w * 2^62)`.  The check then verifies `(M phi)_s >= 2^62 phi_s` for every state in
128-bit integer arithmetic.  Lowering the weights only weakens `M`, so the check is sound.

The nested-loop certificates of section 5c use the same scheme.  The transfer matrix is on
(cell statuses in {dead, live, tested}, pointer, depth, flag, `tau` bit, read bit), restricted to
states that are reachable and can reach the final state.  Its token weight classes are
`x^{1+d} mu_D`, `x^{1+d}` and `x^{2+d} mu_D`.
For `A_err`, the `tau` bit is instead the depth-1 body's first-event type; its exact certificate
uses `W = 9`, `K = 4`, `x0 = 500/2121`, vector scale `10^17` and weight scale `2^62`.
