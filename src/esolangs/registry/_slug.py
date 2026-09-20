"""Display-name slugs for language lookup."""

import re
import unicodedata

# Display names whose canonical id cannot be produced by the slug rules.
_CANONICAL_OVERRIDES = {
    # The parentheses mark optional CV(N)(C) slots but are part of the name;
    # the slug rule yields "cv_n_c" where the language is written as one word.
    "CV(N)(C)": "cvnc",
}

_DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


#: How close a miss has to be before it is offered as "did you mean".
#: Measured over 269 single-edit typos of the registered names: 0.6 and 0.65
#: both rescue 265, 0.7 starts costing real rescues, and 0.65 is the lowest
#: that stays silent for every non-name (``nope``, ``zzzz``, ``xyz``, ...).
#: ``TestASuggestionIsWorthLessThanSilence`` re-runs both halves of that
#: trade; the CLI's option-name suggester shares the number, not a copy.
SUGGESTION_CUTOFF = 0.65


def canonical_id(name: str) -> str:
    """Return a display name's slug, using :data:`_CANONICAL_OVERRIDES` when needed."""
    # Stripped before the slug rules, which tolerate a stray space but whose
    # override lookup is exact: ``CV(N)(C) `` fell through to ``cv_n_c``,
    # matched nothing, and still came back as its own suggestion.
    name = name.strip()
    # Casefolded: an exact-keyed override made ``cv(n)(c)`` miss entirely.
    folded = {key.casefold(): value for key, value in _CANONICAL_OVERRIDES.items()}
    if name.casefold() in folded:
        return folded[name.casefold()]
    # Lowercased before the transliterations, which name lowercase chars:
    # otherwise ``FORÞ`` kept its uppercase thorn and came out ``for``.
    s = name.lower().replace("~", "_tilde").replace("þ", "th").replace("*", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "".join("_" + _DIGIT_WORDS[c] + "_" if c.isdigit() else c for c in s)
        s = re.sub(r"_+", "_", s).strip("_")
    return s
