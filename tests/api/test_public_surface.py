"""Shared public contracts, independent of language ownership."""

import ast
import inspect
import re

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.api.test_api_contracts import (
    PUBLIC_MEMBERS,
    ROOT,
    SIGNATURES,
)
from tests.support.pick import first
from tests.support.reference import REFERENCE

TEMPLATE_LANGUAGE = first(parameterized=True, source_kind="text")


class TestPackageSurface:
    """What ``dir(esolangs)`` advertises is what the package supports."""

    def test_all_is_exactly_the_public_surface(self) -> None:
        """Adding or removing a public name is a deliberate edit here."""
        assert sorted(esolangs.__all__) == [
            "ArgumentError",
            "CompressedText",
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
            "random",
            "reads_input",
            "self_halts",
            "shape",
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
        for path in (ROOT / "src" / "esolangs" / "cli").glob("*.py"):
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
            lambda bits: esolangs.encode_inputs(REFERENCE, bits),
            lambda bits: esolangs.instantiate(
                TEMPLATE_LANGUAGE, esolangs.generate(TEMPLATE_LANGUAGE, "0110"), bits
            ),
        ],
    )
    def test_both_accept_and_refuse_the_same_things(self, call: object) -> None:
        """The annotation is only right while the behaviour matches it."""
        call([1, 0])
        call((1, 0))
        with pytest.raises(esolangs.ArgumentError, match="list or tuple"):
            call(range(2))


class TestWidthIsCheckedWhereverItIsTaken:
    """``generate`` refused these and ``instantiate`` ignored them."""

    @pytest.mark.parametrize("width", [0, "8", 2.5])
    def test_instantiate_refuses_what_generate_refuses(self, width: object) -> None:
        template = esolangs.generate(TEMPLATE_LANGUAGE, "0110")
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.instantiate(TEMPLATE_LANGUAGE, template, [1, 0], width=width)

    @pytest.mark.parametrize("width", [0, "8", 2.5])
    def test_generate_still_refuses_them(self, width: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="width"):
            esolangs.generate(REFERENCE, "0110", width=width)


class TestBitsAreBits:
    """The container as well as the elements."""

    @pytest.mark.parametrize("bits", [None, "10", {0: 1, 1: 0}, [], [1.0, 0.0]])
    def test_both_encoders_refuse_the_same_bits(self, bits: object) -> None:
        """A dict was iterated as its *keys*, answering a different row."""
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.encode_inputs(REFERENCE, bits)
        template = esolangs.generate(TEMPLATE_LANGUAGE, "0110")
        with pytest.raises(esolangs.ArgumentError, match="bits"):
            esolangs.instantiate(TEMPLATE_LANGUAGE, template, bits)

    def test_a_non_string_template_is_refused(self) -> None:
        with pytest.raises(esolangs.TemplateError, match="template must be"):
            esolangs.instantiate(TEMPLATE_LANGUAGE, None, [1, 0])
