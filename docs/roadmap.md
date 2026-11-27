# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `[resource_evidence.scaling]` and `[proof_status.audit]` in its
`language.toml` and run
`just docs` to update it. Proved limits remain
evidence, not optimization tasks.

- **Malbolge:** generation at seventeen inputs is open (2026-10-26).
  - *Why it is hard:* a table cell cannot carry eight
    address-independent meanings (window conflict graph: independence
    number 8, twelve classes); lockstep adjacent-cell reads reach 110 of
    512 triples a phase; the seven-meaning build's 1,994 gotos have 2.77
    cells each in the complement against a 3.6-cell annealed routing
    floor (certified at least 2.99).
  - *Ruled out:* hub substrates in the shipped and re-addressed
    geometries, marching and data-initialized decoders, threaded and
    streaming emission, membership dispatch, the permutation families;
    see [limitations](limitations.md) for eligibility, mechanism or
    measured rates.
  - *Reopen with:* a decoder variant whose word-mediated landing is
    realized in a full build that passes its gates (parity contract,
    per-row cases and a fresh census at the new window embedding, then
    placement and threaded rates inside the 9,897-cell complement), or
    new mathematics toward the 46,076 bits an impossibility proof needs
    beyond counting.
  - *Bulk seeding lead:* a 296-cell fall-through sweep matched all 94 word
    deposits against the stepper but placed 0 of the 74 shipped label cells
    without steering (best steered case: 8–10). Revisit for bulk deposits inside
    the paused loop.
    Sweep results in `a7b3f7abd:docs/roadmap.md`.
  - *Native decoder:* scratch builds ran from reset on all 131,072 inputs
    of four tables. One layout reached 130,347 and 130,277 correct
    answers on the two random tables. Both reads and the output slot
    matched on every row. All 130,949 legal reads per table printed the
    stored bit and halted. On the first table, 58 misses read an invalid
    packed byte and 667 read the wrong stored bit. An earlier one-cell
    return shift freed 42 words. All eight values at each word ran natively.
    After swapping the highest address trit, 103 groups reread their
    selector to choose among three spill routes. This moved 4,944 primary
    words and preserved every spill address. Two other layouts used a
    second selector. The same 64 groups kept 3,072 primary moves and
    reassigned all 4,096 of their spill bits. Both layouts reached 131,072
    distinct bit positions. A separate layout moved 448 primary words by
    reassigning 3,008 spill bits. All eight values worked at 434 of the
    new destinations in 10,416 runs.
  - *Bank capacity:* six navigation edits freed 153 three-bit words while
    preserving both reads and the output slot on every row. All eight labels
    worked at every word in 3,672 native runs. Shortening initialization
    freed 871 consecutive cells for decoder code and a 408-word output
    lookup. Moving the lookup and the final decoder block freed 369 and
    77 three-bit words, respectively. All eight values at each word
    passed in 10,704 row executions across the two layouts. Moving the
    phase read 94 cells earlier made room for a pointer shortcut. Clearing
    one temporary register and rotating the calibration byte earlier freed
    161 more three-bit words. All eight values passed in 3,864 executions.
    Routing startup around one output routine reduced the fixed-bank
    shortfall from 1,213 bits to 961 across eight banks, with 2,048 bits
    per 729-word bank and control words and calibration markers reserved.
    Both reads and the output slot matched on all 131,072 rows of each
    random table. This layout answered 129,805 and 129,560 rows correctly.
    Moving all three output routines into startup memory freed 261 more
    three-bit words. All eight labels worked at every word in 6,264 native
    runs. The displaced startup code raised the shortfall to 3,869 bits.
    A separate layout moved 24 primary words between
    banks, kept every spill address, and gained three writable bit positions
    net. All eight labels worked at
    all 24 destinations.
  - *Storage shared with the decoder:* 93 words in the jump workspace
    stored three answer bits each. In the same layout, 63 fixed instructions
    encoded three bits each through selectable markers. All eight values
    at each word worked across 64 paired patterns (29,952 row executions).
    A separate marker distinguished two fixed instructions while preserving
    all eight values at 101 writable words in its bank. Shortening two output
    routines in the 961-bit layout left 587 bits short with control words
    reserved. Calibration markers let instructions carry answer bits even
    after startup encrypted them. Of 431 independently writable bits, 409
    filled bank deficits. Banks 15, 24 and 26 still lacked 25, 29 and 124
    bits, respectively (178 total). All 1,232 local bit patterns passed in
    3,848 row executions. The two random tables produced 129,909 and
    129,878 correct answers out of 131,072 each.
    A different layout selected one of two adjacent calibration cells by
    address. Each of 84 marker pairs encoded all four bit combinations
    with both data words held fixed (672 row executions). Two ordinary
    words per pair retained all eight labels in 16,128 executions. Moving the
    phase lookup 36,450 cells freed 185 occupied words at its old location.
    All eight labels there passed across 554 row bits in 4,432 executions.
    After packing the new layout, seven banks still lacked 360 bits in
    total. In the single-marker layout, eight instruction substitutions
    moved the phase workspace 10,935 cells. Delaying the lookup six steps
    freed seven three-bit words. The two random tables answered 130,075
    and 130,030 rows correctly. Reserving the control cells used by either
    table left 176 bits short, including 165 in bank 41.
    Shortening startup by 368 instructions made room for the phase lookup
    before the first output routine. A 22-instruction pointer shortcut
    freed space in bank 9. Counting three bits per unreserved word and
    368 independently selectable bits, all 64 banks reached their
    2,048-bit target with the control cells from both traces reserved.
    The decoder still addressed 1,745 row positions outside that writable
    set. Reassigning 4,160 spill rows reduced that count to 1,648.
    A second layout moved 4,608 spill rows and reached two previously
    unused low address values. Its navigation could read 57 words with
    any of their eight labels, freeing 159 row positions. After assigning
    marker bits across all banks, 1,604 positions still lacked independent
    storage. With capacity counted only at reached low address values,
    the two layouts fell 317 and 85 bits short, respectively. The second
    answered 130,360 and 130,336 of 131,072 rows correctly.
    Moving pointer initialization into the low addresses bypassed ten
    startup blocks. Shorter pointer walks and a smaller decoder helped
    free 482 words holding 1,355 row bits. All eight values at each word
    passed in 10,840 row executions per table. With five output lookup
    entries repaired, both programs printed one digit and halted on every
    input. Reassigning 896 spill rows reduced the remaining gap from 346
    to 339 positions. The two tables answered 130,923 and 130,930 rows
    correctly. Of the 339 positions, 209 are in the output routines in banks
    15 and 24.
    Shortening the digit printer by seven instructions let all three output
    routines fit between addresses 4,457 and 4,680. With their final helper
    at 5,565, the layout freed 168 formerly reserved words. All eight values
    passed across their 483 row positions in 3,864 executions per table.
    Moving a fixed address calculation into startup shortened the decoder by
    26 instructions. All eight values passed at 15 freed words in 344 row
    executions per table. Both tables printed one digit and halted on all
    131,072 inputs, with 33 and 41 wrong answers. The independent storage gap
    fell from 115 to 83 positions (78 primary and five spill).
    A shorter pointer walk and alternative encodings for control words
    reduced the gap to 68 positions (67 primary and one spill). Four tables
    printed one digit and halted on every input, with 25, 34, 24 and 28
    wrong answers. Every mismatch fell within those 68 positions.
    Two positions counted as covered relied on an encoding at address 39,391
    that lost the return address for some neighboring guard values.
    Fixing that encoding and changing the output lookup left 61 uncovered
    positions. Switching two lookup entries together encoded row 103,438,
    leaving 60 primary positions and no spills. Four tables printed one
    digit and halted on all 131,072 inputs. Their 24, 24, 29 and 32 wrong
    answers all fell within those 60 positions.
    Four requested bits now select the output lookup using XOR and three
    pairwise ANDs. All 16 settings passed 4,544 control-word and 280,800
    ordinary-word runs in total. The gap fell to 57 primary positions.
    Four tables halted on every input with 20, 24, 31 and 29 wrong answers,
    all within those 57 positions.
    Saving the return address in word 170 freed words 29,538–29,541.
    Each held all eight three-bit values under all eight lookup settings.
    The gap fell to 52 primary positions. On all 131,072 inputs per table,
    four tables printed one digit and halted with 22, 24, 26 and 30 wrong
    answers, all within those 52 positions.
    Changing the data address that selects digit 1 from 45,925 to 41,551
    freed five three-bit words and used three others. Six requested bits
    select the lookup. All 64 settings
    passed 7,680 runs covering all eight values of the five freed words.
    The gap fell to 47 primary positions. Four tables halted on every input
    with 25, 25, 23 and 24 wrong answers, all within those positions.
    The decoder selects between two output addresses three instructions
    earlier and uses a 12-instruction printer. Words 41,559, 45,933 and
    54,681 each regained all eight three-bit values under all four lookup
    settings (288 runs). The gap fell to 44 positions. Four tables
    halted on every input with 17, 26, 27 and 23 wrong answers, all
    within those positions.
    Reordering nine register writes and changing two pointer walks freed
    words 45,929, 45,928 and 41,557. Across four lookup settings, all six
    words freed since the 47-position layout passed 768 runs covering
    all eight values. The gap fell to 37 positions (36 primary, one spill).
    Four tables printed one digit and halted on every input with 17, 21,
    23 and 21 wrong answers, all within those 37 positions.
    Word 41,391 can encode either answer for spill input 80,611. Its
    two source instructions select pointer walks that rejoin before
    the next arithmetic instruction. This leaves 36 primary positions.
    Four tables halted on every input with 16, 20, 23 and 20 wrong
    answers, all within those positions.
    Choosing words 39,391 and 39,394 together covers inputs 82,016 and
    82,017 and gives up 82,018, leaving 35 primary positions. All 32
    assignments to the five covered inputs passed under each of four lookup
    settings. Four tables printed one digit and halted on all 131,072 inputs
    each, with 15, 19, 22 and 19 wrong answers inside those 35 positions.
    Independently reversing the digits printed by output slots 1 and 2
    covers inputs 45,089 and 5,134, leaving 33 primary positions. The four
    tables halted on every input with 12, 12, 15 and 12 wrong answers,
    all within those positions. Moving the slot 0 lookup six instructions
    earlier lets that slot reverse its digits too. Input 127,032 gains
    either answer, leaving 32 primary positions. Four tables printed one
    digit and halted on every input with 13, 12, 15 and 12 wrong answers,
    all within those 32 positions.
    Output slots 1 and 2 can also print from a third address, 54,673.
    Sending it through the same pointer path as 45,925 lets the lookup
    table encode input 103,436, leaving 31 primary positions. Four tables
    printed one digit and halted on every input with 13, 14, 13 and 18
    wrong answers, all within those positions. Rerouting one startup walk
    and two input-dependent walks freed word 54,676 for inputs 61,496
    through 61,498. All eight assignments passed under every lookup and
    polarity setting. The gap fell to 28 primary positions. Four tables
    halted on every input with 11, 13, 11 and 16 wrong answers, all
    within those positions. Moving a register reset ahead of the jump to
    24,814 and bypassing two unused register writes freed word 41,554.
    Inputs 61,473 and 61,474 gained either answer, leaving 26 primary
    positions. Four tables halted on every input with 11, 12, 11 and 15
    wrong answers inside those positions. Choosing the lookup and markers
    for each whole table separately gave exact programs for fixture A and
    its complement on all 131,072 inputs each.
    Rerouting the pointer reads at 41,556 and 45,930 freed five more
    answers (127,009–127,010 and 127,076–127,078). The general gap is
    21 positions. Four lookup settings suffice. The four tables halted
    on every input with 9, 12, 9 and 12 wrong answers, all inside the
    gap. A separate fit reproduced the independently seeded fixture D
    on all 131,072 inputs.
    Choosing the lookup and printer polarities jointly covers three more
    inputs (21,516, 103,437 and 127,034), leaving 18 primary positions.
    Across 26 lookup tables, every one of the 8,192 assignments to the
    13 selector bits has a matching encoding. Four tables halted on every
    input with 8, 9, 8 and 10 wrong answers, all within those 18 positions.
    Rerouting all 14 pointer reads of word 41,555 also gave an exact
    program for fixture B, verified on all 131,072 inputs.
    The same word now encodes any three bits. Redirecting two more pointer
    walks from words 6,903 and 6,904 to 705 and 706 leaves 13 primary
    inputs. The five newly independent answers are 45,088, 45,090, 50,293,
    50,294 and 68,724. Ten lookup tables cover all 32,768 assignments to the
    15 selector bits. Four full tables halted on every input with 5, 4, 5
    and 7 wrong answers, all inside the 13 positions.
    Expanding the lookup choices covers inputs 45,112 and 45,114 as well.
    The general gap is 11. Across 49 lookups, every assignment to the 17
    selector bits has an encoding. Four full runs halted on every input
    with 5, 4, 5 and 2 wrong answers, all within those 11 positions.
    Ending startup at word 29,528 and rerouting the remaining pointer
    reads freed words 29,529–29,536. Each encoded all eight three-bit
    answers. The general gap fell to two inputs, 89,102 and 105,484.
    Fifteen lookups cover all 131,072 selector assignments. Four tables
    printed a digit and halted on every input with 1, 0, 1 and 1 wrong
    answers, all at those two positions.
    [Selector coverage check](../experiments/malbolge-n17/README.md#selector-coverage)
    and [runnable fixtures](../experiments/malbolge-n17/README.md#exact-truth-table).
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

- **Malbolge read-only decoder placement.** Filling each bounded hole
  exactly with movable code blocks fits 22 one-port targets: 283 native
  decoder words, 841 host-staged, 7,112 queries with zero writes to the
  packed table. At 23 targets the zero-slack fill leaves 40 contiguous cells
  for seven late frames that need 56. Free 16 cells by shortening the writer
  or counted code, or place frames across fixed cells.

- **Malbolge navigation, inexpressibility for an algebraic
  signature:** the [bounded-read lower bound](limitations.md#searches)
  excludes rules based on cycle data and bounded algebraic features. The open question is whether a term over the restricted algebraic
  signature can compute the optimal first step. The classified invariant
  relations give no separation. Reopen with a separating non-product or
  non-uniform relation, or a term computing the step.
## Wiki shortlist

- Six screened candidates advance to the next implementation pass. Each subset probe passed all 65,536 arity-four tables
  on all 16 inputs, plus sampled inputs through arity ten. Each emitter has
  O(T) generation time and source size. Order favors direct constructions
  using documented operations with few open questions on the generator's path.
    1. [StrML](https://esolangs.org/wiki/StrML) (rev. 179266).
       A quoted source header carries the fixed base. One grouped test per
       immutable input bit selects the result. The artifact is `8T` characters.
    2. [Numlist](https://esolangs.org/wiki/Numlist) (rev. 138564).
       Each input binds one contiguous block of relative jumps. Shared
       suffix states keep the decimal source linear. One forward pass
       prints the selected bit and exits past the instruction list.
    3. [Pd.NA](https://esolangs.org/wiki/Pd.NA) (rev. 147169).
       One tape cell selects branches and emits the bit. An EOF witness
       exercised the NA catch path. Source is exactly `11T−7` characters.
    4. [Thing of Shock](https://esolangs.org/wiki/Thing_of_Shock) (rev. 204327).
       An acyclic graph binds each input bit to one initial counter.
       Shared suffix graphs keep the serialized source linear. Read the
       designated counter at tick `4n+3` for `n` input bits.
    5. [Globe](https://esolangs.org/wiki/Globe) (rev. 165023). State-dependent
       parity filters table symbols per embedded input bit. The last transition
       prints the remaining bit.
    6. [Turing Code](https://esolangs.org/wiki/Turing_Code) (rev. 204341).
       An acyclic `!!DTM` graph leaves one string bit on the trimmed tape in
       `n+1` transitions. The printed tape format remains open.
  - *Semantic screen:* StrML edits a base string through separate base and
    input cursors. Numlist prints the magnitude of an underflowing jump, so
    character output depends on instruction placement. Pd.NA propagates
    missing tape values and catches them at control boundaries.
  - *Admission:* refresh the public-implementation check and apply the
    [curation rules](limitations.md#curation). Verify the complete
    interpreter and generator before adding each language.

## Wiki candidate backlog

### Reserve (12)

- [XMLfuck](https://esolangs.org/wiki/XMLfuck)
- [Methylmercury](https://esolangs.org/wiki/Methylmercury)
- [Brainfive](https://esolangs.org/wiki/Brainfive)
- [FastBrain](https://esolangs.org/wiki/FastBrain)
- [kxgxyo](https://esolangs.org/wiki/Kxgxyo)
- [ASCII @](https://esolangs.org/wiki/ASCII_@). The translated subset ran
  on public `@`, which rejects raw ASCII source and differs on negative
  fractions. Refresh the search for a public ASCII runner at admission.
- [Helo PkmnQ](https://esolangs.org/wiki/Helo_PkmnQ)
- [诗(PSTF)](https://esolangs.org/wiki/%E8%AF%97(PSTF))
- [NoGolfersLand](https://esolangs.org/wiki/NoGolfersLand)
- [Brаinfuck](https://esolangs.org/wiki/Br%D0%B0infuck) (rev. 202557). The
  two-cell generator passed the full sweep. The tape-edge rule for `&`
  remains unspecified.
- [Gridify](https://esolangs.org/wiki/Gridify) (rev. 201532). Numeric I/O and
  `G` lookup passed the full sweep. Both the stack index and grid width grow
  with the table length.
- [You wait here](https://esolangs.org/wiki/You_wait_here) (rev. 131213).
  A counter reset and two conditional blocks select each branch.
  `repeat`, `split` and `define` remain open outside this subset.

The first-implementation screen dropped QuakeScript and 1nteger from the
shortlist. Their selectors use an accumulator, ordinary tests and jumps or
blocks. Fourteen reserve candidates likewise offered direct scripting
constructions. Reserve entries still need a worked example demonstrating
their semantic constraint before promotion.

The original revision pins and screening sketches are in
`5f3bcddf3:docs/roadmap.md`.
