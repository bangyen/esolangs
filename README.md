# Esolang Interpreters
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7b8ca283cc2e4a8a9e88f0c9eb29f2a3)](https://www.codacy.com/manual/bangyen99/esolangs?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bangyen/esolangs&amp;utm_campaign=Badge_Grade)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) \
Python implementations of different esoteric programming languages. Each interpreter works by reading the file specified by the first command line argument.

## Implemented
| Register-based                                       | Register-based (cont.)                             | Tape-based                                         | Tape-based (cont.)                                                 | Stack-based                                                          | Other                                            |
|------------------------------------------------------|----------------------------------------------------|----------------------------------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|--------------------------------------------------|
| [BIO](https://esolangs.org/wiki/BIO)                 | [Movesum](https://esolangs.org/wiki/Movesum)       | [ASCII art](https://esolangs.org/wiki/ASCII_art)   | [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN) | [BFStack](https://esolangs.org/wiki/BFStack)                         | [Bitdeque](https://esolangs.org/wiki/Bitdeque)   |
| [Dig](https://esolangs.org/wiki/Dig)                 | [Polynomial](https://esolangs.org/wiki/Polynomial) | [Back](https://esolangs.org/wiki/Back)             | [Suffolk](https://esolangs.org/wiki/Suffolk)                       | [Eval](https://esolangs.org/wiki/Eval)                               | [Clockwise](https://esolangs.org/wiki/Clockwise) |
| [dotlang](https://esolangs.org/wiki/Dotlang)         | [Qoibl](https://esolangs.org/wiki/Qoibl)           | [BrainIf](https://esolangs.org/wiki/BrainIf)       | [6-5](https://esolangs.org/wiki/6-5)                               | [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack) | [Container](https://esolangs.org/wiki/Container) |
| [DSDLAI](https://esolangs.org/wiki/DSDLAI)           | [RAM0](https://esolangs.org/wiki/RAM0)             | [circlefuck](https://esolangs.org/wiki/Circlefuck) |                                                                    | [Modulous](https://esolangs.org/wiki/Modulous)                       | [Keys](https://esolangs.org/wiki/Keys)           |
| [huf](https://esolangs.org/wiki/Huf)                 | [Sophie](https://esolangs.org/wiki/Sophie)         | [EXCON](https://esolangs.org/wiki/EXCON)           |                                                                    |                                                                      | [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L)   |
| [Lightlang](https://esolangs.org/wiki/Lightlang)     | [WII2D](https://esolangs.org/wiki/WII2D)           | [Minifuck](https://esolangs.org/wiki/Minifuck)     |                                                                    |                                                                      | [Nevermind](https://esolangs.org/wiki/Nevermind) |
| [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) |                                                    |                                                    |                                                                    |                                                                      |                                                  |

## Extra
Implementations written in languages other than Python.

| Lean                                                                 | x86 Assembly                                               | x86 Assembly (cont.)                                       | Ruby                                                                 | C++                                              | R                                        |
|----------------------------------------------------------------------|------------------------------------------------------------|------------------------------------------------------------|----------------------------------------------------------------------|--------------------------------------------------|------------------------------------------|
| [Albabet](https://esolangs.org/wiki/Albabet)                         | [Brainpocalypse](https://esolangs.org/wiki/Brainpocalypse) | [2 Bits, 1 Byte](https://esolangs.org/wiki/2_Bits,_1_Byte) | [bit~](https://esolangs.org/wiki/Bit~)                               | [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1) | [EXCON](https://esolangs.org/wiki/EXCON) |
| [BF-PDA](https://esolangs.org/wiki/BF-PDA)                           | [NoComment](https://esolangs.org/wiki/NoComment)           |                                                            | [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four) |                                                  |                                          |
| [EXCON](https://esolangs.org/wiki/EXCON)                             | [Stun Step](https://esolangs.org/wiki/Stun_Step)           |                                                            | [Unsquare](https://esolangs.org/wiki/Unsquare)                       |                                                  |                                          |
| [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four) | [123](https://esolangs.org/wiki/123)                       |                                                            | [3x](https://esolangs.org/wiki/3x)                                   |                                                  |                                          |

## Compilers
Sorted by target language.

| C                                            | x86 Assembly                                   | x86 Assembly (cont.)                           |
|----------------------------------------------|------------------------------------------------|------------------------------------------------|
| [BF-PDA](https://esolangs.org/wiki/BF-PDA)   | [BFStack](https://esolangs.org/wiki/BFStack)   | [Unsquare](https://esolangs.org/wiki/Unsquare) |
| [BFStack](https://esolangs.org/wiki/BFStack) | [Home Row](https://esolangs.org/wiki/Home_Row) |                                                |
| [EXCON](https://esolangs.org/wiki/EXCON)     | [Jaune](https://esolangs.org/wiki/Jaune)       |                                                |
| [RAM0](https://esolangs.org/wiki/RAM0)       | [Suffolk](https://esolangs.org/wiki/Suffolk)   |                                                |

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
-   For **Jaune**, only one character can be input at a time.
-   For **Suffolk**, although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.
-   For **123**, input is given at the end of the program. The two are separated by a single `|`.

## Miscellaneous
-   The `binary.py` program implements a given boolean function in Dig.

-   The `generate.py` program implements a function in different languages which output a given string. The supported languages are as follows:
    -   BFStack
    -   BrainIf
    -   Container
    -   Suffolk
    -   123
