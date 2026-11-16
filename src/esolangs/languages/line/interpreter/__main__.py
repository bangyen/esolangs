"""Run a Line source file through the shared interpreter entry point."""

from esolangs.languages.line.interpreter import run
from esolangs.runtime._entry import raster_script_main

if __name__ == "__main__":
    raster_script_main("Line", run)
