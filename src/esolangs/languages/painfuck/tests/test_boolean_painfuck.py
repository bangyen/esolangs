"""Generator suite for painfuck."""

from tests.support.language_suite import load_suite

load_suite(globals(), "painfuck", "generator")
