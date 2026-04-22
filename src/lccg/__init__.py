"""LCCG - Local Claude Code Gateway."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("lccg")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0+unknown"
