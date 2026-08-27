"""Interpreters for esolangs that operate on a 2D grid or beam.

Two coordinate conventions live here, one per module and never mixed
within one.  Which a module uses follows its language, not a house rule:

* ``x``/``y`` -- ``x`` is the column, ``y`` the row.  Used by the
  geometric languages, where headings are direction vectors and turning
  is Cartesian rotation (``flowchart``'s ``(dx, dy) -> (dy, -dx)``):
  ``flowchart``, ``circuit_diagram``, ``clockwise``, ``arrowqueue``.
* ``row``/``col`` -- Used by the languages whose specs navigate the
  program text by line: ``streetcode``, ``wii2d``, ``dig``, ``cod``,
  ``a_painter_ant``, ``laserfuck``.

When adding a module, pick the convention its wiki page reads in and
stay with it throughout; the hazard is a module that switches midway, or
one that calls the row ``x``.
"""
