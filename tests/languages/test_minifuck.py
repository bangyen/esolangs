"""Minifuck through the shared API, CLI and machinery."""

import ast
import inspect
import re
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import _check_program
from esolangs.exceptions import TemplateError
from tests.cli.test_cli import call_main
from tests.cli_support import _failure, call_both
from tests.test_api_contracts import PUBLIC_MEMBERS, ROOT, SIGNATURES, XOR


def test_describe_template_still_hides_stdin_fields(capsys):
    output, _error = call_both(["describe", "Minifuck"], capsys)
    assert "input_shape" not in output
    assert "generate --bits" in output


class TestMessagesNameTheThingThatIsWrong:
    """Small, and each one sent a reader to the wrong word."""

    def test_encode_points_at_a_flag_not_a_python_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`instantiate()` is not reachable from a shell."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "Minifuck", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "instantiate()" not in err
        assert "esolangs generate --bits" in err

    def test_the_details_legend_is_printed_with_the_details(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It lived in `list --help` only, so the columns arrived unexplained."""
        out = call_main(["list", "--details"], capsys)
        assert out.splitlines()[0].strip().startswith("language")
        assert "gen=generator" in out.splitlines()[0]


def test_template_hint_names_cli_bits_and_correction_runs(tmp_path, capsys):
    _, err = _failure(["generate", "--bits", "0", "Minifuck", "0110"], capsys)
    assert "hint: pass exactly 2 0/1 digits to --bits, one per input" in err
    assert "instantiate()" not in err
    program, err = call_both(["generate", "--bits", "01", "Minifuck", "0110"], capsys)
    assert err == ""
    path = tmp_path / "generated.mini"
    path.write_text(program)
    answer, err = call_both(["run", "Minifuck", str(path)], capsys)
    assert answer.strip() == "1"
    assert err == ""


class TestFillingSomethingWithNoSlots:
    """ "0 inputs" is true and answers a question nobody asked."""

    def test_a_plain_program_says_it_is_not_a_template(self) -> None:
        """The mistake is "this is not a template", not a count of zero."""
        with pytest.raises(esolangs.TemplateError, match=re.escape("no run of '$'")):
            esolangs.instantiate("Minifuck", "abc", [1, 0])

    def test_filling_twice_says_the_same_thing(self) -> None:
        """The other way to get here, and it looks identical from inside."""
        template = esolangs.generate("Minifuck", "0110")
        filled = esolangs.instantiate("Minifuck", template, [1, 0])
        with pytest.raises(esolangs.TemplateError, match="already been applied"):
            esolangs.instantiate("Minifuck", filled, [1, 0])

    def test_a_real_slot_mismatch_still_counts(self) -> None:
        """The count is the right answer when there *are* slots."""
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.TemplateError, match="2 inputs"):
            esolangs.instantiate("Minifuck", template, [1, 0, 1])


def test_template_hint_and_example() -> None:
    template = esolangs.generate("Minifuck", "0110")
    with pytest.raises(esolangs.TemplateError) as caught:
        esolangs.instantiate("Minifuck", template, [0])
    assert "exactly 2 integer bits" in caught.value.__notes__[0]
    program = esolangs.instantiate("Minifuck", template, [0, 1])
    assert esolangs.read_answer("Minifuck", esolangs.run("Minifuck", program)) == "1"


class TestInstantiateValidates:
    """A wrong call is refused where it is made, not one layer downstream."""

    def test_the_bit_count_must_match_the_slots(self) -> None:
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError, match="2 inputs, but 1 bit was given"):
            esolangs.instantiate("Minifuck", template, [1])

    def test_a_bit_must_be_a_bit(self) -> None:
        """``2`` was substituted silently into a program that then lied."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.instantiate("Minifuck", template, [2, 0])

    def test_a_non_string_template_is_refused_before_provenance(self) -> None:
        """With a table, ``_is_template_for`` called ``.replace`` on the value."""
        with pytest.raises(TemplateError, match="must be the string"):
            esolangs.instantiate("Minifuck", 5, [1], width=None, truth_table=XOR)  # type: ignore[arg-type]


class TestCapabilityListing:
    """`esolangs list` can answer what the README sends a reader to it for."""

    def test_details_marks_generators_templates_and_examples(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = dict(
            line.split(maxsplit=0) and (line[:32].strip(), line[32:].strip())
            for line in call_main(["list", "--details"], capsys).splitlines()
        )
        assert rows["brainfuck"] == "gen ex"
        assert rows["Minifuck"] == "gen tmpl ex"

    def test_the_plain_listing_is_unchanged(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Scripts parse it, so the default output stays bare names."""
        names = call_main(["list"], capsys).split()
        assert "brainfuck" in names


class TestTemplatesAreReachableFromTheCli:
    """Seventeen languages a CLI-only user could not finish."""

    def test_bits_completes_every_row(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal pointed at ``esolangs.instantiate``, a Python call."""
        got = ""
        for a in (0, 1):
            for b in (0, 1):
                program = call_main(
                    ["generate", "--bits", f"{a}{b}", "Minifuck", "0110"], capsys
                )
                path = tmp_path / "m.txt"
                path.write_text(program.rstrip("\n"))
                got += call_main(["run", "Minifuck", str(path)], capsys)
        assert got == "0110"

    def test_bits_rejects_a_non_binary_string(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "2x", "Minifuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "must be a string of 0s and 1s" in capsys.readouterr().err

    def test_bits_on_a_reader_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "01", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "reads its inputs" in capsys.readouterr().err


class TestPackageSurface:
    """What ``dir(esolangs)`` advertises is what the package supports."""

    def test_all_is_exactly_the_public_surface(self) -> None:
        """Adding or removing a public name is a deliberate edit here."""
        assert sorted(esolangs.__all__) == [
            "ArgumentError",
            "DialectSettings",
            "EsolangError",
            "ExecutionTimeoutError",
            "GeneratorCapError",
            "HaltError",
            "InputExhaustedError",
            "InputSource",
            "InterpreterLimitError",
            "Language",
            "LanguageInfo",
            "MissingDependencyError",
            "Program",
            "ProgramError",
            "ProgramNotFoundError",
            "ProgramSource",
            "Raster",
            "TemplateError",
            "TruthTableError",
            "UnknownLanguageError",
            "describe",
            "dump_program",
            "encode_inputs",
            "generate",
            "instantiate",
            "list_languages",
            "load_program",
            "read_answer",
            "run",
        ]

    def test_the_signatures_are_pinned(self) -> None:
        """Freezing for 1.0: every public name, signature, member and describe key.

        ``test_every_key_is_declared`` compares the TypedDict with live output,
        so deleting a field from both passed; this pins the set itself.
        """
        assert debugger_api.__all__ == [
            "STOP_REASONS",
            "VM",
            "Debugger",
            "StopReason",
            "make_debugger",
            "make_vm",
        ]
        live = {}
        for module in (esolangs, debugger_api):
            for name in module.__all__:
                value = getattr(module, name)
                if inspect.isfunction(value):
                    live[f"{module.__name__}.{name}"] = str(inspect.signature(value))
        for cls in PUBLIC_MEMBERS:
            for name, value in vars(cls).items():
                function = getattr(value, "__func__", value)
                if (name == "__init__" or not name.startswith("_")) and (
                    inspect.isfunction(function)
                ):
                    live[f"{cls.__name__}.{name}"] = str(inspect.signature(function))
        assert live == SIGNATURES
        for cls, members in PUBLIC_MEMBERS.items():
            assert {n for n in dir(cls) if not n.startswith("_")} == members, cls
        assert sorted(esolangs.LanguageInfo.__annotations__) == [
            "answer_convention",
            "answer_encoding",
            "answer_mode",
            "answer_pattern",
            "boolean_generator",
            "dialect_settings",
            "dumps_on_the_post_halt_step",
            "eof_is_a_value",
            "examples",
            "generator_max_inputs",
            "generator_restrictions",
            "id",
            "input_encoding",
            "input_shape",
            "name",
            "parameterized",
            "reads_input",
            "self_halts",
            "source_kind",
            "spec",
            "state_model",
            "steppable_to_answer",
            "width_aware",
            "width_effect",
            "wiki_url",
        ]

    def test_every_exit_status_is_documented(self) -> None:
        """70 and 120 were raised by ``main`` but listed in no help text.

        Collected from the source: literal ``sys.exit``/``_fail`` codes,
        ``*_EXIT`` constants, and ``_exit_code``'s returns.
        """
        from esolangs.cli import HELP, USAGE

        raised: set[int] = set()
        for path in (ROOT / "src" / "esolangs").glob("cli*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                values: list[ast.expr] = []
                if isinstance(node, ast.Call) and ast.unparse(node.func) in {
                    "sys.exit",
                    "_fail",
                }:
                    values = (
                        node.args[-1:]
                        if ast.unparse(node.func) == "sys.exit"
                        else node.args[1:]
                    )
                elif isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id.endswith("_EXIT")
                    for t in node.targets
                ):
                    values = [node.value]
                elif isinstance(node, ast.FunctionDef) and node.name == "_exit_code":
                    values = [
                        n.value
                        for n in ast.walk(node)
                        if isinstance(n, ast.Return) and n.value is not None
                    ]
                for value in values:
                    raised |= {
                        n.value
                        for n in ast.walk(value)
                        if isinstance(n, ast.Constant) and type(n.value) is int
                    }
        raised.add(2)  # ``_fail``'s default
        assert raised == {0, 1, 2, 70, 120, 124, 130}

        def documented(text: str) -> set[int]:
            paragraph = text[text.index("exit codes:") :].split("\n\n")[0]
            return {int(code) for code in re.findall(r"\b(\d+) ", paragraph)}

        assert documented(USAGE) == raised
        assert documented(HELP["run"]) == raised
        usage = (ROOT / "docs" / "usage.md").read_text(encoding="utf-8")
        policy = usage[usage.index("## Compatibility") :]
        assert documented(policy.replace("exit statuses:", "exit codes:")) == raised

    @pytest.mark.parametrize("language", ["Minifuck", "brainfuck"])
    def test_check_runnable_refuses_a_non_source(self, language: str) -> None:
        """An int leaked a TypeError for a template language and passed elsewhere."""
        with pytest.raises(esolangs.ProgramError, match="string of source"):
            _check_program(language, 5)  # type: ignore[arg-type]


class TestTheSignaturesAgreeWithThemselves:
    """Two functions taking the same argument should describe it the same."""

    def test_bits_is_annotated_the_same_in_both_places(self) -> None:
        """``encode_inputs`` promised more than it accepts."""
        annotations = {
            fn.__name__: inspect.signature(fn).parameters["bits"].annotation
            for fn in (esolangs.encode_inputs, esolangs.instantiate)
        }
        assert len(set(annotations.values())) == 1, annotations

    @pytest.mark.parametrize(
        "call",
        [
            lambda bits: esolangs.encode_inputs("brainfuck", bits),
            lambda bits: esolangs.instantiate(
                "Minifuck", esolangs.generate("Minifuck", "0110"), bits
            ),
        ],
    )
    def test_both_accept_and_refuse_the_same_things(self, call: object) -> None:
        """The annotation is only right while the behaviour matches it."""
        call([1, 0])  # type: ignore[operator]
        call((1, 0))  # type: ignore[operator]
        with pytest.raises(esolangs.ArgumentError, match="list or tuple"):
            call(range(2))  # type: ignore[operator]


class TestWidthIsCheckedWhereverItIsTaken:
    """``generate`` refused these and ``instantiate`` ignored them."""

    @pytest.mark.parametrize("width", [0, "8", 2.5])
    def test_instantiate_refuses_what_generate_refuses(self, width: object) -> None:
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.instantiate("Minifuck", template, [1, 0], width=width)  # type: ignore[arg-type]

    @pytest.mark.parametrize("width", [0, "8", 2.5])
    def test_generate_still_refuses_them(self, width: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.generate("brainfuck", "0110", width=width)  # type: ignore[arg-type]


class TestBitsAreBits:
    """The container as well as the elements."""

    @pytest.mark.parametrize("bits", [None, "10", {0: 1, 1: 0}, [], [1.0, 0.0]])
    def test_both_encoders_refuse_the_same_bits(self, bits: object) -> None:
        """A dict was iterated as its *keys*, answering a different row."""
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.encode_inputs("brainfuck", bits)  # type: ignore[arg-type]
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.instantiate("Minifuck", template, bits)  # type: ignore[arg-type]

    def test_a_non_string_template_is_refused(self) -> None:
        with pytest.raises(esolangs.TemplateError, match="template must be"):
            esolangs.instantiate("Minifuck", None, [1, 0])  # type: ignore[arg-type]
