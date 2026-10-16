"""The tools the settings window lists, in order, under their headings in the sidebar.

Free of GTK, so the order and the grouping can be tested anywhere. A tool's name is not
translated: tools keep their names in every language, as PowerToys' do.
"""

from dataclasses import dataclass

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    category: str
    # A symbolic icon from the theme, which the sidebar colours to match.
    icon: str


TOOLS = (
    Tool("awake", "Awake", "system", f"{APP_ID}-awake-on-symbolic"),
    Tool("lightswitch", "Light Switch", "system", "weather-clear-night-symbolic"),
    Tool("hosts", "Hosts File Editor", "system", "network-server-symbolic"),
    Tool("envvars", "Environment Variables", "system", "utilities-terminal-symbolic"),
    Tool("locksmith", "File Locksmith", "files", "changes-prevent-symbolic"),
    Tool("newplus", "New+", "files", "document-new-symbolic"),
    Tool("imageresizer", "Image Resizer", "files", "image-x-generic-symbolic"),
    Tool("renameplus", "Rename+", "files", "document-edit-symbolic"),
    Tool("alwaysontop", "Always on Top", "windows", "view-pin-symbolic"),
    Tool("colorpicker", "Color Picker", "screen", "color-select-symbolic"),
    Tool("screenruler", "Screen Ruler", "screen", f"{APP_ID}-screenruler-symbolic"),
    Tool("textextractor", "Text Extractor", "screen", f"{APP_ID}-textextractor-symbolic"),
    Tool("shortcutguide", "Shortcut Guide", "screen", "input-keyboard-symbolic"),
)


def headings() -> dict[str, str]:
    """Each category's heading, in the order the sidebar shows them."""
    return {
        # TRANSLATORS: a heading in the settings window's sidebar, over the tools that
        # deal with the computer as a whole, such as Awake.
        "system": _("System"),
        # TRANSLATORS: a heading in the settings window's sidebar, over the tools for
        # windows, such as Always on Top.
        "windows": _("Windows"),
        # TRANSLATORS: a heading in the settings window's sidebar, over the tools that work
        # on what is on the screen, such as Color Picker.
        "screen": _("Screen"),
        # TRANSLATORS: a heading in the settings window's sidebar, over the tools for files,
        # such as File Locksmith.
        "files": _("Files"),
    }


def grouped() -> list[tuple[str, list[Tool]]]:
    """The headings that have tools, each with its tools, in order."""
    groups = []
    for category, heading in headings().items():
        tools = [tool for tool in TOOLS if tool.category == category]
        if tools:
            groups.append((heading, tools))
    return groups
