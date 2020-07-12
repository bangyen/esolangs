# Esolang Interpreters
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7b8ca283cc2e4a8a9e88f0c9eb29f2a3)](https://www.codacy.com/manual/bangyen99/esolangs?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bangyen/esolangs&amp;utm_campaign=Badge_Grade)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) \
Python implementations of different esoteric programming languages.

## Implemented
-   [Cell-based](https://esolangs.org/wiki/Category:Cell-based)
    -   [ASCII art](https://esolangs.org/wiki/ASCII_art)
    -   [Back](https://esolangs.org/wiki/Back)
    -   [circlefuck](https://esolangs.org/wiki/Circlefuck)
    -   [Dig](https://esolangs.org/wiki/Dig)
    -   [dotlang](https://esolangs.org/wiki/Dotlang)
    -   [DSDLAI](https://esolangs.org/wiki/Dig_straight_down_like_an_idiot)
    -   [Movesum](https://esolangs.org/wiki/Movesum)
    -   [RAM0](https://esolangs.org/wiki/RAM0)

-   [Stack-based](https://esolangs.org/wiki/Category:Stack-based)
    -   [BFStack](https://esolangs.org/wiki/BFStack)
    -   [Eval](https://esolangs.org/wiki/Eval)
    -   [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack)
-   [Finite Automata](https://esolangs.org/wiki/Category:Finite_state_automata)
    -   [Keys](https://esolangs.org/wiki/Keys)

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
