"""Mammalian dialect constants and validation, independent of execution."""

from dataclasses import dataclass

MODULI = (255, 256)

#: Where execution resumes after a LEAPFROG: after the target instruction
#: (the default) or at it.
LEAPFROG_RESUMES = ("after", "at")

#: How many arrays the machine has; ``SPRINT`` moves the pointer mod this.
ARRAYS = 23


@dataclass(frozen=True)
class MammalianModuli:
    """The dialect settings: moduli, and where a LEAPFROG resumes."""

    cell_modulus: int = 256
    io_modulus: int = 255
    leapfrog_resume: str = "after"

    def __post_init__(self) -> None:
        """Reject unsupported cell and I/O moduli and resume readings."""
        if type(self.cell_modulus) is not int or self.cell_modulus not in MODULI:
            raise ValueError("Mammalian cell_modulus must be 255 or 256")
        if type(self.io_modulus) is not int or self.io_modulus not in MODULI:
            raise ValueError("Mammalian io_modulus must be 255 or 256")
        if self.leapfrog_resume not in LEAPFROG_RESUMES:
            raise ValueError("Mammalian leapfrog_resume must be after or at")


DEFAULT_MODULI = MammalianModuli()
