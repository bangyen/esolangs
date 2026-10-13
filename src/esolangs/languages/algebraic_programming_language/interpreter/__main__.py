"""Run a source file through the shared interpreter entry point."""

from esolangs.runtime._entry import script_main

from . import run

if __name__ == "__main__":
    script_main(run)
