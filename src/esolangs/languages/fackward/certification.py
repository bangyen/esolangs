"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec

# Seeded `5 4$95283322H$` requests 95,283,322 copies before the step cap.
# Three random digits keep literal copy counts below 1,000.
CERTIFICATION = CertificationSpec(fuzz_max_digits=3)
