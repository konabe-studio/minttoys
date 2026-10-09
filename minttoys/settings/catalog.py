"""The tools the settings window lists, in order, under their headings in the sidebar.

Free of GTK, so the order and the grouping can be tested anywhere. A tool's name is not
translated: tools keep their names in every language, as PowerToys' do.
"""

from dataclasses import dataclass

from minttoys import APP_ID
from minttoys.core.i18n import _


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
)


def headings() -> dict[str, str]:
    """Each category's heading, in the order the sidebar shows them."""
    return {
        # TRANSLATORS: a heading in the settings window's sidebar, over the tools that
        # deal with the computer as a whole, such as Awake.
        "system": _("System"),
    }


def grouped() -> list[tuple[str, list[Tool]]]:
    """The headings that have tools, each with its tools, in order."""
    groups = []
    for category, heading in headings().items():
        tools = [tool for tool in TOOLS if tool.category == category]
        if tools:
            groups.append((heading, tools))
    return groups
