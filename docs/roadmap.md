# Roadmap

Future work only, in priority order.  Language assessments, documented
walls, and ruled-out ideas live in `docs/limitations.md` and
`docs/walls.md`; completed work — including sections removed from this
file — lives in the commit history.

## New interpreters (in priority order)

Candidates from the esolangs wiki's Category:Unimplemented (verified via
the category API), restricted to languages with a complete specification
and a boolean-generator capability (input, a value conditional, output).
Per-language verdicts on everything ruled out are in the
assessed-and-rejected ledger in `docs/limitations.md`.

- **DINAC** — `IN` reads an aschar or wubyte, `OUT` prints, IF-ELSE and
  WHILE on zero/nonzero, truth-machine example.  "Bounded storage" is the
  *value* domains (wubyte 0-255, aschar 0-127); the page states no limit on
  the number of declared variables, and says outright that "AND, OR, and XOR
  can easily be implemented, it's left to the programmer".  So the generator
  is an ordinary nested IF-ELSE decision tree, **O(2**n)** with folding and
  **uncapped in arity** — bounded by program size, not by a structural
  ceiling.  `OUT` means leaves print directly, so it needs no
  termination-convention trick.  Two things to pin: block structure is
  indentation-significant (`N × 4` spaces), which nothing in
  `src/esolangs/interpreters/` does yet and is the bulk of the work; and `IN`
  on exhausted input returns a defined sentinel (`\n` for aschar, `00` for
  wubyte) rather than raising, so DINAC would be a second documented
  exception to the EOFError convention beside S*bleq.  A text generator
  comes nearly free (full printable ASCII plus escapes).
- **Alight** — its boolean generator is an indexed lookup, not a routed
  tree.  It reads each input character, subtracts `'0`, and uses
  ``index = index * 2 + bit`` to build the row number; a string literal holds
  the truth table and ``at{table, index + 0.5}`` supplies the character for
  `out` (lists index from 0.5, so `0.5+k` is the language's own rule, not a
  trick).  That is one table character plus a constant-size unrolled update
  per input: **O(2**n + n)** source, additive rather than multiplicative,
  before the interpreter work.  Measured against the suite median of 218
  characters that is ~211 at `n == 3` and ~4767 at `n == 12` — nowhere near
  outlier territory.  The shape is not new: `tools/boolean/ztoalc_l.py`
  already does double-and-add row indexing into a table, and Alight's is
  cheaper because the table is a string literal rather than one command per
  selected row.  The cost is therefore the interpreter — a 2D walker with
  multi-character command words, three data types and a function system,
  Flowchart/COD-sized rather than Streetcode-sized.  The
  two-dimensional `skip`/`turn` control flow is exercised by tests rather
  than made responsible for the generator's cost.  **The page has no
  truth-machine or boolean example** (its three examples are cat variants),
  so the construction above is derived from the primitives rather than
  lifted from ground truth.
- **function x(y)** — Turing-complete: functions with defaults, `[~]`/`` `~ ``
  input, `[a]`/`` `a `` output, comparison operators, a ternary, recursion; a
  boolean generator branches on a comparison and prints 0/1, reusing
  `forbin_boolean`'s shape.  Richest generator story of the six and the
  heaviest interpreter.  **Decide the recursion model before starting**:
  every call in the page's own examples sits in *expression* position
  (factorial nests the recursive call inside a multiplication), which is
  exactly the shape documented below as Forbin's ceiling — so it is the
  normal case here, not an edge case.  Forbin-style native recursion
  documents a ~248-level ceiling; a Lamfunc-style explicit frame stack
  removes it and is the larger build.  Spec debt to pin: the prose defines
  `/` as integer division but both FizzBuzz bodies use `//`; `=>` is the
  greater-or-equal token; two or three recursion notations (`{y}`, bare
  self-call, named call) coexist with no stated relationship; and there is
  no truth machine, so the boolean claim is inferred from factorial's
  comparison-feeds-a-ternary shape.
