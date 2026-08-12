"""Generate docs/languages.md and the README's Implemented Languages list.

Walks the registry and the compiler/example directories to produce the
language capability matrix (docs/languages.md) and the grouped, wiki-linked
language list in the README, so neither page goes stale the way a
hand-maintained list would.
"""

import pathlib

from esolangs.registry import LANGUAGES, RUNNERS

ROOT = pathlib.Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
HELLO = EXAMPLES / "hello-world"
CAT = EXAMPLES / "cat"
TRUTH = EXAMPLES / "truth-machine"

# Languages with a boolean generator in esolangs.tools.booleans, mapped to
# display names.
BOOLEAN = {
    "3x",
    "6-5",
    "ASCII art",
    "Basicfuck",
    "Between",
    "BF",
    "BFStack",
    "BrainIf",
    "CircleFuck",
    "Clockwise",
    "Container",
    "Dig",
    "Dimensional",
    "Forþ",
    "LaserFuck",
    "Modulous",
    "Nevermind",
    "Polynomial",
    "Qoibl",
    "Sophie",
    "Taglate",
    "Unsquare",
}
ASSEMBLY_COMPILERS = {"BFStack", "Home Row", "Jaune", "Suffolk", "Unsquare"}
C_COMPILERS = {"BF-PDA", "BFStack", "EXCON", "RAM0"}

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

# Registry display name -> esolangs wiki page slug where the page name
# differs from ``name.replace(" ", "_")``.
_WIKI_PAGES = {
    "BF": "Brainfuck",
    "BitDeque": "Bitdeque",
    "CircleFuck": "Circlefuck",
    "huf": "Huf",
    "MAMMALIAN": "SLOW_ACV_MAMMALIAN",
    "Temporary": "The_Temporary_Stack",
    "ZTOALC": "ZTOALC_L",
}

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"


def _wiki_slug(name: str) -> str:
    return _WIKI_PAGES.get(name, name.replace(" ", "_"))


def _file_name(name: str) -> str:
    return name.lower().replace(" ", "-")


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    hello = (HELLO / f"{_file_name(name)}.txt").exists()
    return {
        "generator": lang.generator is not None if lang else False,
        "interpreter": lang.interpreter is not None if lang else False,
        "boolean": name in BOOLEAN,
        "compiler": name in ASSEMBLY_COMPILERS or name in C_COMPILERS,
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
        "| Language | Text generator | Interpreter | Boolean | Compiler | Examples |",
        "| --- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name in sorted(set(LANGUAGES) | C_COMPILERS):
        c = _capabilities(name)
        examples = " ".join(k for k in ("hello", "cat", "truth-machine") if c[k])
        lines.append(
            f"| {name} | {'yes' if c['generator'] else ''} | "
            f"{'yes' if c['interpreter'] else ''} | {'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['compiler'] else ''} | {examples} |"
        )
    lines += ["", "The `esolangs` command lists the same languages:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to its esolangs wiki page.
    """
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, (module, _, _) in RUNNERS.items():
        groups[module.split(".")[0]].append(name)

    out: list[str] = []
    for prefix, heading, description in _README_HEADINGS:
        out.append(f"### {heading}")
        out.append("")
        out.append(description)
        out.append("")
        for name in sorted(groups[prefix]):
            out.append(f"- [{name}](https://esolangs.org/wiki/{_wiki_slug(name)})")
        out.append("")
    return "\n".join(out).rstrip()


def update_readme() -> None:
    """Rewrite the Implemented Languages section of README.md."""
    path = ROOT / "README.md"
    text = path.read_text()
    block = _README_START + "\n\n" + render_languages_section() + "\n\n" + _README_END
    start = text.index(_README_START)
    end = text.index(_README_END) + len(_README_END)
    path.write_text(text[:start] + block + text[end:])


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    print(f"wrote {out} ({len(set(LANGUAGES) | C_COMPILERS)} languages)")
    update_readme()
    print(f"updated {ROOT / 'README.md'} Implemented Languages section")
