"""The tools, one package each, loaded by the daemon."""

# Every module MintToys ships, as module id -> "package.module:Class". The daemon imports
# each one only when it gets to it, so a module that fails to import fails alone.
AVAILABLE: dict[str, str] = {}
