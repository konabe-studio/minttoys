"""Reordering rows by dragging them by a handle, as in GNOME's and Mint's own lists: six dots
in front of a row, a drag that shows the row itself under the pointer, and a drop on
another row that puts it there. Only rows of the same list take the drop.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import cairo  # noqa: E402
from gi.repository import Gdk, Gtk  # noqa: E402

TARGET = "TUXTOYS_ROW"
_TARGETS = [Gtk.TargetEntry.new(TARGET, Gtk.TargetFlags.SAME_APP, 0)]


def handle() -> Gtk.Widget:
    """Six dots, two across and three down, in the text's color dimmed; a grab cursor."""
    area = Gtk.DrawingArea()
    area.set_size_request(16, 24)
    area.set_valign(Gtk.Align.CENTER)

    def draw(widget: Gtk.Widget, context: cairo.Context) -> bool:
        color = widget.get_style_context().get_color(widget.get_state_flags())
        context.set_source_rgba(color.red, color.green, color.blue, 0.55)
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        for column in (-1, 1):
            for row in (-1, 0, 1):
                context.arc(width / 2 + column * 3, height / 2 + row * 5, 1.5, 0, 6.2832)
                context.fill()
        return True

    area.connect("draw", draw)
    box = Gtk.EventBox()
    box.add(area)
    box.connect(
        "realize",
        lambda widget: widget.get_window().set_cursor(
            Gdk.Cursor.new_from_name(widget.get_display(), "grab")
        ),
    )
    return box


def make_draggable(
    grip: Gtk.Widget, row: Gtk.Widget, index: int, moved: Callable[[int, int], None]
) -> None:
    """Lets `row`, at `index`, be dragged by `grip` and dropped on: `moved(from, to)`."""
    grip.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, _TARGETS, Gdk.DragAction.MOVE)
    row.drag_dest_set(Gtk.DestDefaults.ALL, _TARGETS, Gdk.DragAction.MOVE)

    def begin(_widget: Gtk.Widget, drag: Gdk.DragContext) -> None:
        width, height = row.get_allocated_width(), row.get_allocated_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)
        # The row has no background of its own: the theme's, so the picture is not see-through.
        found, base = row.get_style_context().lookup_color("theme_base_color")
        if found:
            context.set_source_rgba(base.red, base.green, base.blue, 0.95)
            context.paint()
        row.draw(context)
        surface.set_device_offset(-8, -height / 2)
        Gtk.drag_set_icon_surface(drag, surface)

    def get(
        _widget: Gtk.Widget, _drag: Gdk.DragContext, data: Gtk.SelectionData, *_a: object
    ) -> None:
        data.set(data.get_target(), 8, str(index).encode())

    def received(
        _widget: Gtk.Widget,
        _drag: Gdk.DragContext,
        _x: int,
        _y: int,
        data: Gtk.SelectionData,
        *_a: object,
    ) -> None:
        raw = data.get_data()
        if raw and raw.decode().isdigit() and int(raw.decode()) != index:
            moved(int(raw.decode()), index)

    grip.connect("drag-begin", begin)
    grip.connect("drag-data-get", get)
    row.connect("drag-data-received", received)
