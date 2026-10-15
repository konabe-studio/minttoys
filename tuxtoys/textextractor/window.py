"""Text Extractor's window, as in PowerToys: the frozen screen, dimmed, with a toolbar at
the top of the monitor under the pointer: the language to read in, "single line" (S) and
"table" (T), the settings, and close. Drag a region and its text is read; a click without
a drag reads the one word under it. Holding Shift while dragging moves the region.
"""

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "3.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.textextractor import tesseract  # noqa: E402
from tuxtoys.overlay.monitors import Monitor, monitor_at  # noqa: E402
from tuxtoys.overlay.toolbar import Toolbar, flat, icon  # noqa: E402
from tuxtoys.overlay.window import Overlay  # noqa: E402
from tuxtoys.textextractor.reading import Region, Request, word_region  # noqa: E402

# A drag shorter than this, either way, is a click.
CLICK = 4
DIM = 0.45

# What it hands back once closed: what to read, or None when closed without reading.
type Done = Callable[[Request | None], None]


class Extractor(Overlay):
    def __init__(
        self,
        screen: GdkPixbuf.Pixbuf,
        monitors: Sequence[Monitor],
        pointer: tuple[int, int],
        languages: Sequence[str],
        language: str,
        done: Done,
        open_settings: Callable[[], None],
    ) -> None:
        super().__init__(screen)
        self.monitors = monitors
        self.pointer = pointer
        self.language = language
        self.mode = "text"
        self.start: tuple[int, int] | None = None
        self.region: Region | None = None
        self._last: tuple[int, int] = pointer
        self._done = done
        self._finished = False
        self._showing = False

        self.toolbar = Toolbar(self.close_overlay)
        self.language_button = flat(Gtk.MenuButton(label=tesseract.name(language)))
        self.language_button.set_tooltip_text(_("Language"))
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=6)
        first = None
        for code in languages:
            item = Gtk.RadioButton.new_with_label_from_widget(first, tesseract.name(code))
            first = first or item
            item.set_active(code == language)
            item.connect("toggled", self._on_language, code)
            menu.add(item)
        menu.show_all()
        popover = Gtk.Popover()
        popover.add(menu)
        self.language_button.set_popover(popover)
        self.toolbar.add_item(self.language_button)
        self.single = flat(
            Gtk.ToggleButton(
                image=icon("text-single-line"),
                tooltip_text=_("Format the result as a single line (S)"),
            )
        )
        self.single.connect("toggled", self._on_format, "single")
        self.toolbar.add_item(self.single)
        self.table = flat(
            Gtk.ToggleButton(
                image=icon("text-table"),
                tooltip_text=_("Format the result as a table (T)"),
            )
        )
        self.table.connect("toggled", self._on_format, "table")
        self.toolbar.add_item(self.table)
        settings = flat(Gtk.Button(image=icon("settings")))
        settings.set_tooltip_text(_("Settings"))
        settings.connect("clicked", lambda _button: (self.close_overlay(), open_settings()))
        self.toolbar.add_item(settings)

        fixed = Gtk.Fixed()
        fixed.put(self.toolbar, 0, 0)
        self.add(fixed)
        self._fixed = fixed
        self.connect("realize", lambda _window: self.toolbar.place(fixed, monitors, pointer))
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("destroy", lambda _window: self._finish(None))

    def _finish(self, request: Request | None) -> None:
        if not self._finished:
            self._finished = True
            self._done(request)

    def _on_language(self, item: Gtk.RadioButton, code: str) -> None:
        if item.get_active():
            self.language = code
            self.language_button.set_label(tesseract.name(code))

    def set_mode(self, mode: str) -> None:
        """Single line or table, or the text as it reads with "text"; choosing the one in
        use turns it off. The two exclude each other.
        """
        self.mode = "text" if mode == self.mode else mode
        self._showing = True
        try:
            self.single.set_active(self.mode == "single")
            self.table.set_active(self.mode == "table")
        finally:
            self._showing = False

    def _on_format(self, _button: Gtk.ToggleButton, mode: str) -> None:
        if not self._showing:
            self.set_mode(mode)

    def key_pressed(self, event: Gdk.EventKey) -> bool:
        if event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK):
            return False
        if event.keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self.set_mode("single")
            return True
        if event.keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.set_mode("table")
            return True
        return False

    def _on_press(self, _window: Gtk.Window, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self.start = (int(event.x), int(event.y))
            self._last = self.start
            self.region = Region(*self.start, 1, 1)
        return True

    def _on_motion(self, window: Gtk.Window, event: Gdk.EventMotion) -> bool:
        x, y = int(event.x), int(event.y)
        if self.start is not None:
            if event.state & Gdk.ModifierType.SHIFT_MASK:
                # Shift moves the region instead of growing it, as in PowerToys.
                dx, dy = x - self._last[0], y - self._last[1]
                self.start = (self.start[0] + dx, self.start[1] + dy)
            self.region = spanned(self.start, (x, y))
        self._last = (x, y)
        return super()._on_motion(window, event)

    def _on_release(self, _window: Gtk.Window, event: Gdk.EventButton) -> bool:
        if event.button != 1 or self.start is None or self.region is None:
            return True
        x, y = int(event.x), int(event.y)
        region = self.region
        self.start = None
        self.region = None
        if region.width < CLICK and region.height < CLICK:
            monitor = monitor_at(self.monitors, x, y)
            band = word_region(x, y, Region(monitor.x, monitor.y, monitor.width, monitor.height))
            request = Request(band, "word", self.language, (x, y))
        else:
            request = Request(region, self.mode, self.language)
        self._finish(request)
        self.close_overlay()
        return True

    def draw_over(self, context: cairo.Context) -> None:
        width, height = self.screen_picture.get_width(), self.screen_picture.get_height()
        context.set_source_rgba(0, 0, 0, DIM)
        context.rectangle(0, 0, width, height)
        region = self.region
        if region is not None:
            # The region cut out of the dimming, so it shows as it is.
            context.rectangle(region.x + region.width, region.y, -region.width, region.height)
        context.fill()
        if region is not None:
            context.set_source_rgb(1, 1, 1)
            context.set_line_width(1)
            context.rectangle(region.x - 0.5, region.y - 0.5, region.width + 1, region.height + 1)
            context.stroke()


def spanned(start: tuple[int, int], end: tuple[int, int]) -> Region:
    """The region between two corners, both inside it."""
    left, right = sorted((start[0], end[0]))
    top, bottom = sorted((start[1], end[1]))
    return Region(left, top, right - left + 1, bottom - top + 1)
