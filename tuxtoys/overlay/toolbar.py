"""The screen tools' toolbar, as PowerToys' are: a rounded bar in the theme's colors at the
top of the monitor under the pointer, flat buttons, and after a separator a red close
button. Screen Ruler and Text Extractor put their own buttons on it.
"""

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.overlay.monitors import Monitor, monitor_at  # noqa: E402

ICONS = "data/icons/hicolor/symbolic/apps"
CSS = (
    b"frame.overlay-bar { background-color: @theme_bg_color; border-radius: 8px; }"
    b" frame.overlay-bar > border { border-radius: 8px; }"
    b" .overlay-close image { color: #e01b24; }"
)
_styled = False


def icon(name: str) -> Gtk.Image:
    """One of our own symbolic icons: by name once installed, else the checkout's file."""
    icon_name = f"{APP_ID}-{name}-symbolic"
    if Gtk.IconTheme.get_default().has_icon(icon_name):
        return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
    from tuxtoys.core.nemo_action import PACKAGE_ROOT

    path = PACKAGE_ROOT / ICONS / f"{icon_name}.svg"
    return Gtk.Image.new_from_gicon(
        Gio.FileIcon.new(Gio.File.new_for_path(str(path))), Gtk.IconSize.BUTTON
    )


def flat(button: Gtk.Button) -> Gtk.Button:
    button.get_style_context().add_class("flat")
    return button


class Toolbar(Gtk.Frame):
    """Add the tool's own buttons with add_item(); the separator and the close button,
    which calls `close`, come last.
    """

    def __init__(self, close: Callable[[], None]) -> None:
        super().__init__(shadow_type=Gtk.ShadowType.OUT)
        global _styled
        if not _styled:
            css = Gtk.CssProvider()
            css.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            _styled = True
        self.get_style_context().add_class("overlay-bar")
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        for side in ("top", "bottom", "start", "end"):
            getattr(self.box, f"set_margin_{side}")(4)
        self.add(self.box)
        self._items = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.box.add(self._items)
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_margin_start(4)
        separator.set_margin_end(4)
        self.box.add(separator)
        self.close_button = flat(
            Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON)
        )
        self.close_button.set_tooltip_text(_("Close (Esc)"))
        self.close_button.get_style_context().add_class("overlay-close")
        self.close_button.connect("clicked", lambda _button: close())
        self.box.add(self.close_button)

    def add_item(self, widget: Gtk.Widget) -> None:
        self._items.add(widget)

    def place(
        self, fixed: Gtk.Fixed, monitors: Sequence[Monitor], pointer: tuple[int, int]
    ) -> None:
        """At the top of the monitor the pointer is on, in the middle."""
        monitor = monitor_at(monitors, *pointer)
        self.show_all()
        _least, natural = self.get_preferred_width()
        fixed.move(self, monitor.x + (monitor.width - natural) // 2, monitor.y + 16)


def monitors_of(display: Gdk.Display) -> list[Monitor]:
    """Every monitor's place, and its pixel size from the millimetres it reports."""
    found = []
    for number in range(display.get_n_monitors()):
        monitor = display.get_monitor(number)
        area = monitor.get_geometry()
        width_mm = monitor.get_width_mm()
        mm_per_pixel = width_mm / area.width if width_mm > 0 and area.width > 0 else 0.0
        found.append(Monitor(area.x, area.y, area.width, area.height, mm_per_pixel))
    return found


def pointer_of(display: Gdk.Display) -> tuple[int, int]:
    _screen, x, y = display.get_default_seat().get_pointer().get_position()
    return x, y
