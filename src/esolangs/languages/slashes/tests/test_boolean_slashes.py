"""Constant roots and template recognition for ///."""

import gzip
import random
import subprocess
import sys
from dataclasses import replace

import pytest

import esolangs
from esolangs.cli import main
from esolangs.exceptions import TemplateError
from esolangs.generation.wrap import balance_score, wrap_program
from esolangs.languages.slashes import generator as boolean
from esolangs.languages.slashes import interpreter
from esolangs.languages.slashes.tests.template_shape import _is_unfilled_template
from esolangs.registry import _table
from esolangs.registry._backend import BooleanBackend
from esolangs.runtime._definition import CompressedSourcePolicy
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, make_vm
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_source_length_is_the_documented_formula(n: int) -> None:
    """Alternating run boundaries maximize the compressed sweep count."""
    from scripts.docs.resource_evidence import resource_bounds

    scaling = resource_bounds("///")["scaling"].formula

    if n == 1:
        _check_run_macros()
    for table in witnesses(n):
        assert len(esolangs.generate("///", table).source) <= scaling(n, ""), table
    table = (
        "10" if n == 1 else "10111011" if n == 3 else "10" * (2 ** (n - 1) - 1) + "11"
    )
    assert len(esolangs.generate("///", table).source) == scaling(n, "")


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_root_parses_inputs_without_selecting_a_table(inputs, bit) -> None:
    if inputs == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << inputs)
    template = esolangs.generate("///", table)
    assert len(template.source) == inputs + 4
    assert template.source.count("$") == inputs
    assert _evaluate("///", template, inputs=inputs) == table
    assert _is_unfilled_template(template.source)
    with pytest.raises(TemplateError, match="fill the template"):
        esolangs.run("///", template)
    for row in (0, (1 << inputs) - 1):
        bits = [int(c) for c in format(row, f"0{inputs}b")]
        program = esolangs.instantiate("///", template, bits)
        assert not _is_unfilled_template(program.source)
        vm = make_vm("///", program)
        state = WrittenState(_capture_workspace(vm))
        commands = 0
        while not vm.halted and commands < inputs + 5:
            vm.step()
            state.sample(_capture_workspace(vm))
            commands += 1
        assert vm.halted
        assert vm.output == bit
        assert commands == 3
        assert state.bits <= 16 * inputs + 32


@pytest.mark.parametrize("suffix", ["", "0", "$", "$2", "$x0", "ab0"])
def test_constant_recognizer_does_not_reserve_other_literal_dollars(suffix) -> None:
    assert not _is_unfilled_template("/a///b//" + suffix)


def test_former_all_ignored_layout_is_not_a_template() -> None:
    program = boolean._IGNORE + boolean._UNARY + boolean._DECODE + "X$>qA"
    assert not hasattr(boolean, "_CONSTANT")
    assert not _is_unfilled_template(program)


def test_filled_slots_are_not_a_template() -> None:
    # No $ in the slots: a and b are filled values, not template slots,
    # even when the rest of the string is canonical.
    program = boolean._UNARY + boolean._SWEEP * 4 + boolean._DECODE + "ab>qAqAqAqA"
    assert not _is_unfilled_template(program)


def test_more_ignored_slots_than_slots_is_a_program_not_a_template() -> None:
    # Two X in a three-character slot list once shifted by -1 and raised.
    program = boolean._UNARY + boolean._DECODE + "$XX>qAqB"
    assert not _is_unfilled_template(program)
    assert isinstance(esolangs.run("///", program).output, str)


def test_ignored_input_template_is_recognized_only_while_canonical() -> None:
    assert_analysis_complement("///", "input_weights")
    template = esolangs.generate("///", "0011")  # slots "$X$": one ignored
    assert template.source.endswith("$X$>qAqB")
    assert _is_unfilled_template(template.source)
    body = template.source.removesuffix("$X$>qAqB")
    assert not _is_unfilled_template(body + "$X1>qAqB")  # a filled slot
    assert not _is_unfilled_template(body + "$X$>qAXB")  # a foreign cell


def test_partly_filled_constant_still_requires_its_remaining_input() -> None:
    assert _is_unfilled_template("/a$b//1")
    assert esolangs.run("///", "$0").output == "$0"


