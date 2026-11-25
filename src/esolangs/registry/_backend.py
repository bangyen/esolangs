"""Operational Boolean generation and layout capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import StrEnum
from reprlib import recursive_repr

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
class BooleanBackend:
    """Generator, accepted tables, input binding and source layout rules."""

    entrypoint: OperationRef[GenerationRequest, GeneratedProgram] | Generator
    layout_width: bool = False
    template: TemplateSpec | None = None
    max_inputs: int | None = None
    restrictions: str = ""
    shape: Shape = Shape.TREE
    #: Grid cost is rows times the longest row; default builds race by area.
    grid: bool = False
    #: ``wrap(program, width)``: a meaning-preserving reflow, if one exists.
    wrap: Callable[[str, int], str] | None = None
    wrap_multiline: bool = False
    #: ``wrap_balance(program)``: a language-owned source reflow for balance.
    wrap_balance: Callable[[str], str] | None = None
    #: Why ``wrap`` is absent, when a break would change the program.
    no_wrap: str = ""
    #: Whether two rendered templates have equivalent source layout.
    same_layout: Callable[[str, str, Callable[[int], str]], bool] | None = None
    #: ``balance(table, default)``: the squarest layout a reflow cannot find.
    balance: OperationRef[BalanceRequest, GeneratedProgram] | Balancer | None = None
    #: Native arity check, shared with direct generator calls for its diagnostic.
    arity_guard: Callable[[int], None] | None = None
    #: The generator can select balanced layouts in one request.
    layout_balance: bool = False

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
            self.balance, FunctionRef
        ):
            raise TypeError("backend operations require typed request references")
        if not callable(self.entrypoint):
            raise ValueError("a Boolean backend requires a callable generator")
        if self.max_inputs is not None and (
            type(self.max_inputs) is not int or self.max_inputs < 1
        ):
            raise ValueError("max_inputs must be a positive integer")
        if self.wrap is not None and self.no_wrap:
            raise ValueError("wrap and no_wrap exclude each other")
