# Superoptimizer results log

Runs of the tool in this directory, newest first. A claim appears here
only when a program was executed or a search space exhausted; winners
are certified against the full spec before they are recorded.

## 2026-10-20 — the miner's control gate, re-scoped and passed

The pilot's first control run (the original ten Control 2 pairs)
failed on premises the fix phase had retired, not on the sampler:
main had shipped several of the audit's finds itself, leaving only
four pairs rediscoverable in principle.  The control set was
therefore re-scoped against current main, every candidate verified
by execution (log: `notes/rescope-2026-10-20.log`, uncommitted): a
Control 2 pair qualifies only while its shipped program is strictly
larger than the recorded find and the recorded find still certifies
and consumption-matches; a Control 3 pair only while its shipped
program is byte-identical to the one the v2 audit certified.

Control 2 is now six pairs -- FALSE 10, FALSE 01 (promoted from
Control 3: retirement candidate #23 re-spelled it from the certified
4 chars to 16, and the certified program still computes it), 1 + i
11, Painfuck 00, Painfuck 11, ArrowQueue 00 (promoted from the
secondary set) -- with the bar at all-but-one, 5 of 6.  Control 3 is
Smallfuck 00, Taglate 00 and Bitwise Cyclic Tag 00, bar zero finds.

Gate result: Control 1 passed.  Control 2 rediscovered 5 of 6 --
FALSE 01 `^1&.` (4), 1 + i 11 `Bi:*p` (5), Painfuck 00 `oq` (2),
Painfuck 11 `ssb` (3), ArrowQueue 00 `$` (1) -- missing only FALSE
10, whose best find `1^&a=.` at 6 chars is one over the pilot run's
enumerated 5.  Control 3 recorded zero finds (Bitwise Cyclic Tag's
20,000 evals cost 117.8 CPU-s; its interpreter is this set's slow
tail).  Environment restarts killed the re-scoped gate's first
attempt mid-run and its second just after the final ledger charge,
losing the printed verdict; the verdict above is recounted from the
streamed search records, which are the gate's own output.  Total
control spend across all runs: 244.9 CPU-s of the pilot's 20 CPU-h
cap.  The Painfuck hunt follows from this pass.

## 2026-10-18 — v2: the small-end audit (Boolean fleet at n=1)

For each Boolean generator and each one-input truth table, is the
shipped program the smallest program in its language that computes
the table?  v2 swaps v1's hand-built Malbolge model for each
language's own interpreter: a candidate counts iff the repo's own
machinery says it computes the table.

Method.  Candidates are strings over the language's corpus alphabet:
every character appearing in the generator's own emissions over all
tables of arity 1 and 2 (plus arity 3 when the arity-2 worst size is
at most 2,000 chars), collected from programs under 20,000 chars.
Character strings are a superset of the generator's token sequences,
so an exhausted space certifies token-level minimality too; a gap is
a fortiori a real program.  Cost is emitted text length in
characters.  Rows are checked in discriminating order (rarest
expected bit first) with early exit; a winner is re-certified over
the full table by a separate no-early-exit pass before it is
recorded.  Printing and dump languages run through the public API
(`generate`/`instantiate` per row, `run` with a 5 s timeout,
`read_answer`); termination languages stream the generator tests'
own `_iter_evaluate` (2 s per row, repeated-state cycle detection).
Before any search, the shipped program itself must certify against
its table; a pair where it does not is `unverifiable` and is never
searched.