- **Packlang** — Turing-complete: packages with the built-in IO package
  (`charGet`/`charPut`), `If`/`While`, XOR/`!`; the truth-machine example
  branches on `input ^ 48`.  `Dependency` blocks sit in the same file as the
  `Package`, so this is namespace resolution rather than a linker; the cost
  is the C-like block grammar, Suptiftam/Forbin-class.  Native `^` makes it
  a **third** ANF generator beside `fargo.py` and `super_snusp.py`, reusing
  the existing Möbius-transform construction rather than adding a shape.
  Three gaps to pin, none reaching the generator: no assignment operator
  (only `INIT`/`INCR`/`DECR`/`charGet` mutate), no `Else`, and no documented
  entry point.  A fourth is sharper — **the wiki contradicts itself on
  numeric literal base**: Hello World and cat use decimal ASCII (`72`, `108`,
  `44`, digits 2-9 rule out binary) while `plusOrMinus` and the dependency
  example use bare strings (`101011`, `110000`) that only read as binary.
  One reading falsifies the other; pick one and document the rest as broken,
  per Suptiftam's precedent.  The generator's primitives all sit on the
  decimal, unambiguous side.
- **Interprogck8** — weakest candidate, but not for the reasons first
  recorded here.  `u` input, `div` output, and IFT/IFQ plus self-`EXE` (the
  loop its cat example demonstrates) make a truth-machine.  Steering the
  accumulator to the *fixed* ASCII codes (84/81) that IFT/IFQ compare
  against is a one-instruction gadget, **not** the cost driver.  The real
  open question is control flow: there is exactly one "current function"
  slot, functions cannot nest, and there is no general backward jump, so a
  `2**n`-leaf tree has to route through `DownAccLines`' accumulator-keyed
  computed jump — a mechanism none of the other candidates use, and one
  nobody has attempted.  That is what ranks it here.  Two corrections to the
  earlier entry: `developer`, which prints the interpreter's own source and
  is "technically implementation-dependent" on the page, is **not** in
  Taglate's `t` mould — `t` transforms the program's own queue into a
  translate URL by a host-language-independent algorithm, so the precedent
  does not transfer and the call needs its own argument (excluding the
  command from generated programs is the likely route).  And the randomness
  is a non-issue for a simpler reason than seedability: the wiki's own
  truth-machine uses `[49 49]`, a same-endpoint range that is a disguised
  constant, and `{values/=a/=b/=c}` takes a plain dice literal — so a
  generator never draws at all and the VM branching protocol never binds.
- **Pinyin** — **unpriced; re-audit before building.**  The stack can retain
  one nonzero input character as a source of `1` (duplicate it and divide it
  by itself), but has no table/list storage.  A full planar decision tree is
  the direct construction.  At each node, a character input is normalized
  with ``x % ((x / x) + (x / x))``; copies then make zero and `q` compares it
  with the bit, sending the two outcomes in opposite directions.  The
  retained character lets either leaf print integer `0` or `1`.  It spends 12
  executable character commands per internal node and 3/5 per one/zero leaf,
  plus routing and grid padding.  Three unresolved problems sit under that
  paragraph.  A flat 12-per-node cost over `2**n - 1` nodes is **O(2**n)**;
  the claimed extra factor of `n` must come entirely from the routing and
  padding, which is exactly the part never priced.  Commands dispatch on
  *pinyin phonetics*, so every node and leaf must be a real Chinese
  character whose romanization supplies the needed
  (consonant-condition, vowel-effect, tone-direction) triple — a dictionary
  dependency no other generator here has, and one that breaks the
  construction outright if some triple has no character.  And the spec never
  says whether a tone's direction change still applies when the consonant
  condition fails and the command is a NOP; under the natural reading it does
  not, in which case a single glyph cannot route two ways and every node
  needs two placed characters.  The page's own truth-machine is bare
  characters with no romanization table, so ground truth is not decodable
  from the page.  ABCDirection is the warning: it passed every check a spec
  read can apply, then measured 58x the suite median and was removed.  Give
  this the treatment Super SNUSP got — build the interpreter, attempt one
  real `n == 2` XOR, measure it — before scheduling it.

