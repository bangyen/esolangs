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

The only candidates identified (a second Forth dialect ↔ Forþ,
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
than per-command transliteration).  No candidate currently clears either bar.

**Harness note.**  A fuzz-dependent, input-reading compiler would first need
fixed stdin cases via `run_elf` or a compile-then-fuzz differential; the
current differential never compiles and the unicorn cases feed empty stdin.
Intrinsic-value compilers need none of that.

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

All 60 are measured.  The whole sweep was re-run on 2026-08-29, one
language at a time on an idle machine, and **every figure previously
recorded came back exactly** — which is what the harness commits
`800f071` and `86c89b9` needed, each having been validated against a
single language while nothing checked the rest.

Nineteen suites are at 100% — `%^2^-1`, 3D Brainfuck, ArrowQueue, Back,
BFStack, Bitdeque, brainfuck, BrainIf, Clockwise, Collatz Multiverse, Decleq,
Eval, Factor, Home Row, Minifuck, NoComment, RAM0, Suffolk and Unsquare.
1512 mutants survive across the repo (Fargo, added 2026-08-30, is the
forty-first row and the only one not from the 2026-08-29 sweep); the rest
of the field, worst first:

| language | score | survivors |
| --- | --- | --- |
| WII2D | 80.2% | 33 |
| AddSubJump | 80.2% | 23 |
| Point Break | 80.4% | 94 |
| Painfuck | 81.7% | 46 |
| Dimensional | 83.5% | 56 |
| 3x | 84.8% | 26 |
| Lamfunc | 85.0% | 82 |
| S*bleq | 85.3% | 14 |
| Grapheme | 86.1% | 60 |
| ROTfuck | 86.3% | 20 |
| COD | 86.6% | 38 |
| Nevermind | 86.8% | 36 |
| SLOW ACV MAMMALIAN | 87.4% | 23 |
| Between | 88.1% | 77 |
| MyScript | 88.5% | 71 |
| Container | 88.5% | 16 |
| Forbin | 89.0% | 128 |
| Polynomial | 89.4% | 38 |
| Flowchart | 89.9% | 51 |
| Minsky Swap | 89.9% | 14 |
| Sophie | 90.1% | 23 |
| ZTOALC L | 90.7% | 29 |
| Circlefuck | 90.7% | 17 |
| Circuit Diagram | 90.9% | 53 |
| Dig | 90.9% | 15 |
| LaserFuck | 91.1% | 22 |
| Taglate | 91.7% | 14 |
| Suptiftam | 91.8% | 93 |
| Streetcode | 91.9% | 98 |
| BIO | 92.2% | 9 |
| Fargo | 92.4% | 32 |
| 6-5 | 92.7% | 10 |
| Basicfuck | 92.8% | 50 |
| Jaune | 92.9% | 18 |
| A Painter Ant | 93.1% | 7 |
| 123 | 93.2% | 8 |
| bit~ | 93.3% | 8 |
| BF-PDA | 93.8% | 9 |
| Forþ | 94.1% | 14 |
| Qoibl | 94.7% | 26 |
| Modulous | 95.6% | 11 |

LaserFuck, Forbin and Basicfuck are post-triage rows (they began at 66.7%,
81.4% and 82.8%); four more — ArrowQueue, Decleq, BrainIf and Clockwise —
carried one to three survivors each, were closed to 100%, and have left the
table; NoComment (5), Unsquare (6), Collatz Multiverse (7), Eval (6) and
3D Brainfuck (6) left it the same way.  Painfuck, 3x and Forþ are
post-triage too — the prompt-argument deletion below cut each one's
survivors without ending its triage — so their rows are re-measured, not
swept.  That leaves 36 of the table's 40 rows carrying the sweep's own
numbers, 15 of which had never been recorded per-language.  **Lamfunc (82), Between (77), MyScript
(71) and Grapheme (60) are the largest untriaged pools** and were invisible
before this sweep.

56 of the 60 finish in under half a minute; only Streetcode and Forbin run
to minutes.  So re-running the language you touched is free, and re-running
everything after a change to the shared machinery is worth the few minutes.

What a triage pass has to get right, learned by getting each one wrong
first:

