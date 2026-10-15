"""The settings of every tool in one file, to keep or to take to another computer, and
back again. Free of GTK.

The file holds, for each tool, whether it is on and its settings, as the daemon serves
them; restoring goes through the daemon too, tool by tool, so every value is checked as
if it were set by hand. What only describes this computer (what Nemo's Rename opened
before Rename+) is left out.
"""

import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from tuxtoys.api import MODULE_SETTINGS, ModuleInfo
from tuxtoys.modules import AVAILABLE

FORMAT = "tuxtoys-settings"
FORMAT_VERSION = 1
# Settings that belong to this computer alone.
LOCAL = {("renameplus", "previous_tool")}


def export(infos: list[ModuleInfo], settings: Mapping[str, Mapping[str, Any]]) -> str:
    tools = {}
    for info in infos:
        values = {
            key: value
            for key, value in settings.get(info.id, {}).items()
            if (info.id, key) not in LOCAL
        }
        tools[info.id] = {"enabled": info.state == "on", "settings": values}
    document = {"format": FORMAT, "version": FORMAT_VERSION, "tools": tools}
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


@dataclass(frozen=True)
class Restore:
    tool: str
    enabled: bool | None
    settings: dict[str, Any]


class NotABackup(ValueError):
    """The file is not a TuxToys settings file. The message is in English."""


def read(
    text: str,
    tools: Collection[str] = tuple(AVAILABLE),
    types: Mapping[str, Mapping[str, str]] = MODULE_SETTINGS,
) -> tuple[list[Restore], list[str]]:
    """What to restore, tool by tool, and the tools in the file this version does not have.
    A setting the tool does not know, or one that belongs to the computer, is left out.
    """
    try:
        document = json.loads(text)
    except ValueError as error:
        raise NotABackup(f"not JSON: {error}") from error
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise NotABackup("not a TuxToys settings file")
    sections = document.get("tools")
    if not isinstance(sections, dict):
        raise NotABackup("no tools in it")
    restores, unknown = [], []
    for tool, section in sorted(sections.items()):
        if not isinstance(section, dict):
            continue
        enabled = section.get("enabled")
        values = section.get("settings")
        if tool not in tools:
            unknown.append(tool)
            continue
        kept = {
            key: fit(types[tool][key], value)
            for key, value in (values.items() if isinstance(values, dict) else ())
            if key in types.get(tool, {}) and (tool, key) not in LOCAL
        }
        restores.append(Restore(tool, enabled if isinstance(enabled, bool) else None, kept))
    return restores, unknown


def _parts(signature: str) -> list[str]:
    """The complete types a tuple's inner signature holds, in order: "sdds" gives
    s, d, d, s; "sa(su)" gives s, a(su).
    """
    parts, index = [], 0
    while index < len(signature):
        end = index
        while signature[end] == "a":
            end += 1
        if signature[end] == "(":
            depth = 0
            while True:
                depth += {"(": 1, ")": -1}.get(signature[end], 0)
                end += 1
                if depth == 0:
                    break
        else:
            end += 1
        parts.append(signature[index:end])
        index = end
    return parts


def fit(signature: str, value: object) -> object:
    """A value read from JSON, its lists made tuples where its D-Bus type has a tuple, so
    GLib takes it; anything that does not fit is left as it is, for the daemon to refuse.
    """
    if signature.startswith("a") and isinstance(value, list):
        return [fit(signature[1:], item) for item in value]
    if signature.startswith("(") and isinstance(value, list):
        parts = _parts(signature[1:-1])
        if len(parts) == len(value):
            return tuple(fit(part, item) for part, item in zip(parts, value, strict=True))
    return value
