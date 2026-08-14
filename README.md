# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Coverage](coverage-badge.svg)](coverage-badge.svg)

A comprehensive collection of interpreters and compilers for esoteric programming languages (esolangs). This repository contains implementations of various esoteric languages, ranging from classic stack-based languages to modern register-based systems.

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

## About

Esoteric programming languages are designed to be difficult to program in, often as a form of art or humor. This repository provides working interpreters and compilers for a wide variety of these languages, making them accessible for experimentation and learning.

Most interpreters work by reading the file specified by the first command line argument.

Planned work is tracked in [`docs/roadmap.md`](docs/roadmap.md); documented
limitations and ruled-out ideas live in [`docs/limitations.md`](docs/limitations.md).

## Usage

### Installation

First, clone the repository and install the project in editable mode with development dependencies:

```bash
git clone https://github.com/bangyen/esolangs.git
cd esolangs
just install-dev
```

### Running Tests

You can run the test suite using pytest to verify your installation or check your modifications:

```bash
just test
```

### Running an Interpreter

You can run interpreters as Python modules from the command line:

```bash
python -m esolangs.interpreters.<category>.<language> program.txt
```

Where `<category>` is one of `register_based`, `tape_based`, `stack_based`, or `other`.

### Running a Compiler

Similarly, you can run assembly compilers as Python modules:

```bash
python -m esolangs.compilers.assembly.<language> program.txt
```

This writes the generated assembly to `output.asm`.

### Example: Running a BrainIf Program

```bash
python -m esolangs.interpreters.tape_based.brainif hello_world.bf
```

### The `esolangs` Command

The installed `esolangs` command provides friendly subcommands:

```bash
esolangs list                          # list the supported languages
esolangs generate CircleFuck "Hello"   # print a program that outputs "Hello"
esolangs run CircleFuck program.txt    # run a program through its interpreter
esolangs transpile BF "ASCII art" hello.bf   # rewrite a program as ASCII art
```

## Public API

The package exposes a small typed API:

```python
import esolangs

program = esolangs.generate("CircleFuck", "Hello, World!")
output = esolangs.run("CircleFuck", program)
esolangs.list_languages()   # every supported language
art = esolangs.transpile("BF", "ASCII art", program)   # rewrite between languages
```

## Implemented Languages

<details>
<summary>Show all</summary>

<!-- IMPLEMENTED:START -->

### Register-based Languages

Languages that use registers to store and manipulate data.

