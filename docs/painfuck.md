# Painfuck repeat operators

The implementation reads a run of `c` or `t` as one counted operator, not
one operator per character. A repeated `y` represents that many independent
decisions. These rules match the parser and are covered by interpreter tests.
