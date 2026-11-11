"""Operational Boolean generation and layout capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from esolangs.generation.helpers import TEMPLATE_CHAR, Setters, check_setters
from esolangs.generation.requests import (
    BalanceRequest,
    GeneratedProgram,
    GenerationRequest,
)
from esolangs.registry._functions import FunctionRef
from esolangs.registry._operations import OperationRef

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
    #: Whether a template matches a ``layout(width)`` of the default build;
    #: default: equal up to wrapping newlines.
    same_layout: Callable[[str, str, Callable[[int], str]], bool] | None = None
    #: ``balance(table, default)``: the squarest layout a reflow cannot find.
    balance: OperationRef[BalanceRequest, GeneratedProgram] | Balancer | None = None

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
        if self.wrap is not None and self.no_wrap:
            raise ValueError("wrap and no_wrap exclude each other")
