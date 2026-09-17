"""Interpreters for esolangs that operate on a 2D grid or beam.

Every program grid is ``grid[row][col]`` with ``row``/``col``,
``d_row``/``d_col`` and headings ``(d_row, d_col)``, rows growing
downward, across every module here and ``tape_based.back``.  ``x``/``y``
was retired because it meant the column in ``flowchart`` but the row in
``laserfuck``; do not bring it back.  ``a_painter_ant`` is the exception:
its ant paints a sparse plane keyed by coordinate with a compass table
(``"e": (1, 0)``), not a program grid, so ``x``/``y`` is what that code is.
"""
