"""Canonical type aliases shared by the Packlang parser, store, and machine."""

#: One variable: its name and its value.
type _Slot = tuple[str, object]

#: The variable store: a tuple of ``(name, value)`` slots.
type _Store = tuple[_Slot, ...]

#: An expression node: a tag followed by names, literals, or sub-nodes.
type _Expr = tuple[object, ...]
