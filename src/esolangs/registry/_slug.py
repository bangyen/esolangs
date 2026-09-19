"""Display-name slugs for language lookup."""

import re
import unicodedata

# Display names whose canonical id cannot be produced by the slug rules.
_CANONICAL_OVERRIDES = {
    # The parentheses are part of the name -- they mark the optional slots
    # of the CV(N)(C) syllable -- so the slug rule turns them into
    # separators and yields "cv_n_c".  The language is written and
    # pronounced as one word, so the underscores are noise.
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
#:
#: 0.6 offered ``Sophie`` for ``nope``, which is worse than saying nothing:
#: a wrong guess sends the reader off to check a language they never meant.
#: Measured rather than picked -- across 269 single-edit typos of the
#: registered names, 0.6 and 0.65 both rescue 265, while 0.65 is the lowest value that
#: suggests nothing for any of ``nope``, ``zzzz``, ``xyz``, ``qqqqqq``,
#: ``hello``, ``python``, ``asdf``, ``test`` and ``foo``.  0.7 starts
#: costing real rescues.  ``TestASuggestionIsWorthLessThanSilence`` is the
#: measurement, re-run rather than quoted -- it recomputes both halves of
#: that trade and fails if this number stops being the best one.
#:
#: Shared with the CLI's option-name suggester, which had drifted to its
#: own copy of the number under a docstring promising they were the same.
SUGGESTION_CUTOFF = 0.65


def canonical_id(name: str) -> str:
    """Return a display name's slug, using :data:`_CANONICAL_OVERRIDES` when needed."""
    # Matched case-insensitively: the override is keyed by the display name,
    # so an exact-key lookup made ``CV(N)(C)`` the one language ``resolve``
    # could not match on case -- ``cv(n)(c)`` fell through to the slug rules
    # and became ``cv_n_c``, which is nothing's id.  Every other awkward
    # name (``BRAINFUCK``, ``s*bleq``, ``forþ``) was already tolerant.
    # Stripped before anything else.  The slug rules below collapse runs of
    # non-alphanumerics and strip the result, so almost every name already
    # tolerated a stray surrounding space -- but the override lookup is an
    # exact one, and the name that needs an override was therefore the
    # one that did not.  ``CV(N)(C) `` was the bad one: it fell
    # through to ``cv_n_c``, matched nothing, and came back as "did you mean
    # CV(N)(C)?" -- an invisible diff and no way forward.
    name = name.strip()
    folded = {key.casefold(): value for key, value in _CANONICAL_OVERRIDES.items()}
    if name.casefold() in folded:
        return folded[name.casefold()]
    # Lowercased *before* the transliterations, not after: they name
    # lowercase characters, so ``FORÞ`` kept its uppercase thorn, fell
    # through to the punctuation rule and came out ``for`` -- the one
    # display name whose upper-case spelling did not resolve.
    s = name.lower().replace("~", "_tilde").replace("þ", "th").replace("*", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "".join("_" + _DIGIT_WORDS[c] + "_" if c.isdigit() else c for c in s)
        s = re.sub(r"_+", "_", s).strip("_")
    return s
