"""Shared arithmetic settings for Mammalian execution and generation."""

from dataclasses import dataclass

MODULI = (255, 256)


@dataclass(frozen=True)
class MammalianModuli:
    """Separate cell arithmetic from EXCRETE and PRONOUNCE reductions."""

    cell_modulus: int = 256
    io_modulus: int = 255

    def __post_init__(self) -> None:
        if type(self.cell_modulus) is not int or self.cell_modulus not in MODULI:
            raise ValueError("Mammalian cell_modulus must be 255 or 256")
        if type(self.io_modulus) is not int or self.io_modulus not in MODULI:
            raise ValueError("Mammalian io_modulus must be 255 or 256")


DEFAULT_MODULI = MammalianModuli()
