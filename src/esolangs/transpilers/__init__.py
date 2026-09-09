"""Transpilers between languages, and the admission bar they meet.

The transpilers live in :mod:`esolangs.transpilers.transpilers` rather than
here so that the mutation harness can reach them: ``_modules`` skips
``__init__`` as a non-target, so code in a package init has no harness path
at all -- the silent exemption ``mutate_generator``'s ``tools`` kind was
added to close in the first place.

This module re-exports that surface, so ``from esolangs.transpilers import
TRANSPILERS`` reads the same as it did when transpilers were one module
under ``esolangs.tools``.
"""

from esolangs.transpilers.transpilers import (
    TRANSPILERS,
    bf_to_painfuck,
    bf_to_streetcode,
    bf_to_three_d_brainfuck,
    bfstack_to_bf,
    decleq_to_sbleq,
)

__all__ = [
    "TRANSPILERS",
    "bf_to_painfuck",
    "bf_to_streetcode",
    "bf_to_three_d_brainfuck",
    "bfstack_to_bf",
    "decleq_to_sbleq",
]
