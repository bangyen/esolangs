"""Loaded source shared by text and raster languages."""

from esolangs.raster import Raster

#: Loaded interpreter source; containers are accepted through ProgramSource.
type Program = str | Raster
