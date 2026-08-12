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
- [Roadmap](docs/ROADMAP.md)
- [Limitations](docs/limitations.md)
- [Notes](#notes)

## About

Esoteric programming languages are designed to be difficult to program in, often as a form of art or humor. This repository provides working interpreters and compilers for a wide variety of these languages, making them accessible for experimentation and learning.

Most interpreters work by reading the file specified by the first command line argument.

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

- [BIO](https://esolangs.org/wiki/BIO)
- [DSDLAI](https://esolangs.org/wiki/DSDLAI)
- [Dig](https://esolangs.org/wiki/Dig)
- [Dotlang](https://esolangs.org/wiki/Dotlang)
- [Lightlang](https://esolangs.org/wiki/Lightlang)
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap)
- [Movesum](https://esolangs.org/wiki/Movesum)
- [Polynomial](https://esolangs.org/wiki/Polynomial)
- [Qoibl](https://esolangs.org/wiki/Qoibl)
- [RAM0](https://esolangs.org/wiki/RAM0)
- [Sophie](https://esolangs.org/wiki/Sophie)
- [WII2D](https://esolangs.org/wiki/WII2D)
- [Huf](https://esolangs.org/wiki/Huf)

### Tape-based Languages

Languages that operate on a tape (similar to Turing machines).

- [6-5](https://esolangs.org/wiki/6-5)
- [ASCII art](https://esolangs.org/wiki/ASCII_art)
- [Brainfuck](https://esolangs.org/wiki/Brainfuck)
- [Back](https://esolangs.org/wiki/Back)
- [BrainIf](https://esolangs.org/wiki/BrainIf)
- [Circlefuck](https://esolangs.org/wiki/Circlefuck)
- [Dimensional](https://esolangs.org/wiki/Dimensional)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN)
- [Minifuck](https://esolangs.org/wiki/Minifuck)
- [NoComment](https://esolangs.org/wiki/NoComment)
- [S*bleq](https://esolangs.org/wiki/S*bleq)
- [Suffolk](https://esolangs.org/wiki/Suffolk)

### Stack-based Languages

Languages that use a stack for data manipulation.

- [BFStack](https://esolangs.org/wiki/BFStack)
- [Eval](https://esolangs.org/wiki/Eval)
- [Modulous](https://esolangs.org/wiki/Modulous)
- [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack)

### Other Languages

Languages that don't fit into the above categories.

- [ArrowQueue](https://esolangs.org/wiki/ArrowQueue)
- [Between](https://esolangs.org/wiki/Between)
- [Bitdeque](https://esolangs.org/wiki/Bitdeque)
- [Clockwise](https://esolangs.org/wiki/Clockwise)
- [Container](https://esolangs.org/wiki/Container)
- [Keys](https://esolangs.org/wiki/Keys)
- [Nevermind](https://esolangs.org/wiki/Nevermind)
- [Taglate](https://esolangs.org/wiki/Taglate)
- [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L)

<!-- IMPLEMENTED:END -->

</details>

## Extra Implementations

<details>
<summary>Show all</summary>

Implementations written in languages other than Python.

Note: these are cross-check implementations written in this repository (not
upstream language-author code).  The generators for Forþ, Painfuck,
Dimensional, 2dFish, %^2^-1, Basicfuck, LaserFuck, Unsquare, bit~, 3x, EXCON,
123, and NoComment are round-trip verified against the native implementations
(C++, Rust, R, Ruby, or x86/RISC-V assembly) in CI, and 3x's boolean
generator (n = 1..3) is verified the same way.  Because the Python
interpreters and their native cross-checks share an author, the round-trip
verifies transcription fidelity rather than an independent reading of the
spec; see `docs/ROADMAP.md` for where a truly independent reference matters.

The cross-checks share an exit-code convention mirroring the Python
interpreters' error split: 0 = success, 2 = malformed program (the
`ValueError` analog), 3 = invalid runtime operation (the `HaltError`
analog).  Exit code 1 is reserved for unclassified failures that do not
map to either category.  Languages that cannot express distinct codes
(e.g. Rust's panic) document their behavior in the file header instead.

The in-package interpreters for EXCON and LaserFuck are additionally
differential-tested against their native cross-checks on a full-surface
corpus (`scripts/verify_differential.py`), and the Rust implementations
(`extra/rust`) ship `cargo test` unit suites covering the individual
instructions.

The remaining extra implementations (Kak, Trash, Number Seventy-Four, 2 Bits
1 Byte, Brainpocalypse, Stun Step, Albabet, BF-PDA) are kept as
self-contained interpreters but do not have round-trip-verified generators:
their output classes are too narrow for text (e.g. Kak prints only tape bits,
Trash only primes, Number Seventy-Four only `0`/`1`/`H`), or they lack a
file-based I/O protocol (2 Bits 1 Byte, Brainpocalypse, Stun Step).

### C++ Implementations

- [Basicfuck](https://esolangs.org/wiki/Basicfuck)
- [Dimensional](https://esolangs.org/wiki/Dimensional)
- [Forþ](https://esolangs.org/wiki/For%C3%BE)
- [Kak](https://esolangs.org/wiki/Kak)
- [Painfuck](https://esolangs.org/wiki/Painfuck)
- [Trash](https://esolangs.org/wiki/Trash)
- [2dFish](https://esolangs.org/wiki/2dFish)
- [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1)

### x86 Assembly Implementations

- [Brainpocalypse](https://esolangs.org/wiki/Brainpocalypse)
- [NoComment](https://esolangs.org/wiki/NoComment)
- [Stun Step](https://esolangs.org/wiki/Stun_Step)
- [123](https://esolangs.org/wiki/123)
- [2 Bits, 1 Byte](https://esolangs.org/wiki/2_Bits,_1_Byte)

### Lean Implementations

- [Albabet](https://esolangs.org/wiki/Albabet)
- [BF-PDA](https://esolangs.org/wiki/BF-PDA)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four)

### R Implementations

- [EXCON](https://esolangs.org/wiki/EXCON)

### Ruby Implementations

- [bit~](https://esolangs.org/wiki/Bit~)
- [3x](https://esolangs.org/wiki/3x)
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

### Rust Implementations

- [LaserFuck](https://esolangs.org/wiki/LaserFuck)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

</details>

## Compilers

<details>
<summary>Show all</summary>

Compilers that translate esoteric languages to other target languages.

<!-- COMPILERS:START -->

### x86 Assembly Compilers

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

- [BF](https://esolangs.org/wiki/Brainfuck) <-> [ASCII art](https://esolangs.org/wiki/ASCII_art): each brainfuck command becomes an art block, and vice versa.
- [BF](https://esolangs.org/wiki/Brainfuck) -> [CircleFuck](https://esolangs.org/wiki/Circlefuck): sets up a clean data region inside the program-as-tape and emits the brainfuck commands unchanged. The data region is sized automatically from the program (the smallest bound that contains its data pointer), so `transpile("BF", "CircleFuck", program)` just works for programs with bounded, non-drifting loops; pass `size` explicitly to cover programs that stay within `[0, size)`.
- [NoComment](https://esolangs.org/wiki/NoComment) -> [BF](https://esolangs.org/wiki/Brainfuck): the transpiler handles the c/i/o subset of NoComment, mapping each to brainfuck (`c` = `[-]`, `i` = `+`, `o` = `.`). The full language (a tape, a stack, and s/b jumps) is implemented by the interpreter and the assembly cross-check but not by this transpiler.
- [BFStack](https://esolangs.org/wiki/BFStack) -> [BF](https://esolangs.org/wiki/Brainfuck): BFStack is a stack modelled on brainfuck's tape, so the transpiler is a table lookup (`>` pushes a cell, `<` pops and clears it (`[-]<`), `,` reads and pushes (`>,`)).
- [BIO](https://esolangs.org/wiki/BIO) -> [BF](https://esolangs.org/wiki/Brainfuck): BIO's three registers live in the first three brainfuck cells; each command moves the pointer to its register, acts, and returns to cell 0. Registers must stay within `[0, 255]`.
- [huf](https://esolangs.org/wiki/Huf) -> [BF](https://esolangs.org/wiki/Brainfuck): huf's `num`/`mul` live in cells 0 and 1; `!` multiplies by copying `num` to a temp cell that each loop iteration adds to `num` and refreshes from a running accumulator.

```bash
esolangs transpile BF "ASCII art" program.bf    # print the art
esolangs transpile "ASCII art" BF program.txt   # print the brainfuck
esolangs transpile BF CircleFuck program.bf     # print the CircleFuck
esolangs transpile NoComment BF program.nocom   # print the brainfuck
esolangs transpile BFStack BF program.bstk      # print the brainfuck
esolangs transpile BIO BF program.bio           # print the brainfuck
esolangs transpile huf BF program.huf           # print the brainfuck
```

```python
art = esolangs.transpile("BF", "ASCII art", program)          # or via the API
program = esolangs.transpile("ASCII art", "BF", art)
circlefuck = esolangs.transpile("BF", "CircleFuck", program)  # auto-sized
circlefuck = esolangs.transpile("BF", "CircleFuck", program, size=8)
bf_program = esolangs.transpile("NoComment", "BF", program)
```

## Tools

Utility programs that work with the esoteric languages.

### Boolean Function Generator

The `boolean.py` module builds programs that compute a boolean function from a truth table (most-significant input first) for languages with suitable control flow:

```python
from esolangs.tools.boolean import ascii_art, between, bfstack, brainif, circlefuck, dig, laserfuck, modulous, nevermind, polynomial, qoibl, six_five, sophie, taglate

dig("0110", 2)            # 2-input XOR in Dig
sophie("0110", 2)         # the same truth table in Sophie
between("0110", 2)        # and in Between
modulous("0110", 2)       # and in Modulous
brainif("0110", 2)        # and in BrainIf
nevermind("0110", 2)      # and in Nevermind
circlefuck("0110", 2)     # and in CircleFuck
circlefuck_byte(table)    # arbitrary byte-valued functions
ascii_art("0110", 2)      # and in ASCII art
six_five("0110", 2)       # and in 6-5
qoibl("0110", 2)          # and in Qoibl
polynomial("0110", 2)     # and in Polynomial (up to n = 4)
taglate("0110", 2)        # 2-input XOR in Taglate (up to n = 2)
bfstack("0110", 2)        # and in BFStack
laserfuck("0110", 2)      # and in LaserFuck (random initial heading)
```

### Program Generator

The `generate.py` program outputs programs which output a given string in different languages:

```bash
python -m esolangs.tools.generate "Hello, World!"
```

Every generator is also available through `esolangs list` and `esolangs generate` (see above); run `esolangs list` for the full set.

## Notes

Important information about specific language implementations.

### Known Issues

- **circlefuck**: The `narcissist` program doesn't work — it hangs regardless of input. The `ThisIsAQuine` quine also outputs its source incorrectly; the `{>[.>]@` quine works correctly.

- **dotlang**: The interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.

### Usage Notes

- **Jaune**: Only one character can be input at a time.

- **Suffolk**: Although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.

- **123**: Input is given at the end of the program. The two are separated by a single `|`.

## Contributing

Contributions are welcome! If you find bugs or want to add new language implementations, please feel free to submit issues or pull requests.

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.
