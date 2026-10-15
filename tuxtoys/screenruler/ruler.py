"""Screen Ruler's window: the frozen screen with a small toolbar at the top of the monitor
under the pointer, and over it what the chosen tool measures, as in PowerToys:

- Bounds: drag a box; it is measured and copied when let go. Let go with Shift held to
  keep it on the screen, and the next boxes are copied with it.
- Spacing: from the pointer to the edges around it, left, right, up and down.
- Horizontal and Vertical spacing: one direction of it.

Ctrl+1 to Ctrl+4 choose a tool, the scroll wheel changes how different a pixel has to be
to count as an edge. A click copies a spacing and puts its tool away, as PowerToys does;
the ruler stays until its close button or Escape.
"""

import math
from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, PangoCairo  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.screenruler.measure import (  # noqa: E402
    TOLERANCE_STEP,
    Monitor,
    Rect,
    box,
    copied,
    label,
    measure_at,
    monitor_at,
)
from tuxtoys.modules.screenruler.options import Options  # noqa: E402
from tuxtoys.overlay.window import Overlay  # noqa: E402

TOOLS = ("bounds", "spacing", "horizontal", "vertical")
UNIT_NAMES = {"": "px", "in": "in", "cm": "cm", "mm": "mm"}
FOOT = 4  # half a foot's length, in pixels
ICONS = "data/icons/hicolor/symbolic/apps"


def tool_icon(name: str) -> Gtk.Image:
    """One of our own symbolic icons: by name once installed, else the checkout's file."""
    icon_name = f"{APP_ID}-{name}-symbolic"
    if Gtk.IconTheme.get_default().has_icon(icon_name):
        return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
    from tuxtoys.core.nemo_action import PACKAGE_ROOT

    path = PACKAGE_ROOT / ICONS / f"{icon_name}.svg"
    return Gtk.Image.new_from_gicon(
        Gio.FileIcon.new(Gio.File.new_for_path(str(path))), Gtk.IconSize.BUTTON
    )


def tooltips() -> dict[str, str]:
    return {
        "bounds": _("Bounds (Ctrl+1)"),
        "spacing": _("Spacing (Ctrl+2)"),
        "horizontal": _("Horizontal spacing (Ctrl+3)"),
        "vertical": _("Vertical spacing (Ctrl+4)"),
    }


