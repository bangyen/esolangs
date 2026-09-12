"""Interpreters for esolangs that operate on a 2D grid or beam.

Every module that indexes a *program grid* addresses it as
``grid[row][col]`` and spells its coordinates ``row``/``col``, its deltas
``d_row``/``d_col``, and its headings ``(d_row, d_col)`` with rows growing
downward.  Tuples are built and unpacked in that order throughout, so a
position reads the same way it indexes.  The one convention holds across
``flowchart``, ``circuit_diagram``, ``clockwise``, ``arrowqueue``,
``streetcode``, ``wii2d``, ``dig``, ``cod``, ``super_snusp`` and
``laserfuck``.

Some of these used ``x``/``y`` before, and not all of them agreed on what
``x`` meant: it was the column in ``flowchart`` and ``circuit_diagram``
but the *row* in ``laserfuck``, ``dig`` and ``wii2d``, so the same name
indexed two different axes across the package.  That is the trap the
single convention exists to close; ``x``/``y`` was retired deliberately
and should not come back for a new grid language.

``back`` lives in ``tape_based`` but pads and walks a program grid just
like these, and follows the same convention.

``a_painter_ant`` is the one exception, and it is not a program grid.  Its
ant paints an unbounded sparse plane keyed by coordinate, with an origin
and negative coordinates in every direction, and nothing indexes a line of
program text.  Its moves are a compass table (``"e": (1, 0)``) and its
rendering walks a computed bounding box, so ``x``/``y`` describe what that
code actually is; row/col there would name axes the language does not
have.
"""
