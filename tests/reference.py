"""The language the shared tests use as their concrete example.

``remove`` refuses it, and ``tests/test_language_coupling.py`` does not count
naming it, because it is the fixed fixture every shared test is written
against.  Spelling it once here makes a future change to the reference a
one-line edit instead of a sweep of every call site.
"""

REFERENCE = "brainfuck"
