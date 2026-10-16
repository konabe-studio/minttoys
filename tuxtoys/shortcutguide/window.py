"""Shortcut Guide's window, laid out as PowerToys' is: a tall panel with a title, a search
field and the theme's own close button in its header bar, a rail of sheets on the left
(Cinnamon, TuxToys, the active app), and the chosen sheet's shortcuts beside it, pinned
ones first. Click a shortcut, right-click it, or press Enter or the Menu key on it, to pin
or unpin it. Escape, or clicking elsewhere, puts it away.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.shortcutguide.reading import (  # noqa: E402
    Row,
    Section,
    pinned,
    search,
    toggle_pin,
)

ICONS = "data/icons/hicolor/symbolic/apps"
CSS = b"""
.shortcutguide-keycap {
    border: 1px solid alpha(@theme_fg_color, 0.3);
    border-radius: 4px;
    padding: 1px 6px;
    background-color: alpha(@theme_fg_color, 0.05);
}
.shortcutguide-heading { font-weight: bold; }
.shortcutguide-rail row { padding: 6px 4px; }
list row.shortcutguide-chosen { background-color: alpha(@theme_selected_bg_color, 0.3); }
"""
SEARCH = "search"


@dataclass(frozen=True)
class Tab:
    id: str
    name: str
    icons: Sequence[str]
    sections: Sequence[Section]


def themed(names: str | Sequence[str], size: Gtk.IconSize) -> Gtk.Image:
    """The first of these icons the theme has; one of our own from the checkout until it
    is installed."""
    if isinstance(names, str):
        names = (names,)
    theme = Gtk.IconTheme.get_default()
    name = next((name for name in names if theme.has_icon(name)), names[-1])
    if theme.has_icon(name) or not name.startswith(APP_ID):
        return Gtk.Image.new_from_icon_name(name, size)
    from tuxtoys.core.nemo_action import PACKAGE_ROOT

    path = PACKAGE_ROOT / ICONS / f"{name}.svg"
    return Gtk.Image.new_from_gicon(Gio.FileIcon.new(Gio.File.new_for_path(str(path))), size)


def dim(widget: Gtk.Widget) -> Gtk.Widget:
    widget.get_style_context().add_class("dim-label")
    return widget


def keycaps(keys: Sequence[Sequence[str]]) -> Gtk.Box:
    """The shortcuts as rows of keycaps, "or" between two shortcuts for the same thing."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, valign=Gtk.Align.CENTER)
    for number, shortcut in enumerate(keys):
        if number:
            # TRANSLATORS: between two shortcuts that do the same, "Ctrl+R or F5".
            box.add(dim(Gtk.Label(label=_("or"))))
        for cap in shortcut:
            label = Gtk.Label(label=cap)
            label.get_style_context().add_class("shortcutguide-keycap")
            box.add(label)
    return box


def heading(text: str, top: int = 18) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.get_style_context().add_class("shortcutguide-heading")
    label.set_margin_top(top)
    label.set_margin_bottom(6)
    return label


