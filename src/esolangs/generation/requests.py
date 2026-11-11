"""Typed requests crossing the generator/backend boundary."""

from dataclasses import dataclass

from esolangs._dialect import Scalar
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.generation.template import TemplateLayout
from esolangs.raster import Raster
from esolangs.runtime._program import Program

type GeneratedProgram = Program | TemplateLayout


@dataclass(frozen=True, slots=True)
class Options:
    """Complete, immutable dialect choices validated by the operation layer."""

    values: tuple[tuple[str, Scalar], ...] = ()

    def integer(self, name: str) -> int:
        """Return a declared integer option; bool is not an integer choice."""
        value = dict(self.values).get(name)
        if type(value) is not int:
            raise ArgumentError(f"backend option {name} requires an integer")
        return value

    def text(self, name: str) -> str:
        """Return a declared string option."""
        value = dict(self.values).get(name)
        if not isinstance(value, str):
            raise ArgumentError(f"backend option {name} requires text")
        return value


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """A validated table, layout request and complete dialect choices."""

    table: str
    width: int | None = None
    options: Options = Options()


@dataclass(frozen=True, slots=True)
class BalanceRequest:
    """A table and emitted source to lay out under the same dialect choices."""

    table: str
    source: GeneratedProgram
    options: Options = Options()

    def text_source(self) -> str:
        """Return text for a declared text balancer."""
        if isinstance(self.source, TemplateLayout):
            return self.source.source
        if not isinstance(self.source, str):
            raise ProgramError("text layout requires text source")
        return self.source

    def raster_source(self) -> Raster:
        """Return pixels for a declared raster balancer."""
        if not isinstance(self.source, Raster):
            raise ProgramError("raster layout requires raster source")
        return self.source
