# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Coverage](coverage-badge.svg)](coverage-badge.svg)

## Table of Contents

- [About](#about)
- [Usage](#usage)
- [Implemented Languages](#implemented-languages)
  - [Register-based Languages](#register-based-languages)
  - [Tape-based Languages](#tape-based-languages)
  - [Stack-based Languages](#stack-based-languages)
  - [Other Languages](#other-languages)
- [Extra Implementations](#extra-implementations)
- [Compilers](#compilers)
- [Transpilers](#transpilers)
- [Tools](#tools)
- [Contributing](#contributing)
- [License](#license)

## About

Working interpreters, compilers, and transpilers for esoteric programming
languages, each verified against its spec.  Most interpreters read the
program file from the first command-line argument.

Planned work is tracked in [`docs/roadmap.md`](docs/roadmap.md); documented
limitations and ruled-out ideas live in [`docs/limitations.md`](docs/limitations.md),
with the full wall arguments in [`docs/walls.md`](docs/walls.md).

## Usage

### Installation

```bash
git clone https://github.com/bangyen/esolangs.git
cd esolangs
just install-dev
```

### Running a Program

Interpreters run as modules, with the program file as the first argument
(categories: `register_based`, `tape_based`, `stack_based`, `other`), or
through the `esolangs` command:

```bash
python -m esolangs.interpreters.<category>.<language> program.txt
esolangs run <language> program.txt
esolangs list                          # list the supported languages
esolangs generate <language> "Hello"   # print a program that outputs "Hello"
esolangs transpile BF "ASCII art" program.txt  # rewrite between languages
```

Assembly compilers run the same way and write `output.asm`:

```bash
python -m esolangs.compilers.assembly.<language> program.txt
```

### Public API

The package exposes a small typed API:

```python
import esolangs

program = esolangs.generate("Circlefuck", "Hello, World!")
output = esolangs.run("Circlefuck", program)
esolangs.list_languages()
art = esolangs.transpile("brainfuck", "ASCII art", program)
```

### Running the Tests

```bash
just test
```

## Implemented Languages

<details>
<!-- IMPLEMENTED:START -->

<summary>Show all 62 languages</summary>

The full capability matrix (generators, cross-check and boolean support, examples) is in [`docs/languages.md`](docs/languages.md).

### Grid-based Languages

Languages that move a pointer or beam across a 2D grid.

- [2dFish](https://esolangs.org/wiki/2dFish) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/two_d_fish.py))
- [A Painter Ant](https://esolangs.org/wiki/A_Painter_Ant) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/a_painter_ant.py))
- [ArrowQueue](https://esolangs.org/wiki/ArrowQueue) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/arrowqueue.py))
- [Clockwise](https://esolangs.org/wiki/Clockwise) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/clockwise.py))
- [Dig](https://esolangs.org/wiki/Dig) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/dig.py))
- [Dotlang](https://esolangs.org/wiki/Dotlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/dotlang.py))
- [LaserFuck](https://esolangs.org/wiki/LaserFuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/laserfuck.py))
- [WII2D](https://esolangs.org/wiki/WII2D) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/grid_based/wii2d.py))

### Stack-based Languages

Languages that use a stack for data manipulation.

- [3x](https://esolangs.org/wiki/3x) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/three_x.py))
- [BF-PDA](https://esolangs.org/wiki/BF-PDA) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/bf_pda.py))
- [BFStack](https://esolangs.org/wiki/BFStack) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/bfstack.py))
- [Eval](https://esolangs.org/wiki/Eval) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/eval.py))
- [Forþ](https://esolangs.org/wiki/Forþ) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/forth.py))
- [Grapheme](https://esolangs.org/wiki/Grapheme) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/grapheme.py))
- [Modulous](https://esolangs.org/wiki/Modulous) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/modulous.py))
- [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/the_temporary_stack.py))
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
- [ABCDirection](https://esolangs.org/wiki/ABCDirection) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/abcdirection.py))
- [Back](https://esolangs.org/wiki/Back) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/back.py))
- [Basicfuck](https://esolangs.org/wiki/Basicfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/basicfuck.py))
- [BrainIf](https://esolangs.org/wiki/BrainIf) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/brainif.py))
- [Circlefuck](https://esolangs.org/wiki/Circlefuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/circlefuck.py))
- [Dimensional](https://esolangs.org/wiki/Dimensional) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/dimensional.py))
- [EXCON](https://esolangs.org/wiki/EXCON) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/excon.py))
- [Factor](https://esolangs.org/wiki/Factor) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/factor.py))
- [Home Row](https://esolangs.org/wiki/Home_Row) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/home_row.py))
- [Jaune](https://esolangs.org/wiki/Jaune) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/jaune.py))
- [Minifuck](https://esolangs.org/wiki/Minifuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/minifuck.py))
- [Movesum](https://esolangs.org/wiki/Movesum) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/movesum.py))
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

- [%^2^-1](https://esolangs.org/wiki/%^2^-1) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/pct_squared_minus_one.py))
- [AddSubJump](https://esolangs.org/wiki/AddSubJump) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/addsubjump.py))
- [Albabet](https://esolangs.org/wiki/Albabet) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/albabet.py))
- [BIO](https://esolangs.org/wiki/BIO) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/bio.py))
- [Between](https://esolangs.org/wiki/Between) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/between.py))
- [Collatz Multiverse](https://esolangs.org/wiki/Collatz_Multiverse) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/collatz_multiverse.py))
- [Decleq](https://esolangs.org/wiki/Decleq) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/decleq.py))
- [Lightlang](https://esolangs.org/wiki/Lightlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/lightlang.py))
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/minsky_swap.py))
- [MyScript](https://esolangs.org/wiki/MyScript) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/myscript.py))
- [Nevermind](https://esolangs.org/wiki/Nevermind) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/nevermind.py))
- [Polynomial](https://esolangs.org/wiki/Polynomial) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/polynomial.py))
- [Qoibl](https://esolangs.org/wiki/Qoibl) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/qoibl.py))
- [RAM0](https://esolangs.org/wiki/RAM0) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/ram0.py))
- [Sophie](https://esolangs.org/wiki/Sophie) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/sophie.py))
- [huf](https://esolangs.org/wiki/huf) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/huf.py))

### Other Languages

Languages that don't fit into the above categories.

- [Container](https://esolangs.org/wiki/Container) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/container.py))
- [Forbin](https://esolangs.org/wiki/Forbin) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/forbin.py))
- [Lamfunc](https://esolangs.org/wiki/Lamfunc) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/lamfunc.py))
- [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/ztoalc_l.py))

<!-- IMPLEMENTED:END -->

</details>

## Extra Implementations

<details>
<!-- EXTRA:START -->

<summary>Show all 10 implementations</summary>

Implementations written in languages other than Python, used as cross-check references in CI: most generators are round-trip verified against them.  The cross-checks share an exit-code convention mirroring the Python interpreters: 0 = success, 2 = malformed program, 3 = invalid runtime operation.

### RISC-V Assembly Implementations

- [NoComment](https://esolangs.org/wiki/NoComment)

### Rust Implementations

- [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1)
- [2dFish](https://esolangs.org/wiki/2dFish)
- [3x](https://esolangs.org/wiki/3x)
- [Basicfuck](https://esolangs.org/wiki/Basicfuck)
- [bit~](https://esolangs.org/wiki/Bit~)
- [Forþ](https://esolangs.org/wiki/For%C3%BE)
- [LaserFuck](https://esolangs.org/wiki/LaserFuck)
- [Painfuck](https://esolangs.org/wiki/Painfuck)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

<!-- EXTRA:END -->

</details>

## Compilers

<details>
<!-- COMPILERS:START -->

<summary>Show all 8 compilers</summary>

Compilers that translate esoteric languages to other target languages.

### RISC-V Assembly Compilers

- [BF-PDA](https://esolangs.org/wiki/BF-PDA)
- [BFStack](https://esolangs.org/wiki/BFStack)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [Home Row](https://esolangs.org/wiki/Home_Row)
- [Jaune](https://esolangs.org/wiki/Jaune)
- [RAM0](https://esolangs.org/wiki/RAM0)
- [Suffolk](https://esolangs.org/wiki/Suffolk)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

<!-- COMPILERS:END -->

</details>

## Transpilers

Transpilers rewrite a program in one esolang into an equivalent program in another, and are verified end-to-end: the source runs on its interpreter, the translation runs on the target interpreter, and the outputs must agree.

| Source | Direction | Target |
| --- | :---: | --- |
| BF | ⇄ | ASCII art |
| BF | → | Circlefuck |
| Basicfuck | → | BF |
| BF | → | 6-5 |
| BFStack | → | BF |
| BIO | → | BF |
| Decleq | → | S*bleq |
| Dimensional | → | LaserFuck |
| huf | → | BF |

Each transpiler's supported subset and caveats are documented in `esolangs/tools/transpilers.py`.

```bash
esolangs transpile BF "ASCII art" program.bf    # rewrite a program into another esolang
esolangs transpile "ASCII art" BF program.txt   # and back again
esolangs transpile BF Circlefuck program.bf     # auto-sized data region
```

```python
art = esolangs.transpile("brainfuck", "ASCII art", program)  # or via the API
program = esolangs.transpile("ASCII art", "brainfuck", art)
circlefuck = esolangs.transpile(
    "brainfuck", "Circlefuck", program, size=8
)  # explicit size
```

## Tools

Utility programs that work with the esoteric languages.

### Boolean Function Generator

The `boolean.py` module builds a program that computes a truth table
(most-significant input first) in each language with suitable control flow:

```python
from esolangs.tools.boolean import (
    between,
    circlefuck_byte,
    dig,
    laserfuck,
    polynomial,
    taglate,
)

dig("0110", 2)  # 2-input XOR in Dig
between("0110", 2)  # the same truth table in Between
polynomial("0110", 2)  # in Polynomial (up to n = 4)
taglate("0110", 2)  # 2-input XOR in Taglate (up to n = 2)
laserfuck("0110", 2)  # and in LaserFuck (random initial heading)
circlefuck_byte(table, n)  # arbitrary byte-valued functions
```

Most languages in the suite have such a generator (some cover only a
documented subset, like Minifuck's 0-preserving and one-input tables).

### Program Generator

The `generate.py` module builds a program that prints a given string in each
language with a text generator:

```bash
python -m esolangs.tools.generate "Hello, World!"
```

Every generator is also available through `esolangs list` and
`esolangs generate` (see above); run `esolangs list` for the full set.

### Single-Interpreter Install

Want one interpreter without cloning the repo or installing the package?
`scripts/install_one.sh` fetches that language's interpreter and inlines the
shared `io` and `exceptions` modules (plus any interpreter it imports, e.g.
Factor's brainfuck) into one self-contained file:

```bash
curl -fsSL https://raw.githubusercontent.com/bangyen/esolangs/main/scripts/install_one.sh | sh -s brainfuck
python esolangs_brainfuck.py program.txt
```

The language name matches `esolangs list` (e.g. `brainfuck`, `Nevermind`,
`Forþ`).  Factor and Polynomial need `pip install sympy`; the bundled file
notes this.  `scripts/bundle_one.py` does the same from a local checkout:

```bash
python scripts/bundle_one.py Nevermind
```

## Contributing

Contributions are welcome!  If you find a bug or want to add a language,
check the [roadmap](docs/roadmap.md) and [limitations](docs/limitations.md)
first, and read [CONTRIBUTING.md](CONTRIBUTING.md) — including whether the
language is worth adding — before proposing one.  New languages are
registered in `src/esolangs/registry.py`.  Run `just test` (the full local
check: lint, pytest, bandit, cargo, and the Python verify scripts) to verify
a change.

To run that check automatically on every push:

```sh
sh scripts/check_all.sh        # run it once
git config core.hooksPath .githooks   # or run it automatically on every push
```

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.