These complete the priced survivors of the 2D/grid pass
(`Category:Two-dimensional languages` ∩ `Category:Unimplemented`). Full
per-language table, including the named blockers and rejections for the
rest of the pass, is in `notes/twod-unimplemented-audit.md`.

## Transpilers

**Open research item: lowering drawn control flow.**  A Streetcode ring has
no brainfuck loop image -- the car never returns to the junction that steers
it as the same drive state -- and the boolean generator's programs are
decision trees whose leaves each print.  Both are lowerable in principle
with scratch cells and a converged answer, which is a compiler rather than a
program rewrite.  This is the same class of future work as the OISC pair --
and that pair is the precedent to follow: `decleq_to_sbleq` clears the
admission bar by *emulating* the source machine's semantics, because only an
emulator has no interiors (Decleq can jump into a block's interior;
Streetcode revisits junctions under a different drive state -- the same
shape of problem).  It would be the first real control-flow lowering here:
the other three shipped transpilers are per-command transliteration onto a
superset target.

Three things price this as **large**, not as queued work.  Following the
OISC precedent means emulating a 2115-line interpreter
(`interpreters/grid_based/streetcode.py`) whose own doc lists four-way
junctions and post-corner behaviour as unverified even in the reference.
`Streetcode → LaserFuck` was already built once (`0c991940`) and removed
(`3dab3b18`) as one of six partials that failed the current admission bar,
and a revived pair inherits LaserFuck's own partiality -- no output command,
only a tape dump at halt -- needing a second criterion-3 proof or a switch
to plain brainfuck.  Verification also needs a Streetcode *program* fuzzer
that does not exist, and random grids will not supply one: an earlier sweep
of 40k random grids hit zero junction arcs, so the corpus has to be
constructed.  No worked lowering exists in the repo today; earlier text here
cited `docs/limitations.md` for "the measured argument and the worked
examples", but that file carries the removal rationale and unrelated
decision-tree cost figures, not a construction.

The remaining candidates (a second Forth dialect ↔ Forþ,
Boolfuck ↔ Minifuck) each need a *new* interpreter first, so they belong
under "New interpreters" if that language is ever added.

## Deferred-removal candidates

A language becomes a candidate when it has real language-defined output but
no generator that uses it, or when its only boolean construction would break
a documented convention and its text generator is too thin to stand alone
(criteria and removed cases: `docs/limitations.md`).  Interpreter-only
languages with a working, uncapped boolean generator are **not** candidates.

**No language is currently a candidate.**  The standing argument for when
one reappears: most interpreter-only languages are the *only* implementation
on the wiki, so removal leaves a gap the admission criteria treat as real.
Resolve that tradeoff deliberately, not by default.

## Extra implementations (cross-checks)

`extra/assembly` holds RISC-V ports of already-interpreted languages, fuzzed
against the Python by `scripts/verify_differential.py`.  `extra/line` is a
different category — the only implementation of its language, kept out of
`registry.py` because its programs are PNGs — not an integration gap.

Two admission rules govern new cross-checks:

- **Fuzzability.** The generator's output must be complex enough to fuzz —
  branching, loops, or 2D routing.  A straight-line generator is already
  fully covered by the round-trip test.
- **Toolchain follows the model.** RISC-V fits machine-model languages
  (tape/pointer/counter → cells/registers/jumps).  Semantic languages
  (stacks, typed registers, 2D grids) have no cross-check toolchain, and
  RISC-V cross-checks are no-input only: the fuzzer feeds the *program* to
  the ELF's stdin.

Every audited candidate is either semantic, input-reading, or has
fixed-pattern output, so **none has a route today**.  Circuit Diagram is the
one unassessed case: its output genuinely varies with the table, but its
generator is already replayed over each table's entire input space, so a
differential would mostly re-cover that ground.  Revisit only if a concrete
bug suggests the two implementations could disagree.

## RISC-V assembly compilers

