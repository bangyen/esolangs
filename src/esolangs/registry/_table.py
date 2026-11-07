"""Collect language-owned descriptors without importing generators."""

from collections.abc import Iterator
from importlib import import_module
from importlib.resources import files

from esolangs.registry._language import Language

__all__ = ["LANGUAGES", "Language"]


def _declarations() -> Iterator[Language]:
    """Discover the same descriptor path for every installed language."""
    for package in sorted(
        files("esolangs.languages").iterdir(), key=lambda item: item.name
    ):
        if package.is_dir() and package.joinpath("descriptor.py").is_file():
            yield import_module(
                f"esolangs.languages.{package.name}.descriptor"
            ).LANGUAGE


LANGUAGES: dict[str, Language] = {
    lang.name: lang
    for lang in sorted(_declarations(), key=lambda lang: lang.name.casefold())
}
