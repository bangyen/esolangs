"""Match saved templates against the selected generator's renderings."""

from collections.abc import Callable
from typing import Protocol

from esolangs._bindings import check_setters, validate_spans
from esolangs.artifacts import Artifact, TemplateArtifact, TemplateBindings
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    GeneratorCapError,
    ProgramError,
    TemplateError,
)
from esolangs.generation.requests import (
    GeneratedProgram,
    GenerationRequest,
    call_backend,
)
from esolangs.generation.template import TemplateLayout, layout_fragments
from esolangs.generation.wrap import can_balance_template, can_wrap_template
from esolangs.registry import template_setters
from esolangs.registry._backend import Generator
from esolangs.registry._catalog import Catalog


class _Render(Protocol):
    def __call__(
        self, width: int | None = None, *, balance: bool = False
    ) -> Artifact: ...


class TemplateProbes:
    """Reuse successful backend results within one checked instantiation."""

    def __init__(self) -> None:
        self._sources: dict[GenerationRequest, tuple[Generator, GeneratedProgram]] = {}
        self.bindings: dict[tuple[str, int], TemplateBindings] = {}

    def generate(self, hook: Generator, request: GenerationRequest) -> GeneratedProgram:
        saved = self._sources.get(request)
        if saved is None or saved[0] is not hook:
            saved = hook, call_backend(hook, request)
            self._sources[request] = saved
        return saved[1]

    def matches_bindings(
        self,
        supplied: TemplateBindings,
        text: str,
        *,
        char: str,
        language_id: str,
        catalog: Catalog,
    ) -> bool:
        inputs = len(supplied.setters)
        key = text, inputs
        checked = self.bindings.get(key)
        if checked is None:
            try:
                expected = check_setters(
                    template_setters(language_id, text, inputs, catalog=catalog)
                )
            except EsolangError:
                raise
            except ValueError:
                # A setter extractor can reject a caller-supplied source layout.
                return False
            checked = TemplateBindings(char=char, setters=expected)
            self.bindings[key] = checked
        return supplied.setters == checked.setters


def _template_text(template: TemplateArtifact, char: str) -> str | None:
    """Put the stored slots in the generator's spelling for comparison."""
    if template.bindings.char == char:
        return template.source
    spans = template.spans
    text = layout_fragments(
        TemplateLayout(template.source, spans).fragments(), char=char
    ).source
    try:
        validate_spans(text, char, template.bindings.setters, spans)
    except ValueError:
        return None
    return text


def _same_generated_template(
    rendered: Artifact, template: TemplateArtifact, text: str
) -> bool:
    return (
        isinstance(rendered, TemplateArtifact)
        and text == rendered.source
        and template.spans == rendered.spans
        and template.bindings.setters == rendered.bindings.setters
    )


def _check_source_layout(
    matcher: Callable[[str, str, Callable[[int], str]], bool],
    text: str,
    candidate: str,
    layout: Callable[[int], str],
    name: str,
) -> bool:
    matches: object = call_backend(matcher, text, candidate, layout)
    if type(matches) is not bool:
        raise ProgramError(f"{name}'s layout matcher did not return a boolean")
    return matches


def _render_checked_width(
    render: Callable[[int], Artifact], width: int | None, retained: int | None
) -> Artifact | None:
    declared = width if width is not None else retained
    if declared is None:
        return None
    try:
        return render(declared)
    except (ArgumentError, GeneratorCapError):
        # A replacement catalog may no longer render a saved width.
        if width is not None:
            raise
        return None


def matches_template(
    template: TemplateArtifact,
    name: str,
    *,
    width: int | None,
    catalog: Catalog,
    probes: TemplateProbes,
    render: _Render,
) -> bool:
    """Match retained slots and layout against the cached renderings."""
    if template.generation_balance is not None and (
        width is None or width == template.generation_width
    ):
        try:
            rendered = render(
                template.generation_width, balance=template.generation_balance
            )
        except (ArgumentError, GeneratorCapError):
            if width is not None or template.generation_width is None:
                raise
            return False
        if not isinstance(rendered, TemplateArtifact):
            return False
        text = _template_text(template, rendered.bindings.char)
        if text is None:
            return False
        if text == rendered.source:
            return _same_generated_template(rendered, template, text)
        # Edited templates can still use a backend-declared equivalent layout.
        backend = catalog.languages[name].backend
        if backend is None or backend.layout.same_layout is None:
            return False
    return _match_candidate_layouts(
        template, name, width=width, catalog=catalog, probes=probes, render=render
    )


def _match_candidate_layouts(
    template: TemplateArtifact,
    name: str,
    *,
    width: int | None,
    catalog: Catalog,
    probes: TemplateProbes,
    render: _Render,
) -> bool:
    """Try compatible layouts for older records or an explicit width override."""
    backend = catalog.languages[name].backend
    retained = template.generation_width if width is None else None
    try:
        canonical = render()
        default_available = True
    except GeneratorCapError:
        fallback_width = width if width is not None else retained
        if (
            fallback_width is None
            or backend is None
            or not backend.layout.constructs_width
        ):
            raise
        canonical = render(fallback_width)
        default_available = False
    if not isinstance(canonical, TemplateArtifact):
        return False
    bindings = canonical.bindings
    if len(template.bindings.setters) != bindings.inputs:
        return False
    text = _template_text(template, bindings.char)
    if text is None or not probes.matches_bindings(
        template.bindings,
        text,
        char=bindings.char,
        language_id=catalog.languages[name].id,
        catalog=catalog,
    ):
        return False
    plain = canonical.source
    if not default_available:
        return _same_generated_template(canonical, template, text)
    if text == plain:
        return True
    assert backend is not None  # _generate above refuses absent backends
    canonical_layout = TemplateLayout(plain, canonical.spans)
    width_aware = backend.layout.constructs_width or can_wrap_template(
        canonical_layout, backend.layout.wrap
    )

    def layout(width: int) -> str:
        source = render(width).source
        if not isinstance(source, str):
            raise TemplateError("template layouts must return text")
        return source

    candidates = [plain]
    sized = _render_checked_width(render, width, retained) if width_aware else None
    if isinstance(sized, TemplateArtifact):
        if _same_generated_template(sized, template, text):
            return True
        candidates.append(sized.source)

    def matches_balance() -> bool:
        if (
            not backend.balances_natively
            and backend.layout.balance is None
            and (
                backend.layout.wrap_balance is not None
                or not can_balance_template(canonical_layout, backend.layout.wrap)
            )
        ):
            return False
        try:
            balanced = render(balance=True)
        except GeneratorCapError:
            return False
        return _same_generated_template(balanced, template, text)

    matcher = backend.layout.same_layout
    if matcher is not None:
        try:
            if any(
                _check_source_layout(matcher, text, candidate, layout, name)
                for candidate in candidates
            ):
                return True
        except (ArgumentError, GeneratorCapError):
            if matches_balance():
                return True
            raise
    return matches_balance()
