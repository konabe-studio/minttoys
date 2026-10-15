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
from gi.repository import Gdk, GdkPixbuf, Gtk, PangoCairo  # noqa: E402

from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.screenruler.measure import (  # noqa: E402
    TOLERANCE_STEP,
    Rect,
    box,
    copied,
    label,
    measure_at,
)
from tuxtoys.modules.screenruler.options import Options  # noqa: E402
from tuxtoys.overlay.monitors import Monitor, monitor_at  # noqa: E402
from tuxtoys.overlay.toolbar import Toolbar, flat, icon  # noqa: E402
from tuxtoys.overlay.window import Overlay  # noqa: E402

TOOLS = ("bounds", "spacing", "horizontal", "vertical")
UNIT_NAMES = {"": "px", "in": "in", "cm": "cm", "mm": "mm"}
FOOT = 4  # half a foot's length, in pixels


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
        self.toolbar = Toolbar(self.close_overlay)
        for tool, tip in tooltips().items():
            button = flat(Gtk.ToggleButton(image=icon(f"ruler-{tool}"), tooltip_text=tip))
            button.connect("toggled", self._on_toggled, tool)
            self.buttons[tool] = button
            self.toolbar.add_item(button)
        fixed = Gtk.Fixed()
        fixed.put(self.toolbar, 0, 0)
        self.add(fixed)
        self._fixed = fixed
        self._show_tool()
        self.connect("realize", self._place_toolbar)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("scroll-event", self._on_scroll)

    def _place_toolbar(self, _window: Gtk.Window) -> None:
        self.toolbar.place(self._fixed, self.monitors, self.pointer)

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
