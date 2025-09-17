# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

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
- [Tools](#tools)
- [Notes](#notes)

## About

Esoteric programming languages are designed to be difficult to program in, often as a form of art or humor. This repository provides working interpreters and compilers for a wide variety of these languages, making them accessible for experimentation and learning.

Most interpreters work by reading the file specified by the first command line argument.

## Usage

### Running an Interpreter

```bash
python interpreter.py program.txt
```

### Running a Compiler

```bash
python compiler.py program.txt output.asm
```

### Example: Running a Brainfuck Program

```bash
python tape-based/brainif.py hello_world.bf
```

## Implemented Languages

### Register-based Languages

Languages that use registers to store and manipulate data.

- [BIO](https://esolangs.org/wiki/BIO)
- [Dig](https://esolangs.org/wiki/Dig)
- [dotlang](https://esolangs.org/wiki/Dotlang)
- [DSDLAI](https://esolangs.org/wiki/DSDLAI)
- [huf](https://esolangs.org/wiki/Huf)
- [Lightlang](https://esolangs.org/wiki/Lightlang)
- [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap)
- [Movesum](https://esolangs.org/wiki/Movesum)
- [Polynomial](https://esolangs.org/wiki/Polynomial)
- [Qoibl](https://esolangs.org/wiki/Qoibl)
- [RAM0](https://esolangs.org/wiki/RAM0)
- [Sophie](https://esolangs.org/wiki/Sophie)
- [WII2D](https://esolangs.org/wiki/WII2D)

### Tape-based Languages

Languages that operate on a tape (similar to Turing machines).

- [ASCII art](https://esolangs.org/wiki/ASCII_art)
- [Back](https://esolangs.org/wiki/Back)
- [BrainIf](https://esolangs.org/wiki/BrainIf)
- [circlefuck](https://esolangs.org/wiki/Circlefuck)
- [EXCON](https://esolangs.org/wiki/EXCON)
- [Minifuck](https://esolangs.org/wiki/Minifuck)
- [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN)
- [Suffolk](https://esolangs.org/wiki/Suffolk)
- [6-5](https://esolangs.org/wiki/6-5)

### Stack-based Languages

Languages that use a stack for data manipulation.

- [BFStack](https://esolangs.org/wiki/BFStack)
- [Eval](https://esolangs.org/wiki/Eval)
- [Modulous](https://esolangs.org/wiki/Modulous)
- [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack)

### Other Languages

Languages that don't fit into the above categories.

- [Bitdeque](https://esolangs.org/wiki/Bitdeque)
- [Clockwise](https://esolangs.org/wiki/Clockwise)
- [Container](https://esolangs.org/wiki/Container)
- [Keys](https://esolangs.org/wiki/Keys)
- [Nevermind](https://esolangs.org/wiki/Nevermind)
- [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L)

## Extra Implementations

Implementations written in languages other than Python.

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

### Ruby Implementations

- [bit~](https://esolangs.org/wiki/Bit~)
- [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four)
- [Unsquare](https://esolangs.org/wiki/Unsquare)
- [3x](https://esolangs.org/wiki/3x)

### Rust Implementations

- [LaserFuck](https://esolangs.org/wiki/LaserFuck)
- [Unsquare](https://esolangs.org/wiki/Unsquare)

## Compilers

Compilers that translate esoteric languages to other target languages.

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

## Tools

Utility programs that work with the esoteric languages.

### Binary Function Generator

The `binary.py` program implements a given boolean function in Dig.

```bash
python miscellaneous/binary.py
```

### Program Generator

The `generate.py` program outputs programs which output a given string in different languages.

**Supported languages:**
- BFStack
- BrainIf
- Container
- Forþ (Forth)
- LaserFuck
- Painfuck
- Suffolk
- 123
- %^2^-1 (Magnitude)

```bash
python miscellaneous/generate.py "Hello, World!"
```

## Notes

Important information about specific language implementations.

### Known Issues

- **circlefuck**: The `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.

- **dotlang**: The interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.

### Usage Notes

- **Jaune**: Only one character can be input at a time.

- **Suffolk**: Although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.

- **123**: Input is given at the end of the program. The two are separated by a single `|`.

## Contributing

Contributions are welcome! If you find bugs or want to add new language implementations, please feel free to submit issues or pull requests.

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.