- [%^2^-1](https://esolangs.org/wiki/%^2^-1) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/%^2^-1.py))
- [AddSubJump](https://esolangs.org/wiki/AddSubJump) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/add_sub_jump.py))
- [BIO](https://esolangs.org/wiki/BIO) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/bio.py))
- [Collatz Multiverse](https://esolangs.org/wiki/Collatz_Multiverse) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/collatz_multiverse.py))
- [DSDLAI](https://esolangs.org/wiki/DSDLAI) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/dsdlai.py))
- [Dig](https://esolangs.org/wiki/Dig) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/dig.py))
- [Dotlang](https://esolangs.org/wiki/Dotlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/dotlang.py))
- [Lightlang](https://esolangs.org/wiki/Lightlang) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/lightlang.py))
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/minsky-swap.py))
- [Movesum](https://esolangs.org/wiki/Movesum) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/movesum.py))
- [Polynomial](https://esolangs.org/wiki/Polynomial) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/polynomial.py))
- [Qoibl](https://esolangs.org/wiki/Qoibl) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/qoibl.py))
- [RAM0](https://esolangs.org/wiki/RAM0) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/RAM0.py))
- [Sophie](https://esolangs.org/wiki/Sophie) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/sophie.py))
- [WII2D](https://esolangs.org/wiki/WII2D) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/WII2D.py))
- [huf](https://esolangs.org/wiki/huf) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/register_based/huf.py))

### Tape-based Languages

Languages that operate on a tape (similar to Turing machines).

- [123](https://esolangs.org/wiki/123) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/123.py))
- [3D Brainfuck](https://esolangs.org/wiki/3D_Brainfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/three_d_bf.py))
- [6-5](https://esolangs.org/wiki/6-5) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/6-5.py))
- [ABCDirection](https://esolangs.org/wiki/ABCDirection) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/abcdirection.py))
- [ASCII art](https://esolangs.org/wiki/ASCII_art) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/ascii-art.py))
- [brainfuck](https://esolangs.org/wiki/brainfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/bf.py))
- [BF-PDA](https://esolangs.org/wiki/BF-PDA) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/bfpda.py))
- [Back](https://esolangs.org/wiki/Back) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/back.py))
- [Basicfuck](https://esolangs.org/wiki/Basicfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/basicfuck.py))
- [BrainIf](https://esolangs.org/wiki/BrainIf) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/brainif.py))
- [Brainpocalypse](https://esolangs.org/wiki/Brainpocalypse) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/brainpocalypse.py))
- [Circlefuck](https://esolangs.org/wiki/Circlefuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/circlefuck.py))
- [Dimensional](https://esolangs.org/wiki/Dimensional) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/dimensional.py))
- [EXCON](https://esolangs.org/wiki/EXCON) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/excon.py))
- [Factor](https://esolangs.org/wiki/Factor) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/factor.py))
- [Kak](https://esolangs.org/wiki/Kak) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/kak.py))
- [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/mammalian.py))
- [Minifuck](https://esolangs.org/wiki/Minifuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/minifuck.py))
- [NoComment](https://esolangs.org/wiki/NoComment) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/nocomment.py))
- [Painfuck](https://esolangs.org/wiki/Painfuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/painfuck.py))
- [S*bleq](https://esolangs.org/wiki/S*bleq) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/sbleq.py))
- [Stun Step](https://esolangs.org/wiki/Stun_Step) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/stun_step.py))
- [Suffolk](https://esolangs.org/wiki/Suffolk) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/tape_based/suffolk.py))

### Stack-based Languages

Languages that use a stack for data manipulation.

- [BFStack](https://esolangs.org/wiki/BFStack) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/bfstack.py))
- [Eval](https://esolangs.org/wiki/Eval) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/eval.py))
- [Forþ](https://esolangs.org/wiki/Forþ) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/forth.py))
- [Modulous](https://esolangs.org/wiki/Modulous) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/modulous.py))
- [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/temporary.py))
- [Unsquare](https://esolangs.org/wiki/Unsquare) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/stack_based/unsquare.py))

### Other Languages

Languages that don't fit into the above categories.

- [2 Bits, 1 Byte](https://esolangs.org/wiki/2_Bits,_1_Byte) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/two_bits_one_byte.py))
- [2dFish](https://esolangs.org/wiki/2dFish) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/2dfish.py))
- [3x](https://esolangs.org/wiki/3x) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/three_x.py))
- [A Painter Ant](https://esolangs.org/wiki/A_Painter_Ant) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/a_painter_ant.py))
- [Albabet](https://esolangs.org/wiki/Albabet) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/albabet.py))
- [ArrowQueue](https://esolangs.org/wiki/ArrowQueue) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/arrowqueue.py))
- [Between](https://esolangs.org/wiki/Between) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/between.py))
- [Bitdeque](https://esolangs.org/wiki/Bitdeque) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/bitdeque.py))
- [Clockwise](https://esolangs.org/wiki/Clockwise) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/clockwise.py))
- [Container](https://esolangs.org/wiki/Container) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/container.py))
- [Keys](https://esolangs.org/wiki/Keys) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/keys.py))
- [LaserFuck](https://esolangs.org/wiki/LaserFuck) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/laserfuck.py))
- [Nevermind](https://esolangs.org/wiki/Nevermind) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/nevermind.py))
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/seventy_four.py))
- [Taglate](https://esolangs.org/wiki/Taglate) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/taglate.py))
- [Trash](https://esolangs.org/wiki/Trash) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/trash.py))
- [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/ztoalc.py))
- [bit~](https://esolangs.org/wiki/bit~) ([code](https://github.com/bangyen/esolangs/blob/main/src/esolangs/interpreters/other/bit_tilde.py))

<!-- IMPLEMENTED:END -->

</details>

## Extra Implementations

<details>
<summary>Show all</summary>

Implementations written in languages other than Python.

Note: these are cross-check implementations written in this repository (not
upstream language-author code).  Most generators are round-trip verified
against these native references in CI; Kak, Trash, Number Seventy-Four, 2
Bits 1 Byte, Brainpocalypse, Stun Step, Albabet, and BF-PDA have output
classes too narrow for a text generator, but each now has an in-package
Python interpreter that is differentially verified against its native
reference (and AlbaBet gained a text generator).  The cross-checks share an
exit-code convention mirroring the Python interpreters: 0 = success, 2 =
malformed program, 3 = invalid runtime operation.

<!-- EXTRA:START -->

### RISC-V Assembly Implementations

- [123](https://esolangs.org/wiki/123)
- [2 Bits, 1 Byte](https://esolangs.org/wiki/2_Bits,_1_Byte)
- [Brainpocalypse](https://esolangs.org/wiki/Brainpocalypse)
- [NoComment](https://esolangs.org/wiki/NoComment)
- [Stun Step](https://esolangs.org/wiki/Stun_Step)

### Lean Implementations

- [Albabet](https://esolangs.org/wiki/Albabet)
- [BF-PDA](https://esolangs.org/wiki/BF-PDA)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four)

### Rust Implementations

- [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1)
- [2dFish](https://esolangs.org/wiki/2dFish)
- [3x](https://esolangs.org/wiki/3x)
- [Basicfuck](https://esolangs.org/wiki/Basicfuck)
- [bit~](https://esolangs.org/wiki/Bit~)
- [Forþ](https://esolangs.org/wiki/For%C3%BE)
- [Kak](https://esolangs.org/wiki/Kak)
- [LaserFuck](https://esolangs.org/wiki/LaserFuck)
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four)
- [Painfuck](https://esolangs.org/wiki/Painfuck)
- [Trash](https://esolangs.org/wiki/Trash)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

<!-- EXTRA:END -->

</details>

## Compilers

<details>
<summary>Show all</summary>

Compilers that translate esoteric languages to other target languages.

<!-- COMPILERS:START -->

### RISC-V Assembly Compilers

- [BFStack](https://esolangs.org/wiki/BFStack)
- [Home Row](https://esolangs.org/wiki/Home_Row)
- [Jaune](https://esolangs.org/wiki/Jaune)
- [Suffolk](https://esolangs.org/wiki/Suffolk)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

### C Compilers

- [BF-PDA](https://esolangs.org/wiki/BF-PDA)
- [BFStack](https://esolangs.org/wiki/BFStack)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [RAM0](https://esolangs.org/wiki/RAM0)

<!-- COMPILERS:END -->

</details>

## Transpilers

Transpilers rewrite a program in one esolang into an equivalent program in another, and are verified end-to-end: the source runs on its interpreter, the translation runs on the target interpreter, and the outputs must agree.

- BF <-> ASCII art
- BF -> CircleFuck
- NoComment -> BF
- BFStack -> BF
- BIO -> BF
- huf -> BF

Each transpiler's supported subset and caveats are documented in `esolangs/tools/transpilers.py`.

```bash
esolangs transpile BF "ASCII art" program.bf    # rewrite a program into another esolang
esolangs transpile "ASCII art" BF program.txt   # and back again
esolangs transpile BF CircleFuck program.bf     # auto-sized data region
```

```python
art = esolangs.transpile("BF", "ASCII art", program)   # or via the API
program = esolangs.transpile("ASCII art", "BF", art)
circlefuck = esolangs.transpile("BF", "CircleFuck", program, size=8)  # explicit size
```

## Tools

Utility programs that work with the esoteric languages.

### Boolean Function Generator

The `boolean.py` module builds programs that compute a boolean function from a truth table (most-significant input first) for languages with suitable control flow:

```python
from esolangs.tools.boolean import between, circlefuck_byte, dig, laserfuck, polynomial, taglate

dig("0110", 2)            # 2-input XOR in Dig
between("0110", 2)        # the same truth table in Between
polynomial("0110", 2)     # in Polynomial (up to n = 4)
taglate("0110", 2)        # 2-input XOR in Taglate (up to n = 2)
laserfuck("0110", 2)      # and in LaserFuck (random initial heading)
circlefuck_byte(table, n)  # arbitrary byte-valued functions
```

Most languages in the suite have a matching generator; the rest differ only in the function name.

### Program Generator

The `generate.py` program outputs programs which output a given string in different languages:

```bash
python -m esolangs.tools.generate "Hello, World!"
```

Every generator is also available through `esolangs list` and `esolangs generate` (see above); run `esolangs list` for the full set.

## Contributing

Contributions are welcome! If you find bugs or want to add new language implementations, please feel free to submit issues or pull requests.

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.
