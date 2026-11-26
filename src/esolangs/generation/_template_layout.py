"""Bind and reflow templates with explicit input slots."""

from collections.abc import Callable
from dataclasses import replace

from esolangs.artifacts import TemplateArtifact, TemplateBindings, _freeze_span
from esolangs.exceptions import ProgramError, TemplateError
from esolangs.generation._template_replay import TemplateProbes
from esolangs.generation.requests import call_backend
from esolangs.generation.template import TemplateLayout
from esolangs.generation.wrap import (
    TokenWrapper,
    balance_character_slots,
    can_balance_template,
    can_wrap_template,
    wrap_character_slots,
)
from esolangs.registry import render_template, template_char
from esolangs.registry._catalog import Catalog
from esolangs.runtime._validate import _has_backing_type
from esolangs.settings import DialectSettings


def _structured_template(
    layout: TemplateLayout,
    language_id: str,
    name: str,
    inputs: int,
    settings: DialectSettings | None,
    catalog: Catalog,
    *,
    probes: TemplateProbes | None = None,
    generation_width: int | None = None,
) -> TemplateArtifact:
    """Preserve the backend's slot positions alongside its rendered source."""
    if not _has_backing_type(layout, TemplateLayout):
        raise ProgramError(f"{name}'s template wrapper did not return slots")
    text = layout.source
    if not _has_backing_type(text, str):
        raise TemplateError("template needs text source and TemplateBindings")
    # A backend-supplied str subclass may carry data its own setter reads.
    if type(text) is not str:
        probes = None
    key = text, inputs
    bindings = probes.bindings.get(key) if probes is not None else None
    if layout.setters:
        char = template_char(language_id, catalog=catalog)
        if char is None:
            raise TemplateError(f"{name} has no template declaration")
        bindings = TemplateBindings(char=char, setters=layout.setters)
        if bindings.inputs != inputs:
            raise ProgramError(f"{name}'s template must bind all {inputs} inputs")
    elif bindings is None:
        text, char, pairs = call_backend(
            render_template, language_id, text, inputs, catalog=catalog
        )
        bindings = TemplateBindings(char=char, setters=pairs)
        if bindings.inputs != inputs:
            raise ProgramError(f"{name}'s template must bind all {inputs} inputs")
        if probes is not None:
            probes.bindings[key] = bindings
    return TemplateArtifact(
        text,
        name,
        bindings,
        settings=settings,
        spans=layout.spans,
        generation_width=generation_width,
    )


def _check_reflow_layout(layout: TemplateLayout) -> TemplateLayout:
    """Validate raw offsets before a wrapper uses them to slice source."""
    if not _has_backing_type(layout.source, str):
        raise TemplateError("template needs text source and TemplateBindings")
    if not _has_backing_type(layout.spans, tuple):
        raise TemplateError("template needs one span per input")
    position, size = 0, str.__len__(layout.source)
    spans = []
    try:
        for span in tuple.__iter__(layout.spans):
            start, end = _freeze_span(span)
            if type(start) is not int or type(end) is not int:
                raise ValueError("template spans must be pairs of offsets")
            if not position <= start <= end <= size:
                raise ValueError(f"invalid template span {(start, end)!r}")
            spans.append((start, end))
            position = end
    except ValueError as error:
        raise TemplateError(str(error)) from error
    return TemplateLayout(layout.source, tuple(spans), layout.setters)


def _wrap_template_layout(
    layout: TemplateLayout,
    width: int,
    wrapper: Callable[[str, int], str],
    *,
    name: str,
    char: str,
) -> TemplateLayout:
    """Reflow a generated layout while retaining the input slots."""
    layout = _check_reflow_layout(layout)
    if not can_wrap_template(layout, wrapper):
        raise ProgramError(f"{name} requires a slot-aware wrapper")
    if isinstance(wrapper, TokenWrapper):
        layout = call_backend(
            wrapper.wrap_template,
            layout,
            width,
            char=char,
        )
    else:
        layout = wrap_character_slots(layout, width)
    return layout


def _balance_template(
    template: TemplateArtifact,
    name: str,
    *,
    wrapper: Callable[[str, int], str] | None,
) -> TemplateArtifact:
    """Balance source by moving positional slots with a slot-aware wrapper."""
    layout = TemplateLayout(template.source, template.spans)
    if not can_balance_template(layout, wrapper):
        raise ProgramError(f"{name} requires a slot-aware balancer")
    if isinstance(wrapper, TokenWrapper):
        balanced = call_backend(
            wrapper.balance_template, layout, char=template.bindings.char
        )
    else:
        balanced = balance_character_slots(layout)
    if not _has_backing_type(balanced, TemplateLayout):
        raise ProgramError(f"{name}'s template wrapper did not return slots")
    return replace(template, source=balanced.source, spans=balanced.spans)
