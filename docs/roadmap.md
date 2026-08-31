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
- **Inject** — Turing-complete: label blocks, `readto`/`send` for line I/O,
  `skipq`/`skipif`/`skip` for control flow; the truth-machine example
  compares the input block against a `0` block.
- **Algebraic Programming Language** — Turing-complete: executed lines print
  their result and their variables read user input; `&`/`|` short-circuit
  with `IF(x, c) = x & c()` and a `WHILE` function give the generator its tree.
- **Interprogck8** — weaker candidate: `u` input, `div` output, and IFT/IFQ
  conditionals make a truth-machine, but the `[a b]` random range and `~`'s
  10% side effect need the seeded-randomness judgment call, and the
  function-based conditional is convoluted.

No 2D/grid candidates remain open: the `Category:Two-dimensional` ×
`Category:Unimplemented` pass produced Streetcode, Flowchart, Line, and
Circuit Diagram, all implemented.

## Transpilers

`Streetcode → LaserFuck` ships: the two share a tape of unbounded signed
cells under a pointer, and Streetcode's instructions are brainfuck's eight
under other glyphs, so no new interpreter was needed.  Its supported class
is the programs the tape never steers.

**Open research item: lowering drawn control flow.**  A Streetcode ring has
no brainfuck loop image -- the car never returns to the junction that steers
it as the same drive state -- and the boolean generator's programs are
decision trees whose leaves each print.  Both are lowerable with scratch
cells and a converged answer, which is a compiler rather than a program
rewrite; `docs/limitations.md` carries the measured argument and the
worked examples.  This is the same class of future work as the OISC pair.

The remaining candidates (a second Forth dialect ↔ Forþ,
Boolfuck ↔ ABCDirection/Minifuck) each need a *new* interpreter first, so
they belong under "New interpreters" if that language is ever added.

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

Candidates in priority order.  Two facts constrain every entry: the target
is **`rv64i`**, whose base integer ISA has no float and no hardware
multiply (forth already emits software `mul32`/`divmod32`, so integers are
precedent and floats are not); and a differential is only worth the name
when the generator *reads input*, since an `_embedded` generator substitutes
its bits into a fixed template and replays the same program.

- **MyScript** — the richest call graph left: first-class functions,
  `return`, `while`/`check` blocks, and a `_reader` generator.  Scoping was
  **probed and is not lexical** (a caller's local is visible inside a callee
  that never received it), so like Forbin it needs no captured environments.
  The bill is its *value domain*: `say` prints floats, strings, and arrays,
  and on `rv64i` that means soft-float plus heap-managed strings and
  growable arrays — a different league from Forbin's tagged 64-bit words.
  Worth doing, but scope the value domain before starting.
- **CV(N)(C)** — genuine dispatch, and the most unusual lowering available:
  the program builds a *function* symbol by symbol and applies it on demand,
  over an accumulator, a deque, and that function.  Unbounded unsigned
  integers fit the documented fixed-width caveat, and it carries both a text
  and a boolean generator.  Its cost is the syllable grammar — validity is
  CV(N)(C) structure, so the front end is a real parser rather than a
  character dispatch.

Standing negatives, unchanged.  Plain brainfuck is the trap answer —
uncovered, but `home_row`/`suffolk` already cover that shape, so it is
transliteration; the same disposes of the rest of the bf-shaped tape family.
Taglate is blocked outright: its `t` command rewrites the queue into a
Google Translate URL of its text.  Bitdeque is too thin, and Point Break has
no output command, so its differential could only observe halting.
Polynomial needs complex-root finding, which is not RISC-V work.  Lamfunc's
partial application is real lowering, but its generator is `_embedded`, so
it cannot pay the verification bar the way MyScript can.  The
2D/grid family stays out under the toolchain rule, and the drawn-control-flow
item under **Transpilers** already covers that direction.

**Input-reading compilers are now supported.**  `COMPILER_CASES` entries
take an optional fifth element carrying stdin (pre-existing cases keep
running on empty input), so a new input-reading compiler needs no harness
work.  What a compiled reader must match is *its own language's* refill,
and the two shipped readers differ: Forbin's `in` goes through
`IO.input_char`, which reads a whole *line* and returns its first
character, so that reader is line-faithful and byte-consecutive reads
would diverge.  Container's is not line-faithful — it refills a queue with
`input_str`'s line *contents* and consumes one character per pulse, and
since `input_str` strips terminators that queue is exactly the raw byte
stream minus its newlines.  So `_riscv_common.GETBYTE` plus a newline skip
is the correct lowering there, and Container is the standing precedent that
GETBYTE is fine for an exercised reader whose language reads that way.
Derive the convention from the interpreter's refill, not from a default.

## Forbin's expression-position recursion

Forbin's *expression-position* calls (`x = f(y)`) recurse natively, bounded
only by Python's default recursion limit.  Closing this needs `_eval` itself
extended into a resumable continuation stack (the `_EvalTask` design,
rejected in `docs/walls.md`), and Forbin has no realistic program shape that
recurses this way.  **Not pursued unless a concrete program needs it.**