The compilers in `src/esolangs/compilers/` translate a program to RISC-V
Linux assembly, run under unicorn by `scripts/verify_riscv_unicorn.py`.  The
no-input rule does not apply (a compiled program is embedded, leaving stdin
free), but the toolchain rule does.

A compiler is worth building for **verification value** (a complex-output
generator exercised through a compile-then-fuzz differential) or **intrinsic
value** (genuine lowering — control flow, calls, memory, dispatch — rather
than per-command transliteration).

**The queue is empty.**  Two facts constrained the last candidates: the
target is **`rv64i`**, whose base integer ISA has no float and no hardware
multiply (forth already emits software `mul32`/`divmod32`, so integers are
precedent and floats are not); and a differential is only worth the name
when the generator *reads input*, since an `_embedded` generator substitutes
its bits into a fixed template and replays the same program.

The 2D/grid family stays out under the toolchain rule, and the
drawn-control-flow item under **Transpilers** already covers that direction.

**Input-reading compilers are supported**, no harness work needed
(`COMPILER_CASES` takes an optional fifth element carrying stdin).  The rule
for a new one: match *its own language's* refill, not a default.  Forbin's
`in` reads a whole line and returns its first character (line-faithful,
so byte-consecutive reads would diverge); Container's refills a queue with
line contents minus the stripped terminator and consumes one char per pulse,
so `_riscv_common.GETBYTE` plus a newline skip is the correct lowering there.

## Forbin's expression-position recursion

Forbin's *expression-position* calls (`x = f(y)`) recurse natively, so their
depth is the host's rather than the language's: measured at 248 levels, about
four Python frames per Forbin call.  Past that `_Machine.step` converts the
`RecursionError` into a `HaltError` naming the limit, so the ceiling is a
documented halt rather than a leaked traceback — but it is still a ceiling,
and statement-position calls remain uncapped past 2000.

Lifting it, rather than reporting it, needs `_eval` itself extended into a
resumable continuation stack (the `_EvalTask` design, rejected in
`docs/walls.md`); "expression calls as builtins" does not avoid that work,
since a builtin is a leaf while a call sits at an interior node of a
half-evaluated tree.  Forbin has no realistic program shape that recurses
this way — `return` exits a call immediately, so values thread through
statements, not nested expressions.  **Not pursued unless a concrete program
needs it.**

## Hanging-test optimization via state-cycle detection

See `docs/limitations.md` for what `esolangs.vm.run_until_halt_or_cycle`
already covers.  **Randomness no longer costs a language its hang proof.**
All six random-drawing interpreters — Painfuck's `y`, WII2D's `?`,
LaserFuck's heading, Super SNUSP's `=`, Modulous's `RND` and COD's junction
— implement the branching protocol, so `run_until_halt_or_all_branches_cycle`
decides them by searching every draw instead of one sampled run.
`tests/test_vm.py` derives that set from the registry and asserts the whole
of it conforms, so a new random language fails until it is decided too.

What remains is the class no snapshot can catch: an unbounded-growth loop
never revisits a state, so it stays on the wall-clock backstop whatever else
is built.  That is a property of cycle detection rather than an open
question, and two undecided results sit beside it by design — a reachable
input command, which cannot be forked without sibling branches sharing one
cursor, and a transition whose fanout exceeds its language's per-transition
cap.  Both raise rather than guessing.

**This section is closed.**  Nothing here is scheduled work.

## Input reordering (remainder)

Generators build under every input order and keep the shortest.  **The queue
is closed in both tiers** — every candidate with a measured screen is shipped,
built-and-declined, or costed and closed, and
`docs/generator-optimizations.md` carries each verdict with its figure.  What
is left is below the thresholds that section sets (about 5% for a rename,
10% for a hoist that must restructure), so none of it is scheduled:

- **ArrowQueue's reorder (12.4%)** — the one unclaimed screen figure, and the
  only item here above the bar.  Its queue-fed template needs re-enqueue
  gadgets to bring a bit to the front; permuting which name sits in each
  header slot is not an alternative, since `_header_rows` fills the header
  positionally and the names are inert.
