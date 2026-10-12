"""Interpreter suite for brainfuck."""

from tests.support.language_suite import load_suite

load_suite(globals(), "brainfuck", "interpreter")