## Hanging-test optimization via state-cycle detection

State-cycle detection (`esolangs.vm.run_until_halt_or_cycle`) has replaced
wall-clock timeouts for step-capable deterministic machines; see
`docs/limitations.md` for coverage.  What remains:

- Painfuck's `y`, WII2D's `?`, and LaserFuck's random heading are
  non-deterministic and stay on the wall-clock backstop.
- **Recursion follow-up.**  `run_until_halt_or_ancestor` compares each
  newly-pushed frame's entry state (function, bindings, input position)
  against the frames beneath it.  Built for Forbin; **Suptiftam and Lamfunc
  also recurse and are the obvious follow-up**, each needing a
  `frame_entry_key` matching its own frame shape.
- **Branching cycle detection for `y`/`?` — considered, not started.**
  Forking at every random decision would prove "hangs no matter how the coin
  lands", but each decision doubles the live branches, a branch can still
  hang via unbounded growth, and the common case (hangs under *some* flips)
  is proved neither way.  Only worth building if that guarantee is needed.

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

All 60 suites are measured, and nineteen are at 100%.  Per-language scores
and survivor counts are *not* recorded here: they go stale on any test change
and are cheap to re-derive — 56 of the 60 finish in under half a minute, and
only Streetcode and Forbin run to minutes.  Re-run the language you touched;
re-run everything after a change to the shared machinery.

What is worth keeping is what a triage pass has to get right, each learned by
getting it wrong first.

**Trusting the measurement:**

- **Measure on an idle machine.**  The per-test alarm fails a slow-but-
  passing test and scores it as a kill, so a contended run *under*-reports
  survivors — one reported 17 where a solo run reports 22.
- **`uv run` can measure the wrong tree, silently.**  It reinstalls the
  package from the project root, so a worktree's edits never reach the
  bundle; `PYTHONPATH=$PWD/src` fixes it.  The tell is a survivor on a line
  you already deleted, or a pool size that did not move after deleting code.
- **A probe whose own baseline moves witnesses everything.**  An error
  message interpolating an object with no `__repr__` carries its address, and
  one such program was recorded as the sole witness for 114 mutants that were
  not killable at all.
- **Naming `esolangs.vm` in a docstring drops the test** from the bundle
  exactly as an import would, silently.  A survivor is not a gap until the
  harness is trusted: tests reaching the VM or registry are dropped
  *correctly*.

**The last survivor is often the source's fault, not the suite's.**  A
construct that cannot be observed is usually one that need not exist, so
reach for the interpreter first when the mutated construct carries no
information:

- **A redundant argument is unkillable by construction.**  Five interpreters
  passed `input_str("Input: ")` when that string is already the parameter's
  default, and `ScriptedIO._read` discards the prompt, so no test could ever
  see it.  Each call site carried three permanently surviving mutants;
  deleting the argument removed 24 mutants, **18 of them survivors**, and
  closed Unsquare outright.  Prefer the default over restating it.
- **A default is dead when something upstream already ran it.**  Collatz
  Multiverse's `arrays.setdefault(var1, {})` could never fire, since every
  line reads its target before writing and an indexed read already defaults
  the array — a probe ran 20,000 random programs without the key ever being
  absent.
- **A `*` quantifier never fails, so its fallback is dead.**  Eval's
  `re.match('[^"]*', ...)` fell back to `""` on `None`, which cannot happen;
  `partition('"')[0]` says the same thing with no unmatched case.
- **Dead guards.**  Clockwise's `if ins in "R?!"` early return was
  unreachable, so both of its set-widening survivors sat on code that did
  nothing; deleting it took the suite to 100%.  BrainIf seeded a retry loop
  with `s = ""` when every falsy seed behaves alike.  ArrowQueue guarded grid
  setup with `if code:`, making `_Machine(None)` take the empty-grid path —
  indistinguishable from outside in a language with no output.
- **Two copies of a check can each be half dead.**  NoComment's `s` and `b`
  bounds-checked their jump target separately, and each copy had an
  unreachable half: a forward target is always at least 1, so `s` could never
  fail the floor, while `b` almost never reaches the ceiling.  Merging them
  into one check over a signed delta leaves every fragment live.

**Writing the test that kills it:**

- **A survivor is only as tested as the observables you compare.**  Output
  and step count miss frame bookkeeping entirely; comparing `snapshot()`
  killed seven Forbin mutants and four Basicfuck ones that looked equivalent.
- **"Symmetric table" is not an equivalence argument on its own.**  3D
  Brainfuck's direction tables are closed under negation, long cited as
  making its axis mutants unkillable.  They are not — `snapshot()` carries
  `ap`, `ip` and `heading`, so a relabelled axis is visible even when output
  and step count match.  All 23 non-identity permutations are
  distinguishable.  Assert the *coordinate*, not just the output: five of its
  six survivors were tests asserting output only, where every move walked out
  and back and direction cancels.  The sixth was real — `ip[1]` read as
  `ip[2]` is undetectable because the instruction pointer never leaves the
  `y = z = 0` line alive, so unpacking the triple removes the index that
  could be wrong.
