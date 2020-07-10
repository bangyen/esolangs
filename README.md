# Esolang Interpreters
Python implementations of different esoteric programming languages.

## Implemented
-   [ASCII art](https://esolangs.org/wiki/ASCII_art)
-   [circlefuck](https://esolangs.org/wiki/Circlefuck)
-   [BFStack](https://esolangs.org/wiki/BFStack)
-   [Dig](https://esolangs.org/wiki/Dig)
-   [DSDLAI](https://esolangs.org/wiki/Dig_straight_down_like_an_idiot)
-   [dotlang](https://esolangs.org/wiki/Dotlang)
-   [Back](https://esolangs.org/wiki/Back)

## Notes
-   For **circlefuck**, the `narcissist` program is the only program for which the interpreter doesn't work. The extended `quine` program doesn't work because it modifies a `+` symbol, causing it to increment incorrectly.
-   For **dotlang**, the interpreter skips over strings and warp names after parsing them, so printing a string with spaces is possible. If this additional feature seems to be a negative rather than a positive, feel free to create an issue.
