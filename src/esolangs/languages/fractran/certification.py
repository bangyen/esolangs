"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

# Seeded `2^8460347622` materializes over a gigabyte before the step cap.
# Four random digits keep literal exponents below 10,000.
CERTIFICATION = CertificationSpec(fuzz_max_digits=4)