- **Back's snaked load (+1.9%)** — the load runs up column 0 at one command
  per row, so it is `2n+2` rows tall against the tree's ~7.5; snaking it into
  two columns nets about 1.9% at `n == 3`.  Under the bar, and the turn-mirror
  estimate is the soft part: a turn cell cannot also carry a load command.
- **Bitdeque's free-reorder headroom (0.9%)** — blocked in the *harness*
  rather than the language.  `_fill_bitdeque` derives each setter's parity
  from the input's **name**, assuming input *i* sits at load position
  `n-1-i`, so permuting names between slots desyncs every fill site.

Before reopening any of these, read that section's four rules first — the
screen is neither a floor nor a ceiling, reachable orders are usually far
fewer than `n!`, the cell map is the inverse of the permutation, and a
generator that validates its own output needs that check frame-mapped too.

## Mutation-testing sweep

Per-language scores and survivor counts are not recorded here: they go
stale on any test change and are cheap to re-derive (`just mutate
<language>`, wrapping `scripts/mutate_one.py`) — re-run the language you
touched, and re-run everything after a change to the shared machinery.
Rules a future triage pass has to get right, each cheap to violate
silently; see git history for the worked examples behind them.

**Trusting the measurement:**

- Measure on an idle machine — a contended run's per-test alarm scores
  slow-but-passing tests as kills, under-reporting survivors.
- `uv run` can silently measure the wrong tree (reinstalls from the project
  root, so a worktree's edits never reach the bundle) — use
  `PYTHONPATH=$PWD/src`.  Tell: a survivor on a line already deleted.
- A probe whose own baseline is unstable (e.g. an interpolated object with
  no `__repr__`) can witness a large batch of otherwise-unkillable mutants.
- Naming `esolangs.vm` in a docstring drops the test from the bundle exactly
  as an import would; a survivor is not a gap until the harness is trusted.

**The last survivor is often the source's fault, not the suite's** — a
construct that cannot be observed is usually one that need not exist:

- A redundant argument restating an already-default value is unkillable by
  construction; delete it rather than testing it.
- A default guarded by something upstream that already ran is dead code.
- A `*` regex quantifier never fails, so its fallback branch is dead;
  `partition` often says the same thing with no unmatched case.
- Dead guards (unreachable early returns, seed values every path treats
  alike) produce survivors that teach nothing — delete the guard.
- Two copies of one bounds check can each be half-dead in a different half;
  merging into one check over a signed delta leaves every fragment live.

**Writing the test that kills it:**

- A survivor is only as tested as the observables compared — output and step
  count miss bookkeeping fields; compare full `snapshot()`.
- "Symmetric table" is not an equivalence argument by itself — check what
  the snapshot actually carries (coordinates, heading) before calling a
  relabelling invisible.  Assert the coordinate, not just the output.
- `pytest.raises(match=...)` is a substring search; use
  `assert str(caught.value) == message` to catch a widened message.
- A default argument every test overrides explicitly is untested at its
  default value.

**A rewrite can install a gap where it removed slack** — re-measure after
every refactor rather than assuming the score only improves.  Two observed
mechanisms: swapping a regex for `partition`/`rpartition` can introduce an
agreement neither version's differences previously required; and factoring
matched-length iteration into `zip` can make ruff's `strict=` argument
unfireable when both operands are always fixed-length. A lint rule can
mandate slack that then can't be tested.

Triage from the test file, not the diffs — recurring shapes are
substring-matched `pytest.raises`, comment tests outside the command set,
truth-only `bool` flags, one-sided boundaries, write-only attributes, and
assertions on a constant.  A score is a means: stop where survivors stop
teaching anything.

**Sweeping survivors against a corpus** beats triaging one mutant at a time.
`mutate_one.py --keep` leaves the mutated bundle on disk; import
`mutants/bundled.py`, set `MUTANT_UNDER_TEST=bundled.<name>` in the
environment, run each program in a corpus, and report the first whose output
differs.  Test-writing then aims at a witness instead of a guess.  Three
mechanics to get right:

- `MUTANT_UNDER_TEST` is the only switch — rebinding the module attribute
  does nothing.  A module with an import-time dispatch table needs that
  table entry patched too, for the same reason.
- Drive the machine with a step limit, not `run` — goto loops and unbounded
  tape walks are legal in most of these languages and will hang an
  uncapped sweep.
- Match the language's own entry convention (e.g. a list of lines vs. a
  string) or every program in the corpus silently misparses.

