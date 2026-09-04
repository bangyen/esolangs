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

- **function x(y)** — Turing-complete: functions with defaults, `[~]`/`` `~ ``
  input, `[a]`/`` `a `` output, comparison operators, a ternary, recursion; a
  boolean generator branches on a comparison and prints 0/1.
- **DINAC** — `IN` reads an aschar or wubyte, `OUT` prints, IF-ELSE and
  WHILE on zero/nonzero, truth-machine example.  Bounded-storage machine,
  so the boolean generator is the whole story.
- **Packlang** — Turing-complete: packages with the built-in IO package
  (`charGet`/`charPut`), `If`/`While`, XOR/`!`; the truth-machine example
  branches on `input ^ 48`.
- **Interprogck8** — weakest candidate: `u` input, `div` output, and IFT/IFQ
  plus self-`EXE` (the loop its cat example demonstrates) make a
  truth-machine, but the conditionals compare the accumulator against
  *fixed* ASCII codes (84/81), so a generator steers values to `T`/`Q`
  rather than branching on a bit.  `developer` prints the interpreter's own
  source — "technically implementation-dependent" on the page — which is a
  documented judgment call in Taglate's `t` mould rather than a blocker.
  The randomness is **not** an objection: `[a b]` and `~` are seedable, as
  LaserFuck's heading already is.
- **Alight** — its boolean generator is an indexed lookup, not a routed
  tree.  It reads each input character, subtracts `'0`, and uses
  ``index = index * 2 + bit`` to build the row number; a string literal holds
  the truth table and ``at{table, index + 0.5}`` supplies the character for
  `out`.  That is one table character plus a constant-size unrolled update
  per input: **O(2**n + n)** source, before the interpreter work.  The
  two-dimensional `skip`/`turn` control flow is therefore exercised by tests
  rather than made responsible for the generator's cost.
- **Pinyin** — the stack can retain one nonzero input character as a source
  of `1` (duplicate it and divide it by itself), but has no table/list
  storage.  A full planar decision tree is the direct construction.  At each
  node, a character input is normalized with ``x % ((x / x) + (x / x))``;
  copies then make zero and `q` compares it with the bit, sending the two
  outcomes in opposite directions.  The retained character lets either leaf
  print integer `0` or `1`.  It spends 12 executable character commands per
  internal node and 3/5 per one/zero leaf, plus routing and grid padding:
  **O(n * 2**n)** rendered source.  This is a usable, if deliberately large,
  generator price; the page's `e`/`a`, stack operations, comparison, and
  truth-machine establish the needed I/O and branch primitives.

These complete the priced survivors of the 2D/grid pass
(`Category:Two-dimensional languages` ∩ `Category:Unimplemented`). Full
per-language table, including the named blockers and rejections for the
rest of the pass, is in `notes/twod-unimplemented-audit.md`.

## Transpilers

**Open research item: lowering drawn control flow.**  A Streetcode ring has
no brainfuck loop image -- the car never returns to the junction that steers
it as the same drive state -- and the boolean generator's programs are
decision trees whose leaves each print.  Both are lowerable with scratch
cells and a converged answer, which is a compiler rather than a program
rewrite; `docs/limitations.md` carries the measured argument and the
worked examples.  This is the same class of future work as the OISC pair.

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
already covers.  What remains:

- Painfuck's `y`, WII2D's `?`, and LaserFuck's random heading are
  non-deterministic and stay on the wall-clock backstop.
- **Recursion follow-up.**  `run_until_halt_or_ancestor` compares each
  newly-pushed frame's entry state (function, bindings, input position)
  against the frames beneath it.  Adopted by Forbin, Fargo, APL, Eval,
  Suptiftam, Lamfunc, Forþ, Jaune, and Grapheme — it already generalizes
  past native recursion, since Eval, Fargo, and Grapheme push an explicit
  frame stack rather than recursing in Python.  **The audit is closed:**
  every other frame stack is structurally bounded or hides calls in native
  recursion.
- **Branching cycle detection for `y`/`?` — shipped.**
  `run_until_halt_or_all_branches_cycle` explores every exact successor of
  Painfuck's `y` and WII2D's `?`, merging equal states.  It returns `False`
  only when the finite reachable graph has no halted state (a proof that all
  random outcomes hang); a single halted outcome returns `True`.  It raises
  `TimeoutError` at 10,000 distinct states or outcomes in one repeated step,
  and also when Painfuck would read future input: an unbounded-growth branch
  and a branch-specific input cursor are undecided, not evidence of a hang.
  This intentionally does not prove the common case where only some random
  outcomes hang.

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

## Dependency reduction

A table ignoring some inputs is a smaller table, and where a generator's cost
scales with *input count* rather than row count that beats any per-row
saving.  Clockwise and Decleq are the obvious remaining candidates and
neither reduces: `clockwise` (`other.py:676-883`) makes no
`essential_inputs` call, and Decleq's own docstring (`register.py:61`)
prices its 47-step normalize chains as a fixed `47*n` the fold cannot
reach.  What is open:

- **Taglate's gapped sets** (inputs 0 and 2 but not 1) need a discard between
  the reduced program's own reads, where the queue is not what the following
  reduce block assumes; output comes out arithmetically corrupted rather than
  permuted, so this is a real obstacle.  10 of the 40 reducible tables at
  `n == 3`.  **Odd-sized sets** are sidestepped by widening the window, which
  costs a tier back; narrowing properly needs the reduced program's own ghost
  handling suppressed.
- **Decleq's `47n` normalize chains are not reduced** — its own docstring
  notes the fold folds constant subtrees but leaves the fixed `47 * n`
  normalize cost untouched (`src/esolangs/tools/boolean/register.py:61`),
  so an ignored input still pays its full decrement chain.  Unmeasured.

## Smaller open items

- **ArrowQueue's reusable drain** — a fixed-block leaf drain (rather than a
  staircase) is verified correct and written up in
  `docs/generator-optimizations.md`, but unshipped: it only wins from n≥5,
  past where anything exercises folding.  Worth revisiting if deep tables
  start mattering.
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
- **NoComment's tape size** — `run`/`nocomment` take a `tape` argument
  (`_TAPE = 4096` default, matching the RISC-V cross-check's buffer), so
  `n == 12` (cell 4650) builds at a larger size without moving the default
  every existing program agrees with.  The open question is width, not
  memory: an `n == 11` build is already ~27k characters.
