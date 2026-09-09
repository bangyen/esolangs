# Limitations and contracts

This is the current boundary ledger. Live work is in [the roadmap](roadmap.md);
structural arguments are in [walls](walls.md).

## Interpreter conventions

- Empty input is a no-op unless the language requires a seed or grid.
- Exhausted input raises `EOFError`, except where the specification defines
  another sentinel. Malformed programs raise `ValueError`; runtime failure
  raises `HaltError`.
- Character input is line-delimited: one line supplies one character.
- Explicit frame stacks make supported recursion uncapped. Forbin calls in
  expression position remain host-recursive and report their documented limit.

## Generator boundaries

Text generators are absent where the language has no output, only a binary or
numeric output alphabet, or cannot emit arbitrary byte sequences. Boolean
construction is parameterized for 123 and `%^2^-1`; no program reading its
own inputs overcomes the latter's two-input wall.

Interprogck8's boolean generator caps at three inputs, and the cap is the
*construction's*, not the language's. `DownAccLines` routes the whole
decision tree — the current-function slot is never touched, which answers
the roadmap question it was posed under — but a branch's nine-line jump
window spells a hop of at most 70 lines and one `DownAccLines` at most 255,
while at n=4 the bit-0 arm has to cross a 456-line subtree. A rung parked
inside the crossed region would lift both bounds. All 4, 16 and 256 tables
at n=1, 2 and 3 are executed over every input row; n≥4 raises `ValueError`.

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | It has no output command; the grid dump its interpreter renders at halt is limited to raster symbols. |
| Algebraic Programming Language | Executed lines print numeric results only. |
| ArrowQueue | Has no output. |
| Back | Its halting tape dump has only `0`, `1`, and spaces. |
| BF-PDA | Output is one bit at a time. |
| Bitdeque | Its interpreter-only deque dump is numeric. |
| COD | Its sink prints decimal integers only. |
| Circuit Diagram | Output is a bit string only. |
| Fargo | `$` prints the output register as a number. |
| Flowchart | Its output node emits one bit; the spec's truth machine fixes that convention. |
| Grapheme | String mode cannot contain `E`, and strings cannot be concatenated. |
| Inject | `send` appends a newline to every emitted line, so texts without a final newline are unreachable. |
| Jaune | `^` prints cells as decimal integers only. |
| Lamfunc | Whitespace tokenization and no concatenation prevent arbitrary text. |
| Minsky Swap | It has no output command; the halting register dump is numeric. |
| Point Break | Has no output. |
| RAM0 | It has no output command; its fixed-format final dump cannot address arbitrary text. |

Current caps are deliberate:

- **6-5:** 35 addressable branch labels; a structural language wall.
- **`%^2^-1`:** generic samples build through thirteen inputs; a
  fourteen-input table would need a twelve-input prefix ladder, which is
  open research, not a wall.
- **NoComment, Factor:** host/runtime configuration limits.
- **Polynomial, WII2D, ZTOALC L:** program-cost guards, not capability claims.
- **Route hybrids:** CV(N)(C), Polynomial, Circlefuck, `%^2^-1`, and WII2D
  alternatives were rejected on the grounds that occasional smaller output
  did not repay slower generation — 1.25x, 1.08x, 29x, 3,100x, and 1.85x on
  their audit cases. **Treat those five numbers as unverified**: the harness
  was not kept, and no measurement here reproduces one. Polynomial's figure is
  known wrong — its hybrid was reimplemented and ships (below), which was
  possible only because the bullet named the construction. CV(N)(C) and
  Circlefuck still build competing routes in-tree and were re-priced from
  that code: direct wins 202 of 256 at n=3 against stored's 54, and
  Circlefuck's greedy route never wins on size while costing about twice as
  much to build. Both verdicts stand on those measurements, not on the
  ratios. WII2D and `%^2^-1` both had a *committed* predecessor, recoverable
  from the commit that retired it: `ea65a170` removed WII2D's beam decode
  and `56c0d850` removed `%^2^-1`'s `_fold_search`, `_fold_beam` and
  `_fold_to_cofactors`. The current sources say those constructions keep no
  alternative and never backtrack, which describes what they are now, not
  what was tried. Both were recovered and re-measured, and neither ships.
  WII2D's beam does shorten output — as an optional second decode it shrank
  19,864 of 66,108 tables, none grown, median 5.2% — but it costs 9.8x
  generation at n=5 and reintroduces into a deterministic construction the
  search `ea65a170` removed; the size is not worth that. `%^2^-1`'s descent
  loses outright: over 40 five-input fold states the shipped rules plan all
  40 while the descent plans 5 at width 1 and 13 at width 4, slower at both.
  Recovering a predecessor does not re-derive the recorded ratio — the
  audited variants
  lived in a worktree and may differ — but it does mean these were never
  guesswork to retry.

  Polynomial is the exception. Its tree and state machine are the endpoints
  of one family — `k` tree levels above one machine per residual — and the
  interior wins where both lose: a table whose residuals merge within a
  top-level split but not across it. Shipping the whole family shortens 36
  of 256 three-input tables (median 3.6%, best 30.3%) and 3,846 of 65,536
  four-input ones (median 6.5%, best 39.8%); none grow, and none previously
  refused becomes renderable. Selection is on rendered characters, since
  instruction count disagrees with them; the count screens which candidates
  are worth rendering, costing 2.54x at n=3 (0.3s across 256 programs) and
  1.09x at n=4. The screen's slack is arity-dependent and measured, not
  derived — 6 at n<=3 but 9 at n=4 — so the counts are lower bounds.

