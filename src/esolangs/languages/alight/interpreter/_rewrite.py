"""Alight alias rewriting: swap one list for another through any value."""

from typing import overload

from esolangs.languages.alight.interpreter._parse import (
    _NODE_TYPES,
    _Bin,
    _Call,
    _Expr,
    _List,
    _Not,
    _Num,
    _SpecialNode,
    _Val,
    _Value,
    _Var,
)


#: ``_replace`` preserves its input's type: it returns the input with ``old``
#: swapped for ``updated``.  The overloads carry that to callers; the
#: implementation below works in ``object``.
@overload
def _replace(
    root: dict[str, _Value],
    old: list[_Value],
    updated: list[_Value],
    memo: dict[int, object],
) -> dict[str, _Value]: ...


@overload
def _replace[T](
    root: T, old: list[_Value], updated: list[_Value], memo: dict[int, object]
) -> T: ...


def _replace(
    root: object,
    old: list[_Value],
    updated: list[_Value],
    memo: dict[int, object],
) -> object:
    """Return ``root`` with every occurrence of ``old`` replaced by ``updated``.

    A structural copy that preserves sharing: containers not holding ``old``
    are returned unchanged, and a rebuilt container is reused through
    ``memo`` wherever the original was aliased.  Cyclic lists, which the
    language can build, are pre-registered so the walk terminates; a rebuilt
    cycle keeps pointing at the original, which no registry-corpus program
    reaches.

    AST nodes are rebuilt as their own type, so a pending expression that
    referenced ``old`` stays a typed tree, not plain tuples.
    """
    if root is old:
        return updated
    if not isinstance(root, list | tuple | dict):
        return root
    key = id(root)
    if key in memo:
        return memo[key]
    if isinstance(root, dict):
        rebuilt: dict[object, object] = {}
        memo[key] = rebuilt
        changed = False
        for name, value in root.items():
            replaced = _replace(value, old, updated, memo)
            rebuilt[name] = replaced
            changed = changed or replaced is not value
        if changed:
            return rebuilt
        memo[key] = root
        return root
    if isinstance(root, _NODE_TYPES):
        return _replace_node(root, old, updated, memo)
    if isinstance(root, tuple):
        items = tuple(_replace(item, old, updated, memo) for item in root)
        changed = any(a is not b for a, b in zip(items, root, strict=True))
        memo[key] = items if changed else root
        return memo[key]
    rebuilt_list: list[object] = []
    memo[key] = rebuilt_list
    changed = False
    for item in root:
        replaced = _replace(item, old, updated, memo)
        rebuilt_list.append(replaced)
        changed = changed or replaced is not item
    if not changed:
        memo[key] = root
        return root
    return rebuilt_list


def _replace_node(
    root: _Expr, old: list[_Value], updated: list[_Value], memo: dict[int, object]
) -> _Expr:
    """Rebuild an AST node with ``old`` replaced by ``updated`` inside.

    Numbers, variables, and specials hold no list; every other node is
    rebuilt field by field, returning the original node when nothing inside
    changed.  Nodes are immutable trees, so unlike lists they cannot be
    cyclic -- only the values they wrap can, and those go through
    :func:`_replace`.
    """
    key = id(root)
    if isinstance(root, (_Num, _Var, _SpecialNode)):
        memo[key] = root
        return root
    if isinstance(root, _Val):
        value = _replace(root.value, old, updated, memo)
        node: _Expr = root if value is root.value else _Val("val", value)
        memo[key] = node
        return node
    if isinstance(root, _Not):
        operand = _replace(root.operand, old, updated, memo)
        node = root if operand is root.operand else _Not("not", operand)
        memo[key] = node
        return node
    if isinstance(root, _Bin):
        left = _replace(root.left, old, updated, memo)
        right = _replace(root.right, old, updated, memo)
        if left is root.left and right is root.right:
            memo[key] = root
            return root
        node = _Bin("bin", root.op, left, right)
        memo[key] = node
        return node
    if isinstance(root, _List):
        items = [_replace(item, old, updated, memo) for item in root.items]
        if all(new is current for new, current in zip(items, root.items, strict=True)):
            memo[key] = root
            return root
        node = _List("list", items)
        memo[key] = node
        return node
    args = [_replace(arg, old, updated, memo) for arg in root.args]
    if all(new is current for new, current in zip(args, root.args, strict=True)):
        memo[key] = root
        return root
    node = _Call("call", root.name, args)
    memo[key] = node
    return node
