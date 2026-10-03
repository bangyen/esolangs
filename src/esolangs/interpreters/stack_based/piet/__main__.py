"""Run a Piet source file through the shared interpreter entry point."""

from esolangs.interpreters._entry import script_main

from . import load_source, run

if __name__ == "__main__":
    script_main(run, loader=load_source)
