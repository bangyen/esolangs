"""Shared arithmetic settings for Mammalian execution and generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MammalianModuli:
    """Cell operations use 256; EXCRETE and PRONOUNCE use the I/O modulus."""

    cell_modulus: int = 256
    io_modulus: int = 256

    def __post_init__(self) -> None:
        if type(self.cell_modulus) is not int or self.cell_modulus != 256:
            raise ValueError("Mammalian cell_modulus must be 256")
        if type(self.io_modulus) is not int or self.io_modulus not in (255, 256):
            raise ValueError("Mammalian io_modulus must be 255 or 256")


DEFAULT_MODULI = MammalianModuli()