## Assessed and rejected

- **Pinyin** ([wiki](https://esolangs.org/wiki/Pinyin)) — rejected: the
  command triples are not pinnable to any deterministic reading, and the
  wiki's own truth machine is unreachable under all of them.

  A command is a Chinese character; its tone picks the IP turn, its consonant
  a guard, its vowel a stack operation. Nothing in the repo or the page maps a
  character to a reading, so the table has to come from a pronunciation
  database, and the page's selection rule — smallest tone, then
  lexicographically smallest pinyin — **contradicts its own examples**.
  Applied over the full heteronym set it changes the tone, hence the routing,
  on 8 of the 23 Hello, world! characters: 邓 becomes `shan1` (turn) where the
  program needs `deng4` (straight, push stack size), and 但 兑 兔 待 淡 漏 道
  likewise. The rule reproduces the page's own five-row worked example
  perfectly (一 二 的 我 人, 5/5), so it is the *rule* that is example-hostile,
  not the reading source.

  Routing itself pins cleanly and was worth establishing: start at (0,0)
  facing right; the vowel effect runs, then the tone turns, and only when the
  consonant guard passes; the top and left edges deflect as in Nopfunge Solid;
  outside the written lines is blank, not Nopfunge Solid's infinite tiling;
  and escaping right or below halts. Under that model with common readings,
  Hello, world! emits `Qᮓ\t\tᮟè World!`, whose tail is exact up to the capital
  `W`; the page never states its output string, so that scores 7/13 against
  `Hello, World!` and 6/13 against its own lowercase section title. The tail is
  what fixes the model, and it also settles the duplicated `ui` row in favour
  of `b**a` over `a^b`, since `a^b` breaks it.

  It does not fix the programs. Searching every dictionary reading of every
  character crossed with the five open spec-gap choices (`ui` as power or
  xor, `iu` literal or reduced, EOF halts or pushes 0, division by zero halts
  or pushes 0, tone applied on a failed guard or not) reproduces the cat and
  the trivial half of the truth machine, and nothing else:

  | Example | Runs | Reproductions | Best |
  | --- | --- | --- | --- |
  | Truth machine, input 1 | 384 | **0** | 39/40 — `110111…`, a stray `0` third |
  | Truth machine, input 0 | 384 | 192 | exact |
  | Cat | 384 | 64 | exact, only where EOF halts |

  Input 1 is the falsifier, and it is exhaustive: the half that makes a truth
  machine a truth machine is one output character wrong under every one of its
  384 readings, and no spec-gap choice moves it. Hello, world! reproduces no
  better — its common-reading assignment, the only one matching the author's
  evident intent, is the 7/13 above, tail right and prefix wrong — but
  its 1,327,104-run sweep was not carried to completion, so no exhaustive
  claim is made for it.

  The page also defines `ui` twice (`b**a` and `a^b`) and gives `h` and `j`
  the same condition, never corrected; the examples were added by a third party
  (Cleverxia, "fix yet again"), never confirmed by the author, who left the
  proofs "as an exercise to the reader"; the page is `Category:Unimplemented`.

  Cost is not the objection. A two-input boolean program is **4 characters,
  12 bytes** — `业业但乍` (`ye4` read integer, twice; `dan4` multiply; `zha4`
  print integer), straight-line at tone 4, halting by escaping the right edge.
  Executed over the full truth table it is correct 4/4 for AND, and `业业令乍`
  4/4 for OR, under common readings; AND also holds under the spec's own
  selection rule. The language would price well. It fails CONTRIBUTING's
  "stable, deterministic, verifiable" bar on the spec, not on the generator.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators
  must stay in `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight's prose contradicts its own examples twice, and the examples decide
  both. It calls all operators postfix, but every example is infix
  (`turn c = eof`, `len{l}-0.5`), so expressions evaluate infix left to right
  with no precedence. It says three-argument `at` returns a copy, but the
  reversed cat runs `at{l, len{l}-0.5, c}` as a bare command and discards the
  result: under copy semantics that is a no-op and the example crashes on its
  own first `out`, so `at` sets in place. Both readings are pinned by running
  all three wiki programs.
- Packlang's wiki examples disagree on what base a numeric literal is in.
  Literals are read as **decimal**: Hello World, truth-machine and cat only
  work that way, while PlusOrMinus's `101011`/`101101` and the dependency
  example's `110000`/`101`/`011`/`001` were written as binary character
  codes and are declared wrong. A pure binary reading is refuted outright --
  four of the five examples contain non-binary digits, PlusOrMinus's own
  `Integer(0, 255, 255, 0)` among them. The tie against a hybrid reading
  breaks on the author's error markers: the comment `48 (1100000)`
  mis-writes 48 (`110000`), and `equals(101, 011)` uses leading zeros.
  Rebasing the dependency example's literals reproduces the `0110` its
  comments claim, so its logic is right and only its base is wrong.
- Packlang's cat cannot reach its own terminator here. `While c ^ 10 Do`
  waits for a newline *byte* from `charGet`, but input is line-delimited
  (`splitlines`), so no line begins with byte 10 and a blank line reads as
  the package-wide 0. The program parses and accumulates but never exits
  the loop; this is the line-IO convention, not an interpreter defect.

All generator output claims require execution through the interpreter. Do not
use permissive interpreter behavior or a bounded search as a new capability.
