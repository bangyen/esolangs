"""Generate docs/languages.md and the README's Implemented Languages list.

Walks the registry and the compiler directories to produce the language
capability matrix (docs/languages.md) and the grouped, wiki-linked language
list in the README, so neither page goes stale the way a hand-maintained
list would.  Every column derives from the registry or a capability set --
never from which files happen to sit in examples/.
"""

import pathlib

from esolangs.registry import LANGUAGES, RUNNERS
from esolangs.tools.boolean import BOOLEAN

ROOT = pathlib.Path(__file__).parents[1]
# Compiler source-file stem -> the language's display name.  A compiler file
# without an entry here fails loudly rather than silently dropping out of
# the docs.
_COMPILER_NAMES = {
    "bfstack": "BFStack",
    "home_row": "Home Row",
    "jaune": "Jaune",
    "suffolk": "Suffolk",
    "unsquare": "Unsquare",
    "bf_pda": "BF-PDA",
    "ram0": "RAM0",
    "addsubjump": "AddSubJump",
    "collatz_multiverse": "Collatz Multiverse",
    "sbleq": "S*bleq",
    "decleq": "Decleq",
    "forth": "Forþ",
    "forbin": "Forbin",
    "container": "Container",
}

_COMPILER_DIRS = {
    "assembly": (ROOT / "src" / "esolangs" / "compilers", "*.py"),
}

# Support modules in the compiler directory that aren't language
# implementations, e.g. shared assembly fragments -- an unrecognized file
# still fails loudly via _COMPILER_NAMES.
_COMPILER_SUPPORT_MODULES = {"__init__", "_riscv_common"}


def _compiler_set(kind: str) -> set[str]:
    """Return the display names of the compilers in the given directory."""
    directory, pattern = _COMPILER_DIRS[kind]
    return {
        _COMPILER_NAMES[path.stem]
        for path in directory.glob(pattern)
        if path.stem not in _COMPILER_SUPPORT_MODULES
    }


ASSEMBLY_COMPILERS = _compiler_set("assembly")

# Extra source files that are support modules, not implementations: they are
# globbed alongside the languages but have no display name (an unknown
# implementation file still fails loudly).
_EXTRA_SUPPORT_MODULES = {"common"}

# The README's Extra Implementations section: each entry is the extra/
# subdirectory, its source pattern, the file-stem -> display-name map (an
# unknown file fails loudly), and the heading.  The assembly refs are the
# RISC-V ports (``*-riscv.s``), matched by stripping the ``-riscv`` suffix.
_EXTRA_DIRS = [
    (
        ROOT / "extra" / "assembly",
        "*-riscv.s",
        {
            "nocomment": "NoComment",
            "bfpda": "BF-PDA",
            "ram0": "RAM0",
            "bio": "BIO",
            "minsky_swap": "Minsky Swap",
        },
        "RISC-V Assembly Implementations",
    ),
]

# Display names of the languages with a cross-check implementation in extra/
# (Lean or RISC-V assembly).  These interpreters run as
# standalone programs rather than through the Python package.
NATIVE = {name for _, _, names, _ in _EXTRA_DIRS for name in names.values()}

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
_COMPILERS_START = "<!-- COMPILERS:START -->"
_COMPILERS_END = "<!-- COMPILERS:END -->"
_EXTRA_START = "<!-- EXTRA:START -->"
_EXTRA_END = "<!-- EXTRA:END -->"


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
        "generator": lang.text is not None if lang else False,
        "interpreter": lang.interpreter is not None if lang else False,
        "cross_check": name in NATIVE,
        "boolean": name in BOOLEAN,
        "compiler": name in ASSEMBLY_COMPILERS,
    }


