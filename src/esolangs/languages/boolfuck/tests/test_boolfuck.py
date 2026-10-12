"""Interpreter suite for boolfuck."""

from tests.support.language_suite import load_suite

load_suite(globals(), "boolfuck", "interpreter")