class Guide(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        tabs: Sequence[Tab],
        first: str,
        pins: Sequence[str],
        geometry: tuple[int, int, int, int],
        save_pins: Callable[[tuple[str, ...]], None],
        open_settings: Callable[[], None],
    ) -> None:
        super().__init__(application=application, title=_("Shortcut Guide"))
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.get_style_context().add_class("shortcutguide")
        self.tabs = list(tabs)
        self.pins = tuple(pins)
        self._save_pins = save_pins
        self._open_settings = open_settings
        self._was_active = False
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(False)
        x, y, width, height = geometry
        self.set_size_request(width, height)
        self.move(x, y)

        self.set_titlebar(self._header(width))
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        outer.add(body)
        body.add(self._rail())
        body.add(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.stack = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.NONE)
        body.add(self.stack)
        self._pages: dict[str, Gtk.Box] = {}
        for tab in [*self.tabs, Tab(SEARCH, "", (), ())]:
            scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            for side in ("start", "end"):
                getattr(content, f"set_margin_{side}")(16)
            content.set_margin_bottom(16)
            scrolled.add(content)
            self.stack.add_named(scrolled, tab.id)
            self._pages[tab.id] = content
        for tab in self.tabs:
            self._fill(tab)

        self.connect("key-press-event", self._on_key)
        self.connect("notify::is-active", self._on_active)
        self.show_all()
        chosen = next((row for row in self.rail.get_children() if row.tab_id == first), None)
        self.rail.select_row(chosen or self.rail.get_row_at_index(0))
        self.search.grab_focus()

    def _header(self, width: int) -> Gtk.HeaderBar:
        """A header bar, so the close button is the theme's own, as on Mint's windows."""
        header = Gtk.HeaderBar(show_close_button=True)
        title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title.add(Gtk.Image.new_from_icon_name("input-keyboard-symbolic", Gtk.IconSize.MENU))
        title.add(Gtk.Label(label=_("Shortcut Guide"), xalign=0))
        header.pack_start(title)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(_("Search shortcuts"))
        # A header bar keeps its title in the middle at its own width: the most that fits
        # beside the title and the close button.
        self.search.set_size_request(max(160, width - 240), -1)
        self.search.connect("search-changed", self._on_search)
        header.set_custom_title(self.search)
        return header

    def _rail(self) -> Gtk.Box:
        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.rail = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.rail.get_style_context().add_class("shortcutguide-rail")
        self.rail.get_style_context().add_class("sidebar")
        for tab in self.tabs:
            row = Gtk.ListBoxRow()
            row.tab_id = tab.id
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.add(themed(tab.icons, Gtk.IconSize.LARGE_TOOLBAR))
            name = Gtk.Label(label=tab.name, max_width_chars=10)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            name.get_style_context().add_class("caption")
            box.add(name)
            row.add(box)
            self.rail.add(row)
        self.rail.connect("row-selected", self._on_tab)
        rail.pack_start(self.rail, True, True, 0)
        settings = Gtk.Button()
        settings.add(themed(f"{APP_ID}-settings-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        settings.get_style_context().add_class("flat")
        settings.set_tooltip_text(_("Settings"))
        settings.set_margin_bottom(8)
        settings.connect("clicked", self._on_settings)
        rail.pack_end(settings, False, False, 0)
        return rail

    def _clear(self, page: str) -> Gtk.Box:
        content = self._pages[page]
        for child in content.get_children():
            content.remove(child)
        return content

    def _add_rows(self, content: Gtk.Box, rows: Sequence[Row]) -> None:
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listing.get_style_context().add_class("frame")
        for row in rows:
            listing.add(self._row(row))
        listing.connect("row-activated", lambda _list, item: self._pin_menu(item, item.row))
        content.add(listing)

    def _fill(self, tab: Tab) -> None:
        content = self._clear(tab.id)
        content.add(heading(_("Pinned shortcuts"), top=12))
        rows = pinned(tab.sections, self.pins)
        if rows:
            self._add_rows(content, rows)
        else:
            content.add(dim(Gtk.Label(label=_("No pinned shortcuts"), xalign=0)))
        for section in tab.sections:
            content.add(heading(section.title))
            self._add_rows(content, section.rows)
        content.show_all()

    def _fill_search(self, query: str) -> None:
        content = self._clear(SEARCH)
        top = 12
        for tab in self.tabs:
            sections = search(tab.sections, query)
            if not sections:
                continue
            content.add(heading(tab.name, top=top))
            top = 18
            for section in sections:
                content.add(dim(Gtk.Label(label=section.title, xalign=0, margin_bottom=4)))
                self._add_rows(content, section.rows)
        if not content.get_children():
            label = dim(Gtk.Label(label=_("No shortcuts found."), xalign=0))
            label.set_margin_top(12)
            content.add(label)
        content.show_all()

    def _row(self, row: Row) -> Gtk.ListBoxRow:
        # Activatable, so the theme lights it up under the pointer; Enter or a click opens
        # the menu to pin it.
        item = Gtk.ListBoxRow(activatable=True)
        item.row = row
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(6)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        label = Gtk.Label(label=row.label, xalign=0, wrap=True)
        texts.add(label)
        if row.note:
            note = dim(Gtk.Label(label=row.note, xalign=0, wrap=True))
            note.get_style_context().add_class("caption")
            texts.add(note)
        box.add(texts)
        box.add(keycaps(row.keys))
        events = Gtk.EventBox()
        events.add(box)
        events.connect("button-press-event", self._on_row_button, item)
        item.add(events)
        item.connect("popup-menu", lambda widget: self._pin_menu(widget, row) or True)
        return item

    def _pin_menu(self, item: Gtk.ListBoxRow, row: Row) -> None:
        """The menu to pin or unpin a row, which is marked while the menu is open."""
        chosen = item.get_style_context()
        chosen.add_class("shortcutguide-chosen")
        popover = Gtk.Popover(relative_to=item)
        popover.connect("closed", lambda _popover: chosen.remove_class("shortcutguide-chosen"))
        button = Gtk.ModelButton(text=_("Unpin") if row.id in self.pins else _("Pin"))
        button.connect("clicked", lambda _button: self._toggle(row))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(6)
        box.add(button)
        popover.add(box)
        popover.show_all()
        popover.popup()

    def _toggle(self, row: Row) -> None:
        self.pins = toggle_pin(self.pins, row.id)
        self._save_pins(self.pins)
        # Redrawn after the popover has closed, which the old row still holds.
        GLib.idle_add(self._refill)

    def _refill(self) -> bool:
        for tab in self.tabs:
            self._fill(tab)
        if self.search.get_text().strip():
            self._fill_search(self.search.get_text())
        return False

    def _on_row_button(
        self, _widget: Gtk.Widget, event: Gdk.EventButton, item: Gtk.ListBoxRow
    ) -> bool:
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == Gdk.BUTTON_SECONDARY:
            self._pin_menu(item, item.row)
            return True
        return False

    def _on_tab(self, _rail: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        if self.search.get_text().strip():
            self.search.set_text("")
        self.stack.set_visible_child_name(row.tab_id)

    def _on_search(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        if query:
            self._fill_search(query)
            self.stack.set_visible_child_name(SEARCH)
        else:
            row = self.rail.get_selected_row()
            if row is not None:
                self.stack.set_visible_child_name(row.tab_id)

    def _on_settings(self, _button: Gtk.Button) -> None:
        self._open_settings()
        self.close()

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            if self.search.get_text():
                self.search.set_text("")
            else:
                self.close()
            return True
        return False

    def _on_active(self, *_args: object) -> None:
        # Put away when another window takes the focus, as PowerToys' is.
        if self.is_active():
            self._was_active = True
        elif self._was_active:
            GLib.idle_add(self._close_if_inactive)

    def _close_if_inactive(self) -> bool:
        if not self.is_active():
            self.close()
        return False