- **`pytest.raises(match=...)` is a substring search.**  Passing the whole
  message still matches a mutant that widened it; only
  `assert str(caught.value) == message` catches that.
- **A default argument every test overrides is untested.**  Decleq's
  `limit=10_000` survived widening to 10001 because every test passed
  `limit=` explicitly.  `run_with_limit` checks `halted` at the top of each
  pass, so a program halting in `limit` steps still exhausts the loop — which
  puts the discriminating count at 10,000, not 10,001.

**A rewrite can install a gap where it removed slack**, so re-measure after
every one rather than assuming the score only improves.  The `partition` swap
above introduced a survivor the regex version never had: `partition` and
`rpartition` agree on every program holding a *single* literal, and every
test had exactly one.  That went 6 survivors → 1, and the 1 was newly
created.  3D Brainfuck showed the sharper version: factoring a pointer move
into a `zip`-based helper traded one equivalent mutant for **three**, because
ruff's B905 requires an explicit `strict=` and both operands are always
3-tuples, so that argument can never fire.  A lint rule can mandate slack.

Triage from the test file, not the diffs — six mechanical shapes recur
(substring-matched `pytest.raises`, comment tests outside the command set,
truth-only `bool` flags, one-sided boundaries, write-only attributes,
assertions on a constant).  A score is a means: stop where the survivors stop
teaching anything.

## Dependency reduction

A table ignoring some inputs is a smaller table, and where a generator's cost
scales with *input count* rather than row count that beats any per-row
saving.  Taglate reduces (451 characters → 21).  What is open:

- **Taglate's gapped sets** (inputs 0 and 2 but not 1) need a discard between
  the reduced program's own reads, where the queue is not what the following
  reduce block assumes; output comes out arithmetically corrupted rather than
  permuted, so this is a real obstacle.  10 of the 40 reducible tables at
  `n == 3`.  **Odd-sized sets** are sidestepped by widening the window, which
  costs a tier back; narrowing properly needs the reduced program's own ghost
  handling suppressed.
- **Worth checking elsewhere.**  Any generator whose fixed cost scales with
  `n` admits the same reduction — decleq's `47n` normalize chains and
  clockwise's per-level rows are the obvious candidates, neither measured.

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
  every shipped generator covers `n <= 2` at minimum.
- **Minifuck's four-input coverage** — three inputs is **done**: all 256
  tables build with no search at all, from a derived staging plus `_rescue`
  for the four the enumeration misses.  What is open is four inputs, where
  the shipped staging family reaches 23.9% of the fully-essential tables.
  That is a ceiling of the *family*, not of the language: a two-read chain
  prototype — reads interleaved with chosen walks, a richer pool than the
  enumerated suffix — prints 19.5% of a sample of the tables the family
  misses, 78 of 78 interpreter-verified, and is not shipped.  Wiring it in
  as a fallback after the staged route is the concrete next step; see
  `docs/walls.md`, "Why no chain can escape the counting argument", which
  that prototype refutes.  The other six
  refusing generators stay off this list: 6-5 is the one documented wall
  left (`docs/limitations.md`), %^2^-1 is partly lifted with the rest open,
  and NoComment, Polynomial, Factor and WII2D are resource knobs.  NoComment
  used to be listed as a wall here on the strength of "the `s` skip is
  byte-indexed, capping every jump at 255" -- which bounds one jump and not a
  composition of them; chaining byte-sized skips lifted it from `n <= 8` to
  the interpreter's tape bound.  WII2D's `n == 7` refusal is likewise a cost
  guard that fires before the fold is attempted, and raising it builds
  interpreter-verified `n == 7` programs at a heavy build-time tail.
  NoComment's and Factor's remaining caps are liftable by host config, and
  `docs/walls.md` has both arguments.  ZTOALC L was on
  this list and its refusals are now *size gates only* -- the anchor table's
  1132 commands and the `2**22` line limit -- rather than capability walls:
  its wall was a property of the decision tree it built, not of the
  language, and a branch-free array lookup placed on a Collatz trajectory
  renders every table small enough to materialize (`docs/walls.md`).
- **NoComment's tape size** — *resolved by parameter, not by moving the
  constant.*  The boolean generator reaches `n <= 11` at the default size,
  and what stopped it there was `_TAPE = 4096`, not the language: the wiki
  requires the memory space to be static but never gives a size, so 4096 is a
  host choice matching the RISC-V cross-check's buffer.  Both `run` and
  `nocomment` now take a `tape` argument defaulting to it, so a caller who
  wants `n == 12` (cell 4650) builds and runs at a larger size while every
  existing program keeps the 4096 the cross-check agrees with.  Raising the
  *default* is still declined for the reason first noted here — the buffers
  would disagree about where the tape ends, which is what the cross-check
  exists to catch.  The open question is unchanged and is about width, not
  memory: an `n == 11` build is already ~27k characters.
