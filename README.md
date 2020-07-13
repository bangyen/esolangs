# Esolang Interpreters
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7b8ca283cc2e4a8a9e88f0c9eb29f2a3)](https://www.codacy.com/manual/bangyen99/esolangs?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bangyen/esolangs&amp;utm_campaign=Badge_Grade)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) \
Python implementations of different esoteric programming languages.

## Implemented
| Register-Based                                     | Tape-based                                         | Other                                                |
|----------------------------------------------------|----------------------------------------------------|------------------------------------------------------|
| [Dig](https://esolangs.org/wiki/Dig)               | [ASCII art](https://esolangs.org/wiki/ASCII_art)   | [BFStack](https://esolangs.org/wiki/BFStack)         |
| [dotlang](https://esolangs.org/wiki/Dotlang)       | [Back](https://esolangs.org/wiki/Back)             | [Bitdeque](https://esolangs.org/wiki/Bitdeque)       |
| [DSDLAI](https://esolangs.org/wiki/DSDLAI)         | [circlefuck](https://esolangs.org/wiki/Circlefuck) | [Eval](https://esolangs.org/wiki/Eval)               |
| [huf](https://github.com/Charmaster16/huf)         | [Suffolk](https://esolangs.org/wiki/Suffolk)       | [Keys](https://esolangs.org/wiki/Keys)               |
| [Lightlang](https://esolangs.org/wiki/Lightlang)   |                                                    | [TTS](https://esolangs.org/wiki/The_Temporary_Stack) |
| [Movesum](https://esolangs.org/wiki/Movesum)       |                                                    |                                                      |
| [Polynomial](https://esolangs.org/wiki/Polynomial) |                                                    |                                                      |
| [RAM0](https://esolangs.org/wiki/RAM0)             |                                                    |                                                      |

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
-   For **Suffolk**, although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.
