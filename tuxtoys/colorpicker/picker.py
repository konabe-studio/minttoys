"""Color Picker's picker: the frozen screen with a magnifier at the pointer, and under it
the color there in the format it will be copied in.

As in PowerToys: the scroll wheel zooms, a left or a middle click picks the color, a right
click closes. PowerToys' left click also opens its editor; until TuxToys has one, both
pick and close.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Pango, PangoCairo  # noqa: E402

from tuxtoys.modules.colorpicker.colors import Color, format_color  # noqa: E402
from tuxtoys.overlay.window import Overlay  # noqa: E402

ZOOMS = (2, 4, 6, 8, 12, 16, 24, 32)
MAGNIFIER = 160


class Picker(Overlay):
    def __init__(
        self,
        screen: GdkPixbuf.Pixbuf,
        template: str,
        picked: Callable[[Color], None],
    ) -> None:
        """`template` is the format the color is shown and copied in; `picked` gets the
        color picked, after the picker has closed.
        """
        super().__init__(screen)
        self._template = template
        self._picked = picked
        self.zoom = ZOOMS.index(8)
        self.connect("button-press-event", self._on_button)
        self.connect("scroll-event", self._on_scroll)

    def color_at(self, x: int, y: int) -> Color:
        return Color(*self.pixels.rgb(x, y))

    def pick(self) -> None:
        color = self.color_at(*self.pointer)
        self.close_overlay()
        self._picked(color)

    def _on_button(self, _window: Gdk.Window, event: Gdk.EventButton) -> bool:
        self.pointer = (int(event.x), int(event.y))
        if event.button in (1, 2):
            self.pick()
        elif event.button == 3:
            self.close_overlay()
        return True

    def _on_scroll(self, _window: Gdk.Window, event: Gdk.EventScroll) -> bool:
        direction = event.direction
        if direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
            direction = Gdk.ScrollDirection.UP if dy < 0 else Gdk.ScrollDirection.DOWN
        step = 1 if direction == Gdk.ScrollDirection.UP else -1
        self.zoom = min(max(self.zoom + step, 0), len(ZOOMS) - 1)
        self.queue_draw()
        return True

    def draw_over(self, context: cairo.Context) -> None:
        x, y = self.pointer
        left, top = self.magnify(context, x, y, ZOOMS[self.zoom], MAGNIFIER)
        color = self.color_at(x, y)
        layout = PangoCairo.create_layout(context)
        layout.set_font_description(Pango.FontDescription.from_string("Monospace 10"))
        layout.set_text(format_color(color, self._template), -1)
        _ink, logical = layout.get_pixel_extents()
        swatch = 16
        height = max(logical.height, swatch) + 12
        width = max(MAGNIFIER, swatch + logical.width + 24)
        box_top = top + MAGNIFIER + 4
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
