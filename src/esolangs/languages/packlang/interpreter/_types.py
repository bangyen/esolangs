"""Shared type aliases for the Packlang interpreter.

The parser, the store helpers, and the machine all talk about the same
two shapes -- an expression node and the variable store -- which used to
be spelled separately in ``_parse``, ``_values``, and ``__init__``.  The
spellings agreed in meaning (``_Store`` appeared both as
``tuple[_Slot, ...]`` and as the equivalent
``tuple[tuple[str, object], ...]``), so they are unified here rather than
re-chosen; every module imports the canonical alias.
"""

#: One variable: its name and its value.  Arrays hold a tuple of values;
#: scalars a single int.
type _Slot = tuple[str, object]

#: The variable store: a tuple of ``(name, value)`` slots.
type _Store = tuple[_Slot, ...]

#: An expression node: a tag followed by names, literals, or sub-nodes.
#: Heterogeneous by nature, so the slots are narrowed at use by
#: :func:`_node` and :func:`_int` rather than modelled per tag.
type _Expr = tuple[object, ...]
