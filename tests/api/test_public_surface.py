"""Shared public contracts, independent of language ownership."""

import ast
import inspect
import re
from importlib.resources import files

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


class TestProgramObjectsRefuseMisuse:
    """1.0 audit, round 2: each slipped past ``except EsolangError``."""

    def test_fill_refuses_the_wrong_bit_count(self) -> None:
        template = esolangs.generate(TEMPLATE_LANGUAGE, "0110")
        with pytest.raises(esolangs.TemplateError):
            template.fill([0])  # type: ignore[union-attr]

    def test_a_generated_programs_tag_is_read_only(self) -> None:
        program = esolangs.generate(REFERENCE, "0110")
        with pytest.raises(AttributeError, match="immutable"):
            program.language = TEMPLATE_LANGUAGE  # type: ignore[union-attr]

    @pytest.mark.parametrize("language", ["nonesuch", 5])
    def test_a_tag_must_name_a_language(self, language: object) -> None:
        with pytest.raises(esolangs.UnknownLanguageError):
            esolangs.Raster((((0, 0, 0),),)).tagged(language)  # type: ignore[arg-type]

    def test_compressed_limits_are_typed(self) -> None:
        import gzip

        with pytest.raises(esolangs.ArgumentError, match="limits"):
            esolangs.CompressedText(gzip.compress(b"x"), limits=5)  # type: ignore[arg-type]

    def test_an_alias_tag_is_stored_canonically(self) -> None:
        """Stored as typed, ``run`` refused it under every spelling."""
        tagged = esolangs.CompressedText.from_chunks(iter(["+."])).tagged(
            REFERENCE.upper()
        )
        assert tagged.language == REFERENCE
        assert esolangs.run(REFERENCE, tagged) == "\x01"

    def test_public_annotations_resolve_at_runtime(self) -> None:
        """``DialectSettings`` was a TYPE_CHECKING-only name: NameError."""
        import typing

        for cls in (esolangs.Raster, esolangs.CompressedText):
            typing.get_type_hints(cls)
            typing.get_type_hints(cls.tagged)

    def test_a_scaled_raster_pickles(self) -> None:
        """Its renderer was a local closure: PicklingError."""
        import pickle

        raster = esolangs.Raster((((0, 0, 0),),)).upscaled(2)
        restored = pickle.loads(pickle.dumps(raster))
        assert restored == raster
        assert restored.scale == 2

    @pytest.mark.parametrize(
        "call",
        [
            lambda: esolangs.CompressedText.repeated("a", 3, limits=5),
            lambda: esolangs.CompressedText.repeated(b"x", 3),
            lambda: esolangs.CompressedText.from_chunks(None),
            lambda: esolangs.CompressedText.from_chunks([b"x"]),
        ],
    )
    def test_compressed_builders_refuse_bad_types(self, call: object) -> None:
        with pytest.raises(esolangs.ArgumentError):
            call()  # type: ignore[operator]

    def test_a_refused_object_is_named_without_its_address(self) -> None:
        debugger = debugger_api.make_debugger(REFERENCE, "+")
        with pytest.raises(esolangs.ArgumentError) as caught:
            debugger.watch_cell(object())  # type: ignore[arg-type]
        assert " at 0x" not in str(caught.value)

    def test_a_refused_value_keeps_the_callers_text(self) -> None:
        """Round 5's address stripping swallowed strings; a raising repr leaked."""

        class Raises:
            def __repr__(self) -> str:
                raise RuntimeError("boom")

        with pytest.raises(esolangs.ArgumentError, match="'x at 0xdead'"):
            esolangs.run(REFERENCE, "+", isolated="x at 0xdead")  # type: ignore[arg-type]
        with pytest.raises(esolangs.ArgumentError, match="<Raises>"):
            esolangs.run(REFERENCE, "+", isolated=Raises())  # type: ignore[arg-type]

    def test_quoted_text_in_a_container_is_kept(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match=r"\['x at 0xdead'\]"):
            esolangs.encode_inputs(REFERENCE, ["x at 0xdead"])  # type: ignore[list-item]

    def test_memory_is_integer_cells_or_empty(self) -> None:
        """Three languages exposed tuples and instructions as ``list[int]``."""
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["examples"]:
                continue
            source = (files("esolangs") / facts["examples"][0]).read_bytes()
            try:
                vm = debugger_api.make_vm(name, source.decode())
            except (UnicodeDecodeError, esolangs.EsolangError):
                continue
            assert all(type(cell) is int for cell in vm.memory), name

    def test_a_portable_surrogate_is_refused_like_a_file(self) -> None:
        document = esolangs.dump_program(REFERENCE, "+.").replace('"+."', '"+.\\ud800"')
        with pytest.raises(esolangs.ProgramError, match="surrogates"):
            esolangs.load_program(REFERENCE, document)

    def test_a_debugger_needs_a_vm(self) -> None:
        vm = debugger_api.make_vm(REFERENCE, "+")
        for junk in (None, type(vm)):  # A VM *class* built, then broke on .run.
            with pytest.raises(esolangs.ArgumentError, match="must be a VM"):
                debugger_api.Debugger(junk)  # type: ignore[arg-type]

        class Proxy:
            def __getattr__(self, name: str) -> object:
                return getattr(vm, name)

        assert debugger_api.Debugger(Proxy()).run() == "halted"  # type: ignore[arg-type]

    def test_a_portable_setter_surrogate_is_refused(self) -> None:
        import json

        document = json.loads(
            esolangs.dump_program(
                TEMPLATE_LANGUAGE, esolangs.generate(TEMPLATE_LANGUAGE, "0110")
            )
        )
        document["setters"] = [["\ud800", "\udfff"]] * len(document["setters"])
        with pytest.raises(esolangs.ProgramError):
            esolangs.load_program(TEMPLATE_LANGUAGE, json.dumps(document))

    def test_break_at_takes_a_negative_position(self) -> None:
        """AddSubJump and Subleq halt at -8 and -1; break_at refused them."""
        debugger_api.make_debugger(REFERENCE, "+").break_at(-1)

    def test_the_debugger_mirrors_every_vm_trait(self) -> None:
        debugger = debugger_api.make_debugger(REFERENCE, "+")
        assert debugger.eof_is_a_value is debugger.vm.eof_is_a_value

    def test_a_stepped_timeout_reads_as_an_unstepped_one(self) -> None:
        with pytest.raises(esolangs.ExecutionTimeoutError, match=r"0\.2-second"):
            esolangs.run(REFERENCE, "+[]", timeout=0.2, max_steps=10**9)

    def test_settings_need_a_language(self) -> None:
        """Untagged, ``run`` ignored them silently."""
        with pytest.raises(esolangs.ArgumentError, match="need a language"):
            esolangs.Raster((((0, 0, 0),),), settings=esolangs.DialectSettings())

    def test_an_uninspectable_predicate_is_refused(self) -> None:
        """``break_when(max)`` leaked inspect's bare ValueError."""
        debugger = debugger_api.make_debugger(REFERENCE, "+.")
        with pytest.raises(esolangs.ArgumentError, match="lambda"):
            debugger.break_when(max)  # type: ignore[arg-type]

    def test_flags_must_be_bools(self) -> None:
        """A truthy ``isolated="no"`` switched the sandbox on."""
        with pytest.raises(esolangs.ArgumentError, match="isolated"):
            esolangs.run(REFERENCE, "+", isolated="no")  # type: ignore[arg-type]
        with pytest.raises(esolangs.ArgumentError, match="balance"):
            esolangs.generate(REFERENCE, "0110", balance="no")  # type: ignore[arg-type]

    @pytest.mark.medium
    def test_both_routes_word_a_timeout_alike(self) -> None:
        messages = set()
        for isolated in (False, True):
            with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
                esolangs.run(REFERENCE, "+[]", timeout=0.5, isolated=isolated)
            messages.add(str(caught.value))
        assert messages == {"execution exceeded the 0.5-second timeout"}
