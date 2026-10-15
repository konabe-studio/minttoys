"""Color Picker's editor, laid out as PowerToys' is: a Pick button and the colors picked
last along the top; on the left a bar of similar colors, the color itself in the middle,
which opens GTK's own color editor to fine-tune it; on the right the color in each format
shown, each with a button that copies it.

A color chosen from the bar or fine-tuned joins the history, as in PowerToys. A right
click on a color of the history offers to remove it.
"""

from collections.abc import Callable, Sequence
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

import cairo  # noqa: E402
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.colorpicker.colors import Color, format_color  # noqa: E402
from tuxtoys.modules.colorpicker.names import name  # noqa: E402
from tuxtoys.modules.colorpicker.shades import shades  # noqa: E402

SWATCH = 28


class Controller(Protocol):
    """What the editor asks of the program; app.ColorPickerApp is the real one."""

    history: Sequence[Color]
    formats: Sequence[tuple[str, str]]  # name, template, the shown ones

    def pick_again(self) -> None: ...
    def choose(self, color: Color) -> None: ...
    def remove(self, color: Color) -> None: ...
    def copy(self, text: str) -> None: ...


def swatch(
    color: Color, size: int, round_: bool, clicked: Callable[[Gdk.EventButton], None]
) -> Gtk.Widget:
    """A patch of `color` that takes clicks, round for the history, square for the bar."""
    area = Gtk.DrawingArea()
    area.set_size_request(size, size)
    area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    area.set_tooltip_text(f"{color.hex}  {name(color)}")

    def draw(widget: Gtk.Widget, context: cairo.Context) -> bool:
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        if round_:
            context.arc(width / 2, height / 2, min(width, height) / 2 - 1, 0, 6.2832)
        else:
            context.rectangle(0, 0, width, height)
        context.set_source_rgb(color.r / 255, color.g / 255, color.b / 255)
        context.fill_preserve()
        context.set_source_rgba(0, 0, 0, 0.25)
        context.set_line_width(1)
        context.stroke()
        return True

    area.connect("draw", draw)
    area.connect("button-press-event", lambda _w, event: clicked(event) or True)
    return area


class EditorWindow(Gtk.Window):
    def __init__(self, controller: Controller) -> None:
        super().__init__(title=_("Color Picker"))
        self.set_icon_name(APP_ID)
        self.set_default_size(460, 360)
        self._controller = controller
        self.selected: Color | None = None
        self.connect("key-press-event", self._on_key)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=12)
        top = Gtk.Box(spacing=12)
        pick = Gtk.Button(label=_("Pick"), always_show_image=True)
        pick.set_image(Gtk.Image.new_from_icon_name("color-select-symbolic", Gtk.IconSize.BUTTON))
        pick.set_tooltip_text(_("Pick a color from the screen"))
        pick.connect("clicked", lambda _button: controller.pick_again())
        top.pack_start(pick, False, False, 0)
        self.history = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=10,
            column_spacing=6,
            row_spacing=6,
            valign=Gtk.Align.CENTER,
        )
        top.pack_start(self.history, True, True, 0)
        layout.pack_start(top, False, False, 0)
        body = Gtk.Box(spacing=12)
        self.bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.pack_start(self.bar, False, False, 0)
        self.values = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.values.get_style_context().add_class("frame")
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scrolled.add(self.values)
        body.pack_start(scrolled, True, True, 0)
        layout.pack_start(body, True, True, 0)
        self.empty = Gtk.Label(label=_("No colors picked yet. Pick one from the screen."))
        self.empty.get_style_context().add_class("dim-label")
        layout.pack_start(self.empty, False, False, 0)
        self.add(layout)
        layout.show_all()
        self.show_colors()

    def show_colors(self, selected: Color | None = None) -> None:
        """Draws it all anew, `selected` or the newest color picked shown."""
        history = list(self._controller.history)
        self.selected = selected or (history[0] if history else None)
        for child in self.history.get_children():
            self.history.remove(child)
        for color in history:
            self.history.add(
                swatch(color, SWATCH, True, lambda event, c=color: self._on_history(event, c))
            )
        self.history.show_all()
        for child in self.bar.get_children():
            self.bar.remove(child)
        for row in self.values.get_children():
            self.values.remove(row)
        self.empty.set_visible(self.selected is None)
        if self.selected is None:
            return
        for shade in shades(self.selected):
            middle = shade == self.selected

            def clicked(_event: Gdk.EventButton, c: Color = shade, m: bool = middle) -> None:
                if m:
                    self.fine_tune()
                else:
                    self._controller.choose(c)

            patch = swatch(shade, 48, False, clicked)
            patch.set_size_request(48, 72 if middle else 48)
            if middle:
                patch.set_tooltip_text(_("Fine-tune this color"))
            self.bar.pack_start(patch, True, True, 0)
        self.bar.show_all()
        for format_name, template in self._controller.formats:
            self.values.add(self._value_row(format_name, format_color(self.selected, template)))
        self.values.show_all()

    def _value_row(self, format_name: str, value: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(activatable=False)
        box = Gtk.Box(spacing=12, margin=6)
        label = Gtk.Label(label=format_name, xalign=0, width_chars=8)
        label.get_style_context().add_class("dim-label")
        box.pack_start(label, False, False, 0)
        text = Gtk.Label(label=value, xalign=0, selectable=True, ellipsize=Pango.EllipsizeMode.END)
        box.pack_start(text, True, True, 0)
        copy = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        copy.set_image(Gtk.Image.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON))
        copy.set_tooltip_text(_("Copy"))
        copy.connect("clicked", lambda _button: self._controller.copy(value))
        box.pack_end(copy, False, False, 0)
        row.add(box)
        row.value = value
        return row

    def _on_history(self, event: Gdk.EventButton, color: Color) -> None:
        if event.button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label=_("Remove"))
            item.connect("activate", lambda _item: self._controller.remove(color))
            menu.append(item)
            menu.show_all()
            menu.attach_to_widget(self)
            menu.popup_at_pointer(event)
        else:
            self.show_colors(color)

    def fine_tune(self) -> None:
        """GTK's own color editor, on the color shown; what it gives joins the history."""
        if self.selected is None:
            return
        dialog = Gtk.ColorChooserDialog(
            title=_("Fine-tune the color"), transient_for=self, modal=True
        )
        dialog.set_use_alpha(False)
        rgba = Gdk.RGBA()
        rgba.parse(self.selected.hex)
        dialog.set_rgba(rgba)
        dialog.props.show_editor = True
        if dialog.run() == Gtk.ResponseType.OK:
            chosen = dialog.get_rgba()
            self._controller.choose(
                Color(round(chosen.red * 255), round(chosen.green * 255), round(chosen.blue * 255))
            )
        dialog.destroy()

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
