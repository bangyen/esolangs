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
  Flowchart/COD-sized rather than Streetcode-sized.  The two-dimensional
  `skip`/`turn` control flow is exercised by tests rather than made
  responsible for the generator's cost.  **The page has no
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
program rewrite.  The OISC pair is the precedent to follow: `decleq_to_sbleq`
clears the admission bar by *emulating* the source machine's semantics,
because only an emulator has no interiors (Decleq can jump into a block's
interior; Streetcode revisits junctions under a different drive state -- the
same shape of problem).  It would be the first real control-flow lowering:
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

### Jaune's computed dispatch: implement in both engines, or delete

`compilers/jaune.py` emits `switch:` and `.switch:` blocks for a `v`-operand
marker — `v@` (call the subroutine the input names) and `v?`/`v!` (jump to
the label it names).  **The interpreter does not implement those forms**:
its `_READ_OPERAND` maps `+` and `-` only, so `v@`, `v?` and `v!` raise
`ValueError`.  That is a scope decision to ratify or reverse, not an
oversight to patch — and it is the one Jaune divergence the round-trip
cases cannot settle, because there is no reference behaviour to compare
against.

Measured rather than assumed: the blocks are live, not dead.  `prep` strips
`v:` and `v$` but leaves `v@`/`v?`/`v!` standing, and all four probes below
emit a switch block.  What they then do is the argument for doing something:

| program | interpreter | compiled |
| --- | --- | --- |
| `v@^.1$5+;2$3+;` | `ValueError` | `1` — echoes the input, never calls sub 1 |
| `v?^.1:9+;` | `ValueError` | emulator fault |
| `v!^.1:9+;` | `ValueError` | emulator fault |
| `5+1:v?^.` | `ValueError` | prints nothing |

So the compiler accepts a form the interpreter rejects and then miscompiles
it.  The fork is the wiki spec, and it decides the work:

- **If the wiki defines the `v` forms** — implement them in the interpreter
  (a `_READ_OPERAND` entry per marker plus dispatch), fix the emitted
  blocks, and pin round-trip cases.  Only then is the compiler's existing
  machinery worth keeping.
- **If it does not** — delete the `switch:` blocks, the `inp` flags that
  gate them, and the `-1` operand path in `count` that routes to them, and
  let `prep` strip `v@`/`v?`/`v!` the way it already strips `v:`/`v$`.

Do not settle it by reading `compilers/jaune.py`: the emitted code is the
thing under suspicion, so it cannot be its own specification.

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
is built — a property of cycle detection rather than an open question.  Two
undecided results sit beside it by design: a reachable input command, which
cannot be forked without sibling branches sharing one cursor, and a
transition whose fanout exceeds its language's per-transition cap.  Both
raise rather than guessing.

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

## Generator build cost

A build-frontier sweep over all 64 registry languages — one random table per
arity, an 8s build budget, **build only: the generated programs are not
executed** — put 54 generators past `n == 9` and stopped ten below it.  Five
stop by *raising a declared cap* (6-5, Factor, Polynomial, WII2D, ZTOALC L),
each already in the `docs/limitations.md` ledger and structural rather than
scheduled.  The other five stop by *running out of time*.  Two of those five
were recomputation and are now fixed (see the commit history for the
figures); re-derive the sweep rather than trusting a table here.

What the two fixes did **not** buy is the interesting part:

- **SLOW ACV MAMMALIAN's candidate sweep is closed and shipped.**  The
  former `_candidates` scan (118.7s at `n == 4`, then 17.5s after
  memoization) is now an arithmetic construction.  A read node chooses
  `j1` by residue -- at most 49 `SEED`s put its first digest on the even
  `01` bits-4--5 aim class -- and its taken branch consequently lands at
  exactly `start - 15`, independent of `j1`.  Stash chunks raise that start
  sum to aim the landing, while a `DIGEST`-based trampoline cancels the head
  and solves any target with one byte plus enough 255-valued chunks.  No
  candidate or neighbour is retried.

  The build cost is now 0.0003s for the `n == 3` parity table (from 0.745s)
  and 0.02s for the contract sweep entry (from 3.04s).  It was checked by
  running all 276 tables through `n == 3`, 50 random `n == 4` tables, and
  five `n == 5` tables over every input row.  The tradeoff is source size:
  `n == 3` parity grew from 4264 to 8704 tokens because fixed trampoline
  slots and dead pads replace adaptive placement.  This is not scheduled
  work; re-measure only if a future layout wants to reclaim that size.
