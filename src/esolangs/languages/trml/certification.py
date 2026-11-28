"""Trml's folding probe uses the generic tree."""

from esolangs.registry._certification import CertificationSpec

# Both tables are balanced and nonlinear. The folded one ignores the first bit.
CERTIFICATION = CertificationSpec(folding_probe=("01" * 7 + "10", ("01010110" * 2,)))
