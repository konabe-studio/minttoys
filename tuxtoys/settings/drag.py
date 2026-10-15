"""Reordering a list's rows by dragging them by a handle: six dots in front of a row, the
row itself under the pointer while it moves, and the other rows making room for it where
it would land, sliding apart, as in GNOME's and Mint's own lists.

The list (a vertical Gtk.Box of rows) takes the drop, not each row: the dragged row leaves
a gap that follows the pointer, closing where it was and opening where it goes.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import cairo  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

TARGET = "TUXTOYS_ROW"
_TARGETS = [Gtk.TargetEntry.new(TARGET, Gtk.TargetFlags.SAME_APP, 0)]
SLIDE_MS = 150


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


def _picture(row: Gtk.Widget) -> cairo.ImageSurface:
    """The row as it looks, on the theme's background so it is not see-through."""
    width, height = row.get_allocated_width(), row.get_allocated_height()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(width, 1), max(height, 1))
    context = cairo.Context(surface)
    found, base = row.get_style_context().lookup_color("theme_base_color")
    if found:
        context.set_source_rgba(base.red, base.green, base.blue, 0.95)
        context.paint()
    row.draw(context)
    surface.set_device_offset(-8, -height / 2)
    return surface


class DragList:
    """A Gtk.Box of rows that the user reorders by their handles; `moved(source, target)`
    gets the row's old place and the one it lands in, counted as after it has left.
    """

    def __init__(self, box: Gtk.Box, moved: Callable[[int, int], None]) -> None:
        self._box = box
        self._moved = moved
        self._rows: list[Gtk.Widget] = []
        self._dragged: int | None = None
        self._gap: Gtk.Revealer | None = None
        self._position: int | None = None
        box.drag_dest_set(Gtk.DestDefaults.DROP, _TARGETS, Gdk.DragAction.MOVE)
        box.connect("drag-motion", self._on_motion)
        box.connect("drag-data-received", self._on_received)

    def clear(self) -> None:
        for child in self._box.get_children():
            self._box.remove(child)
        self._rows = []
        self._dragged = None
        self._gap = None
        self._position = None

    def add(self, row: Gtk.Widget, grip: Gtk.Widget) -> None:
        index = len(self._rows)
        self._rows.append(row)
        self._box.pack_start(row, False, False, 0)
        grip.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, _TARGETS, Gdk.DragAction.MOVE)
        grip.connect("drag-begin", lambda _g, drag: self._begin(index, drag))
        grip.connect(
            "drag-data-get",
            lambda _g, _d, data, *_a: data.set(data.get_target(), 8, str(index).encode()),
        )
        grip.connect("drag-end", lambda *_a: self._end())

    def _begin(self, index: int, drag: Gdk.DragContext) -> None:
        row = self._rows[index]
        Gtk.drag_set_icon_surface(drag, _picture(row))
        self._dragged = index
        height = row.get_allocated_height()
        row.hide()
        # The gap starts where the row was, open, so nothing jumps.
        self._open_gap(index, height, animate=False)

    def _end(self) -> None:
        """After a drop, or a drag given up: everything back as it was drawn."""
        if self._dragged is not None and self._dragged < len(self._rows):
            self._rows[self._dragged].show()
        self._close_gap(animate=False)
        self._dragged = None

    def _others(self) -> list[Gtk.Widget]:
        return [row for i, row in enumerate(self._rows) if i != self._dragged]

    def _on_motion(self, box: Gtk.Box, drag: Gdk.DragContext, _x: int, y: int, time: int) -> bool:
        if self._dragged is None:
            return False
        others = self._others()
        top = box.get_allocation().y
        position = 0
        for row in others:
            allocation = row.get_allocation()
            if y > allocation.y - top + allocation.height / 2:
                position += 1
        if position != self._position:
            height = self._rows[self._dragged].get_allocated_height()
            self._close_gap(animate=True)
            self._open_gap(position, height, animate=True)
        Gdk.drag_status(drag, Gdk.DragAction.MOVE, time)
        return True

    def _open_gap(self, position: int, height: int, animate: bool) -> None:
        """An empty space of `height` before the `position`th of the other rows."""
        gap = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=SLIDE_MS if animate else 0,
        )
        space = Gtk.Box()
        space.set_size_request(-1, height)
        gap.add(space)
        others = self._others()
        before = others[position] if position < len(others) else None
        self._box.pack_start(gap, False, False, 0)
        place = (
            self._box.get_children().index(before)
            if before is not None
            else len(self._box.get_children()) - 1
        )
        self._box.reorder_child(gap, place)
        gap.show_all()
        gap.set_reveal_child(True)
        self._gap = gap
        self._position = position

    def _close_gap(self, animate: bool) -> None:
        gap, self._gap, self._position = self._gap, None, None
        if gap is None:
            return
        if not animate:
            gap.destroy()
            return
        gap.set_transition_duration(SLIDE_MS)
        gap.set_reveal_child(False)
        gap.connect("notify::child-revealed", lambda g, _p: g.destroy())

    def _on_received(
        self,
        _box: Gtk.Box,
        _drag: Gdk.DragContext,
        _x: int,
        _y: int,
        data: Gtk.SelectionData,
        *_args: object,
    ) -> None:
        raw = (data.get_data() or b"").decode()
        position = self._position
        if raw.isdigit() and position is not None and int(raw) != position:
            source = int(raw)
            # Once the drag is over: the list is drawn anew from what was saved.
            GLib.idle_add(lambda: self._moved(source, position) and False)
