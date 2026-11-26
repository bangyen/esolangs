"""Operational Boolean generation and layout capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from reprlib import recursive_repr
from typing import Any, Literal

from esolangs._bindings import TEMPLATE_CHAR, Setters, check_setters
from esolangs.exceptions import GeneratorCapError
from esolangs.generation.requests import (
    BalanceRequest,
    GeneratedProgram,
    GenerationRequest,
    call_backend,
)
from esolangs.registry._functions import FunctionRef
from esolangs.registry._operations import OperationRef
from esolangs.runtime._validate import _argument_repr
from esolangs.runtime.memory import repr_record

Generator = Callable[[GenerationRequest], GeneratedProgram]
Balancer = Callable[[BalanceRequest], GeneratedProgram]


class Shape(StrEnum):
    """How a backend's program grows with its truth table."""

    #: A decision tree: a table that ignores an input folds that subtree.
    TREE = "tree"
    #: A sum over the essential inputs: a degenerate table is a smaller one.
    REDUCING = "reducing"
    #: Branch-free: every table of one arity renders to about one length.
    LOOKUP = "lookup"


@dataclass(frozen=True)
class TemplateSpec:
    """How a backend embeds inputs independently of its examples."""

    pair: tuple[str, str] | None = None
    setters: Callable[[str, int], Setters] | None = None
    char: str = TEMPLATE_CHAR

    def __post_init__(self) -> None:
        """Require one binding rule and a single placeholder character."""
        if (self.pair is None) == (self.setters is None):
            raise ValueError("exactly one of pair and setters")
        if len(self.char) != 1:
            raise ValueError("template char must be one character")
        if self.pair is not None:
            check_setters((self.pair,))

    def bindings(self, template: str, inputs: int) -> Setters:
        """Return ordered zero/one substitutions for this template."""
        if self.pair is not None:
            return (self.pair,) * inputs
        assert self.setters is not None
        return self.setters(template, inputs)


@dataclass(frozen=True)
class SourceLayout:
    """Layout operations applied to emitted source."""

    wrap: Callable[[str, int], str] | None = None
    wrap_multiline: bool = False
    wrap_balance: Callable[[str], str] | None = None
    no_wrap: str = ""
    same_layout: Callable[[str, str, Callable[[int], str]], bool] | None = None
    balance: OperationRef[BalanceRequest, GeneratedProgram] | Balancer | None = None
    layout_balance: bool | OperationRef[GenerationRequest, GeneratedProgram] = False
    grid: bool = False

    @property
    def width_effect(self) -> Literal["layout", "wrap", "none"]:
        """Describe how a width request is applied."""
        if self.constructs_width:
            return "layout"
        return "wrap" if self.wrap is not None else "none"

    @property
    def constructs_width(self) -> bool:
        """Whether the generator needs the requested width before emission."""
        return False


@dataclass(frozen=True)
class ConstructedLayout(SourceLayout):
    """The generator places instructions for a requested width."""

    @property
    def constructs_width(self) -> bool:
        """Pass the width to the construction."""
        return True