- **Measure on an idle machine.**  The per-test alarm fails a slow-but-
  passing test and scores it as a kill, so a contended run *under*-reports
  survivors — one reported 17 where a solo run reports 22.
- **The last survivor is often the source's fault, not the suite's.**  Two
  of the three one-survivor languages were closed by *deleting* the slack
  rather than testing it: BrainIf seeded a retry loop with `s = ""` when
  every falsy seed behaves alike (a walrus condition leaves no seed to
  mutate, and drops the pool 88→85), and ArrowQueue guarded its grid setup
  with `if code:` so that `_Machine(None)` took the empty-grid path and
  halted — indistinguishable from outside in a language with no output.
  Consuming `code` unconditionally makes that mutant raise.  Clockwise is
  the same lesson at its limit: its `if ins in "R?!"` early return was
  *dead*, since the dispatch below has no branch for a turn cell and the
  flush cannot fire on one, so both of its set-widening survivors sat on
  code that did nothing.  Deleting the guard took the suite to 100% and
  the pool from 150 mutants to 140.  Reach for the interpreter first when
  the mutated construct carries no information: a construct that cannot be
  observed is usually one that need not exist.
- **A redundant argument is unkillable by construction.**  Five
  interpreters passed `input_str("Input: ")` (and one `input_num`) when
  that string is already the parameter's default, so the argument changed
  nothing — and `ScriptedIO._read` discards the prompt, so no test under
  the harness could ever see it.  Each call site therefore carried three
  permanently surviving mutants (the `XX` sentinel and two re-casings),
  alongside a fourth the tests already killed.  Deleting the argument
  removed 24 mutants across Painfuck, 3x, Forþ, Collatz Multiverse and
  Unsquare, **18 of them survivors** — closing Unsquare outright, since
  all six of its survivors were the two call sites'.  The interactive `IO`
  path prints the identical prompt either way.  Prefer the default over
  restating it: a restated default is slack that mutation testing counts.
- **A default is dead when something upstream already ran it.**  Collatz
  Multiverse's write path used `arrays.setdefault(var1, {})`, but every
  line reads its target before writing it and an indexed *read* already
  defaults the array — so by the write the key always exists.  Two of its
  four survivors were mutations of that unreachable default (`None` and
  the argument dropped entirely); a probe asserting the key's presence ran
  20,000 random array programs without firing.  Plain subscripting is
  enough.  The other two were ordinary gaps: an error branch no test
  reached, and a `snapshot()` whose arrays half was only ever exercised
  empty.  Pool 102 → 98, suite to 100%.
- **A `*` quantifier never fails, so its fallback is dead.**  Eval matched
  a string literal with `re.match('[^"]*', ...)` and fell back to `""` when
  the match was `None` — which cannot happen, since `[^"]*` matches the
  empty string anywhere (300,000 random inputs, never `None`).  Replacing
  the whole thing with `partition('"')[0]` says the same thing with no
  unmatched case, and retires the `re` import with it.
- **"Symmetric table" is not an equivalence argument on its own.**  3D
  Brainfuck's direction tables are closed under negation, which was long
  cited as making its axis mutants unkillable.  They are not: `snapshot()`
  carries `ap`, `ip` and `heading`, so a relabelled axis is visible even
  when output and step count match.  All 23 non-identity permutations of
  the four off-axis headings are distinguishable, and each array sign-flip
  dies to a program as short as `n+`.  Five of its six survivors were
  ordinary gaps — the tests asserted output only, and every move walked out
  and back, where direction cancels.  Assert the *coordinate*.
  The sixth was real: `ip[1]` read as `ip[2]` is undetectable because the
  instruction pointer never leaves the `y = z = 0` line alive (a heading
  block walks it off the source and halts it), so both are always 0 there —
  44,680 programs found no witness.  Unpacking the triple into named
  components removes the index that could be wrong.