def _check_cli_fill_dialect(capsysbinary, monkeypatch) -> None:
    name = "///"
    original = _table.CATALOG.languages[name]
    execute = interpreter._execute
    calls = []

    def validate(**choices):
        if choices in calls:
            raise esolangs.ArgumentError("duplicate mode validation")
        calls.append(choices)

    def run(source, io, *, mode="fast"):
        assert mode in ("fast", "slow")
        return execute(source, io)

    schema = esolangs.DialectSchema(name, {"mode": ("fast", "slow")}, {"mode": "fast"})
    runtime = replace(original.runtime, dialect=validate, dialect_schema=schema)
    scope = esolangs.Catalog([replace(original, runtime=runtime)])
    api = scope.bind(name)
    monkeypatch.setattr(_table, "CATALOG", scope)
    monkeypatch.setattr(interpreter, "_execute", run)
    for flags, mode in (([], "fast"), (["--set=mode=slow"], "slow")):
        calls.clear()
        monkeypatch.setattr(
            sys, "argv", ["esolangs", "generate", name, "01", "--bits=1", *flags]
        )
        main()
        source, diagnostics = capsysbinary.readouterr()
        if mode == "slow":
            assert b'--settings={"mode":"slow"}' in diagnostics
        else:
            assert not diagnostics
        assert calls == [{"mode": mode}]
        calls.clear()
        settings = api.settings(mode=mode)
        calls.clear()
        assert (
            api.run(source.decode().removesuffix("\n"), settings=settings).output == "1"
        )


