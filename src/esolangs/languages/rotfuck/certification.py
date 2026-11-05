"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

CERTIFICATION = CertificationSpec(
    # Retain the even scaling rungs across bias phases; parity now measures
    # 285/339/390 chars there ([ablations.constant_runs_by_multiplication]).
    scaling_rungs=(10, 12, 14),
)