class Ruler(Overlay):
    def __init__(
        self,
        screen: GdkPixbuf.Pixbuf,
        monitors: Sequence[Monitor],
        pointer: tuple[int, int],
        options: Options,
        copy: Callable[[str], None],
    ) -> None:
        """`copy` puts a measurement on the clipboard."""
        super().__init__(screen)
        self.monitors = monitors
        self.pointer = pointer
        self.options = options
        self.tolerance = options.tolerance
        self._copy = copy
        self.tool = options.default_mode if options.default_mode in TOOLS else ""
        self.kept: list[Rect] = []
        self.dragging: tuple[int, int] | None = None
        self._measured: tuple[tuple[int, int, int], Rect] | None = None
        self.color = Gdk.RGBA()
        self.color.parse(options.line_color)
        self._showing = False

        self.buttons: dict[str, Gtk.ToggleButton] = {}
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        for side in ("top", "bottom", "start", "end"):
            getattr(toolbar, f"set_margin_{side}")(4)
        for tool, tip in tooltips().items():
            button = Gtk.ToggleButton(image=tool_icon(f"ruler-{tool}"), tooltip_text=tip)
            button.get_style_context().add_class("flat")
            button.connect("toggled", self._on_toggled, tool)
            self.buttons[tool] = button
            toolbar.add(button)
        close = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON)
        close.set_tooltip_text(_("Close (Esc)"))
        close.connect("clicked", lambda _button: self.close_overlay())
        close.get_style_context().add_class("flat")
        close.get_style_context().add_class("ruler-close")
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_margin_start(4)
        separator.set_margin_end(4)
        toolbar.add(separator)
        toolbar.add(close)
        # A bar in the theme's own colors, floating over the frozen screen.
        # A rounded bar in the theme's own colors, floating over the frozen screen, with a
        # red close button, as PowerToys has it.
        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.OUT)
        css = Gtk.CssProvider()
        css.load_from_data(
            b"frame.ruler-bar { background-color: @theme_bg_color; border-radius: 8px; }"
            b" frame.ruler-bar > border { border-radius: 8px; }"
            b" .ruler-close image { color: #e01b24; }"
        )
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        frame.get_style_context().add_class("ruler-bar")
        frame.add(toolbar)
        self.toolbar = frame
        fixed = Gtk.Fixed()
        fixed.put(frame, 0, 0)
        self.add(fixed)
        self._fixed = fixed
        self._show_tool()
        self.connect("realize", self._place_toolbar)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("scroll-event", self._on_scroll)

    def _place_toolbar(self, _window: Gtk.Window) -> None:
        """At the top of the monitor the pointer is on, in the middle."""
        monitor = monitor_at(self.monitors, *self.pointer)
        self.toolbar.show_all()
        _least, natural = self.toolbar.get_preferred_width()
        self._fixed.move(self.toolbar, monitor.x + (monitor.width - natural) // 2, monitor.y + 16)

    def _show_tool(self) -> None:
        self._showing = True
        try:
            for tool, button in self.buttons.items():
                button.set_active(tool == self.tool)
        finally:
            self._showing = False

    def choose(self, tool: str) -> None:
        """A tool, or none with ""; choosing the one in use puts it away, as in PowerToys."""
        self.tool = "" if tool == self.tool else tool
        self.kept = []
        self.dragging = None
        self._show_tool()
        self.queue_draw()

    def _on_toggled(self, _button: Gtk.ToggleButton, tool: str) -> None:
        if not self._showing:
            self.choose(tool)

    def key_pressed(self, event: Gdk.EventKey) -> bool:
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            keys = (Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_3, Gdk.KEY_4)
            if event.keyval in keys:
                self.choose(TOOLS[keys.index(event.keyval)])
                return True
        return False

    def measured(self) -> Rect:
        """The edges around the pointer, found again only when it or the tolerance moved."""
        key = (*self.pointer, self.tolerance)
        if self._measured is None or self._measured[0] != key:
            rect = measure_at(
                self.pixels, self.monitors, *self.pointer, self.tolerance, self.options.per_channel
            )
            self._measured = (key, rect)
        return self._measured[1]

    def sides(self, rect: Rect) -> tuple[int | None, int | None]:
        """What the tool in use measures of a rectangle: its width, its height, or both."""
        width = rect.width if self.tool != "vertical" else None
        height = rect.height if self.tool != "horizontal" else None
        return width, height

    def _on_press(self, _window: Gtk.Window, event: Gdk.EventButton) -> bool:
        self.pointer = (int(event.x), int(event.y))
        if event.button == 1 and self.tool == "bounds":
            self.dragging = self.pointer
        elif event.button == 1 and self.tool:
            self._copy(copied([self.sides(self.measured())]))
            self.choose(self.tool)
        return True

    def _on_release(self, _window: Gtk.Window, event: Gdk.EventButton) -> bool:
        if event.button != 1 or self.dragging is None:
            return True
        self.pointer = (int(event.x), int(event.y))
        dragged = box(self.dragging, self.pointer)
        self.dragging = None
        measured = [*self.kept, dragged]
        self._copy(copied([(rect.width, rect.height) for rect in measured]))
        # As in PowerToys, a box goes when let go, unless Shift keeps it.
        self.kept = measured if event.state & Gdk.ModifierType.SHIFT_MASK else []
        self.queue_draw()
        return True

    def _on_scroll(self, _window: Gtk.Window, event: Gdk.EventScroll) -> bool:
        direction = event.direction
        if direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
            if dy == 0:
                return True
            direction = Gdk.ScrollDirection.UP if dy < 0 else Gdk.ScrollDirection.DOWN
        step = TOLERANCE_STEP if direction == Gdk.ScrollDirection.UP else -TOLERANCE_STEP
        self.tolerance = min(max(self.tolerance + step, 0), 255)
        self.queue_draw()
        return True

    def draw_over(self, context: cairo.Context) -> None:
        context.set_line_width(1)
        if self.tool == "bounds":
            boxes = list(self.kept)
            if self.dragging is not None:
                boxes.append(box(self.dragging, self.pointer))
            for rect in boxes:
                self._draw_box(context, rect)
        elif self.tool:
            self._draw_spacing(context, self.measured())

    def _line(self, context: cairo.Context) -> None:
        context.set_source_rgba(self.color.red, self.color.green, self.color.blue, 1)

    def _draw_box(self, context: cairo.Context, rect: Rect) -> None:
        context.set_source_rgba(self.color.red, self.color.green, self.color.blue, 0.15)
        context.rectangle(rect.left, rect.top, rect.width, rect.height)
        context.fill()
        self._line(context)
        context.rectangle(rect.left + 0.5, rect.top + 0.5, rect.width - 1, rect.height - 1)
        context.stroke()
        self._label(
            context,
            (rect.width, rect.height),
            rect.left + rect.width / 2,
            rect.top + rect.height / 2,
        )

    def _draw_spacing(self, context: cairo.Context, rect: Rect) -> None:
        x, y = self.pointer
        self._line(context)
        if self.tool != "vertical":
            context.move_to(rect.left, y + 0.5)
            context.line_to(rect.right + 1, y + 0.5)
            if self.options.draw_feet:
                for foot in (rect.left + 0.5, rect.right + 0.5):
                    context.move_to(foot, y - FOOT)
                    context.line_to(foot, y + FOOT + 1)
        if self.tool != "horizontal":
            context.move_to(x + 0.5, rect.top)
            context.line_to(x + 0.5, rect.bottom + 1)
            if self.options.draw_feet:
                for foot in (rect.top + 0.5, rect.bottom + 0.5):
                    context.move_to(x - FOOT, foot)
                    context.line_to(x + FOOT + 1, foot)
        context.stroke()
        self._label(context, self.sides(rect), x + 20, y + 20, beside=True)

    def _label(
        self,
        context: cairo.Context,
        sides: tuple[int | None, int | None],
        x: float,
        y: float,
        beside: bool = False,
    ) -> None:
        """The measurement in a small dark box: centred on (x, y), or beside the pointer
        with its top left corner there, turned back inside the monitor near its edges.
        """
        mm_per_pixel = monitor_at(self.monitors, *self.pointer).mm_per_pixel
        text = label(*sides, self.options.extra_unit, mm_per_pixel, UNIT_NAMES)
        layout = self.create_pango_layout(text)
        _ink, logical = layout.get_pixel_extents()
        width, height = logical.width + 16, logical.height + 10
        if beside:
            monitor = monitor_at(self.monitors, *self.pointer)
            left, top = x, y
            if left + width > monitor.x + monitor.width:
                left = x - 40 - width
            if top + height > monitor.y + monitor.height:
                top = y - 40 - height
        else:
            left, top = x - width / 2, y - height / 2
        left, top = round(left), round(top)
        radius = 4
        context.new_sub_path()
        quarter = math.pi / 2
        context.arc(left + width - radius, top + radius, radius, -quarter, 0)
        context.arc(left + width - radius, top + height - radius, radius, 0, quarter)
        context.arc(left + radius, top + height - radius, radius, quarter, 2 * quarter)
        context.arc(left + radius, top + radius, radius, 2 * quarter, 3 * quarter)
        context.close_path()
        context.set_source_rgba(0.12, 0.12, 0.12, 0.92)
        context.fill()
        context.set_source_rgb(1, 1, 1)
        context.move_to(left + 8, top + 5)
        PangoCairo.show_layout(context, layout)


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
