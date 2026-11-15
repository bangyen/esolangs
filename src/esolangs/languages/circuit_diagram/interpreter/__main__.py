"""Run a Circuit Diagram source file through the shared interpreter entry point."""

from esolangs.runtime._entry import script_main
from esolangs.runtime._source import native_text_source

from . import run

if __name__ == "__main__":
    script_main(run, shape="strip", loader=native_text_source)
