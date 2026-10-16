"""The screen tools' shared layer: a window over every monitor that shows the screen as it
was when the tool opened, frozen, and takes the mouse and the keyboard until it closes.
Color Picker picks from it and Screen Ruler measures on it; the other screen tools of M3
build on it too.

It is an override-redirect window over the whole root window, as screenshot tools make
them, with the pointer and the keyboard grabbed, so nothing under it reacts. Escape
always closes it. X11 only, as TuxToys is (see tuxtoys.platform.x11).
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from tuxtoys.overlay.pixels import Pixels  # noqa: E402


class Overlay(Gtk.Window):
    """Draws the frozen screen; a tool draws over it in draw_over() and takes the mouse
    in its own handlers.
    """

    def __init__(self, screen: GdkPixbuf.Pixbuf, cursor: str = "crosshair") -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self.screen_picture = screen
        self.pixels = Pixels.from_pixbuf(screen)
        self._cursor_name = cursor
        # Where the pointer is, from the start: the window covers the root window from its
        # corner, so the screen's coordinates are the window's. Without it, what a tool
        # draws beside the pointer would sit in the corner until the mouse moved.
        self.pointer = (0, 0)
        display = Gdk.Display.get_default()
        if display is not None:
            _screen, x, y = display.get_default_seat().get_pointer().get_position()
            self.pointer = (x, y)
        self.move(0, 0)
        self.set_default_size(screen.get_width(), screen.get_height())
        self.set_app_paintable(True)
        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        self.connect("draw", self._on_draw)
        self.connect("map-event", self._on_map)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("key-press-event", self._on_key)

    def _on_map(self, _window: Gtk.Window, _event: Gdk.Event) -> bool:
        window = self.get_window()
        cursor = Gdk.Cursor.new_from_name(window.get_display(), self._cursor_name)
        window.set_cursor(cursor)
        seat = window.get_display().get_default_seat()
        seat.grab(window, Gdk.SeatCapabilities.ALL, True, cursor, None, None, None)
        self.present()
        return False

    def close_overlay(self) -> None:
        window = self.get_window()
        if window is not None:
            window.get_display().get_default_seat().ungrab()
        self.destroy()

    def _on_motion(self, _window: Gtk.Window, event: Gdk.EventMotion) -> bool:
        self.pointer = (int(event.x), int(event.y))
        self.queue_draw()
        return True

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close_overlay()
            return True
        return self.key_pressed(event)

    def key_pressed(self, _event: Gdk.EventKey) -> bool:
        return False

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        Gdk.cairo_set_source_pixbuf(context, self.screen_picture, 0, 0)
        context.paint()
        self.draw_over(context)
        # On to the window's children, if a tool has any, such as Screen Ruler's toolbar.
        return False

    def draw_over(self, context: cairo.Context) -> None:
        """Whatever the tool shows over the frozen screen."""

    def magnify(
        self, context: cairo.Context, x: int, y: int, zoom: int, size: int, below: int = 0
    ) -> tuple[int, int]:
        """A square `size` pixels wide showing the screen around (x, y) `zoom` times as
        large, beside the pointer and inside the screen with `below` pixels more under it
        for the tool's own; where its top left corner went.
        """
        width, height = self.screen_picture.get_width(), self.screen_picture.get_height()
        left = x + 24 if x + 24 + size < width else x - 24 - size
        tall = size + below
        top = y + 24 if y + 24 + tall < height else y - 24 - tall
        context.save()
        context.rectangle(left, top, size, size)
        context.clip()
        context.translate(left + size / 2, top + size / 2)
        context.scale(zoom, zoom)
        Gdk.cairo_set_source_pixbuf(context, self.screen_picture, -x - 0.5, -y - 0.5)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()
        # The pixel picked, outlined; and the square's edge.
        context.set_line_width(1)
        center_x = left + size / 2 - zoom / 2
        center_y = top + size / 2 - zoom / 2
        for colour, inset in ((0.0, 0.5), (1.0, 1.5)):
            context.set_source_rgb(colour, colour, colour)
            context.rectangle(
                center_x - inset, center_y - inset, zoom + 2 * inset, zoom + 2 * inset
            )
            context.stroke()
        context.set_source_rgb(0.2, 0.2, 0.2)
        context.rectangle(left + 0.5, top + 0.5, size - 1, size - 1)
        context.stroke()
        return left, top
