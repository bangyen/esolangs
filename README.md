# Esolang Interpreters
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/bangyen/esolangs.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/bangyen/esolangs/context:python)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) \
Python implementations of different esoteric programming languages. Each interpreter works by reading the file specified by the first command line argument.

## Implemented
| Register-based                                       | Register-based (cont.)                             | Tape-based                                         | Tape-based (cont.)                                                 | Stack-based                                                          | Other                                            |
|------------------------------------------------------|----------------------------------------------------|----------------------------------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|--------------------------------------------------|
| [BIO](https://esolangs.org/wiki/BIO)                 | [Movesum](https://esolangs.org/wiki/Movesum)       | [ASCII art](https://esolangs.org/wiki/ASCII_art)   | [SLOW ACV MAMMALIAN](https://esolangs.org/wiki/SLOW_ACV_MAMMALIAN) | [BFStack](https://esolangs.org/wiki/BFStack)                         | [Bitdeque](https://esolangs.org/wiki/Bitdeque)   |
| [Dig](https://esolangs.org/wiki/Dig)                 | [Polynomial](https://esolangs.org/wiki/Polynomial) | [Back](https://esolangs.org/wiki/Back)             | [Suffolk](https://esolangs.org/wiki/Suffolk)                       | [Eval](https://esolangs.org/wiki/Eval)                               | [Clockwise](https://esolangs.org/wiki/Clockwise) |
| [dotlang](https://esolangs.org/wiki/Dotlang)         | [Qoibl](https://esolangs.org/wiki/Qoibl)           | [BrainIf](https://esolangs.org/wiki/BrainIf)       | [6-5](https://esolangs.org/wiki/6-5)                               | [Modulous](https://esolangs.org/wiki/Modulous)                       | [Container](https://esolangs.org/wiki/Container) |
| [DSDLAI](https://esolangs.org/wiki/DSDLAI)           | [RAM0](https://esolangs.org/wiki/RAM0)             | [circlefuck](https://esolangs.org/wiki/Circlefuck) |                                                                    | [The Temporary Stack](https://esolangs.org/wiki/The_Temporary_Stack) | [Keys](https://esolangs.org/wiki/Keys)           |
| [huf](https://esolangs.org/wiki/Huf)                 | [Sophie](https://esolangs.org/wiki/Sophie)         | [EXCON](https://esolangs.org/wiki/EXCON)           |                                                                    |                                                                      | [Nevermind](https://esolangs.org/wiki/Nevermind) |
| [Lightlang](https://esolangs.org/wiki/Lightlang)     | [WII2D](https://esolangs.org/wiki/WII2D)           | [Minifuck](https://esolangs.org/wiki/Minifuck)     |                                                                    |                                                                      | [ZTOALC L](https://esolangs.org/wiki/ZTOALC_L)   |
| [Minsky Swap](https://esolangs.org/wiki/Minsky_Swap) |                                                    |                                                    |                                                                    |                                                                      |                                                  |

## Extra
Implementations written in languages other than Python.

| C++                                                  | C++ (cont.)                                 | x86 Assembly                                               | Lean                                                                 | Ruby                                                                 | R                                        |
|------------------------------------------------------|---------------------------------------------|------------------------------------------------------------|----------------------------------------------------------------------|----------------------------------------------------------------------|------------------------------------------|
| [Dimensional](https://esolangs.org/wiki/Dimensional) | [Forþ](https://esolangs.org/wiki/For%C3%BE) | [Brainpocalypse](https://esolangs.org/wiki/Brainpocalypse) | [Albabet](https://esolangs.org/wiki/Albabet)                         | [bit~](https://esolangs.org/wiki/Bit~)                               | [EXCON](https://esolangs.org/wiki/EXCON) |
| [Painfuck](https://esolangs.org/wiki/Painfuck)       |                                             | [NoComment](https://esolangs.org/wiki/NoComment)           | [BF-PDA](https://esolangs.org/wiki/BF-PDA)                           | [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four) |                                          |
| [Trash](https://esolangs.org/wiki/Trash)             |                                             | [Stun Step](https://esolangs.org/wiki/Stun_Step)           | [EXCON](https://esolangs.org/wiki/EXCON)                             | [Unsquare](https://esolangs.org/wiki/Unsquare)                       |                                          |
| [2dFish](https://esolangs.org/wiki/2dFish)           |                                             | [123](https://esolangs.org/wiki/123)                       | [Number Seventy-Four](https://esolangs.org/wiki/Number_Seventy-Four) | [3x](https://esolangs.org/wiki/3x)                                   |                                          |
| [%^2^-1](https://esolangs.org/wiki/%25%5E2%5E-1)     |                                             | [2 Bits, 1 Byte](https://esolangs.org/wiki/2_Bits,_1_Byte) |                                                                      |                                                                      |                                          |

## Compilers
Sorted by target language.

| x86 Assembly                                   | C                                            |
|------------------------------------------------|----------------------------------------------|
| [BFStack](https://esolangs.org/wiki/BFStack)   | [BF-PDA](https://esolangs.org/wiki/BF-PDA)   |
| [Home Row](https://esolangs.org/wiki/Home_Row) | [BFStack](https://esolangs.org/wiki/BFStack) |
| [Jaune](https://esolangs.org/wiki/Jaune)       | [EXCON](https://esolangs.org/wiki/EXCON)     |
| [Suffolk](https://esolangs.org/wiki/Suffolk)   | [RAM0](https://esolangs.org/wiki/RAM0)       |
| [Unsquare](https://esolangs.org/wiki/Unsquare) |                                              |

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
-   For **Jaune**, only one character can be input at a time.
-   For **Suffolk**, although the language is specified to run on an infinite loop, a second command line argument may be given to set the number of loops. The default is `10`.
-   For **123**, input is given at the end of the program. The two are separated by a single `|`.

## Miscellaneous
-   The `binary.py` program implements a given boolean function in Dig.

-   The `generate.py` program outputs programs which output a given string in different languages. The supported languages are as follows:
    -   BFStack
    -   BrainIf
    -   Container
    -   Painfuck
    -   Suffolk
    -   123
    -   %^2^-1 (Magnitude)
    -   Forþ (Forth)
