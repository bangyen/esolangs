"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

CERTIFICATION = CertificationSpec(
    # A 2^12-row raster renders in about 24s.
    slow_scaling=True,
)
