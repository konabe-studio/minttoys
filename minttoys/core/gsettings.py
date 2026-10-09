"""GSettings, asked first: Gio.Settings.new aborts the whole process for a schema that is not
installed, and a module must fail alone.
"""

from gi.repository import Gio


def settings(schema: str, path: str | None = None) -> Gio.Settings:
    """The settings of `schema`, at `path` for a relocatable one. RuntimeError, naming the
    schema, when it is not installed.
    """
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema, True) is None:
        raise RuntimeError(f"needs Cinnamon: no {schema} settings")
    return Gio.Settings.new_with_path(schema, path) if path else Gio.Settings.new(schema)
