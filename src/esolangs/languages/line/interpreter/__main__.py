"""Run a Line source file through the shared interpreter entry point."""

from esolangs.runtime._entry import script_main
from esolangs.runtime._source import raster_source

from . import run

if __name__ == "__main__":
    script_main(run, loader=raster_source)
