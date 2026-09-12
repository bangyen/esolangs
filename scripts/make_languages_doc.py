r"""Generate docs/languages.md and the README's Implemented Languages."""

import pathlib
import textwrap

from esolangs.registry import LANGUAGES, RUNNERS, parameterized_ids, wiki_url
from esolangs.tools.boolean import BOOLEAN

ROOT = pathlib.Path(__file__).parents[1]
# Extra source files that are.
# globbed alongside the.
# implementation file still.
_EXTRA_SUPPORT_MODULES = {"common"}

# Extra-implementation display.
# differs from ``name.replace(".
# literal as in the.
_EXTRA_WIKI = {
    "Forþ": "For%C3%BE",
    "%^2^-1": "%25%5E2%5E-1",
    "bit~": "Bit~",
}

# The README's Implemented.
# category.
# filed by its most distinctive.
# on a 2D surface) > stack >.
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
    r"""Return the esolangs wiki page title for the displayed language name."""
    return name


def _wiki_link(name: str) -> str:
    r"""Return the language's wiki URL, built by the registry so the two."""
    return wiki_url(_wiki_name(name))


def _source_link(name: str) -> str:
    r"""Return the GitHub URL of the language's Python interpreter."""
    module = RUNNERS[name][0]
    path = module.replace(".", "/")
    return (
        f"https://github.com/bangyen/esolangs/blob/main/"
        f"src/esolangs/interpreters/{path}.py"
    )


def _template_list() -> str:
    r"""Return the parameterized languages as one wrapped Markdown line."""
    ids = parameterized_ids()
    names = sorted(name for name, lang in LANGUAGES.items() if lang.id in ids)
    return textwrap.fill(", ".join(names) + ".", width=72)


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    return {
        "interpreter": lang.interpreter is not None if lang else False,
        "boolean": name in BOOLEAN,
        "template": lang is not None and lang.id in parameterized_ids(),
    }


def render() -> str:
    r"""Render the languages documentation table as Markdown."""
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
        "**Template** marks the parameterized ones -- see below.",
        "",
        "## Parameterized generators",
        "",
        "A parameterized generator embeds the input bits in a template with",
        "one `{Xi}` slot per input, rather than returning a program that",
        "reads them. `esolangs.generate` returns that template; fill it with",
        "`esolangs.instantiate(language, template, bits)`, which is what the",
        "committed `examples/` programs are built by, or from the command",
        "line with `esolangs generate --bits 10 <language> <table>`. Running",
        "one unfilled raises `TemplateError`; filling the slots by hand does",
        "not work, since each language spells a set-input its own way.",
        "",
        f"The {len(parameterized_ids())} of them are marked **Template** in the",
        "matrix below:",
        "",
        _template_list(),
        "",
        "Most have no input command at all. The exceptions are COD, Minifuck,",
        "123, Home Row and %^2^-1, where an embedded input is the supported",
        "Boolean-generator route: %^2^-1 cannot compute a two-input function",
        "from runtime input, and COD's edge input would require horizontal",
        "routing.",
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
        "| Language | Python | Boolean | Template |",
        "| --- | :---: | :---: | :---: |",
    ]
    for name in sorted(LANGUAGES):
        c = _capabilities(name)
        lines.append(
            f"| {name} | {'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['template'] else ''} |"
        )
    lines += ["", "The `esolangs` command lists the languages with Python support:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


def render_languages_section() -> str:
    r"""Render the README's Implemented Languages section between the."""
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
                f"- [{_wiki_name(name)}]({_wiki_link(name)})"
                f" ([code]({_source_link(name)}))"
            )
        out.append("")
    return "\n".join(out).rstrip()


def render_examples_section() -> str:
    r"""Render the README's Examples paragraph between the markers."""
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
    r"""Render the README's boolean-generator count between the markers."""
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
    r"""Rewrite the generated sections of README.md between their markers."""
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