**The yield is a function of corpus breadth — a no-witness result means "not
reached by this corpus," not equivalence.**  Read the diffs of the
no-witness set and ask what input shape each one needs; missing shapes
cluster, and widening the corpus (unusual operands, multi-pass loops, both
operand slots of every operation) has repeatedly turned "equivalent" verdicts
into witnessed kills.

A corpus worth writing covers each command with a non-default argument, both
directions of every movement, a zero and a maximum operand, an empty
container and one of length three, a loop of more than one pass, each error
path, and every optional token both present and absent.

## Generator build cost (measured, not previously catalogued)

A build-frontier sweep over all 64 registry languages — one random table per
arity, an 8s build budget, **build only: the generated programs were not
executed** — puts 54 generators past `n == 9` and stops ten below it.  Five
stop by *raising a declared cap* (6-5, Factor, Polynomial, WII2D, ZTOALC L),
each already in the `docs/limitations.md` ledger and structural rather than
scheduled.  The other five stop by *running out of time*, and two of those
are recomputation rather than irreducible work.  Re-derive the sweep rather
than trusting a table here; the figures below are what it found.

- **SLOW ACV MAMMALIAN's search recomputes (6.8x measured, unshipped)** — the
  lowest build frontier in the repo: `n == 3` builds in 1.5s, `n == 4` in
  **118.7s**, roughly 30x per input while the program itself grows only 2.2x.
  It is search cost, not size.  `_candidates` is 62% of the build across
  338,671 calls, and it is a *pure* function of `(array, acc)` asked the same
  question over and over — at `n == 3`, 4,615 calls carry only **90 distinct
  argument pairs** (51x redundancy).  Memoizing it on a tuple key cuts
  `n == 4` from 118.7s to **17.5s** and leaves the emitted program
  **byte-identical** (verified on 14 tables plus the `n == 4` build).  The
  module already caches `_zero_arm_length_cached` exactly this way, so the
  shape has precedent in its own file.  **The open question is whether the
  cache alone reaches `n == 4` inside a test budget and `n == 5` at all, or
  whether `_candidates`' per-node `range(256)` sweep needs restructuring** —
  a 6.8x on a 30x-per-input curve buys well under one input.  Same status as
  ArrowQueue's reusable drain below: verified, unshipped, worth it only if
  deeper tables start mattering.
- **Forþ searches `n!` orders when only `2 * 3**(n-2)` are reachable** — its
  order loop iterates every permutation and calls `_forth_ordered` on each,
  which validates the table and *then* discovers the arrangement is
  unreachable and returns `""`.  The reachable count is the one
  `_forth_stack_programs` already enumerates, so the filter runs after the
  cost instead of before it: **28x wasted builds at `n == 8`** (40,320
  iterated, 1,458 reachable), 10x at `n == 7`, and the waste grows with
  arity.  Its sibling `unsquare` iterates the *reachable set* directly and is
  additionally capped by `_ORDER_SEARCH_MAX`; `forth` has no cap at all.
  Two candidate fixes with different reach — iterate the reachable
  arrangements as `unsquare` does, or hoist the reachability check above the
  validation — and neither changes which program wins, since the losers are
  exactly the orders that return `""` today.  Confirm that before shipping:
  the reorder rules in `docs/generator-optimizations.md` apply.

## Dependency reduction

A table ignoring some inputs is a smaller table, and where a generator's cost
scales with *input count* rather than row count that beats any per-row
saving.  Clockwise is the obvious remaining candidate and does not reduce:
`clockwise` (`other.py:681-888`) makes no `essential_inputs` call.  What is
open:

