# Roadmap

Future work only, in priority order.  **An item leaves this file when it
closes**, and closing one is a migration rather than a deletion: the
structural negatives and instrumentation traps it produced go to
[`docs/walls.md`](walls.md), recurring method that binds a future sweep goes
to [`docs/verification_tooling.md`](verification_tooling.md), and a
deliberate engine-to-engine divergence goes to
[`docs/limitations.md`](limitations.md).  Only the status prose is dropped,
and the construction itself lives in the source and the commit history.
Language assessments and ruled-out ideas live in those same two files.

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

**Open research item: lowering drawn control flow.**  Recovering an
arbitrary Streetcode grid's control flow, and lowering the boolean
generator's decision trees (whose leaves each print), are both compilers
rather than program rewrites.  It would be the first real control-flow
lowering: the other three shipped transpilers are per-command
transliteration onto a superset target.

**Read `docs/limitations.md` before scoping this: the reason this entry
used to give was false.**  It claimed a Streetcode ring has no brainfuck
loop image because the car never returns to a junction in the same drive
state.  Driving the emitted grids shows the full steering tuple *does*
recur on every lap — only the cell differs, and the road choice is a
runtime test (`streetcode.py:1125`), not a compile-time proof obligation.
The difficulty is real but it is the one below, not a control-flow wall.
The OISC pair is still the precedent worth following: `decleq_to_sbleq`
clears the admission bar by *emulating* the source machine's semantics,
and an emulator has no interiors to jump into.

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
saving.  **Nothing is currently open here.**  Clockwise, the obvious
remaining candidate, does not reduce: `clockwise` (`other.py:681-888`) makes
no `essential_inputs` call.  Taglate's odd-sized sets were the last live
item and the premise turned out to be wrong — the refutation and its
measurements are in [`docs/walls.md`](walls.md), which is also where a
future attempt should look before re-running the pattern.

## Smaller open items

- **Jaune's markers read one digit — reachable, and `prep` corrupts the
  program before `count` ever misreads it.**  `count` takes the operand of
  `:`, `$`, `@`, `?` and `!` from the single character before them, so ten
  or more labels spell one `10:` that reads as `0:`.  This was filed as
  unreachable because `prep` renumbers from 0 upward; **re-probed, that is
  wrong on both halves.**  Renumbering is exactly what *creates* the
  two-digit marker once a program has ten of one kind, and `prep` does not
  survive it.  Measured on `'+v?' + '0:+1:+...'` — eleven labels separated
  by commands, so no run collapses — ten labels round-trip unchanged, and
  the eleventh makes `prep` emit **`10:` twice**: the *first* label, spelled
  `0:` and renumbered to `0`, is clobbered into a duplicate of the eleventh,
  so the program ends up with two `10:` markers and no label `0` at all.
  (Adjacent markers are a separate, documented case — a run like `0:1:`
  collapses to a single label by design.)  The cause is the substring
  rewrite in the renumbering loop
  (`code.replace(n + k, m + k)` and `code.replace(s, m + c)`), which matches
  a one-character number inside a two-character one.  Confirmed identical
  on `main`, so it predates the computed-dispatch work and is not a
  regression from it.  The interpreter is unaffected: it does not renumber,
  and `_parse` reads whole digit runs already.
  Fixing it means rewriting the renumbering to work on parsed positions
  rather than by substring replacement, and widening the marker read in
  `count` to a digit run the way the counts beside them were widened.  It
  now has a test route it lacked: a program with ten labels reaches it
  directly, and the computed forms make such a program meaningful rather
  than merely spellable.
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
