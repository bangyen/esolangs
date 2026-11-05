"""Temporary source adapters during the 2.0 caller migration."""

from __future__ import annotations

from typing import cast

import esolangs
from esolangs.artifacts import Artifact
from esolangs.portable import load_program as load_program
from esolangs.runtime._program import Program
from esolangs.settings import DialectSettings
from esolangs.tagged import source_adapter

__all__ = ["generate", "instantiate", "load_program"]


def generate(
    language: str,
    truth_table: str,
    *,
    width: int | None = None,
    balance: bool = False,
    scale: int = 1,
    settings: DialectSettings | None = None,
) -> Program:
    """Return tagged source; options and errors follow :func:`esolangs.generate`."""
    return source_adapter(
        esolangs.generate(
            language,
            truth_table,
            width=width,
            balance=balance,
            scale=scale,
            settings=settings,
        )
    )


def instantiate(
    language: str,
    template: Program | Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    width: int | None = None,
    truth_table: str | None = None,
    settings: DialectSettings | None = None,
) -> str:
    """Return filled text; options and errors follow :func:`esolangs.instantiate`."""
    return cast(
        str,
        source_adapter(
            esolangs.instantiate(
                language,
                template,
                bits,
                width=width,
                truth_table=truth_table,
                settings=settings,
            )
        ),
    )
