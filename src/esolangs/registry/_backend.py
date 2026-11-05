"""Operational Boolean generation and layout capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any

from esolangs.generation.helpers import TEMPLATE_CHAR, Setters, check_setters
from esolangs.registry._functions import FunctionRef
from esolangs.runtime._program import Program

# The width-aware generators also take ``width``, hence ``...``.
Generator = Callable[..., Program]


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
    #: Whether text is unfilled, where ``char`` is also source.
    unfilled: Callable[[str], bool] | None = None

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


class _Unset:
    pass


_UNSET = _Unset()


@dataclass(frozen=True, init=False)
class BooleanBackend:
    """Generator, accepted tables, input binding and source layout rules."""

    entrypoint: Generator
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
    same_layout: Callable[[str, str, Callable[[int], Any]], bool] | None = None
    #: ``balance(table, default)``: the squarest layout a reflow cannot find.
    balance: Callable[..., Any] | None = None

    def __init__(
        self,
        entrypoint: Generator | _Unset | None = _UNSET,
        template: TemplateSpec | None = None,
        max_inputs: int | None = None,
        restrictions: str = "",
        shape: Shape = Shape.TREE,
        grid: bool = False,  # noqa: FBT001, FBT002
        wrap: Callable[[str, int], str] | None = None,
        wrap_multiline: bool = False,  # noqa: FBT001, FBT002
        wrap_balance: Callable[[str], str] | None = None,
        no_wrap: str = "",
        same_layout: Callable[[str, str, Callable[[int], Any]], bool] | None = None,
        balance: Callable[..., Any] | None = None,
        *,
        generate: Generator | _Unset | None = _UNSET,
    ) -> None:
        """Accept the legacy alias, including ``replace(backend, generate=...)``."""
        # Keep the former dataclass positional arguments, including its flags.
        # replace() supplies the old entrypoint too; the explicit alias wins.
        selected = entrypoint if isinstance(generate, _Unset) else generate
        if isinstance(selected, _Unset):
            raise TypeError("a Boolean backend requires a generator argument")
        values = locals()
        for field in fields(BooleanBackend):
            value = selected if field.name == "entrypoint" else values[field.name]
            object.__setattr__(self, field.name, value)
        self.__post_init__()

    @property
    def generator_name(self) -> str:
        """Return the declared export name without loading its implementation."""
        return self.entrypoint.__name__

    @property
    def generate(self) -> Generator:
        """Load only the selected generator; ordinary callables remain unchanged."""
        entrypoint = self.entrypoint
        return entrypoint.load() if isinstance(entrypoint, FunctionRef) else entrypoint

    def __post_init__(self) -> None:
        """Require a generator and consistent wrapping declarations."""
        if not callable(self.entrypoint):
            raise ValueError("a Boolean backend requires a callable generator")
        if self.wrap is not None and self.no_wrap:
            raise ValueError("wrap and no_wrap exclude each other")
