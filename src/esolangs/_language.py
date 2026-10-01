"""The public API with one language bound."""

import os
from dataclasses import dataclass

import esolangs
from esolangs._describe import LanguageInfo
from esolangs._evaluate import _DEFAULT, _Default
from esolangs.raster import Raster
from esolangs.registry import resolve


@dataclass(frozen=True, slots=True)
class Language:
    """Bind a canonical language name to the package's existing functions."""

    name: str

    def __post_init__(self) -> None:
        """Resolve the supplied name before any operation."""
        object.__setattr__(self, "name", resolve(self.name))

    def generate(
        self,
        truth_table: str,
        width: int | None = None,
        *,
        balance: bool = False,
        scale: int = 1,
    ) -> str | Raster:
        """Return a program computing ``truth_table``."""
        return esolangs.generate(
            self.name, truth_table, width, balance=balance, scale=scale
        )

    def instantiate(
        self,
        template: str,
        bits: list[int] | tuple[int, ...],
        width: int | None = None,
        truth_table: str | None = None,
    ) -> str:
        """Fill a parameterized template with ``bits``."""
        return esolangs.instantiate(self.name, template, bits, width, truth_table)

    def run(
        self,
        program: str | Raster | os.PathLike[str],
        stdin: str = "",
        timeout: float | _Default | None = _DEFAULT,
        seed: int | None = None,
        *,
        isolated: bool = False,
        max_steps: int | None = None,
        scale: int | None = None,
    ) -> str:
        """Execute source using the same bounds as :func:`esolangs.run`."""
        return esolangs.run(
            self.name,
            program,
            stdin,
            timeout,
            seed,
            isolated=isolated,
            max_steps=max_steps,
            scale=scale,
        )

    def evaluate(
        self,
        program: str | Raster | os.PathLike[str],
        timeout: float | _Default | None = _DEFAULT,
        *,
        inputs: int,
        isolated: bool = False,
        scale: int | None = None,
    ) -> str:
        """Return the table computed over ``inputs`` bits."""
        return esolangs.evaluate(
            self.name, program, timeout, inputs=inputs, isolated=isolated, scale=scale
        )

    def describe(self) -> LanguageInfo:
        """Return this language's registry metadata and interpreter description."""
        return esolangs.describe(self.name)

    def encode_inputs(
        self, bits: list[int] | tuple[int, ...], truth_table: str | None = None
    ) -> str:
        """Return the stdin encoding for ``bits``."""
        return esolangs.encode_inputs(self.name, bits, truth_table)

    def read_answer(self, output: str) -> str:
        """Extract the answer bit from raw output."""
        return esolangs.read_answer(self.name, output)

    def check_program(
        self, program: str | Raster | os.PathLike[str], stdin: str = ""
    ) -> str | Raster:
        """Load and validate runnable source."""
        return esolangs.check_program(self.name, program, stdin)

    def check_stdin(self, stdin: str, truth_table: str | None = None) -> None:
        """Refuse stdin that contradicts this language's input convention."""
        esolangs.check_stdin(self.name, stdin, truth_table)
