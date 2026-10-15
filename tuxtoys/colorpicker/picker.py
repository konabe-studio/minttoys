"""Color Picker's picker: the frozen screen, and beside the pointer a small label with the
color there, its value in the format it will be copied in, and its name if asked.

As in PowerToys: scrolling up shows a magnifier and zooms in, scrolling down zooms out
and hides it again. What each mouse button does is a setting: pick the color and open
the editor, pick it and close, or close; Escape always closes.
"""

from collections.abc import Callable, Mapping

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, GLib, Pango, PangoCairo  # noqa: E402

from tuxtoys.modules.colorpicker.colors import Color, format_color  # noqa: E402
from tuxtoys.modules.colorpicker.names import name  # noqa: E402
from tuxtoys.overlay.window import Overlay  # noqa: E402

ZOOMS = (2, 4, 6, 8, 12, 16, 24, 32)
MAGNIFIER = 160
# The zoom step before the first: no magnifier, the label alone.
NO_ZOOM = -1

# What it hands back: the color picked, or None, and what to do next.
type Done = Callable[[Color | None, str], None]


class Picker(Overlay):
    def __init__(
        self,
        screen: GdkPixbuf.Pixbuf,
        template: str,
        show_name: bool,
        actions: Mapping[int, str],
        done: Done,
    ) -> None:
        """`template` is the format the color is shown in; `actions` is what mouse
        buttons 1, 2 and 3 do: "pick-editor", "pick-close" or "close"; `done` gets the
        color picked, or None, and that action, once the picker has closed.
        """
        super().__init__(screen)
        self._template = template
        self._show_name = show_name
        self._actions = actions
        self._done = done
        self.zoom = NO_ZOOM
        self.connect("button-press-event", self._on_button)
        self.connect("scroll-event", self._on_scroll)
        self.connect("destroy", lambda _window: self._finish(None, "close"))
        self._finished = False

    def color_at(self, x: int, y: int) -> Color:
        return Color(*self.pixels.rgb(x, y))

    def _finish(self, color: Color | None, action: str) -> None:
        if not self._finished:
            self._finished = True
            # After the grab is gone and the window with it.
            GLib.idle_add(lambda: self._done(color, action) and False)

    def act(self, action: str) -> None:
        color = None if action == "close" else self.color_at(*self.pointer)
        self._finish(color, action)
        self.close_overlay()

    def _on_button(self, _window: Gdk.Window, event: Gdk.EventButton) -> bool:
        self.pointer = (int(event.x), int(event.y))
        if event.button in self._actions:
            self.act(self._actions[event.button])
        return True

    def _on_scroll(self, _window: Gdk.Window, event: Gdk.EventScroll) -> bool:
        direction = event.direction
        if direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
            direction = Gdk.ScrollDirection.UP if dy < 0 else Gdk.ScrollDirection.DOWN
        step = 1 if direction == Gdk.ScrollDirection.UP else -1
        self.zoom = min(max(self.zoom + step, NO_ZOOM), len(ZOOMS) - 1)
        self.queue_draw()
        return True

    def label_text(self, color: Color) -> str:
        text = format_color(color, self._template)
        return f"{text}\n{name(color)}" if self._show_name else text

    def draw_over(self, context: cairo.Context) -> None:
        x, y = self.pointer
        color = self.color_at(x, y)
        layout = PangoCairo.create_layout(context)
        layout.set_font_description(Pango.FontDescription.from_string("Monospace 10"))
        layout.set_text(self.label_text(color), -1)
        _ink, logical = layout.get_pixel_extents()
        swatch = 16
        height = max(logical.height, swatch) + 12
        if self.zoom == NO_ZOOM:
            left, top, below = x + 16, y + 16, 0
        else:
            # The label goes under the magnifier, so both have to fit.
            zoom = ZOOMS[self.zoom]
            left, top = self.magnify(context, x, y, zoom, MAGNIFIER, 4 + height)
            below = MAGNIFIER + 4
        width = swatch + logical.width + 24
        if self.zoom != NO_ZOOM:
            width = max(width, MAGNIFIER)
        screen_width, screen_height = (
            self.screen_picture.get_width(),
            self.screen_picture.get_height(),
        )
        if self.zoom == NO_ZOOM:
            # Beside the pointer, turned back inside the screen near its edges.
            if left + width > screen_width:
                left = x - 16 - width
            if top + height > screen_height:
                top = y - 16 - height
        box_top = top + below
        context.set_source_rgba(0.12, 0.12, 0.12, 0.92)
        context.rectangle(left, box_top, width, height)
        context.fill()
        context.set_source_rgb(color.r / 255, color.g / 255, color.b / 255)
        context.rectangle(left + 6, box_top + (height - swatch) / 2, swatch, swatch)
        context.fill_preserve()
        context.set_source_rgb(1, 1, 1)
        context.set_line_width(1)
        context.stroke()
        context.move_to(left + swatch + 14, box_top + (height - logical.height) / 2)
        PangoCairo.show_layout(context, layout)
