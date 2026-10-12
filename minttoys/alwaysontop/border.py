"""The frame around a pinned window: a see-through window of its own around it, which lets
every click through, so it shows and never gets in the way.
"""

import logging
import math
import shutil
import subprocess

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from minttoys.modules.alwaysontop.frame import Rect, around  # noqa: E402

log = logging.getLogger(__name__)

type Rgb = tuple[float, float, float]


def theme_accent() -> Rgb:
    """The theme's selection colour, which Mint's themes use as their accent."""
    context = Gtk.Label().get_style_context()
    found, color = context.lookup_color("theme_selected_bg_color")
    return (color.red, color.green, color.blue) if found else (0.21, 0.52, 0.89)


class Style:
    def __init__(self, color: Rgb, width: int, opacity: int, radius: int) -> None:
        self.color = color
        self.width = width
        self.alpha = opacity / 100
        self.radius = radius


class Border(Gtk.Window):
    def __init__(self, style: Style) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self._style = style
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
        frame = around(window, self._style.width * scale)
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
        line = self._style.width
        half = line / 2
        # The window's own corner, grown by the frame around it.
        radius = self._style.radius + half if self._style.radius else 0
        _rounded(context, half, half, width - line, height - line, radius)
        context.set_source_rgba(*self._style.color, self._style.alpha)
        context.set_line_width(line)
        context.stroke()
        return True


def _rounded(context: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    r = min(r, w / 2, h / 2)
    if r <= 0:
        context.rectangle(x, y, w, h)
        return
    context.new_sub_path()
    context.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    context.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    context.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    context.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    context.close_path()


class Sounds:
    """Cinnamon's own window sounds, as its Sound settings have them: maximize for pinning,
    unmaximize for letting go.
    """

    def __init__(self) -> None:
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.cinnamon.sounds", True) if source else None
        settings = Gio.Settings.new("org.cinnamon.sounds") if schema else None
        self._files = {}
        for event, key in (("pin", "maximize-file"), ("unpin", "unmaximize-file")):
            if settings is not None and schema.has_key(key):
                self._files[event] = settings.get_string(key)
        self._player = shutil.which("canberra-gtk-play") or shutil.which("paplay")

    def play(self, event: str) -> None:
        sound = self._files.get(event)
        if not sound or not self._player:
            return
        command = (
            [self._player, "-f", sound] if "canberra" in self._player else [self._player, sound]
        )
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            log.warning("could not play %s", sound)


class Borders:
    """One frame for each pinned window, made, moved and taken away as they change, with a
    sound on pinning and letting go when wanted.
    """

    def __init__(self, style: Style, sounds: Sounds | None = None) -> None:
        self._style = style
        self._sounds = sounds
        self._frames: dict[int, Border] = {}
        self._known: set[int] | None = None

    def show(self, windows: dict[int, Rect], open_ids: set[int] | None = None) -> None:
        if self._sounds is not None and self._known is not None:
            if set(windows) - self._known:
                self._sounds.play("pin")
            let_go = self._known - set(windows)
            if open_ids is not None and let_go & open_ids:
                self._sounds.play("unpin")
        self._known = set(windows)
        for xid in list(self._frames):
            if xid not in windows:
                self._frames.pop(xid).destroy()
        for xid, window in windows.items():
            frame = self._frames.get(xid)
            if frame is None:
                frame = self._frames[xid] = Border(self._style)
            frame.follow(window)
            frame.queue_draw()


def parse_color(text: str) -> Rgb | None:
    rgba = Gdk.RGBA()
    return (rgba.red, rgba.green, rgba.blue) if text and rgba.parse(text) else None
