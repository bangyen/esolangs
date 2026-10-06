"""Grid geometry shared by the LaserFuck generators."""

# The leftmost column code may use.  Columns 0..2 carry the funnel (``|o^``
# and the ``_`` beneath it), which every initial heading is routed through
# at startup, so code there would drop the beam back onto the funnel and
# start the program over.
MARGIN = 3
