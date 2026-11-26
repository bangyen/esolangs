"""Inspect support for a specific truth table and retain its construction."""

from dataclasses import dataclass

from esolangs.artifacts import Artifact
from esolangs.exceptions import GeneratorCapError
from esolangs.registry._catalog import Catalog
from esolangs.settings import DialectSettings

__all__ = ["Ready", "Unsupported", "plan_generation"]


@dataclass(frozen=True, slots=True)
class Ready:
    """A supported construction whose backend has already run."""

    artifact: Artifact

    def build(self) -> Artifact:
        """Return the retained construction."""
        return self.artifact


@dataclass(frozen=True, slots=True)
class Unsupported:
    """A table-specific construction refusal."""

    cap: GeneratorCapError

    @property
    def reason(self) -> str:
        """Return the backend's explanation."""
        return str(self.cap)


def plan_generation(
    language: str,
    truth_table: str,
    *,
    width: int | None = None,
    balance: bool = False,
    scale: int | None = None,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
) -> Ready | Unsupported:
    """Return a ready plan or the cap that prevents construction.

    Planning runs the selected backend once, including layout and compression.
    Call Ready.build() to obtain its artifact without rerunning the backend.

    Raises:
        UnknownLanguageError: The language is unknown.
        ArgumentError: Generation or the supplied options are unsupported.
        TruthTableError: The supplied table is invalid.
        ProgramError: The backend returned an incompatible source type.
    """
    from esolangs.operations.generation import generate

    try:
        return Ready(
            generate(
                language,
                truth_table,
                width=width,
                balance=balance,
                scale=scale,
                settings=settings,
                catalog=catalog,
            )
        )
    except GeneratorCapError as error:
        return Unsupported(error.with_traceback(None))
