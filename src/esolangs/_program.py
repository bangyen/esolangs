"""Source shapes shared by text and raster languages."""

from esolangs.raster import Raster

#: Loaded interpreter source; containers are accepted through ProgramSource.
type Program = str | Raster

#: Internal runner arguments after line splitting.
type RunnerProgram = Program | list[str]