@dataclass(frozen=True, init=False)
class BooleanBackend:
    """Generator, accepted tables, input binding and source layout rules."""

    entrypoint: OperationRef[GenerationRequest, GeneratedProgram] | Generator
    template: TemplateSpec | None
    max_inputs: int | None
    restrictions: str
    shape: Shape
    arity_guard: Callable[[int], None] | None
    layout: SourceLayout

    def __init__(
        self,
        entrypoint: OperationRef[GenerationRequest, GeneratedProgram] | Generator,
        layout_width: bool | None = None,  # noqa: FBT001 - legacy positional argument
        template: TemplateSpec | None = None,
        max_inputs: int | None = None,
        restrictions: str = "",
        shape: Shape = Shape.TREE,
        *positional_layout: Any,
        arity_guard: Callable[[int], None] | None = None,
        layout: SourceLayout | None = None,
        **layout_options: Any,
    ) -> None:
        """Accept legacy layout keywords when adapting older catalog declarations."""
        if positional_layout:
            # Positional order of the original backend dataclass.
            names = (
                "grid",
                "wrap",
                "wrap_multiline",
                "wrap_balance",
                "no_wrap",
                "same_layout",
                "balance",
                "arity_guard",
                "layout_balance",
            )
            if len(positional_layout) > len(names):
                raise TypeError("too many positional backend arguments")
            for key, value in zip(names, positional_layout, strict=False):
                if key in layout_options or (
                    key == "arity_guard" and arity_guard is not None
                ):
                    raise TypeError(f"multiple values for {key}")
                if key == "arity_guard":
                    arity_guard = value
                else:
                    layout_options[key] = value
        policy = SourceLayout() if layout is None else layout
        if layout_width is not None and layout_width != policy.constructs_width:
            kind = ConstructedLayout if layout_width else SourceLayout
            policy = kind(**{f.name: getattr(policy, f.name) for f in fields(policy)})
        if layout_options:
            policy = replace(policy, **layout_options)
        object.__setattr__(self, "entrypoint", entrypoint)
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "max_inputs", max_inputs)
        object.__setattr__(self, "restrictions", restrictions)
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "arity_guard", arity_guard)
        object.__setattr__(self, "layout", policy)
        self.__post_init__()

    @property
    def layout_width(self) -> bool:
        """Whether this backend constructs to a requested width."""
        return self.layout.constructs_width

    @property
    def wrap(self) -> Callable[[str, int], str] | None:
        """Expose the declared layout option to older catalogs."""
        return self.layout.wrap

    @property
    def wrap_multiline(self) -> bool:
        """Expose the declared layout option to older catalogs."""
        return self.layout.wrap_multiline

    @property
    def wrap_balance(self) -> Callable[[str], str] | None:
        """Expose the declared layout option to older catalogs."""
        return self.layout.wrap_balance

    @property
    def no_wrap(self) -> str:
        """Expose the declared layout option to older catalogs."""
        return self.layout.no_wrap

    @property
    def same_layout(self) -> Callable[[str, str, Callable[[int], str]], bool] | None:
        """Expose the declared layout option to older catalogs."""
        return self.layout.same_layout

    @property
    def balance(
        self,
    ) -> OperationRef[BalanceRequest, GeneratedProgram] | Balancer | None:
        """Expose the declared layout option to older catalogs."""
        return self.layout.balance

    @property
    def layout_balance(
        self,
    ) -> bool | OperationRef[GenerationRequest, GeneratedProgram]:
        """Expose the declared layout option to older catalogs."""
        return self.layout.layout_balance

    @property
    def grid(self) -> bool:
        """Expose the declared layout option to older catalogs."""
        return self.layout.grid

    @property
    def balances_natively(self) -> bool:
        """Whether this entrypoint accepts a native balance request."""
        native = self.layout.layout_balance
        return native if isinstance(native, bool) else native == self.entrypoint

    @recursive_repr()
    def __repr__(self) -> str:
        return repr_record(self, fields(BooleanBackend))

    def check_arity(self, language: str, inputs: int) -> None:
        """Enforce the catalog cap before loading or calling its generator."""
        cap = self.max_inputs
        if cap is None or inputs <= cap:
            return
        if self.arity_guard is not None:
            call_backend(self.arity_guard, inputs)
        raise GeneratorCapError(
            f"{language} declares max-inputs={_argument_repr(cap)}, "
            f"got {_argument_repr(inputs)} inputs"
        )

    @property
    def generate(self) -> Generator:
        """Load only the selected generator; ordinary callables remain unchanged."""
        entrypoint = self.entrypoint
        return entrypoint.load() if isinstance(entrypoint, OperationRef) else entrypoint

    def __post_init__(self) -> None:
        """Require a generator and consistent wrapping declarations."""
        if isinstance(self.entrypoint, FunctionRef) or isinstance(
            self.layout.balance, FunctionRef
        ):
            raise TypeError("backend operations require typed request references")
        if not callable(self.entrypoint):
            raise ValueError("a Boolean backend requires a callable generator")
        if self.max_inputs is not None and (
            type(self.max_inputs) is not int or self.max_inputs < 1
        ):
            raise ValueError("max_inputs must be a positive integer")
        if self.layout.wrap is not None and self.layout.no_wrap:
            raise ValueError("wrap and no_wrap exclude each other")
