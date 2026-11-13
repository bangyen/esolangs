"""Immutable language declarations and their scoped lookup indexes."""

from __future__ import annotations

import difflib
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import esolangs
from esolangs.exceptions import ArgumentError, UnknownLanguageError
from esolangs.registry._language import Language
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id


@dataclass(frozen=True, slots=True, eq=False, init=False, repr=False)
class Catalog:
    """Own a frozen declaration set; derived indexes share the same scope."""

    languages: Mapping[str, Language]
    _by_id: Mapping[str, str]
    _by_folded: Mapping[str, str]
    _by_boolean: Mapping[str, Language]
    _runners: Mapping[str, tuple[str, bool]]
    _interpreters: Mapping[str, str]

    def __init__(self, declarations: Iterable[Language]) -> None:
        try:
            records = tuple(declarations)
        except TypeError as error:
            raise ArgumentError(
                "catalog requires iterable Language declarations"
            ) from error
        if any(not isinstance(lang, Language) for lang in records):
            raise ArgumentError("catalog declarations must be Language records")
        if any(not isinstance(lang.aliases, tuple) for lang in records):
            raise ArgumentError("catalog aliases must be immutable tuples")
        languages = {lang.name: lang for lang in records}
        if len(languages) != len(records):
            raise ArgumentError("catalog language names must be unique")
        ids = {lang.id: lang.name for lang in records}
        if len(ids) != len(records):
            raise ArgumentError("catalog language identifiers must be unique")
        folded: dict[str, str] = {}
        for language in records:
            for spelling in (language.name, *language.aliases):
                key = spelling.casefold()
                if key in folded and folded[key] != language.name:
                    raise ArgumentError("catalog aliases must have one owner")
                folded[key] = language.name
        object.__setattr__(self, "languages", MappingProxyType(languages))
        object.__setattr__(self, "_by_id", MappingProxyType(ids))
        object.__setattr__(self, "_by_folded", MappingProxyType(folded))
        object.__setattr__(
            self,
            "_by_boolean",
            MappingProxyType({lang.id: lang for lang in records if lang.has_backend}),
        )
        object.__setattr__(
            self,
            "_runners",
            MappingProxyType(
                {
                    lang.name: (lang.runtime.interpreter, lang.runtime.split)
                    for lang in records
                    if lang.runtime.interpreter is not None
                }
            ),
        )
        object.__setattr__(
            self,
            "_interpreters",
            MappingProxyType(
                {
                    lang.name: f"esolangs.languages.{lang.id}.interpreter"
                    for lang in records
                    if lang.runtime.interpreter is not None
                }
            ),
        )

    def __repr__(self) -> str:
        return f"Catalog({len(self.languages)} languages)"

    def with_language(self, language: Language) -> Catalog:
        """Return a new scope with one declaration added or replaced."""
        if not isinstance(language, Language):
            raise ArgumentError("catalog declarations must be Language records")
        return Catalog(({**self.languages, language.name: language}).values())

    def bind(self, name: str) -> esolangs.Language:
        """Bind public operations to this immutable catalog."""
        from esolangs._language import Language as BoundLanguage

        return BoundLanguage(name, catalog=self)

    def resolve(self, name: str) -> str:
        """Return the registered display name matching ``name``.

        An exact hit wins; otherwise :func:`canonical_id` makes the lookup case-
        and punctuation-insensitive: ``Brainfuck``, ``brainfuck`` and ``BRAINFUCK``
        all reach the registered ``brainfuck``.  Display names mix conventions, so
        callers cannot guess the spelling.  Only punctuation the name itself has
        may be dropped: ``Piet++`` and ``Brainfuck++`` are other wiki languages,
        and slugging them onto Piet and brainfuck ran the wrong one.  A miss raises
        :class:`UnknownLanguageError` naming the closest registered spellings.
        """
        if not isinstance(name, str):
            # Before ``canonical_id`` touches it: a ``None`` name would otherwise
            # escape as ``'NoneType' object has no attribute 'replace'`` from
            # inside the API.
            raise ArgumentError(
                f"a language name must be a string, got {type(name).__name__}"
            )
        if name in self.languages:
            return name
        match = self._by_folded.get(name.strip().casefold())
        if match is not None:
            return match
        match = self._by_id.get(canonical_id(name))
        if match is not None:
            own = _symbols(match, *self.languages[match].aliases)
            if not _symbols(name) - own:
                return match
        close = difflib.get_close_matches(
            canonical_id(name), self._by_id, n=2, cutoff=SUGGESTION_CUTOFF
        )
        if not close:
            # A head of a long name is too far for difflib: "lol" scores 0.18
            # against lol_waht_i_cant_edit_talk_pages.  Suggest, never resolve:
            # a head unique today turns ambiguous when a language is added.
            head = canonical_id(name).replace("_", "")
            starts = [i for i in self._by_id if i.replace("_", "").startswith(head)]
            close = starts if len(head) >= 3 and len(starts) <= 2 else []
        raise UnknownLanguageError(
            name, suggestions=tuple(self._by_id[c] for c in close)
        )


def _symbols(*names: str) -> Counter[str]:
    """Count the characters a slug drops that are not separators."""
    counts: Counter[str] = Counter()
    for name in names:
        counts |= Counter(c for c in name if not (c.isalnum() or _separator(c)))
    return counts


def _separator(c: str) -> bool:
    # Whitespace and every dash: ``'\tfor_thorn\n'``, ``'Super\xa0SNUSP'`` and
    # ``'6\u20135'`` resolved before the symbol rule and must still.
    return c.isspace() or c == "_" or unicodedata.category(c) == "Pd"


def get_catalog(catalog: Catalog | None = None) -> Catalog:
    """Choose an explicit scope or the immutable installed catalog."""
    if catalog is None:
        from esolangs.registry._table import CATALOG

        return CATALOG
    if not isinstance(catalog, Catalog):
        raise ArgumentError("catalog must be a Catalog")
    return catalog
