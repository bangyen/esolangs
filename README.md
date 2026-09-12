# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Interpreters and generators for esoteric
languages. Current work is in [the roadmap](docs/roadmap.md); contracts and
known boundaries are in [limitations](docs/limitations.md). The rest of
[`docs/`](docs/README.md) is indexed there.

## Use

```bash
just install-dev                 # installs into ./.venv
source .venv/bin/activate        # ...or prefix each command with `uv run`

esolangs --help
esolangs list
esolangs generate Suffolk 0110 > program.txt
printf '0\n1\n' | esolangs run Suffolk program.txt

esolangs generate brainfuck 0110 > bf.txt
printf '0\n1\n' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
just test
```

Pass each command the language it was generated for: running a Suffolk
program as brainfuck does not fail, it reports something useless.

`just install-dev` puts the `esolangs` entry point in `.venv/bin`, so it is
on `PATH` only once that venv is active; `uv run esolangs ...` works
without activating it.

The Python API is `esolangs.run`, `generate`, `instantiate`,
`encode_inputs`, `read_answer`, `evaluate`, `verify`, `check_stdin`,
`check_program`, `make_vm`, `make_debugger`, `describe`, `spec`, and
`list_languages`.  `generate` takes a
truth table -- `0110` is XOR -- and returns a program computing it.  Use
`--width` for command-oriented generated programs; grids and
newline-sensitive languages retain their own layout.

**How a language reads its input bits is not universal.**  Most take one
`0`/`1` line each, but Grapheme reads `%`/`A`, Clockwise wants every bit on
one line, Fargo wants the row index as a single decimal number (`1111` is
`15`), and Taglate pads an odd input count with a leading zero line (its
three-input programs read four lines).  Stdin is checked against the shape and alphabet a
language declares: `esolangs run` warns, `esolangs run --judge` refuses,
and `esolangs.check_stdin(language, stdin, truth_table)` is the same judge
from Python -- give it the table and it checks the bit *count* too, which
catches a surplus line as well as a missing one.  A shape it cannot tell
apart from a legitimate one still answers the wrong row, so let
`esolangs.encode_inputs(language, bits)` build the stdin — or read the
Input column of [`examples/boolean/MANIFEST.md`](examples/boolean/MANIFEST.md),
which lists every language's.

