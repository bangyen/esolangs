# Esolang Interpreters
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7b8ca283cc2e4a8a9e88f0c9eb29f2a3)](https://www.codacy.com/manual/bangyen99/esolangs?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bangyen/esolangs&amp;utm_campaign=Badge_Grade)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) \
Python implementations of different esoteric programming languages. Each interpreter works by reading the file specified by the first command line argument.

## Implemented
| Register-based                                     | Register-based (cont.)                               | Tape-based                                         | Stack-based                                                          | Other                                          |
|----------------------------------------------------|------------------------------------------------------|----------------------------------------------------|----------------------------------------------------------------------|------------------------------------------------|
| [Dig](https://esolangs.org/wiki/Dig)               | [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) | [ASCII art](https://esolangs.org/wiki/ASCII_art)   | [BFStack](https://esolangs.org/wiki/BFStack)                         | [Bitdeque](https://esolangs.org/wiki/Bitdeque) |
| [dotlang](https://esolangs.org/wiki/Dotlang)       | [Movesum](https://esolangs.org/wiki/Movesum)         | [Back](https://esolangs.org/wiki/Back)             | [Eval](https://esolangs.org/wiki/Eval)                               | [Keys](https://esolangs.org/wiki/Keys)         |
| [DSDLAI](https://esolangs.org/wiki/DSDLAI)         | [Polynomial](https://esolangs.org/wiki/Polynomial)   | [circlefuck](https://esolangs.org/wiki/Circlefuck) | [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack) |                                                |
| [huf](https://esolangs.org/wiki/Huf)               | [RAM0](https://esolangs.org/wiki/RAM0)               | [Suffolk](https://esolangs.org/wiki/Suffolk)       | [Modulous](https://esolangs.org/wiki/Modulous)                       |                                                |
| [Lightlang](https://esolangs.org/wiki/Lightlang)   | [WII2D](https://esolangs.org/wiki/WII2D)             | [EXCON](https://esolangs.org/wiki/EXCON)           |                                                                      |                                                |
|                                                    |                                                      | [6-5](https://esolangs.org/wiki/6-5)               |                                                                      |                                                |

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
-   For **Suffolk**, although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.
-   The `binary.py` program implements a given boolean function in Dig.
-   The `generate.py` program implements a function in Suffolk which outputs a given string.