Input consumption is part of correctness.  The repo's contract is
that a Boolean program consumes all its inputs on every row (a
caller's next program would otherwise be handed the leftovers), so a
gap must also match the shipped program's per-row input-read count,
measured by running both on a scripted-IO oracle that counts reads.
Without this rule every constant table shows a fake gap (FALSE's
`1.` computes the constant-1 table in 2 chars but reads nothing).
The oracle needs an importable interpreter module; where none is
available -- grid-form languages and all termination languages --
gaps are recorded flagged "consumption unverified".

Outcomes per (language, table): `gap` (a shorter certified program
exists), `certified` (the space below shipped size is exhausted),
`bounded` (candidate cap or wall stopped the search mid-space;
deepest fully covered length is in the run record), `priced_out`
(not run: the space exceeds 20x the candidate cap, or the global
budget was spent, or no alphabet is extractable), `unverifiable`,
`unsupported`.  Bounded and priced-out are never certificates.

Positive control.  Beyond the per-pair shipped certification, the
FALSE pilot's enumerator was run up to shipped size inclusive on
the identity table and found a correct, consumption-matching
program of exactly shipped size (`1^&.`), as it must if the
alphabet and runner are right.

Pilot: FALSE at n=1 (full space, no candidate cap; run twice, the
second time after the harness fixes below -- identical verdicts).

| table | shipped | verdict | found |
|-------|---------|---------|-------|
| 00 | 4 (`^%0.`) | gap | `0.^` (3) |
| 01 | 4 (`^1&.`) | certified minimal (4,369 candidates) | |
| 10 | 6 (`^'0=_.`) | gap | `'0^=.` (5; 290,470 candidates) |
| 11 | 4 (`^%1.`) | gap | `1.^` (3) |

The constant gaps print first and read afterwards -- same read
count, later position.  The NOT gap prints `-1` for true, whose
last character is the answer digit `read_answer` reads.

Pricing.  The pilot's effective cost was ~0.08 ms per candidate
(early exit kills most candidates on the first row); mid-fleet
interpreters run 0.1--2 ms per candidate, slow ones seconds.  The
fleet therefore ran cheapest-first under a 150,000-candidate cap
and a 90 s wall per pair and a global CPU budget; pairs whose
space exceeded 20x the cap were priced out without running.  Total
v2 spend was ~54 CPU-minutes including two lost runs (below).

Fleet at n=1: 87 generators, 348 pairs -- 12 gaps, 14 certified,
8 bounded, 306 priced out, 8 unsupported.

Gaps (all re-certified over the full table):

| language | table | shipped | found size | found |
|----------|-------|---------|------------|-------|
| Unary | 00 | 13 | 0 | (empty program; halts on both rows) |
| Unary | 11 | 53,431 | 695 | `0` x 695 (diverges on both rows) |
| FALSE | 00 | 4 | 3 | `0.^` |
| FALSE | 10 | 6 | 5 | `'0^=.` (pilot run; the fleet run bounded this pair at the cap) |
| FALSE | 11 | 4 | 3 | `1.^` |
| 1 + i | 11 | 7 | 5 | `Bi:*p` |
| Caballo | 11 | 3 | 2 | `pi` |
| Painfuck | 00 | 3 | 2 | `ok` |
| Painfuck | 11 | 5 | 3 | `ssb` |
| Circuit Diagram | 01 | 4 | 2 | `-:` |
| ArrowQueue | 00 | 3 | 1 | `$` |
| Eval | 00 | 7 | 4 | `$$0.` |
| Eval | 11 | 7 | 4 | ``$$`.`` |

The Unary and ArrowQueue gaps are termination-mode and flagged
consumption-unverified; both Unary winners were additionally
re-certified through `_evaluate` directly (the empty program
answers 00, `0` x 695 answers 11, against a shipped 53,431).  The
other ten gaps passed the consumption oracle.

Certified minimal at n=1: Unary 01 (887) and 10 (6,839) -- the
single-char alphabet makes those spaces linear; FALSE 01 (4);
1 + i 01 (2); Caballo 00 (1); Cyclic tag 00 and 11 (3); Bitwise
Cyclic Tag 00 and 11 (4); Smallfuck 00 (4) and 11 (6); Taglate 00
and 11 (4); 6-5 01 (2).

Bounded (cap or wall reached mid-space, deepest data in the run
record): FALSE 10 in the fleet run (the pilot's full-space run
above resolves it as a gap), 1 + i 00, Circlefuck 00 and 11,
B-tapemark 00 and 11, A Painter Ant 00 and 11.  A Painter Ant's
candidates cost seconds each, so its 30 s walls covered only 16
candidates per pair; its shipped programs themselves certify
through `_evaluate` at its 30 s row default -- the audit runner's
5 s rows are the binding bound there, not the language.

Unsupported: Line and Piet generate Rasters, which have no
character length; the char metric does not apply.  Malbolge is
priced out on scope: every emission is 59,049 chars, so the corpus
rule extracts no alphabet.  All other priced-out pairs carry the
20x-cap or budget reason in the run record
(`notes/audit-fleet-n1.json` in the worktree, not committed).

Fleet at n=2: not run -- priced out by the global budget.  The
pricing says why: even FALSE, the smallest, has n=2 worst shipped
size 22 over a 16-char alphabet, a space of ~1e25 strings below
shipped size; the other nine of the ten smallest are larger.  Under
the fleet rule essentially every n=2 pair prices out at any cap the
remaining budget could serve, so the phase is recorded priced-out
with these numbers rather than silently skipped.

Per-language grid (A = alphabet size, worst = largest shipped size
at n=1, outcomes in table order 00 01 10 11; $ = priced out,
n/a = unsupported):

| language | A | worst | outcomes |
|----------|---|-------|----------|
| Line | 0 | -1 | n/a n/a n/a n/a |
| Piet | 0 | -1 | n/a n/a n/a n/a |
| Malbolge | 0 | 59049 | $ $ $ $ |
| Unary | 1 | 53431 | GAP cert cert GAP |
| FALSE | 16 | 6 | GAP cert bnd GAP |
| Cyclic tag | 5 | 13 | cert $ $ cert |
| 1 + i | 11 | 11 | bnd cert $ GAP |
| Bitwise Cyclic Tag | 4 | 19 | cert $ $ cert |
| Smallfuck | 6 | 16 | cert $ $ cert |
| Fargo | 11 | 14 | $ $ $ $ |
| A Painter Ant | 9 | 15 | bnd $ $ bnd |
| Caballo | 9 | 16 | cert $ $ GAP |
| Painfuck | 21 | 13 | GAP $ $ GAP |
| Taglate | 17 | 14 | cert $ $ cert |
| Eval | 10 | 17 | GAP $ $ GAP |
| 6-5 | 13 | 18 | $ cert $ $ |
| Underload | 9 | 24 | $ $ $ $ |
| Fish | 15 | 21 | $ $ $ $ |
| FRACTRAN | 15 | 24 | $ $ $ $ |
| Circuit Diagram | 12 | 27 | $ GAP $ $ |
| CV(N)(C) | 12 | 28 | $ $ $ $ |
| Clockwise | 9 | 32 | $ $ $ $ |
| Boolfuck | 7 | 38 | $ $ $ $ |
| Unlambda | 11 | 33 | $ $ $ $ |
| Forþ | 19 | 27 | $ $ $ $ |
| Befunge | 18 | 28 | $ $ $ $ |
| Dig | 17 | 30 | $ $ $ $ |
| Algebraic Programming Language | 18 | 31 | $ $ $ $ |
| What!? | 19 | 32 | $ $ $ $ |
| Back | 10 | 41 | $ $ $ $ |
| Unsquare | 11 | 40 | $ $ $ $ |
| RAM0 | 18 | 35 | $ $ $ $ |
| Fackward | 11 | 43 | $ $ $ $ |
| SStack | 15 | 39 | $ $ $ $ |
| Home Row | 8 | 53 | $ $ $ $ |
| Minsky Swap | 15 | 46 | $ $ $ $ |
| Super SNUSP | 21 | 44 | $ $ $ $ |
| Minifuck | 7 | 70 | $ $ $ $ |
| ArrowQueue | 6 | 84 | GAP $ $ $ |
| Crement | 17 | 55 | $ $ $ $ |
| thisthat | 16 | 57 | $ $ $ $ |
| Circlefuck | 12 | 64 | bnd $ $ bnd |
| 3x | 9 | 76 | $ $ $ $ |
| EGL | 17 | 65 | $ $ $ $ |
| Subleq | 12 | 78 | $ $ $ $ |
| Dimensional | 12 | 80 | $ $ $ $ |
| bit~ | 7 | 102 | $ $ $ $ |
| Alight | 34 | 58 | $ $ $ $ |
| brainfuck | 8 | 115 | $ $ $ $ |
| BFStack | 8 | 119 | $ $ $ $ |
| Smu | 12 | 102 | $ $ $ $ |
| /// | 15 | 94 | $ $ $ $ |
| Inject | 26 | 82 | $ $ $ $ |
| ROTfuck | 8 | 128 | $ $ $ $ |
| LaserFuck | 19 | 91 | $ $ $ $ |
| Rubic | 16 | 98 | $ $ $ $ |
| Qoibl | 8 | 131 | $ $ $ $ |
| B-tapemark | 14 | 106 | bnd $ $ bnd |
| Object disoriented | 19 | 96 | $ $ $ $ |
| Forbin | 32 | 88 | $ $ $ $ |
| Suffolk | 5 | 200 | $ $ $ $ |
| Blindfolded Arithmetic | 12 | 131 | $ $ $ $ |
| Ascenic | 3 | 300 | $ $ $ $ |
| INTERCAL | 33 | 97 | $ $ $ $ |
| Hot | 6 | 193 | $ $ $ $ |
| Bitdeque | 26 | 113 | $ $ $ $ |
| Codesick | 22 | 121 | $ $ $ $ |
| Flowchart | 16 | 146 | $ $ $ $ |
| Modulous | 26 | 129 | $ $ $ $ |
| SendStuff | 37 | 122 | $ $ $ $ |
| Thue | 12 | 189 | $ $ $ $ |
| ABCDirection | 5 | 344 | $ $ $ $ |
| Container | 41 | 164 | $ $ $ $ |
| Packlang | 50 | 162 | $ $ $ $ |
| Streetcode | 14 | 302 | $ $ $ $ |
| Pointless | 15 | 346 | $ $ $ $ |
| Quassaunt | 41 | 388 | $ $ $ $ |
| Polynomial | 19 | 619 | $ $ $ $ |
| Collatz Multiverse | 43 | 751 | $ $ $ $ |
| BrainIf | 26 | 883 | $ $ $ $ |
| Interprogck8 | 25 | 1160 | $ $ $ $ |
| SLOW ACV MAMMALIAN | 18 | 11954 | $ $ $ $ |

Harness bugs found by the audit itself, fixed in the tool: the
runner called `encode_inputs` for parameterized languages (it
raises for them; five languages' constant tables first read as
unverifiable -- after the fix, three certified and Eval showed its
two gaps); a 20,000-step cap wrongly rejected A Painter Ant's
shipped programs (rows are timeout-governed, as in `_evaluate`);
the search consulted its budget every 256 candidates, which lets
one block of slow-interpreter candidates overrun a wall by minutes
(now every 8); corpus collection and the magnitude formatter each
needed a hard bound (a 150 s alarm, a 30 s one for the arity-3
extension; bit-length digit counts past Python's 4,300-digit
int-to-string limit).  Two early fleet runs were lost to these
(the first stalled inside one pair past its budget; the second
crashed in the formatter after 60 languages) -- the fleet above is
the third run, with records streamed to disk per language.

Commands run:

```
PYTHONPATH=src:scripts python -m superopt audit-one FALSE --arity 1 --wall 900
PYTHONPATH=src:scripts python -m superopt audit-fleet --arity 1 --budget 900 \
    --cap 150000 --wall 90 --out notes/audit-fleet-n1.json
PYTHONPATH=src:scripts python -m superopt audit-fleet --arity 1 --budget 300 \
    --cap 150000 --wall 90 \
    --names "Cyclic tag,Bitwise Cyclic Tag,Smallfuck,A Painter Ant,Eval" \
    --out notes/audit-fleet-n1-fix.json
PYTHONPATH=src:scripts python -m superopt audit-fleet --arity 1 --budget 200 \
    --cap 150000 --wall 30 --names "Eval,A Painter Ant" \
    --out notes/audit-fleet-n1-fix2.json
```

## Idioms (v2)

- Print-then-read: at the smallest sizes, constant programs win by
  emitting their answer before consuming input -- the consumption
  contract fixes *how much* a program reads, not *when*.
- The answer is the last character printed, so printing `-1` is a
  one-char-shorter true than printing `1` (FALSE's NOT gap).
- Termination is a channel: Unary's constant-1 ships 53,431 zeros
  where 695 already diverge on every row, because the generator
  builds a uniform construction instead of the smallest loop.

## 2026-10-18 — the digits gadget is minimal as a whole program, not only as a suffix

Target: any program over the full alphabet (`/ 0 1 2 K0 K1 K2`) that,
from zeroed cells, reads the three input bits and leaves them
injectively in trit 0 of cells 1 and 2. The repo proved the shipped
gadget's *suffix* uniquely shortest after its hand-designed 10-op
wipe prefix; whether some interleaving of reads and applies beats
16 ops in total was open, and the staged prefix looked like the kind
of human design choice a search could improve on. It cannot, in this
model: breadth-first search over full row-state signatures exhausted
depth 15 with no hit, and at depth 16 the first hit is the shipped
gadget itself, certified.

```
PYTHONPATH=src:scripts python -m superopt novel --max-depth 15 --budget-seconds 1500 --node-cap 2000000
  signatures by depth: 1, 7, 19, 52, 163, 377, 843, 1700, 3270, 5962,
  10831, 21002, 45257, 105173, 246174, 549060
  no injective program up to depth 15 (shipped: 16 ops)   [19.0 s wall]
PYTHONPATH=src:scripts python -m superopt novel --max-depth 16 --budget-seconds 1500 --node-cap 3000000
  hit at 16 ops (shipped: 16): / 0 / 1 K2 0 K2 1 / 2 0 1 0 K1 0 2  certified: True   [20.4 s wall]
```

Priced before running from the depth-≤12 calibration (45,257
signatures, 1.5 s): under ~2 CPU-minutes to depth 15; actual total for
both runs ≈ 26 s CPU, inside the stated ≈30 CPU-minute cap.

Scope of the claim: the trit-0 model with zeroed starts. The model is
faithful to the shipped build at that resolution — the wipe prefix
leaves identical post-prefix states from all five groups' real
initial trit patterns as from zeroed cells (checked by running the
prefix from each), and the machine is pinned to the interpreter by
tests. It says nothing about the full 10-trit machine.

## 2026-10-18 — positive control: the shipped suffix, rediscovered

```
PYTHONPATH=src:scripts python -m superopt control
  candidates evaluated: 55987; rows evaluated: 218538
  first injective length: 6; hits: 1
    0 1 0 K1 0 2  certified: True
  control passed
```

No injective suffix of length 0–5 after the wipe prefix; at length 6
exactly one, the shipped suffix. The early-exit filter is measurable
in the counters: 55,987 candidates took 218,538 row evaluations
(≈3.9 of 8 rows per candidate), against 447,896 for full-table
evaluation of every candidate.

## Idioms

- The unique shortest suffix is apply-heavy: `0 1 0 K1 0 2` — five
  cell applies and a single constant. Constants set up one trit
  pattern; the applies do the separating.
- Wipe-then-compute is size-optimal here as a whole: the from-scratch
  optimum (16) equals prefix + suffix (10 + 6), so staging the reads
  in a wipe costs nothing against free interleaving.

## Negative results

- No injective suffix of length ≤5 after the digits wipe prefix
  (exhaustive, this run and the repo's own test).
- No injective full program of length ≤15 over the full alphabet from
  zeroed cells (breadth-first, exhaustive to depth 15).
- The wipe prefix alone leaves only 4 of 8 inputs distinct in
  (cell 1, cell 2); any suffix must manufacture the other four
  distinctions, which is why none is shorter than 6.
