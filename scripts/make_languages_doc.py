"""Generate docs/languages.md and the README's Implemented Languages list.

Walks the registry and the compiler/example directories to produce the
language capability matrix (docs/languages.md) and the grouped, wiki-linked
language list in the README, so neither page goes stale the way a
hand-maintained list would.
"""

import pathlib

from esolangs.registry import LANGUAGES, RUNNERS
from esolangs.tools.boolean import BOOLEAN

ROOT = pathlib.Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
HELLO = EXAMPLES / "hello-world"
CAT = EXAMPLES / "cat"
TRUTH = EXAMPLES / "truth-machine"
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
    "excon": "EXCON",
    "ram0": "RAM0",
}

_COMPILER_DIRS = {
    "assembly": (ROOT / "src" / "esolangs" / "compilers" / "assembly", "*.py"),
}


def _compiler_set(kind: str) -> set[str]:
    """Return the display names of the compilers in the given directory."""
    directory, pattern = _COMPILER_DIRS[kind]
    return {
        _COMPILER_NAMES[path.stem]
        for path in directory.glob(pattern)
        if path.stem != "__init__"
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
            "123": "123",
            "2b1b": "2 Bits, 1 Byte",
            "brainpocalypse": "Brainpocalypse",
            "nocomment": "NoComment",
            "stun-step": "Stun Step",
        },
        "RISC-V Assembly Implementations",
    ),
    (
        ROOT / "extra" / "rust",
        "*.rs",
        {
            "two_d_fish": "2dFish",
            "basicfuck": "Basicfuck",
            "bit_tilde": "bit~",
            "forth": "Forþ",
            "kak": "Kak",
            "laserfuck": "LaserFuck",
            "painfuck": "Painfuck",
            "pct_squared_minus_one": "%^2^-1",
            "number_seventy_four": "Number Seventy-Four",
            "three_x": "3x",
            "trash": "Trash",
            "unsquare": "Unsquare",
        },
        "Rust Implementations",
    ),
]

# Display names of the languages with a native implementation in extra/
# (Rust, Lean, or RISC-V assembly).  These interpreters run as
# standalone programs rather than through the Python package.
NATIVE = {name for _, _, names, _ in _EXTRA_DIRS for name in names.values()}

# Extra-implementation display name -> wiki slug, where the page name
# differs from ``name.replace(" ", "_")`` (URL-encoded characters kept
# literal as in the pre-existing hand-written list).
_EXTRA_WIKI = {
    "Forþ": "For%C3%BE",
    "%^2^-1": "%25%5E2%5E-1",
    "bit~": "Bit~",
    "Number Seventy-Four": "Number_Seventy-Four",
    "Stun Step": "Stun_Step",
}

# The README's Implemented Languages section, grouped by interpreter
# category in this order, with its one-line descriptions.
_README_HEADINGS = [
    (
        "register_based",
        "Register-based Languages",
        "Languages that use registers to store and manipulate data.",
    ),
    (
        "tape_based",
        "Tape-based Languages",
        "Languages that operate on a tape (similar to Turing machines).",
    ),
    (
        "stack_based",
        "Stack-based Languages",
        "Languages that use a stack for data manipulation.",
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


def _file_name(name: str) -> str:
    return name.lower().replace(" ", "-")


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    hello = (HELLO / f"{_file_name(name)}.txt").exists()
    return {
        "generator": lang.generator is not None if lang else False,
        "interpreter": lang.interpreter is not None if lang else False,
        "native": name in NATIVE,
        "boolean": name in BOOLEAN,
        "compiler": name in ASSEMBLY_COMPILERS,
        "hello": hello,
        "cat": (CAT / f"{_file_name(name)}.txt").exists(),
        "truth-machine": (TRUTH / f"{_file_name(name)}.txt").exists(),
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
        "Native means an implementation in `extra/` that runs as a standalone",
        "program (Rust, Lean, or RISC-V assembly).  The Boolean",
        "column marks the boolean-function generators; Back, BIO, and",
        "NoComment's are parameterized (the harness substitutes input bits",
        "into a template) rather than the program reading input.",
        "",
        "| Language | Text generator | Python | Native | Boolean | "
        "Compiler | Examples |",
        "| --- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name in sorted(set(LANGUAGES) | ASSEMBLY_COMPILERS | NATIVE):
        c = _capabilities(name)
        examples = " ".join(k for k in ("hello", "cat", "truth-machine") if c[k])
        lines.append(
            f"| {name} | {'yes' if c['generator'] else ''} | "
            f"{'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['native'] else ''} | "
            f"{'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['compiler'] else ''} | {examples} |"
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
        "The full capability matrix (generators, native and boolean support,"
        " examples) is in [`docs/languages.md`](docs/languages.md).",
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
        " verified against them, and languages whose output classes are too"
        " narrow for a text generator (Kak, Trash, Number Seventy-Four, 2"
        " Bits 1 Byte, Brainpocalypse, Stun Step) still get a Python"
        " interpreter differentially verified against the native cross-check."
        "  The cross-checks share an exit-code convention mirroring the"
        " Python interpreters: 0 = success, 2 = malformed program, 3 ="
        " invalid runtime operation.",
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