Seventeen languages have a **parameterized** generator: it embeds the
inputs in the program rather than reading them, so `generate` returns a
template with a `{Xi}` slot per input.  Fill it with
`esolangs.instantiate(language, template, bits)` -- running one unfilled is
refused.  `esolangs list --details` marks them `tmpl`, and
[`docs/languages.md`](docs/languages.md#parameterized-generators) lists
them.

**Reading the answer back is the same story.**  Most languages print it,
but six dump their whole final state with the answer somewhere inside, and
three answer by *terminating* -- they halt for a 0 and loop forever for a 1.
`esolangs.read_answer(language, output)` handles the first two cases; for
the third, bound the run and catch `ExecutionTimeoutError` as the 1.  With
`describe`, `encode_inputs`, `instantiate` and `read_answer`, a caller can
generate, feed and judge a program in a language it knows nothing about,
with no per-language branch anywhere.

**That round trip is `evaluate`, so you do not have to write it.**  It runs
the generated program on every row of its input space and returns the table
it actually computes; `verify` is the same thing with the comparison done:

```python
esolangs.evaluate("A Painter Ant", "0110")  # -> '0110'
esolangs.verify("Fargo", "10010110")  # -> True
```

Both work for all 69 -- the four odd input shapes, the seventeen template
languages and the three that answer by diverging included -- because every
decision they make reads a `describe` field rather than a language name.

`debug` runs a program under the breakpoint/watch VM and reports where it
stopped: `--steps` bounds the run and `--watch-cell` prints one value per
step.  `--break-at`, `--break-on-cell I=V`, and `--break-on-output` each
stop with their condition still true.

`--tui` steps it on screen instead, highlighting the op about to run and
showing the tape, stack, output, and the language's own named state beside
it, with `--watch-cell`'s history as a row that grows as you step and
shortens as you go back.  `hjkl` move a selector so a breakpoint can be set
where the run has not reached yet; `t` marks under it and `c` continues to
the next one.  Feed such a run with `--stdin`, since the keys and the
program cannot share one stream.  A language whose position is not a place
in the source — a call stack, a 3-D point — is left unhighlighted rather
than marked in the wrong place; the header always shows the raw `ip`.

## Examples

`esolangs generate Sophie 0110` emits 51 characters computing XOR:

```
;@$48{;@$48{#$48,&}{#$49,&}}{;@$48{#$49,&}{#$48,&}}
```

Feeding it the two input bits, one per line, prints their XOR.
`tests/test_readme_example.py` runs all four rows, so the block cannot
drift.

<!-- EXAMPLES:START -->

Ready-to-run programs are committed under [`examples/`](examples/):
`examples/boolean/` holds a truth-table program for each of the 69
languages with a boolean generator.  It regenerates via
`scripts/write_examples.py`.

<!-- EXAMPLES:END -->

## Implemented languages

<details>
<!-- IMPLEMENTED:START -->

<summary>Show all 69 languages</summary>

The full capability matrix (generators, boolean support, examples) is in [`docs/languages.md`](docs/languages.md).

### Grid-based Languages

Languages that move a pointer or beam across a 2D grid.

- [A Painter Ant](https://esolangs.org/wiki/A_Painter_Ant) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/a_painter_ant.py))
- [Alight](https://esolangs.org/wiki/Alight) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/alight.py))
- [ArrowQueue](https://esolangs.org/wiki/ArrowQueue) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/arrowqueue.py))
- [COD](https://esolangs.org/wiki/COD) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/cod.py))
- [Circuit Diagram](https://esolangs.org/wiki/Circuit_Diagram) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/circuit_diagram.py))
- [Clockwise](https://esolangs.org/wiki/Clockwise) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/clockwise.py))
- [Dig](https://esolangs.org/wiki/Dig) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/dig.py))
- [Flowchart](https://esolangs.org/wiki/Flowchart) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/flowchart.py))
- [LaserFuck](https://esolangs.org/wiki/LaserFuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/laserfuck.py))
- [Streetcode](https://esolangs.org/wiki/Streetcode) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/streetcode.py))
- [Super SNUSP](https://esolangs.org/wiki/Super_SNUSP) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/super_snusp.py))
- [WII2D](https://esolangs.org/wiki/WII2D) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/wii2d.py))

### Stack-based Languages

Languages that use a stack for data manipulation.

- [3x](https://esolangs.org/wiki/3x) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/three_x.py))
- [BF-PDA](https://esolangs.org/wiki/BF-PDA) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/bf_pda.py))
- [BFStack](https://esolangs.org/wiki/BFStack) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/bfstack.py))
- [Eval](https://esolangs.org/wiki/Eval) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/eval.py))
- [Forþ](https://esolangs.org/wiki/For%C3%BE) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/forth.py))
- [Grapheme](https://esolangs.org/wiki/Grapheme) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/grapheme.py))
- [Modulous](https://esolangs.org/wiki/Modulous) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/modulous.py))
- [Unsquare](https://esolangs.org/wiki/Unsquare) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/unsquare.py))

### Queue-based Languages

Languages whose primary data structure is a queue or deque.

- [Bitdeque](https://esolangs.org/wiki/Bitdeque) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/queue_based/bitdeque.py))
- [Taglate](https://esolangs.org/wiki/Taglate) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/queue_based/taglate.py))

### Tape-based Languages

Languages that operate on a tape (similar to Turing machines).

- [123](https://esolangs.org/wiki/123) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/one_two_three.py))
- [3D Brainfuck](https://esolangs.org/wiki/3D_Brainfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/three_d_brainfuck.py))
- [6-5](https://esolangs.org/wiki/6-5) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/six_five.py))
- [Back](https://esolangs.org/wiki/Back) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/back.py))
- [Basicfuck](https://esolangs.org/wiki/Basicfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/basicfuck.py))
- [BrainIf](https://esolangs.org/wiki/BrainIf) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/brainif.py))
- [Circlefuck](https://esolangs.org/wiki/Circlefuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/circlefuck.py))
- [Dimensional](https://esolangs.org/wiki/Dimensional) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/dimensional.py))
- [Factor](https://esolangs.org/wiki/Factor) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/factor.py))
- [Home Row](https://esolangs.org/wiki/Home_Row) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/home_row.py))
- [Jaune](https://esolangs.org/wiki/Jaune) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/jaune.py))
- [Minifuck](https://esolangs.org/wiki/Minifuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/minifuck.py))
- [NoComment](https://esolangs.org/wiki/NoComment) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/nocomment.py))
- [Painfuck](https://esolangs.org/wiki/Painfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/painfuck.py))
- [ROTfuck](https://esolangs.org/wiki/ROTfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/rotfuck.py))
- [S*bleq](https://esolangs.org/wiki/S*bleq) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/sbleq.py))
- [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/slow_acv_mammalian.py))
- [Suffolk](https://esolangs.org/wiki/Suffolk) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/suffolk.py))
- [bit~](https://esolangs.org/wiki/bit~) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/bit_tilde.py))
- [brainfuck](https://esolangs.org/wiki/brainfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/brainfuck.py))

### Register-based Languages

Languages that use registers to store and manipulate data.

- [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/pct_squared_minus_one.py))
- [AddSubJump](https://esolangs.org/wiki/AddSubJump) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/addsubjump.py))
- [BIO](https://esolangs.org/wiki/BIO) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/bio.py))
- [Between](https://esolangs.org/wiki/Between) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/between.py))
- [Collatz Multiverse](https://esolangs.org/wiki/Collatz_Multiverse) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/collatz_multiverse.py))
- [Decleq](https://esolangs.org/wiki/Decleq) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/decleq.py))
- [Interprogck8](https://esolangs.org/wiki/Interprogck8) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/interprogck8.py))
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/minsky_swap.py))
- [MyScript](https://esolangs.org/wiki/MyScript) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/myscript.py))
- [Nevermind](https://esolangs.org/wiki/Nevermind) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/nevermind.py))
- [Point Break](https://esolangs.org/wiki/Point_Break) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/point_break.py))
- [Polynomial](https://esolangs.org/wiki/Polynomial) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/polynomial.py))
- [Qoibl](https://esolangs.org/wiki/Qoibl) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/qoibl.py))
- [RAM0](https://esolangs.org/wiki/RAM0) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/ram0.py))
- [Sophie](https://esolangs.org/wiki/Sophie) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/sophie.py))

### Other Languages

Languages that don't fit into the above categories.

- [Algebraic Programming Language](https://esolangs.org/wiki/Algebraic_Programming_Language) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/algebraic_programming_language.py))
- [CV(N)(C)](https://esolangs.org/wiki/CV(N)(C)) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/cvnc.py))
- [Container](https://esolangs.org/wiki/Container) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/container.py))
- [DINAC](https://esolangs.org/wiki/DINAC) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/dinac.py))
- [Fargo](https://esolangs.org/wiki/Fargo) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/fargo.py))
- [Forbin](https://esolangs.org/wiki/Forbin) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/forbin.py))
- [Inject](https://esolangs.org/wiki/Inject) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/inject.py))
- [Lamfunc](https://esolangs.org/wiki/Lamfunc) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/lamfunc.py))
- [Packlang](https://esolangs.org/wiki/Packlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/packlang.py))
- [Suptiftam](https://esolangs.org/wiki/Suptiftam) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/suptiftam.py))
- [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/ztoalc_l.py))
- [function x(y)](https://esolangs.org/wiki/function_x(y)) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/function_x_y.py))

<!-- IMPLEMENTED:END -->
</details>

Line remains a standalone PNG-language tool under `extra/line`; run
`just test-line` for its suite.

## Generators

Boolean generators accept a most-significant-input-first binary truth table.

<!-- BOOLEAN-COUNT:START -->

The truth table is a binary string of length `2**n`, most-significant input
first; its length implies `n`, so it isn't passed separately.  69 of the
languages have such a generator, some covering only a documented subset of
tables.

<!-- BOOLEAN-COUNT:END -->

Generators are available through `esolangs generate`; `esolangs list
--details` marks which languages have one (`gen`), which return a template
(`tmpl`), and which have a committed example (`ex`). Add `--json` to get
those as an object per language instead of a marker column, and `esolangs
describe --json <language>` for the whole record. Regenerate committed
examples with `python scripts/write_examples.py`.

## Contributing

Read [the contribution guide](docs/CONTRIBUTING.md), then run `just test`.
The project is GPL v3; see [LICENSE](LICENSE).
