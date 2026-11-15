"""Run a Line source file through the shared interpreter entry point."""

from esolangs.runtime._entry import raster_script_main

from . import run

if __name__ == "__main__":
    raster_script_main("Line", run)
