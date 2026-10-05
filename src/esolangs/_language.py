"""The public API with one language bound."""

from dataclasses import dataclass

import esolangs
from esolangs._describe import LanguageInfo
from esolangs._evaluate import _DEFAULT, _Default
from esolangs._program import Program
from esolangs._source import InputSource, ProgramSource
from esolangs.registry import resolve
from esolangs.settings import DialectSettings


@dataclass(frozen=True, slots=True)
class Language:
    """Bind a canonical language name to the package's existing functions.

    Methods follow the package split by who supplies the program:
    ``generate``/``instantiate`` are generator-made, ``run`` executes
    caller-supplied source, ``encode_inputs``/``read_answer`` and
    ``dump_program``/``load_program`` are contract adapters, and
    ``describe`` is catalog.  Boolean evaluation is private machinery.
    """

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
        settings: DialectSettings | None = None,
    ) -> Program:
        """Return a program computing ``truth_table``."""
        return esolangs.generate(
            self.name,
            truth_table,
            width,
            balance=balance,
            scale=scale,
            settings=settings,
        )

    def instantiate(
        self,
        template: str,
        bits: list[int] | tuple[int, ...],
        width: int | None = None,
        truth_table: str | None = None,
        *,
        settings: DialectSettings | None = None,
    ) -> str:
        """Fill a parameterized template with ``bits``."""
        return esolangs.instantiate(
            self.name, template, bits, width, truth_table, settings=settings
        )

    def dump_program(
        self, program: Program, *, settings: DialectSettings | None = None
    ) -> str:
        """Return portable JSON retaining source and dialect choices."""
        return esolangs.dump_program(self.name, program, settings=settings)

    def load_program(self, document: str) -> Program:
        """Restore portable JSON as this language's tagged source."""
        return esolangs.load_program(self.name, document)

    def run(
        self,
        program: ProgramSource,
        stdin: InputSource = "",
        timeout: float | _Default | None = _DEFAULT,
        seed: int | None = None,
        *,
        isolated: bool = False,
        max_steps: int | None = None,
        max_output: int | None = None,
        max_memory: int | None = None,
        settings: DialectSettings | None = None,
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
            max_output=max_output,
            max_memory=max_memory,
            settings=settings,
            scale=scale,
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
