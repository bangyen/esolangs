"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

CERTIFICATION = CertificationSpec(
    # The H-layout is not asymptotic below n=8, so it has no room for a
    # third rung; the deep contract carries it on a backstop for the same
    # reason, and its area recurrence is checked with the construction
    # invariants.
    scaling_rungs=(8, 9),
    documented_sizes=(52_057, 106_751, 2.05),
)
