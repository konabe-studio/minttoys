"""The frame around a pinned window: a see-through window of its own around it, which lets
every click through, so it shows and never gets in the way.
"""

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from minttoys.modules.alwaysontop.frame import Rect, around  # noqa: E402

type Rgb = tuple[float, float, float]


def theme_accent() -> Rgb:
    """The theme's selection colour, which Mint's themes use as their accent."""
    context = Gtk.Label().get_style_context()
    found, color = context.lookup_color("theme_selected_bg_color")
    return (color.red, color.green, color.blue) if found else (0.21, 0.52, 0.89)


class Border(Gtk.Window):
    def __init__(self, color: Rgb, width: int) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self._color = color
        self._width = width
        self.set_app_paintable(True)
        self.set_accept_focus(False)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.connect("draw", self._on_draw)
        self.connect("realize", self._on_realize)

    def follow(self, window: Rect) -> None:
        """Puts the frame around `window`, in device pixels as X11 has them."""
        scale = self.get_scale_factor() or 1
        frame = around(window, self._width * scale)
        self.move(frame.x // scale, frame.y // scale)
        self.resize(max(1, frame.width // scale), max(1, frame.height // scale))
        self.show()

    def _on_realize(self, _window: Gtk.Window) -> None:
        # An empty input shape: every click goes to whatever is under the frame.
        self.input_shape_combine_region(cairo.Region())

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(0, 0, 0, 0)
        context.paint()
        width, height = self.get_size()
        half = self._width / 2
        context.set_source_rgba(*self._color, 1)
        context.set_line_width(self._width)
        context.rectangle(half, half, width - self._width, height - self._width)
        context.stroke()
        return True


class Borders:
    """One frame for each pinned window, made, moved and taken away as they change."""

    def __init__(self, color: Rgb, width: int) -> None:
        self._color = color
        self._width = width
        self._frames: dict[int, Border] = {}

    def show(self, windows: dict[int, Rect]) -> None:
        for xid in list(self._frames):
            if xid not in windows:
                self._frames.pop(xid).destroy()
        for xid, window in windows.items():
            frame = self._frames.get(xid)
            if frame is None:
                frame = self._frames[xid] = Border(self._color, self._width)
            frame.follow(window)
            frame.queue_draw()


def parse_color(text: str) -> Rgb | None:
    rgba = Gdk.RGBA()
    return (rgba.red, rgba.green, rgba.blue) if text and rgba.parse(text) else None
