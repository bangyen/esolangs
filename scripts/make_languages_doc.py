"""Generate docs/languages.md and the README's Implemented Languages list.

Walks the registry to produce the language capability matrix
(docs/languages.md) and the grouped, wiki-linked language list in the
README, so neither page goes stale the way a hand-maintained list would.
Every column derives from the registry or a capability set -- never from
which files happen to sit in examples/.
"""

import pathlib

from esolangs.registry import LANGUAGES, RUNNERS
from esolangs.tools.boolean import BOOLEAN

ROOT = pathlib.Path(__file__).parents[1]
# Extra source files that are support modules, not implementations: they are
# globbed alongside the languages but have no display name (an unknown
# implementation file still fails loudly).
_EXTRA_SUPPORT_MODULES = {"common"}

# Extra-implementation display name -> wiki slug, where the page name
# differs from ``name.replace(" ", "_")`` (URL-encoded characters kept
# literal as in the pre-existing hand-written list).
_EXTRA_WIKI = {
    "Forþ": "For%C3%BE",
    "%^2^-1": "%25%5E2%5E-1",
    "bit~": "Bit~",
}

# The README's Implemented Languages section, grouped by interpreter
# category.  The list order is the classification priority (a language is
# filed by its most distinctive data structure): grid (a beam/pointer moving
# on a 2D surface) > stack > queue > tape > register (the imperative
# default) > other.
_README_HEADINGS = [
    (
        "grid_based",
        "Grid-based Languages",
        "Languages that move a pointer or beam across a 2D grid.",
    ),
    (
        "stack_based",
        "Stack-based Languages",
        "Languages that use a stack for data manipulation.",
    ),
    (
        "queue_based",
        "Queue-based Languages",
        "Languages whose primary data structure is a queue or deque.",
    ),
    (
        "tape_based",
        "Tape-based Languages",
        "Languages that operate on a tape (similar to Turing machines).",
    ),
    (
        "register_based",
        "Register-based Languages",
        "Languages that use registers to store and manipulate data.",
    ),
    (
        "other",
        "Other Languages",
        "Languages that don't fit into the above categories.",
    ),
]

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_EXAMPLES_START = "<!-- EXAMPLES:START -->"
_EXAMPLES_END = "<!-- EXAMPLES:END -->"
_BOOLEAN_COUNT_START = "<!-- BOOLEAN-COUNT:START -->"
_BOOLEAN_COUNT_END = "<!-- BOOLEAN-COUNT:END -->"


def _wiki_name(name: str) -> str:
    """Return the esolangs wiki page title for the displayed language name."""
    return name


def _wiki_slug(name: str) -> str:
    return _wiki_name(name).replace(" ", "_")


def _source_link(name: str) -> str:
    """Return the GitHub URL of the language's Python interpreter."""
    module = RUNNERS[name][0]
    path = module.replace(".", "/")
    return (
        f"https://github.com/bangyen/esolangs/blob/main/"
        f"src/esolangs/interpreters/{path}.py"
    )


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    return {
        "interpreter": lang.interpreter is not None if lang else False,
        "boolean": name in BOOLEAN,
    }


def render() -> str:
    """Render the languages documentation table as Markdown."""
    lines = [
        "# Language capabilities",
        "",
        "Generated from `esolangs/registry.py` by",
        "`scripts/make_languages_doc.py`; do not edit by hand.",
        "",
        "## Columns",
        "",
        "**Python** means an in-repo interpreter under `esolangs.interpreters`.",
        "**Boolean** marks the boolean-function generators.",
        "",
        "## Parameterized generators",
        "",
        "Parameterized generators embed `{Xi}` input bits in a template. The",
        "harness instantiates and runs one program per input row.",
        "",
        "- **The no-input languages** (Back, BIO, NoComment, BF-PDA, Lamfunc,",
        "  Bitdeque, RAM0, Minsky Swap, Eval, ArrowQueue, A Painter Ant, WII2D),",
        "  which have no input command at all.",
        "- **Cod, Minifuck, and %^2^-1**, where embedded input is the supported",
        "  Boolean-generator route. %^2^-1 cannot compute a two-input function",
        "  from runtime input; Cod's edge input would require horizontal routing.",
        "",
        "## How %^2^-1 reaches its tables",
        "",
        "The generator combines subcube, affine, threshold, band, and fold",
        "constructions. It is exhaustive through four inputs; the fold reaches",
        "sampled generic tables through eleven inputs, and the interleaved",
        "fold reaches generic twelve- and thirteen-input tables.",
        "",
        "## The matrix",
        "",
        "| Language | Python | Boolean |",
        "| --- | :---: | :---: |",
    ]
    for name in sorted(LANGUAGES):
        c = _capabilities(name)
        lines.append(
            f"| {name} | {'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['boolean'] else ''} |"
        )
    lines += ["", "The `esolangs` command lists the languages with Python support:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to both its esolangs wiki
    page and the interpreter's source file on GitHub.  The ``<summary>``
    count and the pointer to the capability matrix are generated too, so they
    stay in sync.
    """
    out: list[str] = [
        f"<summary>Show all {len(RUNNERS)} languages</summary>",
        "",
        "The full capability matrix (generators, boolean support, examples)"
        " is in [`docs/languages.md`](docs/languages.md).",
        "",
    ]
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, (module, _) in RUNNERS.items():
        groups[module.split(".")[0]].append(name)

    for prefix, heading, description in _README_HEADINGS:
        out.append(f"### {heading}")
        out.append("")
        out.append(description)
        out.append("")
        for name in sorted(groups[prefix]):
            out.append(
                f"- [{_wiki_name(name)}](https://esolangs.org/wiki/{_wiki_slug(name)})"
                f" ([code]({_source_link(name)}))"
            )
        out.append("")
    return "\n".join(out).rstrip()


def render_examples_section() -> str:
    """Render the README's Examples paragraph between the markers.

    The count is the number of registered boolean generators, taken from
    the registry rather than from ``ls examples/`` -- the same rule the rest
    of this script follows.  A separate sync test already pins that every
    generator has its committed file, so the registry is the source that
    cannot drift.
    """
    return "\n".join(
        [
            "Ready-to-run programs are committed under [`examples/`](examples/):",
            f"`examples/boolean/` holds a truth-table program for each of the"
            f" {len(BOOLEAN)}",
            "languages with a boolean generator.  It regenerates via",
            "`scripts/write_examples.py`.",
        ]
    )


def render_boolean_count_section() -> str:
    """Render the README's boolean-generator count between the markers."""
    return "\n".join(
        [
            "The truth table is a binary string of length `2**n`,"
            " most-significant input",
            f"first; its length implies `n`, so it isn't passed separately."
            f"  {len(BOOLEAN)} of the",
            "languages have such a generator, some covering only a documented"
            " subset of",
            "tables.",
        ]
    )


def update_readme() -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = ROOT / "README.md"
    text = path.read_text()
    for start, end, render in (
        (_README_START, _README_END, render_languages_section),
        (_EXAMPLES_START, _EXAMPLES_END, render_examples_section),
        (_BOOLEAN_COUNT_START, _BOOLEAN_COUNT_END, render_boolean_count_section),
    ):
        block = start + "\n\n" + render() + "\n\n" + end
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
    path.write_text(text)


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    count = len(LANGUAGES)
    print(f"wrote {out} ({count} languages)")
    update_readme()
    print("updated the generated sections of README.md")