- **A rewrite can install a gap where it removed slack.**  That same
  `partition` swap introduced a survivor the regex version never had:
  `partition` and `rpartition` agree on every program holding a *single*
  literal, because the closing quote is then also the program's last one,
  and every test had exactly one.  Two literals separate them —
  `"a"."b".` prints `ab`, or `a"."b` if the split takes the last quote.
  So re-measure after every rewrite rather than assuming the score only
  improves: this one went 6 survivors → 1, and the 1 was newly created.
  3D Brainfuck showed the sharper version: factoring the pointer move into
  a `zip`-based helper traded one equivalent mutant for **three**, because
  ruff's B905 requires an explicit `strict=` and both operands are always
  3-tuples, so that argument can never fire.  A lint rule can mandate
  slack.  Unpacking the two triples instead satisfies the linter with no
  extra argument, and took the pool 117 → 114.
- **`uv run` can measure the wrong tree, silently.**  Three runs of the
  same command reported an unchanged 6 survivors — including a mutant of
  a line that had already been deleted — because `uv run` reinstalls the
  package from the project root, so a worktree's edits never reached the
  bundle.  `PYTHONPATH=$PWD/src` fixes it.  The tell is a survivor that
  cannot exist in the source you are looking at, or a pool size that did
  not move after deleting code.
- **Two copies of a check can each be half dead.**  NoComment's `s` and `b`
  bounds-checked their jump target separately, and each copy had an
  unreachable half: a forward target is always at least 1, so `s` could
  never fail the floor, while `b` almost never reaches the ceiling.  Three
  of its five survivors sat on those dead halves.  Merging the two into one
  check over a signed delta leaves every fragment live through at least one
  command — the floor via a `b` landing on index 0, the ceiling via `s` —
  which turned two equivalent mutants into deleted code and the third into
  an ordinary boundary test.  Pool 108 → 95, suite to 100%.
- **`pytest.raises(match=...)` is a substring search.**  Passing the whole
  message still matches a mutant that widened it; only
  `assert str(caught.value) == message` catches that.
- **A default argument every test overrides is untested.**  Decleq's
  `limit=10_000` survived widening to 10001 because each test passed
  `limit=` explicitly.  Killing it needs a run that takes *exactly* the
  default: `run_with_limit` checks `halted` at the top of each pass, so a
  program halting in `limit` steps still exhausts the loop and raises,
  which puts the discriminating count at 10,000 rather than 10,001.
- **A survivor is only as tested as the observables you compare.**
  Output and step count miss frame bookkeeping entirely: comparing
  `snapshot()` killed seven Forbin mutants and four Basicfuck ones that
  looked equivalent.
- **A probe whose own baseline moves witnesses everything.**  An error
  message interpolating an object with no `__repr__` carries its address,
  and one such program was recorded as the sole witness for 114 mutants
  that were not killable at all.
- **Naming `esolangs.vm` in a docstring drops the test** from the bundle
  exactly as an import would, silently.

Triage from the test file, not the diffs — six mechanical shapes recur
(substring-matched `pytest.raises`, comment tests outside the command set,
truth-only `bool` flags, one-sided boundaries, write-only attributes,
assertions on a constant).  Two cautions: a survivor is not a gap until the
harness is trusted (tests reaching the VM or registry are dropped from the
bundle *correctly*), and a score is a means — stop where the survivors stop
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
- **Minifuck's three-input coverage** — the one cap here that is liftable
  rather than a wall.  It builds all sixteen two-input tables but only
  eight of the fourteen three-input orbits, the other six raising after
  about two minutes; the failures are depth-cap exhaustion, not an
  argument, so the reach is set by the search rather than by the language.
  The route is a *construction* in wii2d's shape instead of a search —
  `docs/walls.md` has the piece that does not yet compose.  The other six
  refusing generators stay off this list: NoComment and 6-5 are documented
  walls (`docs/limitations.md`), %^2^-1 is partly lifted with the rest open,
  and Polynomial, Factor and WII2D are resource knobs — Factor's liftable by
  host config, and WII2D's `n == 7` refusal is a cost guard that fires before
  the fold is attempted (raising it builds interpreter-verified `n == 7`
  programs, at a heavy build-time tail).  ZTOALC L was on
  this list and its refusals are now *size gates only* -- the anchor table's
  1132 commands and the `2**22` line limit -- rather than capability walls:
  its wall was a property of the decision tree it built, not of the
  language, and a branch-free array lookup placed on a Collatz trajectory
  renders every table small enough to materialize (`docs/walls.md`).