def render() -> str:
    """Render the languages documentation table as Markdown."""
    lines = [
        "# Language capabilities",
        "",
        "What the repository implements for each language. Generated from",
        "`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by",
        "hand.",
        "",
        "Python means an in-repo interpreter under `esolangs.interpreters`;",
        "Cross-check means an implementation in `extra/` that runs as a",
        "standalone program (Lean or RISC-V assembly), used to",
        "differentially verify the Python interpreter.  The Boolean",
        "column marks the boolean-function generators; the no-input "
        "languages (Back, BIO, NoComment, BF-PDA, Lamfunc, Bitdeque, RAM0, "
        "Minsky Swap, Eval, ArrowQueue, A Painter Ant, WII2D) use "
        "parameterized generators (the harness substitutes input bits into "
        "a template).  Minifuck and %^2^-1 use parameterized generators too, "
        "for a different reason: both *have* an input command, but neither "
        "can branch on what it reads, so their reading models are walled "
        "(the %^2^-1 wall is proved in Lean) and embedding is what reaches "
        "the two-input tables.  %^2^-1 goes further: a subcube cascade "
        "builds every conjunction or disjunction of literals at any arity, "
        "a composed-affine search adds the tables that are no subcube, a "
        "threshold ladder adds the ones neither reaches by letting the "
        "over-3003 reset read a weighted sum, and a band construction makes "
        "three inputs **total** -- all 256 -- by printing with `e` "
        "(`chr(acc & 0xFF)`), so a row need only be congruent to 48 or 49 "
        "mod 256 rather than exactly 0 or 1, which lets the reset be used "
        "once per run of the table (see `docs/limitations.md`).",
        "",
        "| Language | Text generator | Python | Cross-check | Boolean | Compiler |",
        "| --- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name in sorted(set(LANGUAGES) | ASSEMBLY_COMPILERS | NATIVE):
        c = _capabilities(name)
        lines.append(
            f"| {name} | {'yes' if c['generator'] else ''} | "
            f"{'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['cross_check'] else ''} | "
            f"{'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['compiler'] else ''} |"
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
        "The full capability matrix (generators, cross-check and boolean"
        " support, examples) is in [`docs/languages.md`](docs/languages.md).",
        "",
    ]
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, (module, _, _) in RUNNERS.items():
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


def render_compilers_section() -> str:
    """Render the README's Compilers section between the markers."""
    compilers = ASSEMBLY_COMPILERS
    out: list[str] = [
        f"<summary>Show all {len(compilers)} compilers</summary>",
        "",
        "Compilers that translate esoteric languages to other target languages.",
        "",
    ]
    out.append("### RISC-V Assembly Compilers")
    out.append("")
    for name in sorted(_compiler_set("assembly")):
        out.append(f"- [{name}](https://esolangs.org/wiki/{name.replace(' ', '_')})")
    out.append("")
    return "\n".join(out).rstrip()


def render_extra_section() -> str:
    """Render the README's Extra Implementations lists between the markers."""
    out: list[str] = [
        f"<summary>Show all {len(NATIVE)} implementations</summary>",
        "",
        "Implementations written in languages other than Python, used as"
        " cross-check references in CI: most generators are round-trip"
        " verified against them.  The cross-checks share an exit-code"
        " convention mirroring the Python interpreters: 0 = success, 2 ="
        " malformed program, 3 = invalid runtime operation.",
        "",
    ]
    for directory, pattern, names, heading in _EXTRA_DIRS:
        out.append(f"### {heading}")
        out.append("")
        for name in sorted(
            {
                names[path.stem.removesuffix("-riscv")]
                for path in directory.glob(pattern)
                if path.stem not in _EXTRA_SUPPORT_MODULES
            },
            key=str.lower,
        ):
            slug = _EXTRA_WIKI.get(name, name.replace(" ", "_"))
            out.append(f"- [{name}](https://esolangs.org/wiki/{slug})")
        out.append("")
    return "\n".join(out).rstrip()


def update_readme() -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = ROOT / "README.md"
    text = path.read_text()
    for start, end, render in (
        (_README_START, _README_END, render_languages_section),
        (_COMPILERS_START, _COMPILERS_END, render_compilers_section),
        (_EXTRA_START, _EXTRA_END, render_extra_section),
    ):
        block = start + "\n\n" + render() + "\n\n" + end
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
    path.write_text(text)


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    count = len(set(LANGUAGES) | ASSEMBLY_COMPILERS | NATIVE)
    print(f"wrote {out} ({count} languages)")
    update_readme()
    print("updated the generated sections of README.md")
