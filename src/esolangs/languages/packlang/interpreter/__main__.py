"""Run a source file through the shared interpreter entry point."""

from esolangs.languages.packlang.interpreter import run
from esolangs.runtime._entry import script_main

if __name__ == "__main__":
    script_main(run)