- **The reachable-set lesson does not generalize — swept, and `forth` was
  the only case.**  `forth` iterated all `n!` input orders when only
  `2 * 3**(n-2)` are buildable, filtering *after* paying for each, while
  `unsquare` in the same module had always iterated the reachable set.  A
  sweep for that shape covered both routes: the 20 generators reaching
  `best_input_order`, instrumented at the helper to count per-order builds
  returning `""`, and the three self-rolled loops (`six_five`, `streetcode`,
  `laserfuck`) read individually.  **No generator now pays materially for a
  build it discards.**  Two near-misses, neither worth changing:
    - `CV(N)(C)` discards the most orders — 17% at `n == 4`, 65% at
      `n == 6` — but `_hoisted` calls `_deque_schedule` *first* and returns
      before building, so a rejected order costs the schedule search and the
      caller's `permute_truth_table`, not a program.  That is the right shape
      already; it is the opposite of `forth`'s.
    - `six_five`'s empty candidate is a label-budget overflow, which is only
      knowable *after* building — so it cannot be pre-filtered.  It never
      fires below the arity where the table is unbuildable anyway: 0 of 1200
      order builds discarded at `n <= 5`, and 5760 of 5760 at `n == 6`, where
      `six_five` raises regardless.
  **Both negatives are controlled**: the first sweep reported zero discards
  everywhere because patching `esolangs.tools.boolean.cvnc` silently patched
  the *generator function* the package `__init__` exports under that name,
  not the module.  A positive control — `CV(N)(C)`, documented to return
  `""` — caught it, and `six_five` at `n == 6` is the control for the
  self-rolled half.  Re-derive with those controls or not at all.

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

- **Jaune's markers read one digit** — `count` takes the operand of `:`,
  `$`, `@`, `?` and `!` from the single character before them, so a program
  with ten or more labels or subroutines would spell one `10:` and be read
  as `0:`.  Not reachable today, and that is the whole reason it is filed
  here rather than fixed: `prep` renumbers labels and routines from 0
  upward, so reaching two digits needs a program with ten of one kind.  The
  counts beside them were widened to full digit runs when they turned out
  to be broken (`10+` compiled to an add of one); the markers were left
  alone deliberately, since widening an unreachable path is untestable
  except through `prep` itself.  Fix it together with any change that lets
  `prep` emit two-digit markers.