def _check_standalone_native_source(path) -> None:
    api = esolangs.Language("///")
    source = api.instantiate(api.generate("01"), [1])
    expected = api.run(source).output.encode()
    assert expected == b"1"
    native = esolangs.registry.INTERPRETERS[api.name]
    emitted = subprocess.run(
        [sys.executable, "-m", "esolangs", "generate", "--bits", "1", api.name, "01"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=5,
    )
    assert emitted.stdout == source.source.encode("utf-8") + b"\n"
    for transport, output in (
        (source.source.encode("utf-8"), expected),
        (emitted.stdout, expected),
        (emitted.stdout.replace(b"\n", b"\r\n"), expected),
        (gzip.compress(emitted.stdout, mtime=0), expected),
        (b"1\n\n", b"1\n"),
    ):
        path.write_bytes(transport)
        api_source = api.from_file(path, normalize=True)
        assert api.run(api_source).output.encode() == output
        result = subprocess.run(
            [sys.executable, "-m", native, str(path)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=5,
        )
        expected = output.replace(b"\n", b"\r\n") if sys.platform == "win32" else output
        assert (result.returncode, result.stdout, result.stderr) == (0, expected, b"")


def test_cli_preserves_literal_source(tmp_path, capsysbinary, monkeypatch) -> None:
    with monkeypatch.context() as patch:
        _check_cli_fill_dialect(capsysbinary, patch)
    path = tmp_path / "literal.txt"
    _check_standalone_native_source(path)
    name = "///"
    run = ["esolangs", "run", name, str(path)]
    path.write_text("$", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", run)
    main()
    assert capsysbinary.readouterr() == (b"$", b"")

    original = _table.CATALOG.languages[name]
    backend = BooleanBackend(entrypoint=lambda _request: payload)
    execute = interpreter._execute

    def run_compressed(code, io):
        if isinstance(code, esolangs.CompressedText):
            code = "".join(code.chunks())
        return execute(code, io)

    monkeypatch.setattr(interpreter, "_execute", run_compressed)
    generate = ["esolangs", "generate", name, "11"]
    for policy in (original.runtime.source_policy, CompressedSourcePolicy()):
        runtime = replace(original.runtime, source_policy=policy)
        entry = replace(original, backend=backend, runtime=runtime)
        scope = esolangs.Catalog([entry])
        monkeypatch.setattr(_table, "CATALOG", scope)
        api = scope.bind(name)
        cases = [
            ("1\n", b"1\n\n", b"1\n"),
            ("1\r", b"1\r\r\n", b"1\n"),
            ("1", b"1" if runtime.compressed_source else b"1\n", b"1"),
        ]
        for source, native, output in cases:
            limits = esolangs.TextLimits(
                plain_chars=len(native), generation_chars=32, gzip_bytes=100
            )
            payload = esolangs.CompressedText.from_chunks((source, ""), limits=limits)
            artifact = api.from_json(api.to_json(api.generate("11")))
            assert api.run(artifact).output == source
            for flags in ([], ["--gzip"], ["--plain"]):
                monkeypatch.setattr(sys, "argv", [*generate, *flags])
                main()
                data, error = capsysbinary.readouterr()
                assert not error
                assert (
                    data if flags == ["--plain"] else gzip.decompress(data)
                ) == native
                if runtime.compressed_source and source == "1" and flags != ["--plain"]:
                    assert data == payload.to_gzip()
                path.write_bytes(data)
                monkeypatch.setattr(sys, "argv", run)
                main()
                assert capsysbinary.readouterr() == (output, b"")

        limits = esolangs.TextLimits(plain_chars=4, generation_chars=4, gzip_bytes=100)
        original_size = len(esolangs.CompressedText.from_chunks(("1\r",)).to_gzip())
        for flag, budget, diagnostic in (
            ("--plain", replace(limits, plain_chars=3), b"3-character cap"),
            ("--gzip", replace(limits, generation_chars=3), b"3-character work cap"),
            ("--gzip", replace(limits, gzip_bytes=original_size), b"byte file cap"),
        ):
            payload = esolangs.CompressedText.from_chunks(("1\r",), limits=budget)
            monkeypatch.setattr(sys, "argv", [*generate, flag])
            with pytest.raises(SystemExit) as exited:
                main()
            assert exited.value.code == 2
            out, err = capsysbinary.readouterr()
            assert not out
            assert diagnostic in err


def test_unwrappable_source_is_untouched() -> None:
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"


@pytest.mark.parametrize(
    "table", ["00", "11", "0110", "00001111", "01010101", "0001000100010001"]
)
def test_balanced_program_folds_behind_the_newline_rule(table: str) -> None:
    """Constant, ignored-input and full tables all run once folded."""
    n = len(table).bit_length() - 1
    plain = esolangs.generate("///", table)
    balanced = esolangs.generate("///", table, balance=True)
    assert balance_score(balanced.source) <= balance_score(plain.source)
    assert _evaluate("///", balanced, inputs=n) == table
    assert _evaluate("///", balanced, inputs=n) != table[:-1] + str(1 - int(table[-1]))


def test_balanced_side_is_square_at_n8() -> None:
    """Seed 8 folds to 18 x 38 behind the newline rule."""
    table = format(random.Random(8).getrandbits(256), "0256b")
    balanced = esolangs.generate("///", table, balance=True)
    assert balance_score(balanced.source)[0] == 38
    assert balanced.source.startswith("/\n//")


def _check_run_macros() -> None:
    from esolangs.languages.slashes.generator import _SWEEP_DEF
    from esolangs.languages.slashes.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("///")["workspace"].formula

    io = ScriptedIO("Q")
    machine = _Machine(_SWEEP_DEF + "SS", io)
    for _ in range(4):
        machine.step()
    assert machine.state == (boolean._SWEEP * 2, None)
    for table in ("1011", "10111011", "00010100", "0101101000011010"):
        n = len(table).bit_length() - 1
        for balanced in (False, True):
            template = esolangs.generate("///", table, balance=balanced)
            assert balanced or _is_unfilled_template(template.source)
            for row in range(1 << n):
                program = esolangs.instantiate(
                    "///", template, [int(c) for c in f"{row:0{n}b}"]
                )
                io = ScriptedIO("Q")
                machine = _Machine(program.source, io)
                written = WrittenState(machine.workspace_snapshot())
                while not machine.halted:
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                assert io.getvalue() == table[row]
                assert io.reads == 0
                assert io.input_char() == ord("Q")
                if not balanced:
                    assert written.bits <= workspace(n, template.source)
                    if row == (1 << n) - 1:
                        assert written.bits == workspace(n, template.source)


def _check_constants() -> None:
    from esolangs.languages.slashes.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("///", bit * (1 << n), **options)
                for bits in ([0] * n, [1] * n):
                    program = esolangs.instantiate("///", template, bits)
                    io = ScriptedIO("7")
                    machine = _Machine(program.source, io)
                    pattern = "".join("ab"[b] for b in bits)
                    parsed = False
                    for _ in range(20):
                        if machine.halted:
                            break
                        machine.step()
                        if machine.state[1] == (pattern, ""):
                            parsed = True
                        if io.getvalue():
                            assert parsed
                    assert machine.halted
                    assert parsed
                    assert io.getvalue() == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")


def test_ignored_markers_must_prefix_their_own_slot() -> None:
    for slots in ("XX$$", "$XX$", "X$$X", "$$XX"):
        program = boolean._IGNORE + boolean._UNARY + boolean._DECODE + slots + ">qA"
        assert not _is_unfilled_template(program)