- **Taglate's odd-sized sets** — **closed; the premise was wrong.**  Earlier
  text here said widening the window by one adjacent ignored input "costs a
  tier back".  It does not: `taglate` already pads any odd `n` to
  `n_eff = n + 1` with a leading ghost digit (`other.py:630-637`), and the
  whole `_even_reduce`/`_odd_reduce` cascade is written for even `n_eff`
  only, so an odd-sized essential set lands on the same tier either way.
  Measured on parity tables (all inputs essential, so no reduction fires):

  | `n` | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | chars | 14 | 121 | 451 | 451 | 1521 | 1521 | 5499 | 5499 |

  Odd `n` costs exactly what `n + 1` costs, so the sidestep is already near
  optimal — its marginal cost is one `h` read plus a few selector
  characters, not a tier.  A real saving would need `taglate`'s core
  rewritten to handle odd `n_eff` natively: a new odd-parity cascade and a
  replacement for `_SEL1_N2`, which is committed to exactly two remaining
  inputs (`other.py:355-368`), plus the seed/prefix formulas that assume
  even `n_eff`.  That is new machinery rather than a thirteenth instance of
  the reduction pattern, its payoff is unmeasured, and it would break the
  read-count contract `test_reduced_programs_still_read_every_input` asserts.
  Not scheduled.

## Smaller open items

- **ArrowQueue's reusable drain** — a fixed-block leaf drain (rather than a
  staircase) is verified correct and written up in
  `docs/generator-optimizations.md`, but unshipped: it only wins from n≥5,
  past where anything exercises folding.  Two things to know before picking
  it up.  "Verified but unshipped" means *no source exists* — the commit
  behind it (`a6ec99de`) touched only the two docs files, so shipping is a
  build (drain construction, an entry-mode parameter, a depth dispatch, and
  extending `test_folding_never_grows_a_program` past its `n <= 3` pin), not
  a swap; the design is settled but the code is not written.  And the
  crossover is out of reach rather than merely unexercised: the staircase
  wins at every fold depth through 4 (60/93/111 characters against
  92/108/116) and only loses from depth 5, which needs an `n >= 5` table
  carrying a 5-deep constant subtree — `n == 5` is exhaustively ~407
  CPU-days away, and the suite's two random `n == 5` samples will
  essentially never contain one.  A wrong entry-mode dispatch previously
  failed 530/2120 cases, so a careless port costs correctness at `n <= 4`,
  not just characters.  Revisit if a *proof* pushes exercised coverage to
  `n >= 5`.
- **Streetcode evidence types** — carrying `_Machine._validate`'s five proofs
  in a chain of evidence classes would make the ordering checked rather than
  documented.  Deferred: it removes two correct `pragma: no cover` lines and
  nothing else, the ordering lives in one six-line method with one call site,
  and marker classes are erased at runtime.  Revisit only if the module is
  restructured anyway, or a validator lands whose ordering is non-obvious.
- **Severely constrained boolean generators** — caps are tracked so removal
  or lifting is deliberate.  No language is currently a *removal* candidate:
  every shipped generator covers `n <= 2` at minimum.  6-5 is the one
  documented wall left (`docs/limitations.md`); %^2^-1 is partly lifted with
  the rest open.
- **NoComment's tape size** — **closed; already shipped.**  The `tape`
  argument on `run`/`nocomment` is the whole mechanism this item proposed,
  and `n == 12` at `tape=16384` already builds, runs and is asserted by
  `test_a_bigger_tape_lifts_the_cap`, with the lifted bound recorded in
  `docs/limitations.md`.  Measured source is 27158 characters at `n == 11`
  and 51407 at `n == 12`; the default 4096 refuses `n == 12` because the
  generator needs cell 4650, and it stays 4096 because the size is
  observable through the wrap.  Nothing in the repo calls for `n >= 12`, and
  raising the tape further buys little: the wide path's *construction* walls
  well before the tape does (an `n == 15` build does not finish).