- **Closed forms for the search-based boolean generators** — **all
  closed and shipped.**  Most generators construct their answer; five
  searched for it, and each now names what it finds instead.  A sweep of
  every module in `tools/boolean/` for a live frontier (rather than for
  the word "search", which appears mostly in prose describing searches
  that were *replaced*) found these, all confirmed by instrumenting the
  function and building real tables.  **Instrument the function the
  shipped entry actually calls, over enough tables to see it fire**: this
  sweep has now reported a false negative *twice*.  It first missed
  Minifuck by patching `_derived_plans`, the offline sibling, which
  fires zero times in a real build — the runtime path reaches the
  enumeration through `_staging_index` instead.  Then, having closed
  `_staging_index`, it declared Minifuck done while `_mux_probe` was
  still probing the interpreter per table, because the tables sampled
  happened not to route through the sculpt.  Patching the wrong name —
  or the right name on too few tables — reports a clean negative:
    - **Eval** — **closed; shipped.**  `_eval_stack_programs`
      (`parameterized.py`) was a genuine BFS over `(tree stack, input
      stack, active stack)`; it is now a fold over `_EVAL_REORDERS`, the
      named catalog of every reorder program the 16-op cap admits.  The
      catalog is finite because a non-identity program spends two ops on
      toggles and one on a reversal, leaving at most 13 `=`s of travel —
      it never moves more than six values, so past `n == 12` no new
      arrangement can appear: the capped search returns 620, 691, 717,
      728, 733, 735 entries over `n == 7..12` and is frozen at 735 from
      then on (checked through `n == 16`; byte-identical dicts, order
      included, plus a 736-table corpus with zero output diffs).  Two
      hypotheses failed on the way and are worth not rediscovering: the
      *uncapped* metric has no small exact theory — minimal op strings at
      `n >= 5` zigzag the cursor, and contracting runs to units is lossy
      (133 arrangements at `n <= 7` are only optimal via maneuvers that
      transiently split a run) — so the closed form names the capped
      catalog, not a distance formula.  The BFS itself survives as the
      specification oracle in `test_reorder_catalog_matches_search`.
    - **%^2^-1** — **closed; shipped.**  All five searches are gone.  The
      two enumerations froze as named data, the way `_FOLD_SKELETONS` froze
      the mined plans: `_ladder_tables`' suffix BFS became `_LADDER_BUILT`
      (24 witnesses, byte-identical templates, each re-derived by `_apply`
      over its ladder's rungs in the tests) and `_spellings_by_width`'s
      enumeration became `_SPELL_BASES` (a minimal witness per parity per
      grid map; every other width derives by `pp`-suffix or, after the
      erase, `s`-prefix padding — width sets checked equal to the
      enumeration's over the whole grid, so which tables build and at what
      width is unchanged).  The three planner searches (`_fold_search`,
      `_fold_beam`, `_fold_to_cofactors`) fell to one rule construction,
      `_fold_rule_move`: merge where a landing window holds a same-class
      wiped point, wipe a same-class end run together, double to grow the
      windows, hop an end group by the first *collision-free* amount to
      compress — that computed amount is what the descent's ±2/±4
      candidate sweeps were actually buying, and naming it is what made
      the packed eleven-input ladder plan under rules.  Acceptance is
      measured, not argued: 610 planner states (n == 3 exhaustive, 200 at
      four, 150 at five, specials included) and 658 harvested bridge
      states accept exactly the search's set — zero lost, zero gained —
      and a 452-table baseline diff shows 72 outputs changed (22 affine
      respellings at non-minimal widths, 50 fold plans at `r >= 6`), every
      one re-executed on the interpreter, aggregate 22.1% shorter.  Plans
      are also faster than the searches they replace: 89ms → 1.0ms median
      at five inputs, 0.53s → 3.2ms at six, and a 997-group eleven-input
      table plans in 2.3s.  What the mining falsified is worth keeping:
      the `(r, delta, pat[1])` skeleton key is ambiguous at `r == 6`
      (patterns 011000 and 110000 share it and need different plans), so
      the generalisation past the tabulated `r <= 5` is the rule loop, not
      a wider table.
    - **123** — **closed; shipped.**  `_verdict_search` — a bounded DFS
      over kills, boosts and ring rounds whose totality was a conjecture,
      and which made a dense table expensive (a sampled `n == 5` table
      took 401s) — was replaced by a planned shield-and-sweep: separation
      leaves every row at a distinct odd position with nothing marked
      above its own cell, on which one kill segment is a closed form
      (dipped rows provably loop unless their tested cell was pre-marked,
      undipped rows return to their exact positions), so the verdict is
      one `_paint` shield per 0-row plus a single kill above the highest
      1-row.  The whole move algebra the DFS chose from went with it —
      `_try_kill`, boosts, ring rounds, `_gap_fix`, `_align_residues`,
      and the two-geometry budget probe (the parity law that forced it
      bound the searched kills' mark anchors, which no longer exist).
      Exhaustive at `n == 4` (65536/65536 built and replayed) and random
      sampling at 5 and 6: `n == 5` builds in ~0.5s against the 401s
      sample, and dense tables stopped being the expensive case.  See
      `docs/walls.md` for the derivation.
    - **Minifuck's staging index** — **closed** (the module's *other*
      search is the mux sculpt below, also closed).
      `_staging_index` used to run the
      interpreter over every staging — 4640 `claim` calls driving 63.8M
      steps, 25.6s of a 38.4s `n == 5` build — and now derives every
      column arithmetically: the suffix is a prefix-XOR staircase
      (`_Chain`), the pool code is a slice constant (the embed leaves
      every cell below 16 row-independent, a suffix never writes below 15,
      and no pool code reaches past cell 6), and the walk out is an
      interval XOR.  The recorded negative — "the printed column does not
      reduce in `(suffix, accumulator)`" — was about translations and
      still holds; the column *is* closed-form in the embed's standing
      columns once the pool's state-dependence is proved slice-constant.
      Accepted on whole-index equality, key for key and staging for
      staging, at every staged arity, so the first-hit contract is intact
      and no template changed.  Measured cold: `_staging_index(4)` 6.5s to
      0.62s, `_staging_index(5)` 31.5s to 1.12s; what survives of the old
      cost is ten embeds and twenty pool probes per arity.  The emit-and-walk
      spelling lives on in `_derived_plans`/`_column_sweep` as the oracle
      the tests compare against.
    - **Minifuck's mux sculpt — closed; shipped.**  `_mux_probe` scanned
      `_POOL_CODES` through `_pool_reaches`, a real interpreter probe, once
      a round.  It is now `_SCULPT_POOL_CODE`: the fifth code answers
      `cell7 == 0` at every arity, accumulator and round, and `cell7 == 1`
      is answered by none.  The rule is structural in three steps —
      `_mux_probe` emits `x` and clamps, so every probe sees rows at
      pointer 0 with pool region `(0,1,1,1,1,1,1,1)`; running a pool code
      from there touches at most cell 6, inside the 8-wide region the
      verdict reads; and a sculpting round cannot write into that region
      under the rewind guard `rewind > min(ptrs) - _POOL_WIDTH`.  So the
      state the verdict reads is a constant of the construction, and the
      `hint`'s "zero switches" was a theorem, not a coincidence.  Measured
      at 2 distinct full probe states (the two `cell7` values, nothing
      else) over exhaustive `n == 3`, 200 sampled at four and 12 at five —
      169628 probes, code index 4 every time, hint suppressed so the scan's
      own verdict was recorded.  Acceptance is byte equality on 468 tables
      (exhaustive three, 200 at four, 12 at five): **0 differ**.  The scan
      survives as the specification oracle in
      `test_sculpt_pool_code_matches_scan`, and `_find_pool` keeps its own
      scan — it asks the same question of the *derivation* path, whose
      joints are not clamped to this state.
      **What the entry that opened this got wrong, worth not repeating.**
      It read "14.5s of a 17.9s warm five-input build" as the cost of the
      scan.  That was cumulative time in `_mux_probe`, and the scan was the
      smaller half: the `hint` already skipped the list on every round but
      the first, so naming the code is worth about 10% (~3.1s to ~2.8s
      warm), and `_pool_reaches` profiles at 3% afterwards.  The bulk of
      `_mux_probe` is the *column derivation* — the walk and clamp over
      every row, once a round — which is a different question and is not
      closed by this constant.  A cumulative-time attribution names the
      caller, not the cost; the value here is the rule, not the seconds.
      **The round loop itself does not close, and the reason is
      structural.**  A round is provably clean above the frontier — over
      36864 round transitions at exhaustive `n == 3`, **0** moved a row
      above the frontier, which is the monotonicity that bounds the loop —
      but **27656 of 36864 (75%) moved a row below it**, exactly the
      "value-dependent cascade debris" the section comment predicts for
      rows that cross `C - 1` on the way back.  So the post-fix column is
      not predictable without walking, the frontier sequence cannot be
      computed up front, and the loop stays.  Only the search inside it
      was removable.
  The five entries above stay as the record of what each search was and
  what named it.  SLOW ACV MAMMALIAN is the worked precedent for what
  closing one buys: its own search was replaced by an arithmetic
  construction once the `j1` sweep turned out to be a residue solve, taking
  the contract sweep entry from 3.04s to 0.02s.  The move is always the
  same — name what the search returns rather than caching the search.
- **ArrowQueue's reusable drain** — a fixed-block leaf drain (rather than a
  staircase) is verified correct and written up in
  `docs/generator-optimizations.md`, but unshipped: it only wins from n≥5,
  past where anything exercises folding.  Two things to know before picking
  it up.  "Verified but unshipped" means *no source exists* — the commit
  behind it (`a6ec99de`) touched only the two docs files, so shipping is a
  build (drain construction, an entry-mode parameter, a depth dispatch, and
  extending `test_folding_never_grows_a_program` past its `n <= 3` pin), not
  a swap.  And the crossover is out of reach rather than merely
  unexercised: the staircase wins at every fold depth through 4 (60/93/111
  characters against 92/108/116) and only loses from depth 5, which needs an
  `n >= 5` table carrying a 5-deep constant subtree — `n == 5` is
  exhaustively ~407 CPU-days away, and the suite's two random `n == 5`
  samples will essentially never contain one.  A wrong entry-mode dispatch
  previously failed 530/2120 cases, so a careless port costs correctness at
  `n <= 4`, not just characters.  Revisit if a *proof* pushes exercised
  coverage to `n >= 5`.
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
- **The remaining literal tables in `tools/boolean/`** — swept by AST over
  every module in `src/`, classified by provenance, and each one probed
  rather than read.  **Four closed and are shipped; the rest are not
  candidates**, with the evidence for each recorded so the sweep is
  not re-run from scratch.  The standing rule ("a named rule,
  never a search or a frozen table") is about *frozen search output* — a
  measured cover or a tuned ordering over a proven-total structure is a
  different artefact and converting one trades a table for a search,
  which is backwards.
  Two method notes from the pass that closed `_SCHEDULES`, both of which
  cost time here: **the multiplicity of a table can be the finding.**
  Four schedules per arity looked like a cover and were a size contest —
  every one served every table — and that is what turned "collapse ten
  tuples" into "find one shape".  And **a longer entry can be the
  collapsible one**: length-optimal entries are incompressible *because*
  they are optimal, so the family that closes is found by relaxing size,
  not by chasing the shipped bytes.  Both closures that needed a new
  construction (`_LADDER_GADGETS`, `_LAWS`) came from paying characters
  for uniformity; every attempt to reproduce a minimal entry exactly
  failed.
    - **`_FOLD_SERVED` (%^2^-1)** — **closed; shipped** at `57d4c0bb`.  The
      twelve-entry frozenset is now `_fold_served()`.  Its comment called
      the four absences a corpus measurement; they are structural.
      `delta` is set when every middle index `{(r-1)//2, r//2}` is `1`, and
      for `r` of 2, 3 and 4 that set contains index 1, so `delta` implies
      `pat[1]` and `(2,1,0)`, `(3,1,0)`, `(4,1,0)` cannot be built; at
      `r == 3` index 1 is the only middle, so the implication runs both
      ways and `(3,0,1)` dies too; at `r == 5` the middles are `{2}`,
      which frees index 1 and is why `(5,1,0)` is served where `(4,1,0)`
      is not.  **The implication is one-directional** — `(2,0,1)` and
      `(4,0,1)` are reachable, so the obvious `delta == pat1` predicate
      looks right on the tabulated keys and silently drops two served
      ones.  Enumerating every run pattern to `r == 12` reproduces the set
      exactly; `test_fold_served_is_reachability` re-derives it each run.
      Byte-identical on all 272 tables at `n <= 3`, and twelve
      fold-served tables at `n == 4..7` execute every row correctly at
      equal fill width.
    - **`_WII2D_JUNCTIONS`** — **not a candidate.**  Not a freeze but the
      *product* of one: `ea65a170` removed `_WII2D_BEAMS`, the
      `(4, 16, 32)` width ladder, `_WII2D_MAX_STATE_BITS` and the
      magnitude-first retry, leaving this catalogue plus the totality
      argument for Horner in last place.  Order is a size preference, not
      a correctness constraint: permuting the twenty merge entries (Horner
      pinned last) changes 360 of 392 emitted programs with **zero
      errors**, exhaustive at `n == 2, 3` and sampled at 4 and 5, and the
      shipped order beats 7 of 8 random permutations on total size (57708
      against up to 59557; worst case 382 against up to 476).  Recovering
      the ordering would mean re-running that tuning.  **The negative is
      now a proof, and the comment is fixed** (`8434def4`).  Widening the
      earlier three failed sort keys to 1.9M candidates — 63 features
      (field lengths, per-character counts, weighted op costs) in every
      1-to-3-deep lexicographic composition, both directions — yields
      **zero** monotone along the shipped sequence, against a positive
      control recovering 172 keys for a deliberately sorted list.  Two
      adjacent *descents* in total length (index 10→11 and 17→18) close
      it outright: no key monotone in length can order this table, so no
      wider battery is worth running.  The old "cheapest first" claim
      was false and undercounted — `('', '0')` sits behind **six**
      two-character entries, not three, and the table holds **42**
      total-character inversions across two regions.  The header now
      reads "in merge order", so a reader cannot mistake a size-tuned
      preference for a cost sort.
    - **`_SLICE_YIELD_ORDER` (Minifuck)** — **derived; the derivation is
      now checked** (`8434def4`).  The order is the ten slices ranked by
      *marginal* first-hit column yield at `n == 4` — what each slice is
      first to reach walking the plain enumeration, not what it could
      place alone, which ranks them differently and was the ambiguity
      that made this look frozen.  All ten counts differ (2874 best, 424
      worst, matching the figures the comment already quoted), so
      descending order is total and needs no tie-break, and
      `test_the_slice_order_is_its_measured_yield` reproduces the tuple
      exactly from `_staging_index(4)` each run.  A stated measurement is
      not a checked one, and this table is **dormant, not dead** — so
      nothing else would have caught it drifting.  Unreachable as
      shipped — `_slices` returns the plain
      enumeration at every arity because `_STAGING_BUDGET` and
      `_STAGING_BUDGET_N5` are both `None` and nothing outside the tests
      assigns them — but a working knob rather than dead code.  With
      a budget set at `n == 4`, the only state that reaches it, the frozen
      order and the plain order disagree on **3 of 8 tables about whether
      a staging is found at all** (budget 2000) and emit a different
      template on one (budget 20000).  Deleting it would silently change
      behaviour for the documented slow-machine case, whose surrounding
      machinery is live and tested by
      `test_a_budget_gives_up_length_not_coverage`.  Whether the frozen
      order is *better* is **unmeasured**: over 40 random tables 35-38
      decline at every budget tried, leaving 2-5 to compare, and those
      split both ways.  Settling it needs a corpus sized to the decline
      rate, which is a measurement task and not a retirement.
    - **`_WIDE_A_VALS` (%^2^-1)** — **closed; shipped** at `765f9564`.
      The seven multipliers are the closure of the two commands its own
      comment already named — `m` doubles, `p` negates — so they are the
      signed powers of two plus the erase, and only the *bound* is a
      measurement (`|a| <= 4` reaches no further table).  Now generated
      from `_WIDE_A_LIMIT`, byte-identical **including order**, which is
      load-bearing: the wide search takes the first spelling that
      behaves, so iteration order decides the winning spelling even
      though it cannot change what is reachable.  Missed by every earlier
      sweep because a seven-element tuple does not look like a table;
      found by grepping module-level literals for *provenance language*
      in their comments, which is the method note below applied.
    - **`_LADDERS` (%^2^-1)** — **not a candidate; a minimal cover, and
      its stated price was wrong by 240x.**  Eight ladders chosen by
      greedy set cover over 150 yielding paths.  Re-probed: the cover is
      **minimal** (dropping any one strands tables — 4,4,4,2,2,2,2,2) and
      load-bearing on size (removing the ladder path costs no correctness
      but **+88%** over the twenty it serves, 31615 → 59457).  The
      comment priced the full-grid alternative at ~50s; folding all 256
      takes **0.21s**.  What that alternative actually changes is reach —
      50 tables against 26 — with all 24 extras already building by
      earlier paths, so widening moves which path claims them.  The
      defence is assignment stability, not build cost; comment corrected.
    - **`_LADDER_GADGETS` (%^2^-1)** — **closed; the spellings are
      constructed.**  The old comment's claim that deriving them meant
      re-running the rung composition was wrong: every gadget is
      `PRE + "psp" + MID + "ipsp"`, where `PRE` (`"s"*k + "m"*j`) spells
      the outer cut as `ceil(3004/2^j) - 2k` — reproducing the measured
      3004/1502/1500/751 exactly — and `MID`'s subtractions are *pinned*
      by normalisation: the class surviving the first reset must land on
      2 and a rung at 0 on 3, forcing the deficit `max(0, 2m - m*b - 4)`.
      That formula predicts "msm" (4), "m" (0), "mimm" (12) and predicts
      the `(1500, 4)` gadget cannot normalise rung 0 (it would need −8),
      matching its measured garbage there.  `_ladder_gadget(cut, slope)`
      emits all five byte-identically from `_LADDER_CUTS`; the frozen
      strings moved into the suite as the fixture
      (`test_ladder_gadgets_match_frozen_spellings`).  The five pairs
      that remain are a measured cover in the `_LADDERS` sense, with the
      analogous defence now measured: folding every comparator the
      grammar spells (83, one per outer band per slope) serves nothing
      the five miss — ten extra tables all build through earlier paths,
      and four would flip away from the deep band/fold, so the full
      family is a behaviour change, not reach.  Going fully literal-free
      is therefore a priced option, not a gap.
    - **`_TWO_INPUT_SHORT` (Super SNUSP)** — **not a candidate.**  Five
      hand-found forms that beat the general ANF path by reusing `48`;
      deleting them is safe (ANF is correct and total) but regresses size,
      which is the metric.
    - Method note, since element count misled this sweep once: a small
      literal can hold a large frozen table.  The `>= 4`-element threshold
      that found the six above would have missed the ten separation
      schedules (three keys, one per arity) entirely — and their
      replacement `_LAWS` is three keys too, so the threshold would miss
      it again.  Sweep by provenance, not by size.
    - **`_SCHEDULES` (123)** — **closed; the table is gone** (`56c3754a`).
      The ten frozen schedules are replaced by `_LAWS`, one separation
      *shape* per arity.  Two findings reframed it.  First, the
      multiplicity bought nothing structural: **every schedule serves
      every table at `n >= 2`** (4/4 candidates build all 16 and all 256),
      so the four per arity were a size contest over an already-total
      structure, not a cover.  Second, the reason a walk-only law fails
      here: after a bare fill the rows differ in their **marks**, not
      their positions (8 distinct states for 8 rows, all sharing a
      parity), so no walk can split them and the separator has to be a
      *test* whose displacement leaves some rows marked and others clear.
      That collapses the grammar — one constant pre-fill walk, then pure
      tests alternating `1`-runs and `2`-runs, no raw repositioning part
      at all.  Selecting by least mean template length, one rule at every
      arity, gives `(0, ())`, `(2, (3,2,4))`, `(3, (1,3,9,4))`; at
      `n == 3` only **13 laws** cover all 256 tables and the winner leads
      by 18%.  Price: **1.28x** (55238 characters over 276 tables against
      43020; 1.02/1.26/1.29 by arity, worst single table 3.0x, best
      0.62x), still 2.9x under `construct()`'s 158152.  All 276 replay
      row by row, and `test_the_separation_law_is_the_least_mean`
      re-derives the `n <= 2` constants by the same sweep each run.
      **Two routes rejected first, both worth not re-running.** Deriving
      the shipped moves by shortest-then-lex search reproduces 3 of 4 at
      `n == 2` but is **not cap-stable** at `n == 3` — widening the
      per-field cap returns *costlier* tuples (14→22, 11→25), so those
      constants are not canonical and re-freezing a search's output only
      moves the table.  And the retired synchronized pipeline's geometry
      *is* a real closed form — `marks[i] = (i+1)*2**n + 1`,
      `ws[i] = 2**(n-i)`, which its own comment called "an observation,
      not a totality argument" but which **separates at `n = 4` and `5`**,
      two arities past its freeze — yet costs **2.65x**, because the
      merge choreography that buys a mark per input is what makes
      gap-halving work at all.
    - Re-audit additions (2026-09-05, second pass): **`_PLANS`
      (Minifuck)** is already the accepted end state — five semantic
      parameter tuples rendered by `_step`, an ablation-measured cover,
      the same class as `_LADDERS`; not a candidate.  **`_RING_ROWS` /
      `_SHARED_ROWS` (Streetcode, boolean and text)** are hand-designed
      2D program blocks mirrored from the hand-written test program —
      code, not data, the assembly-template class.  **`_POOL`,
      `_DEGENERATE_COLUMNS`, `_STAGED_ARITIES` (Minifuck)** are spec
      constants (ASCII `'0'` bits with the rule in the comment; the
      complete `<= 1`-bit column enumeration; an arity range); `_SEPS`
      is a measured cover with its ablation recorded in-line.  A sweep
      over long *string* literals in `tools/` (the hole the AST
      element-count sweep leaves) found nothing frozen — four hits, all
      spec or derived.  Six-Five has no literal table; its capped input-
      order search is live code with its cost trade documented, a
      different artefact class.
    - Third pass (2026-09-06), re-probing rather than quoting the five
      covers — which is what caught three wrong stated numbers.
      **`_PLANS`**: the *spelling* is already a construction (`_step`
      derives each code from `(carry, backs, odd)` by the `ceil(k/2)`
      law); only the values are a cover, and drop-one strands
      0/0/20/18/8.  **Plans 0 and 1 strand nothing** — dropping both is
      byte-identical at `n == 3` exhaustive (256/256 build, all rows
      correct, 60382 bytes either way) and over 60 sampled `n == 4`
      tables (30799 bytes either way).  A priced deletion, not a
      closure: the remaining defence is unsampled `n >= 4` behaviour.
      **`_TWO_INPUT_SHORT`** confirmed exactly — with it monkeypatched
      away all 16 tables still build and execute correctly (including
      the `"0000"` constant, the case that could have changed how many
      inputs are read), at **+138.9%** over the five it covers.
      **`ANCHORS`** — `make_ztoalc_table.py --check` reproduces all 21;
      empirical Collatz records with a working regenerator is already
      the right shape.  **`_SEPS` is load-bearing but its figures did
      not reproduce, and the convention is unrecovered**: two
      independent probes disagreed with the comment *and with each
      other's denominator* (49 against the stated "Two separators: 99 of
      109"; a 252-pair population via `_staging_index` against the
      comment's 109), and the nearby "92 distinct columns" measured 126.
      Flagged rather than corrected — an edit here would be guessing,
      and whoever takes it should recover the population first.
      One further priced option: adding 3 to `_INSERT_ARITIES` reaches
      `01101101`/`10010010`, which prose near `_Staging` calls
      unreachable, changing exactly 2 of 256 templates (60382 → 60128).
      Also swept module-level literals by *provenance language* rather
      than element count, which found three the size sweeps missed:
      `_WIDE_A_VALS` (closed, above), **`_X0` (A Painter Ant)** — dead
      code, its own comment said "Unused", one definition and zero uses,
      now deleted — and **`_COND` (Polynomial)** plus
      **`_PRINTED_COLUMNS` (Minifuck)**, which are not tables at all: a
      spec dispatch on instruction codes, and an empty runtime memo.
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
