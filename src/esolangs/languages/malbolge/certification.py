"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

CERTIFICATION = CertificationSpec(
    # Every source loads into the fixed store, so every program -- this
    # generator's or any other -- is bounded by a constant.
    size_bound=lambda _n: 59_049,
)
