"""Collect language-owned descriptors without importing generators."""

from collections.abc import Iterator, Mapping
from importlib import import_module
from importlib.resources import files

from esolangs.registry._catalog import Catalog
from esolangs.registry._language import LanguageDeclaration

__all__ = ["LANGUAGES", "LanguageDeclaration"]


def _declarations() -> Iterator[LanguageDeclaration]:
    """Discover the same descriptor path for every installed language."""
    for package in sorted(
        files("esolangs.languages").iterdir(), key=lambda item: item.name
    ):
        if package.is_dir() and package.joinpath("descriptor.py").is_file():
            yield import_module(
                f"esolangs.languages.{package.name}.descriptor"
            ).LANGUAGE


CATALOG = Catalog(sorted(_declarations(), key=lambda lang: lang.name.casefold()))
LANGUAGES: Mapping[str, LanguageDeclaration] = CATALOG.languages
