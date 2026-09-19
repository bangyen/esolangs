# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![CI](https://github.com/bangyen/esolangs/actions/workflows/ci.yml/badge.svg)](https://github.com/bangyen/esolangs/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/esolangs.svg)](https://pypi.org/project/esolangs/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Interpreters and boolean-circuit generators for 59 esoteric languages.
`generate` takes a truth table and returns a program computing it;
`verify` runs that program on every row and checks what it answers.

[usage](https://github.com/bangyen/esolangs/blob/main/docs/usage.md) is the
caller's guide -- the exported functions, the four odd input shapes,
templates, reading an answer back, the debugger.
[architecture](https://github.com/bangyen/esolangs/blob/main/docs/architecture.md)
shows how the registry, generators, interpreters, and answer extraction
connect.
[roadmap](https://github.com/bangyen/esolangs/blob/main/docs/roadmap.md) tracks
live work and
[limitations](https://github.com/bangyen/esolangs/blob/main/docs/limitations.md)
records contracts.

Start with the [CLI](#command-line), [Python API](#python-api), or
[contribution guide](https://github.com/bangyen/esolangs/blob/main/docs/CONTRIBUTING.md).

## Command line

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

## Python API

```python
import esolangs

esolangs.verify("Fargo", "10010110")  # -> True
```

Pass each command the language it was generated for: running a Suffolk
program as brainfuck does not fail, it reports something useless.  How a
language reads its input bits is not universal either -- let
[`encode_inputs`](https://github.com/bangyen/esolangs/blob/main/docs/usage.md#feeding-a-program)
build the stdin.

## Examples

`esolangs generate Sophie 0110` emits 51 characters computing XOR:

```
;@$48{;@$48{#$48,&}{#$49,&}}{;@$48{#$49,&}{#$48,&}}
```

Feeding it the two input bits, one per line, prints their XOR.
`tests/test_readme_example.py` runs all four rows, so the block cannot
drift.

## Stepping a program

<!-- TUI-FRAME:START -->

`--tui` steps it on screen instead.  This is a real frame -- Flowchart at
step 14, redrawn by `tui.render` every time this file is generated:

```
Flowchart  step 14  ip (9, 7, 1, 0)  running
--------------------------------------------------------------------------
 5 |     ┌───< >───┐
 6 |     │         │
 7 |    / /       / /
 8 |     │         │
 9 |   ┌< >─┐    ┌< >─┐
10 |   │    │    │    │
11 |  { ]  [ }  [ }  { ]
12 |   │    │    │    │
13 |  \ \  \ \  \ \  \ \
14 |   │    │    │    │
15 | (( ))(( ))(( ))(( ))
--------------------------------------------------------------------------
memory   (empty)
stack    (empty)
output   ''
views    deques={}  pointers=[_Pointer(row=9, col=7, d=(1, 0), reg=1, dequ
hjkl move | t break | space step | c continue | r run | b back | q quit
```

The live screen reverse-videos the cell at that `ip`; colour does not survive
the page.  [usage](https://github.com/bangyen/esolangs/blob/main/docs/usage.md#debugging) names every key.

<!-- TUI-FRAME:END -->

<!-- EXAMPLES:START -->

Ready-to-run programs are committed under [`examples/`](https://github.com/bangyen/esolangs/tree/main/src/esolangs/examples):
`examples/` holds a truth-table program for each of the 59
languages with a boolean generator.  It regenerates via
`scripts/generate.py examples`.

<!-- EXAMPLES:END -->

## Implemented languages

<details>
<!-- IMPLEMENTED:START -->

<summary>Show all 59 languages</summary>

### Grid-based Languages

Languages that move a pointer or beam across a 2D grid.

- [A Painter Ant](https://esolangs.org/wiki/A_Painter_Ant) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/a_painter_ant.py))
- [Alight](https://esolangs.org/wiki/Alight) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/alight.py))
- [ArrowQueue](https://esolangs.org/wiki/ArrowQueue) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/arrowqueue.py))
- [B-tapemark](https://esolangs.org/wiki/B-tapemark) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/b_tapemark.py))
- [Circuit Diagram](https://esolangs.org/wiki/Circuit_Diagram) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/circuit_diagram.py))
- [Clockwise](https://esolangs.org/wiki/Clockwise) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/clockwise.py))
- [Dig](https://esolangs.org/wiki/Dig) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/dig.py))
- [EGL](https://esolangs.org/wiki/EGL) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/egl.py))
- [Flowchart](https://esolangs.org/wiki/Flowchart) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/flowchart.py))
- [LaserFuck](https://esolangs.org/wiki/LaserFuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/laserfuck.py))
- [Streetcode](https://esolangs.org/wiki/Streetcode) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/streetcode.py))
- [Super SNUSP](https://esolangs.org/wiki/Super_SNUSP) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/super_snusp.py))

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

- [AddSubJump](https://esolangs.org/wiki/AddSubJump) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/addsubjump.py))
- [BIO](https://esolangs.org/wiki/BIO) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/bio.py))
- [Collatz Multiverse](https://esolangs.org/wiki/Collatz_Multiverse) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/collatz_multiverse.py))
- [Decleq](https://esolangs.org/wiki/Decleq) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/decleq.py))
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/minsky_swap.py))
- [Polynomial](https://esolangs.org/wiki/Polynomial) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/polynomial.py))
- [Qoibl](https://esolangs.org/wiki/Qoibl) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/qoibl.py))
- [RAM0](https://esolangs.org/wiki/RAM0) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/ram0.py))
- [Sophie](https://esolangs.org/wiki/Sophie) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/sophie.py))

### Other Languages

Languages that don't fit into the above categories.

- [Algebraic Programming Language](https://esolangs.org/wiki/Algebraic_Programming_Language) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/algebraic_programming_language.py))
- [CV(N)(C)](https://esolangs.org/wiki/CV(N)(C)) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/cvnc.py))
- [Container](https://esolangs.org/wiki/Container) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/container.py))
- [Crement](https://esolangs.org/wiki/Crement) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/crement.py))
- [Fargo](https://esolangs.org/wiki/Fargo) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/fargo.py))
- [Forbin](https://esolangs.org/wiki/Forbin) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/forbin.py))
- [Inject](https://esolangs.org/wiki/Inject) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/inject.py))
- [Packlang](https://esolangs.org/wiki/Packlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/packlang.py))
- [Vandevelo](https://esolangs.org/wiki/Vandevelo) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/vandevelo.py))

<!-- IMPLEMENTED:END -->
</details>

Line is an image-language module under `esolangs.line`; run
`just test-line` for its suite.

## Generators

Boolean generators accept a most-significant-input-first binary truth table.

<!-- BOOLEAN-COUNT:START -->

The truth table is a binary string of length `2**n`, most-significant input
first; its length implies `n`, so it isn't passed separately.  59 of the
languages have such a generator, some covering only a documented subset of
tables.

<!-- BOOLEAN-COUNT:END -->

`esolangs list --details` marks which languages have one (`gen`), which
return a template (`tmpl`), and which have a committed example (`ex`); add
`--json` for structured output:

```bash
esolangs list --details --json | jq '.[] | select(.name == "Sophie")'
```

```json
{
  "name": "Sophie",
  "boolean_generator": true,
  "parameterized": false,
  "has_example": true
}
```

Regenerate the committed examples with `python scripts/generate.py examples`.

## Contributing

Read [the contribution guide](https://github.com/bangyen/esolangs/blob/main/docs/CONTRIBUTING.md),
then run `just test`.
The project is GPL v3; see [LICENSE](https://github.com/bangyen/esolangs/blob/main/LICENSE).
