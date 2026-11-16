"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

# Seeded `704^7025137` stalls while parsing, before the step cap.
# Four random digits keep literal exponents below 10,000.
CERTIFICATION = CertificationSpec(fuzz_max_digits=4)
