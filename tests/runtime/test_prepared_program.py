"""Reusable preparation must isolate source acquisition, state and randomness."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import replace
from io import BytesIO, StringIO
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from time import monotonic
from types import ModuleType
from unittest.mock import patch

import pytest

import esolangs
from esolangs.languages.brainfuck.interpreter import prepare_machine
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import HALTED_REPORT
from esolangs.runtime._prepared import prepare_program
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.support.pick import first, one_where
from tests.support.reference import REFERENCE


def test_unsupported_text_scale_does_not_consume_source() -> None:
    api = esolangs.Language(REFERENCE)
    for operation in (api.run, api.prepare, api.make_vm, api.make_debugger):
        source = StringIO("+.")
        with pytest.raises(esolangs.ArgumentError, match="scale is only supported"):
            operation(source, scale=2)
        assert source.tell() == 0
        assert api.run(source).output == "\x01"


def test_prepared_constructor_accepts_owner_spelling_and_refuses_invalid_types():
    api = esolangs.Language(REFERENCE)
    artifact = esolangs.ProgramArtifact(",+.", api.name.upper())
    direct = esolangs.PreparedProgram(artifact, api.catalog)
    assert direct.language == api.name
    assert direct.run(stdin="A") == api.prepare(artifact).run(stdin="A")
    with pytest.raises(esolangs.ProgramError, match="requires a program artifact"):
        esolangs.PreparedProgram(artifact.source, api.catalog)
    with pytest.raises(esolangs.ArgumentError, match="catalog must be a Catalog"):
        esolangs.PreparedProgram(artifact, object())

    malformed = esolangs.ProgramArtifact("[", api.name)
    with pytest.raises(esolangs.ProgramError) as expected:
        api.prepare(malformed)
    with pytest.raises(esolangs.ProgramError) as caught:
        esolangs.PreparedProgram(malformed, api.catalog)
    assert caught.value.args == expected.value.args

    class ClaimedArtifact:
        def __init__(self, claim: type) -> None:
            self.claim = claim

        @property
        def __class__(self) -> type:
            return self.claim

    false_program = ClaimedArtifact(esolangs.ProgramArtifact)
    with pytest.raises(esolangs.ProgramError, match="requires a program artifact"):
        esolangs.PreparedProgram(false_program, api.catalog)
    with pytest.raises(esolangs.ProgramError, match="requires a program or template"):
        api.evaluate(false_program, [1])
    with pytest.raises(esolangs.TemplateError):
        api.instantiate(ClaimedArtifact(esolangs.TemplateArtifact), [1])


@pytest.mark.parametrize("use_id", [False, True], ids=["alias", "id"])
@pytest.mark.parametrize("retain_settings", [False, True], ids=["plain", "settings"])
def test_prepared_constructor_refuses_foreign_ownership(
    *, use_id: bool, retain_settings: bool
) -> None:
    owner = esolangs.Language(REFERENCE)
    declaration = owner.catalog.languages[owner.name]
    renamed = replace(
        declaration,
        name="Scoped Runtime",
        id=owner.name if use_id else "",
        aliases=() if use_id else (owner.name,),
    )
    api = esolangs.Catalog([renamed]).bind(owner.name)
    assert api.name == renamed.name
    assert api.run(api.from_source("+.")).output == "\x01"
    settings = owner.settings() if retain_settings else None
    artifact = owner.from_source("+.", settings=settings)
    assert owner.run(artifact).output == "\x01"
    for use in (
        lambda: api.run(artifact),
        lambda: api.prepare(artifact),
        lambda: esolangs.PreparedProgram(artifact, api.catalog),
        lambda: api.to_json(artifact),
        lambda: artifact.evaluate([1], catalog=api.catalog),
    ):
        with pytest.raises(esolangs.ProgramError, match="generated for"):
            use()
    with pytest.raises(esolangs.ProgramError, match="program language must be"):
        api.from_json(owner.to_json(artifact))


def test_stored_owner_slug_is_independent_of_lookup() -> None:
    declaration = esolangs.Language(REFERENCE).catalog.languages[REFERENCE]
    for owner_id, decoy_id, aliases in (
        ("", "", ("scoped-runtime",)),
        ("owner", "scoped_runtime", ()),
    ):
        owner = replace(declaration, name="Scoped Runtime", id=owner_id)
        decoy = replace(declaration, name="Alias Runtime", id=decoy_id, aliases=aliases)
        catalog = esolangs.Catalog([owner, decoy])
        assert catalog.bind("scoped-runtime").name == decoy.name
        api = catalog.bind(owner.name)
        artifact = esolangs.ProgramArtifact(",.", " scoped-runtime ")
        direct = esolangs.PreparedProgram(artifact, catalog)
        assert direct.language == owner.name
        assert direct.run(stdin="1").output == "1"
        assert artifact.evaluate([1], catalog=catalog).answer == "1"
        assert api.evaluate(artifact, [1]).answer == "1"
    _check_ambiguous_owner_slug_requires_a_display_name()


def _check_ambiguous_owner_slug_requires_a_display_name() -> None:
    declaration = esolangs.Language(REFERENCE).catalog.languages[REFERENCE]
    left = replace(declaration, name="Scoped Runtime", id="scoped_runtime")
    right = replace(declaration, name="Scoped-Runtime", id="runtime_right")
    catalog = esolangs.Catalog([left, right])
    ambiguous = esolangs.ProgramArtifact("+.", "scoped—runtime")
    assert catalog.resolve(ambiguous.language) == left.name
    for owner in (left, right):
        api = catalog.bind(owner.name)
        canonical = replace(ambiguous, language=f" {owner.name.upper()} ")
        assert api.prepare(canonical).language == owner.name
        assert api.run(canonical).output == "\x01"
        with pytest.raises(esolangs.ProgramError, match="generated for"):
            api.run(ambiguous)
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        ambiguous.evaluate([1], catalog=catalog)
    without_matching_id = esolangs.Catalog([replace(left, id="runtime_left"), right])
    with pytest.raises(esolangs.UnknownLanguageError):
        without_matching_id.resolve(ambiguous.language)


@pytest.mark.medium
@pytest.mark.parametrize("direct", [False, True], ids=["prepare", "constructor"])
def test_prepared_gzip_keeps_export_limits_without_decoding_again(
    tmp_path, monkeypatch, direct
):
    api = esolangs.Language(REFERENCE)
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=2, gzip_bytes=100)
    source = esolangs.CompressedText.from_chunks((",.",), limits=limits)
    document = api.to_json(esolangs.ProgramArtifact(source, api.name, input_arity=1))
    restored = api.from_json(document)
    reads = []
    chunks = esolangs.CompressedText.chunks

    def count_decodes(compressed):
        if compressed is restored.source:
            reads.append(compressed)
        return chunks(compressed)

    monkeypatch.setattr(esolangs.CompressedText, "chunks", count_decodes)
    prepared = (
        esolangs.PreparedProgram(restored, api.catalog)
        if direct
        else api.prepare(restored)
    )
    assert prepared.artifact.source is restored.source
    assert api.to_json(prepared.artifact) == document
    path = tmp_path / "source"
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        api.to_file(prepared.artifact, path)
    assert not path.exists()
    api.to_file(prepared.artifact, path, gzip=True)
    assert path.read_bytes() == source.to_gzip()
    assert prepared.run(stdin="1").output == "1"
    assert (
        prepared.run(stdin="1", limits=esolangs.ExecutionLimits(max_steps=2)).output
        == "1"
    )
    assert prepared.run(stdin="1", isolated=True).output == "1"
    assert complete_vm(prepared.make_vm(stdin="1"), max_steps=2) == "1"
    assert prepared.evaluate([1]).answer == "1"
    assert reads == [restored.source]


def test_prepared_termination_uses_its_retained_preparation():
    api = esolangs.Language(first(answer_mode="termination", reads_input=True))
    prepared = api.prepare(api.generate("01"))
    limits = esolangs.ExecutionLimits(max_steps=100, preparation_timeout=0.000001)
    for bit in (0, 1):
        result = prepared.evaluate([bit], limits=limits)
        assert result.answer == str(bit)
        assert result.termination.halts is (bit == 0)


@pytest.mark.medium
@pytest.mark.parametrize("options", [{}, {"max_steps": 3}, {"total_timeout": 5}])
def test_invalid_stdin_container_leaves_source_unread(options, tmp_path, monkeypatch):
    source = BytesIO(b",+.")
    limits = esolangs.ExecutionLimits(**options)
    api = esolangs.Language(REFERENCE)
    rejected = api.execute(source, stdin=object(), limits=limits)
    assert rejected.status == "rejected"
    assert isinstance(rejected.error, esolangs.ArgumentError)
    assert source.tell() == 0
    assert api.run(source, stdin="A", limits=limits).output == "B"
    assert source.tell() == 3

    caller, other = tmp_path / "caller", tmp_path / "other"
    caller.mkdir()
    other.mkdir()
    (caller / "program").write_text(",+.")
    (other / "program").write_text("++.")
    monkeypatch.chdir(caller)

    class Source:
        calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            return f"{caller.drive}program"

    class Stdin(StringIO):
        @property
        def read(self):
            monkeypatch.chdir(other)
            return super().read

    provider = Source()
    rejected = api.execute(provider, stdin=object(), limits=limits)
    assert isinstance(rejected.error, esolangs.ArgumentError)
    assert provider.calls == 0
    assert api.run(provider, stdin=Stdin("A"), limits=limits).output == "B"
    assert provider.calls == 1
    monkeypatch.chdir(caller)
    assert api.run(Path("program"), stdin=Stdin("A"), limits=limits).output == "B"
    monkeypatch.chdir(caller)
    assert api.run(caller / "program", stdin=Stdin("A"), limits=limits).output == "B"
    monkeypatch.chdir(caller)
    assert complete_vm(api.make_vm(Path("program"), stdin=Stdin("A"))) == "B"


def _check_preparation_consumes_source_once_and_keeps_fresh_invocations():
    source = BytesIO(b",+.")
    prepared = esolangs.Language(REFERENCE).prepare(source)
    source.close()
    first, second = prepared.make_vm(stdin="A"), prepared.make_vm(stdin="Z")
    first.step()
    assert second.ip == 0
    assert complete_vm(first) == "B"
    assert complete_vm(second) == "["
    assert prepared.run(stdin="A").output == "B"
    bounded = prepared.run(stdin="Z", limits=esolangs.ExecutionLimits(max_steps=3))
    assert bounded.output == "["
    assert bounded.input_position == bounded.input_reads == 1
    assert bounded.steps == 3
    assert prepared.run(stdin="A").output == "B"

    language = esolangs.Language(REFERENCE)
    with pytest.raises(esolangs.ProgramError, match="program or template artifact"):
        language.evaluate(",.", [0])
    generated = language.prepare(esolangs.generate(REFERENCE, "0110"))
    with pytest.raises(
        esolangs.ArgumentError, match="has 2 inputs, but 1 bit was given"
    ):
        generated.evaluate([0])
    assert generated.evaluate([0, 1]).answer == "1"
    assert generated.evaluate([1, 1]).answer == "0"


def _check_prepared_isolation_preserves_the_same_observation():
    prepared = esolangs.Language(REFERENCE).prepare(",+.")
    assert prepared.run(stdin="A", isolated=True) == prepared.run(stdin="A")


def _check_prepared_failures_retain_partial_observations():
    prepared = esolangs.Language(REFERENCE).prepare(".,")
    for options in ({}, {"limits": esolangs.ExecutionLimits(max_steps=2)}):
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            prepared.run(**options)
        assert caught.value.partial_output == "\x00"
        observed = caught.value.observation
        assert observed.output == "\x00"
        assert observed.input_reads == 0
        assert observed.input_past_end == 1
        assert observed.completion is None


def _check_preparation_resets_seeded_randomness_for_each_invocation():
    declaration = LANGUAGES[REFERENCE]
    catalog = esolangs.Catalog(
        [replace(declaration, runtime=replace(declaration.runtime, random=True))]
    )
    module = ModuleType("prepared_random_control")
    draws = []

    def execute(_code, io, rng):
        values = tuple(rng.randbelow(256) for _ in range(8))
        draws.append(values)
        io.print_char(chr(values[0]))
        return HALTED_REPORT

    setattr(module, declaration.runtime.completion_entrypoint, execute)
    prepared = prepare_program(
        esolangs.PreparedProgram,
        REFERENCE,
        "",
        catalog=catalog,
        module_loader=lambda *_a, **_k: module,
    )
    assert prepared.run(seed=7) == prepared.run(seed=7)
    prepared.run(seed=8)
    assert draws[0] == draws[1] != draws[2]

    factories = []

    def prepare(_code, options):
        rng = options["rng"]
        factories.append(rng)
        return prepare_machine("+" * rng.randbelow(256) + ".", {})

    setattr(module, declaration.runtime.machine_preparation, prepare)
    first = complete_vm(prepared.make_vm(seed=7))
    second = complete_vm(prepared.make_vm(seed=7))
    third = complete_vm(prepared.make_vm(seed=8))
    assert first == second != third
    assert len(factories) == 3
    assert len({id(rng) for rng in factories}) == 3


def _check_prepared_factory_owns_state_and_input():
    factory = prepare_machine(",+.", {})
    first_io, second_io = ScriptedIO("A"), ScriptedIO("Z")
    first, second = factory(first_io), factory(second_io)
    before = second.snapshot()
    first.step()
    assert second.snapshot() == before
    assert second_io.progress() == 0
    while not first.halted:
        first.step()
    while not second.halted:
        second.step()
    assert first_io.getvalue() == "B"
    assert second_io.getvalue() == "["


def _check_prepared_source_options_and_lines_are_reused():
    from esolangs._dialect import DialectSchema
    from esolangs.runtime._definition import LineSourcePolicy

    declaration = LANGUAGES[REFERENCE]
    schema = DialectSchema(declaration.name, {"increment": (1, 2)}, {"increment": 1})
    validated = []

    def validate(increment=1):
        validated.append(increment)

    runtime = replace(
        declaration.runtime,
        source_policy=LineSourcePolicy(),
        dialect=validate,
        dialect_schema=schema,
    )
    catalog = esolangs.Catalog([replace(declaration, runtime=runtime)])
    module = ModuleType("prepared_source_control")

    def execute(lines, io, increment):
        assert lines.pop() == "last"
        io.print_str(lines.pop() * increment)
        return HALTED_REPORT

    setattr(module, runtime.completion_entrypoint, execute)
    api = esolangs.Language(REFERENCE, catalog=catalog)
    settings = api.settings(increment=2)
    validated.clear()
    prepared = prepare_program(
        esolangs.PreparedProgram,
        REFERENCE,
        "first\r\nlast\r\n",
        settings=settings,
        catalog=catalog,
        module_loader=lambda *_args, **_kwargs: module,
    )
    assert validated == [2]
    validated.clear()
    assert prepared.run().output == "firstfirst"
    assert prepared.run().output == "firstfirst"
    assert validated == []


def _check_prepared_dialect_validates_distinct_options_once() -> None:
    name = one_where(lambda info: "rotation" in info.dialect_settings)[0]
    declaration = LANGUAGES[name]
    calls = []
    once = False
    repeated = esolangs.ProgramError("rotation already validated")

    def validate(rotation="backward"):
        calls.append(rotation)
        if once and len(calls) > 1:
            raise repeated

    runtime = replace(declaration.runtime, dialect=validate)
    api = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(name)
    settings = api.settings(rotation="forward")
    document = api.to_json(",,", settings=settings)
    restored = api.from_json(document)
    once = True
    for perform in (
        lambda: api.prepare(restored).run(stdin="A").output,
        lambda: esolangs.PreparedProgram(restored, api.catalog).run(stdin="A").output,
        lambda: api.run(restored, stdin="A").output,
        lambda: (
            api.run(
                restored, stdin="A", limits=esolangs.ExecutionLimits(max_steps=2)
            ).output
        ),
        lambda: complete_vm(api.make_vm(restored, stdin="A"), max_steps=2),
    ):
        calls.clear()
        assert perform() == "A"
        assert calls == ["forward"]

    class Untouched:
        def read(self):
            pytest.fail("an unsupported isolated scope accessed stdin or source")

    calls.clear()
    with pytest.raises(esolangs.ArgumentError, match="installed catalog"):
        api.run(Untouched(), stdin=Untouched(), settings=settings, isolated=True)
    assert not calls

    schema = runtime.dialect_schema
    assert schema is not None
    extended = esolangs.DialectSchema(
        name,
        schema.choices | {"approval": ("recorded",)},
        schema.defaults | {"approval": "recorded"},
    )
    checked = []
    refusal = esolangs.ArgumentError("effective options refused")

    def distinguish(**choices):
        checked.append(choices)
        if "approval" in choices:
            raise refusal

    configured = replace(runtime, dialect=distinguish, dialect_schema=extended)
    scoped = esolangs.Catalog([replace(declaration, runtime=configured)]).bind(name)
    partial = scoped.settings(rotation="forward")
    checked.clear()
    source = StringIO(",,")
    with pytest.raises(esolangs.ArgumentError) as raised:
        scoped.prepare(source, settings=partial)
    assert raised.value is refusal
    assert checked == [
        {"rotation": "forward"},
        {"rotation": "forward", "approval": "recorded"},
    ]
    assert source.tell() == 2


def _check_relative_source_precedes_dialect_callbacks(tmp_path, monkeypatch):
    caller, other = tmp_path / "caller", tmp_path / "other"
    caller.mkdir()
    other.mkdir()
    (caller / "program").write_text("+.")
    (other / "program").write_text("++.")
    (other / "absent").write_text("++.")
    declaration = LANGUAGES[REFERENCE]
    schema = esolangs.DialectSchema(REFERENCE, {"mode": ("move",)}, {"mode": "move"})
    armed = False

    def validate(mode="move"):
        if armed and mode == "move":
            monkeypatch.chdir(other)

    runtime = replace(declaration.runtime, dialect=validate, dialect_schema=schema)
    api = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(REFERENCE)
    settings = api.settings()
    armed = True

    class Source:
        calls = 0

        def __fspath__(self) -> str:
            assert Path.cwd().samefile(other)  # Validation precedes path binding.
            self.calls += 1
            return "program"

    def exported(source):
        path = caller / "export"
        api.to_file(source, path, settings=settings)
        return path.read_text()

    for route, expected in (
        (lambda source: api.from_file(source, settings=settings).source, "+."),
        (lambda source: api.run(source, settings=settings).output, "\x01"),
        (lambda source: api.prepare(source, settings=settings).run().output, "\x01"),
        (
            lambda source: api.from_json(api.to_json(source, settings=settings)).source,
            "+.",
        ),
        (exported, "+."),
    ):
        monkeypatch.chdir(caller)
        provider = Source()
        assert route(provider) == expected
        assert provider.calls == 1
        monkeypatch.chdir(caller)
        assert route(caller / "program") == expected

    monkeypatch.chdir(caller)
    assert api.from_file("program", settings=settings).source == "+."
    monkeypatch.chdir(caller)
    with pytest.raises(
        esolangs.ProgramNotFoundError, match=r"cannot read absent:"
    ) as missing:
        api.from_file("absent", settings=settings)
    assert missing.value.__cause__.filename == "absent"

    class RedirectingSource(Source):
        def __fspath__(self) -> str:
            monkeypatch.chdir(other)
            return super().__fspath__()

    armed = False
    for route in (api.from_file, api.prepare):
        monkeypatch.chdir(caller)
        provider = RedirectingSource()
        record = route(provider)
        result = (
            api.run(record)
            if isinstance(record, esolangs.ProgramArtifact)
            else record.run()
        )
        assert result.output == "\x01"
        assert provider.calls == 1


@pytest.mark.medium
def test_prepared_invocations_own_source_state_and_randomness(monkeypatch, tmp_path):
    _check_uniform_outcomes_and_phase_limits()
    with monkeypatch.context() as patch:
        _check_preparation_timeout(patch)
    _check_outcomes_are_the_internal_boundary(monkeypatch)
    _check_prepared_factory_owns_state_and_input()
    _check_prepared_source_options_and_lines_are_reused()
    _check_prepared_dialect_validates_distinct_options_once()
    _check_preparation_consumes_source_once_and_keeps_fresh_invocations()
    _check_prepared_isolation_preserves_the_same_observation()
    _check_prepared_failures_retain_partial_observations()
    _check_preparation_resets_seeded_randomness_for_each_invocation()
    with monkeypatch.context() as paths:
        _check_relative_source_precedes_dialect_callbacks(tmp_path, paths)


@pytest.mark.parametrize("max_steps", [None, 2])
@pytest.mark.parametrize("block", ["binding", "read"])
def test_prepared_stdin_acquisition_respects_preparation_deadline(
    monkeypatch, max_steps, block
) -> None:
    from esolangs.runtime import _acquire, _isolated

    declaration = LANGUAGES[REFERENCE]
    runtime = replace(
        declaration.runtime, reproducible_seed=declaration.runtime.reproducible_seed + 1
    )
    api = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(REFERENCE)
    prepared = api.prepare(",.")
    started, release = Event(), Event()
    threads, bindings, reads = [], [], []
    reader_binding: ContextVar[str] = ContextVar("reader_binding")

    def capture_thread(*args, **kwargs):
        thread = Thread(*args, **kwargs)
        threads.append(thread)
        return thread

    def wait():
        started.set()
        assert release.wait(3)

    def launch(*_args, **_kwargs):
        pytest.fail("prepared stdin acquisition launched a worker")

    class Input:
        @property
        def read(self):
            value = "ABC"[len(bindings)]
            bindings.append(value)
            reader_binding.set(value)
            if value == "A" and block == "binding":
                wait()

            def consume():
                assert reader_binding.get() == value
                reads.append(value)
                if value == "A" and block == "read":
                    wait()
                return value

            return consume

    monkeypatch.setattr(_acquire, "Thread", capture_thread)
    monkeypatch.setattr(_isolated, "_launch", launch)
    stdin = Input()
    limits = esolangs.ExecutionLimits(preparation_timeout=0.2, max_steps=max_steps)
    try:
        outcome = prepared.execute(stdin=stdin, limits=limits)
        assert started.is_set()
        assert not release.is_set()
        assert outcome.bound == "preparation_timeout"
        assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
    finally:
        release.set()
        for thread in threads:
            thread.join(4)
    assert all(not thread.is_alive() for thread in threads)
    assert reads == (["A"] if block == "read" else [])

    result = prepared.run(stdin=stdin, limits=replace(limits, preparation_timeout=2))
    assert result.output == "B"
    assert result.input_reads == 1
    assert bindings == ["A", "B"]
    assert reads == (["A", "B"] if block == "read" else ["B"])


def test_prepared_input_binding_and_read_share_deadline(monkeypatch) -> None:
    from esolangs.runtime import _acquire, _input, _prepared

    prepared = esolangs.Language(REFERENCE).prepare(",.")
    stdin = StringIO("A")
    timeline = [monotonic()]
    resolve = _prepared.runtime_hook

    def delayed_runner(*args):
        timeline[0] += 2
        return resolve(*args)

    monkeypatch.setattr(_acquire, "monotonic", lambda: timeline[0])
    monkeypatch.setattr(_prepared, "runtime_hook", delayed_runner)
    outcome = prepared.execute(
        stdin=stdin, limits=esolangs.ExecutionLimits(preparation_timeout=1)
    )
    assert outcome.bound == "preparation_timeout"
    assert stdin.tell() == 0

    monkeypatch.setattr(_prepared, "runtime_hook", resolve)
    decode = _input._decode_input

    def delayed_decode(raw):
        timeline[0] += 2
        return decode(raw)

    monkeypatch.setattr(_input, "_decode_input", delayed_decode)
    encoded = "é".encode()
    for max_steps in (None, 2):
        limits = esolangs.ExecutionLimits(preparation_timeout=1, max_steps=max_steps)
        for binary in (encoded, BytesIO(encoded)):
            stopped = prepared.execute(stdin=binary, limits=limits)
            assert stopped.bound == "preparation_timeout"
            assert stopped.observation == esolangs.ExecutionResult("", None, None, None)
        for binary in (encoded, BytesIO(encoded)):
            ready = prepared.run(
                stdin=binary, limits=replace(limits, preparation_timeout=3)
            )
            assert (ready.output, ready.input_reads) == ("é", 1)
        ready = prepared.run(
            stdin="é", limits=replace(limits, preparation_timeout=1e-30)
        )
        assert ready.output == "é"

    monkeypatch.setattr(_input, "_decode_input", decode)
    _check_utf8_chunk_cancellation(monkeypatch, prepared)


def _check_utf8_chunk_cancellation(monkeypatch, prepared) -> None:
    from esolangs.runtime import _acquire, _files, _isolated

    timeline = [monotonic()]
    chunks = []
    readers = []
    decode = _files.utf_8_decode

    def clock():
        return timeline[0]

    def decode_first_block(value, *options):
        chunks.append(value)
        result = decode(value, *options)
        timeline[0] += 2
        return result

    def record_thread(*args, **kwargs):
        reader = Thread(*args, **kwargs)
        readers.append(reader)
        return reader

    def refuse_launch(*_args, **_kwargs):
        pytest.fail("expired stdin decoding launched a worker")

    for module in (_acquire, _files, _isolated):
        monkeypatch.setattr(module, "monotonic", clock)
    monkeypatch.setattr(_files, "_BLOCK", 8)
    monkeypatch.setattr(_files, "utf_8_decode", decode_first_block)
    monkeypatch.setattr(_acquire, "Thread", record_thread)
    monkeypatch.setattr(_isolated, "_launch", refuse_launch)

    api = esolangs.Language(REFERENCE)
    encoded = ("a" * 7 + "é😀" * 3).encode()
    limits = esolangs.ExecutionLimits(preparation_timeout=1, max_steps=2)
    for run in (prepared.execute, lambda **options: api.execute(",.", **options)):
        for stdin in (encoded, BytesIO(encoded)):
            try:
                stopped = run(stdin=stdin, limits=limits)
            finally:
                for reader in readers:
                    reader.join(2)
                    assert not reader.is_alive()
            assert stopped.bound == "preparation_timeout"
            assert stopped.observation == esolangs.ExecutionResult("", None, None, None)
            assert chunks == [encoded[:8]]
            chunks.clear()
            readers.clear()


def _check_uniform_outcomes_and_phase_limits():
    api = esolangs.Language(REFERENCE)
    for options in (
        {},
        {"limits": esolangs.ExecutionLimits(max_steps=10)},
        {"isolated": True},
    ):
        completed = api.execute(",+.", stdin="A", **options)
        assert completed.status == "completed"
        assert completed.unwrap().output == "B"
        assert completed.observation.input_position == 1
        failed = api.execute(".,", **options)
        assert failed.status == "input_exhausted"
        assert failed.observation.output == "\x00"
        assert failed.observation.input_past_end == 1
        assert failed.observation.completion is None
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            failed.unwrap()
        assert caught.value is failed.error

    class Unread:
        def read(self):
            raise AssertionError("rejected options consumed stdin")

    for options in (
        {},
        {"limits": esolangs.ExecutionLimits(max_steps=10)},
        {"isolated": True},
    ):
        rejected = api.execute(",.", stdin=Unread(), seed=0, **options)
        assert rejected.status == "rejected"
        assert rejected.observation.completion is None
    prepared = api.prepare("+[]")
    stopped = prepared.execute(limits=esolangs.ExecutionLimits(max_steps=3))
    assert stopped.status == "limit"
    assert stopped.bound == "max_steps"
    assert stopped.observation.steps == 3
    for isolated in (False, True):
        stopped = prepared.execute(
            isolated=isolated,
            limits=esolangs.ExecutionLimits(
                execution_timeout=0.01, total_timeout=3 if isolated else None
            ),
        )
        assert stopped.status == "limit"
        assert stopped.bound == "execution_timeout"
        assert stopped.observation.completion is None
    from esolangs.operations import execution

    with patch.object(
        execution, "_execute_isolated", wraps=execution._execute_isolated
    ) as worker:
        stopped = prepared.execute(
            limits=esolangs.ExecutionLimits(max_steps=3, execution_timeout=3),
        )
    assert worker.call_args is not None
    assert worker.call_args.kwargs["execution_timeout"] == 3
    assert worker.call_args.kwargs["max_steps"] == 3
    assert stopped.status == "limit"
    assert stopped.bound == "max_steps"
    assert stopped.observation.steps == 3
    stopped = prepared.execute(
        limits=esolangs.ExecutionLimits(max_steps=10**9, execution_timeout=0.01),
    )
    assert stopped.status == "limit"
    assert stopped.bound == "execution_timeout"
    assert stopped.observation.completion is None
    with ThreadPoolExecutor(max_workers=1) as threads:
        stopped = threads.submit(
            prepared.execute,
            limits=esolangs.ExecutionLimits(execution_timeout=0.01, total_timeout=3),
        ).result(timeout=5)
    assert stopped.status == "limit"
    assert stopped.bound == "execution_timeout"
    assert stopped.observation.completion is None
    stopped = prepared.execute(limits=esolangs.ExecutionLimits(total_timeout=0.02))
    assert stopped.status == "limit"
    assert stopped.bound == "total_timeout"
    rejected = api.execute("[")
    assert rejected.status == "rejected"
    assert rejected.observation.completion is None
    for kwargs in (
        {"max_steps": True},
        {"max_output": -1},
        {"max_memory": 0},
        {"max_memory": -1},
        {"total_timeout": float("inf")},
        {"execution_timeout": 0},
        {"preparation_timeout": 0},
    ):
        # Each names its own field; all three timeouts said "timeout".
        with pytest.raises(esolangs.ArgumentError, match=f"^{next(iter(kwargs))} "):
            esolangs.ExecutionLimits(**kwargs)
    # run said "non-negative" for -1 while refusing 0.
    with pytest.raises(esolangs.ArgumentError, match="max_memory must be a positive"):
        esolangs.run(
            REFERENCE,
            "+",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_memory=-1),
        )
    with pytest.raises(esolangs.ArgumentError, match="completion evidence"):
        esolangs.ExecutionOutcome("completed", esolangs.ExecutionResult("", 0, 0, 0))


def _check_preparation_timeout(monkeypatch):
    from threading import Event

    from esolangs.runtime import _isolated

    api = esolangs.Language(REFERENCE)
    phase_limits = esolangs.ExecutionLimits(preparation_timeout=1, total_timeout=4)
    for steps in (None, 10):
        limits = replace(phase_limits, max_steps=steps)
        assert api.execute(",+.", stdin="A", limits=limits).unwrap().output == "B"
    prepared = api.prepare(",+.")
    tiny_budget = esolangs.ExecutionLimits(preparation_timeout=0.001)
    assert prepared.execute(stdin="A", limits=tiny_budget).unwrap().output == "B"

    release = Event()

    class Blocked:
        def read(self):
            release.wait()
            return "+."

    try:
        stopped = api.execute(Blocked(), limits=tiny_budget)
    finally:
        release.set()
    assert stopped.bound == "preparation_timeout"
    assert stopped.observation.steps is None

    spawn = _isolated.subprocess.Popen
    children = []

    def slow_parser(argv, **options):
        patch = (
            "from time import sleep; "
            "from esolangs.runtime import _prepared; "
            "_prepared.prepare_program = lambda *a, **kw: sleep(10); "
        )
        child = spawn([*argv[:-1], patch + argv[-1]], **options)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", slow_parser)
    stopped = api.execute("+.", limits=phase_limits)
    assert stopped.bound == "preparation_timeout"
    assert stopped.observation.output == ""
    assert len(children) == 1
    assert children[0].poll() is not None
    stopped = api.execute("+.", limits=replace(phase_limits, total_timeout=0.1))
    assert stopped.bound == "total_timeout"


def _check_outcomes_are_the_internal_boundary(monkeypatch):
    from esolangs.operations import execution
    from esolangs.runtime import _isolated

    def refuse_legacy_run(*_args, **_kwargs):
        raise AssertionError("execute used the raising result adapter")

    with monkeypatch.context() as patch:
        patch.setattr(execution, "run", refuse_legacy_run)
        api = esolangs.Language(REFERENCE)
        for options in ({}, {"limits": esolangs.ExecutionLimits(max_steps=10)}):
            assert api.execute(",+.", stdin="A", **options).unwrap().output == "B"
            assert api.execute(".,", **options).status == "input_exhausted"
        # The real worker runs the same primitive; direct serving is covered
        # by the worker protocol tests, without this parent's monkeypatches.
        assert api.execute(",+.", stdin="A", isolated=True).unwrap().output == "B"

    fault = esolangs.HaltError("same fault", hint="retain this note")
    observed = esolangs.ExecutionResult("prefix", 1, 1, 0, steps=2)
    fault.observation, fault.partial_output = observed, observed.output
    from esolangs.outcomes import _failed_outcome

    failed = _failed_outcome(fault)
    assert failed.error is fault
    assert failed.observation is observed
    assert failed.status == "fault"
    with pytest.raises(esolangs.HaltError) as caught:
        failed.unwrap()
    assert caught.value is fault
    assert "retain this note" in fault.__notes__[0]
    response = _isolated._decode_outcome('{"output":"prefix"}\n', expired=True)
    assert response.status == "limit"
    assert response.observation == esolangs.ExecutionResult("prefix", None, None, None)
    assert response.observation.completion is None
    assert response.error.observation is None


@pytest.mark.medium
def test_longest_execution_timeout_leaves_time_for_worker_startup() -> None:
    from esolangs.runtime._validate import _TIMEOUT_CEILING

    limits = esolangs.ExecutionLimits(execution_timeout=_TIMEOUT_CEILING)
    assert esolangs.run(REFERENCE, "+.", limits=limits).output == "\x01"
    with pytest.raises(esolangs.ArgumentError, match="total_timeout must be at most"):
        esolangs.ExecutionLimits(total_timeout=_TIMEOUT_CEILING + 1)


@pytest.mark.medium
def test_an_execution_budget_outlasts_the_default_total() -> None:
    """An implicit total includes startup time beyond the execution budget."""
    from esolangs.operations import execution
    from esolangs.runtime import _isolated

    with patch.object(execution, "_ISOLATED_TIMEOUT", 3.0):
        total = execution.default_total(None, 4.0)
        assert total == 7.0
        explicit = execution.default_total(3.0, 4.0)
    for deadline, bound in ((total, "execution_timeout"), (explicit, "total_timeout")):
        records = Queue()
        records.put('{"prepared":true}\n')
        with patch.object(_isolated, "monotonic", side_effect=(0.0, 0.0, 5.0)):
            stopped = _isolated._read_worker_output(None, records, deadline, None, 4.0)
        assert stopped.bound == bound

    source = "+.[]"
    api = esolangs.Language(REFERENCE)
    limits = esolangs.ExecutionLimits(execution_timeout=0.5)
    with patch.object(execution, "_ISOLATED_TIMEOUT", 1.0):
        stopped = api.execute(source, limits=limits)
        assert stopped.bound == "execution_timeout"
        assert stopped.observation.output == "\x01"
        with pytest.raises(esolangs.ExecutionTimeoutError, match=r"0\.5-second") as e:
            esolangs.run(REFERENCE, source, limits=limits, isolated=True)
        assert e.value.bound == "execution_timeout"
        assert e.value.partial_output == "\x01"
        with pytest.raises(esolangs.ExecutionTimeoutError, match=r"1\.0-second") as e:
            esolangs.run(REFERENCE, source, isolated=True)
        assert e.value.bound == "total_timeout"
        assert e.value.partial_output == "\x01"
    with pytest.raises(esolangs.ExecutionTimeoutError, match=r"0\.5-second") as e:
        api.prepare(source).run(limits=limits)
    assert e.value.bound == "execution_timeout"
    assert e.value.partial_output == "\x01"
