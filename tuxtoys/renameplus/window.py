"""Rename+'s window: what to search for and what to put in its place, PowerRename's
choices, and a preview of every chosen item with its new name, which renames on Rename.
"""

import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.clock import local_zone  # noqa: E402
from tuxtoys.core.i18n import _, ngettext  # noqa: E402
from tuxtoys.modules.renameplus import files  # noqa: E402
from tuxtoys.modules.renameplus.options import Options, remember  # noqa: E402
from tuxtoys.modules.renameplus.pattern import APPLY_TO, TEXT_CASES, PatternError  # noqa: E402
from tuxtoys.modules.renameplus.plan import (  # noqa: E402
    CLASH,
    INVALID,
    RENAME,
    SKIPPED,
    TOO_LONG,
    UNCHANGED,
    Include,
    Item,
    Outcome,
    count,
    plan,
)
from tuxtoys.modules.renameplus.text import (  # noqa: E402
    apply_to_names,
    text_case_names,
    variables,
)

type Renamer = Callable[[Sequence[files.Move]], tuple[list[files.Move], list[files.Failure]]]

WARNING_ICON = "dialog-warning-symbolic"
WARNING_CSS = b"entry image.right { color: @warning_color; }"
# The preview's columns: the box, the file type's icon or a thumbnail, the names, a
# warning sign, its tooltip, the index into the items, and whether the row is shown.
SELECTED, ICON, NAME, NEW, WARNING, TOOLTIP, INDEX, SHOWN, THUMBNAIL = range(9)
WAIT_MS = 150
# As Bulky shows them: thumbnails Nemo has made, this big, else the file type's icon.
THUMBNAIL_SIZE = 22
# How many rows get their icon at a time, while the window is already in use.
ICONS_AT_ONCE = 40


def bold(text: str) -> str:
    """Markup for a heading. The message is passed in, never written inside an f-string,
    where xgettext would not find it.
    """
    return f"<b>{GLib.markup_escape_text(text)}</b>"


class Client(Protocol):
    def module_settings(self, module_id: str) -> dict: ...
    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None: ...


def item_time(path: Path) -> datetime | None:
    """When the item was made, where the file system keeps it (GIO reads it with statx),
    else when it was last changed.
    """
    try:
        info = Gio.File.new_for_path(str(path)).query_info(
            "time::created,time::modified", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None
        )
    except GLib.Error:
        return None
    for key in ("time::created", "time::modified"):
        if info.has_attribute(key):
            return datetime.fromtimestamp(info.get_attribute_uint64(key), local_zone())
    return None


def look(path: Path, scale: int) -> tuple[Gio.Icon | None, GdkPixbuf.Pixbuf | None]:
    """The file type's icon, and the thumbnail Nemo has made of it if there is one: Bulky
    reads the same, and makes none of its own.
    """
    try:
        info = Gio.File.new_for_path(str(path)).query_info(
            "standard::icon,thumbnail::path,thumbnail::is-valid",
            Gio.FileQueryInfoFlags.NONE,
            None,
        )
    except GLib.Error:
        return None, None
    thumbnail = None
    if info.get_attribute_boolean("thumbnail::is-valid"):
        found = info.get_attribute_byte_string("thumbnail::path")
        if found:
            with suppress(GLib.Error):
                size = THUMBNAIL_SIZE * scale
                thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_scale(found, size, size, True)
    return info.get_icon(), thumbnail


def local_paths(arguments: Sequence[str]) -> tuple[list[Path], list[str]]:
    """The chosen items as paths: Nemo's Rename passes URIs, its action paths. And what
    has no path on this computer.
    """
    paths, elsewhere = [], []
    for argument in arguments:
        path = Gio.File.new_for_commandline_arg(argument).get_path()
        if path:
            paths.append(Path(path))
        else:
            elsewhere.append(argument)
    return paths, elsewhere


class RenameWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        chosen: Sequence[Path],
        client: Client | None,
        rename: Renamer = files.rename_all,
        when: Callable[[Path], datetime | None] = item_time,
        in_background: bool = True,
    ) -> None:
        """Without a client, the window starts from the defaults and saves nothing. The
        tests hand in their own renaming and run it in the foreground.
        """
        super().__init__(application=application, title=_("Rename+"))
        self.set_icon_name(APP_ID)
        self.set_default_size(820, 600)
        self.connect("key-press-event", self._on_key)
        self._client = client
        self._rename = rename
        self._in_background = in_background
        self._waiting = 0
        self.options = self._load()
        self.items, self.cut = files.gather(chosen, when)
        self.outcomes: list[Outcome] = []
        self.failed: list[files.Failure] = []

        warning = Gtk.CssProvider()
        warning.load_from_data(WARNING_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), warning, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._choose_page(), "choose")
        self.stack.add_named(self._working_page(), "working")
        self.stack.add_named(self._done_page(), "done")
        self.add(self.stack)
        self.stack.show_all()
        self.refresh()
        self._next_icon = 0
        GLib.idle_add(self._load_icons)

    # The first page: the search, the choices and the preview.

    def _choose_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        fields = Gtk.Grid(column_spacing=12, row_spacing=6)
        options = self.options if self.options.restore_flags else Options()
        self.search = self._entry(self.options.recent_search)
        self.replace = self._entry(self.options.recent_replace)
        if self.options.show_recent:
            self.search.set_text(next(iter(self.options.recent_search), ""))
            self.replace.set_text(next(iter(self.options.recent_replace), ""))
        fields.attach(Gtk.Label(label=_("Search for"), xalign=0), 0, 0, 1, 1)
        fields.attach(self.search, 1, 0, 1, 1)
        fields.attach(Gtk.Label(label=_("Replace with"), xalign=0), 0, 1, 1, 1)
        replace_row = Gtk.Box(spacing=6)
        replace_row.pack_start(self.replace, True, True, 0)
        replace_row.pack_start(self._variables_button(), False, False, 0)
        fields.attach(replace_row, 1, 1, 1, 1)
        box.pack_start(fields, False, False, 0)

        checks = Gtk.Grid(column_spacing=24, row_spacing=6, column_homogeneous=True)
        self.regex = self._check(_("Use regular expressions"), options.regex)
        self.match_all = self._check(_("Match all occurrences"), options.match_all)
        self.case_sensitive = self._check(_("Case sensitive"), options.case_sensitive)
        self.enumerate = self._check(_("Enumerate items"), options.enumerate)
        self.randomize = self._check(_("Random text"), options.randomize)
        self.include_files = self._check(_("Include files"), options.include_files)
        self.include_folders = self._check(_("Include folders"), options.include_folders)
        self.include_subfolders = self._check(
            _("Include what is inside folders"), options.include_subfolders
        )
        layout = (
            (self.regex, self.match_all, self.case_sensitive),
            (self.enumerate, self.randomize),
            (self.include_files, self.include_folders, self.include_subfolders),
        )
        for column, group in enumerate(layout):
            for row, check in enumerate(group):
                checks.attach(check, column, row, 1, 1)
        box.pack_start(checks, False, False, 0)

        combos = Gtk.Box(spacing=12)
        self.apply_to = self._combo(apply_to_names(), APPLY_TO, options.apply_to)
        self.text_case = self._combo(text_case_names(), TEXT_CASES, options.text_case)
        combos.pack_start(Gtk.Label(label=_("Apply to")), False, False, 0)
        combos.pack_start(self.apply_to, False, False, 0)
        combos.pack_start(Gtk.Label(label=_("Text case"), margin_start=12), False, False, 0)
        combos.pack_start(self.text_case, False, False, 0)
        box.pack_start(combos, False, False, 0)

        box.pack_start(self._preview(), True, True, 0)

        bottom = Gtk.Box(spacing=6)
        self.summary = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        bottom.pack_start(self.summary, True, True, 0)
        self.only_changing = Gtk.CheckButton(label=_("Show only items that change"))
        self.only_changing.connect("toggled", lambda _check: self.refresh())
        bottom.pack_start(self.only_changing, False, False, 12)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _button: self.close())
        self.rename_button = Gtk.Button(label=_("Rename"), can_default=True)
        self.rename_button.get_style_context().add_class("suggested-action")
        self.rename_button.connect("clicked", lambda _button: self.start())
        bottom.pack_end(self.rename_button, False, False, 0)
        bottom.pack_end(cancel, False, False, 0)
        box.pack_start(bottom, False, False, 0)
        return box

    def _entry(self, recent: Sequence[str]) -> Gtk.Entry:
        entry = Gtk.Entry(hexpand=True)
        store = Gtk.ListStore(str)
        for text in recent:
            store.append([text])
        completion = Gtk.EntryCompletion(model=store, minimum_key_length=0)
        completion.set_text_column(0)
        entry.set_completion(completion)
        entry.connect("changed", lambda _entry: self.refresh_soon())
        return entry

    def _check(self, label: str, active: bool) -> Gtk.CheckButton:
        check = Gtk.CheckButton(label=label, active=active)
        check.connect("toggled", lambda _check: self.refresh_soon())
        return check

    def _combo(self, names: Mapping[str, str], ids: Sequence[str], active: str) -> Gtk.ComboBoxText:
        combo = Gtk.ComboBoxText()
        for key in ids:
            # A combo's id cannot be empty: "" (keep the case) goes in as "-".
            combo.append(key or "-", names[key])
        combo.set_active_id(active or "-")
        combo.connect("changed", lambda _combo: self.refresh_soon())
        return combo

    def _variables_button(self) -> Gtk.Widget:
        """A button with what the replace text can hold; a click on one puts it in."""
        button = Gtk.MenuButton(image=Gtk.Image(icon_name="list-add-symbolic"))
        button.set_tooltip_text(_("Insert a variable"))
        popover = Gtk.Popover()
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True
        )
        scrolled.set_max_content_height(420)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin=12)
        for heading, entries in variables():
            label = Gtk.Label(xalign=0, margin_top=6)
            label.set_markup(bold(heading))
            rows.pack_start(label, False, False, 0)
            for text, meaning in entries:
                row = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
                line = Gtk.Box(spacing=12)
                code = Gtk.Label(label=text, xalign=0, width_chars=22)
                code.get_style_context().add_class("monospace")
                line.pack_start(code, False, False, 0)
                small = Gtk.Label(label=meaning, xalign=0)
                small.get_style_context().add_class("dim-label")
                line.pack_start(small, False, False, 0)
                row.add(line)
                row.connect("clicked", lambda _row, text=text: self._pick(popover, text))
                rows.pack_start(row, False, False, 0)
        scrolled.add(rows)
        scrolled.show_all()
        popover.add(scrolled)
        button.set_popover(popover)
        return button

    def _pick(self, popover: Gtk.Popover, text: str) -> None:
        popover.popdown()
        self.insert(text)

    def insert(self, text: str) -> None:
        """Puts `text` in the replace field where the cursor is."""
        position = self.replace.get_position()
        self.replace.insert_text(text, position)
        self.replace.set_position(position + len(text))
        self.replace.grab_focus_without_selecting()

    def _preview(self) -> Gtk.Widget:
        self.store = Gtk.TreeStore(bool, Gio.Icon, str, str, bool, str, int, bool, object)
        self._rows: list[Gtk.TreeIter] = []
        # The folders above the item at hand, as rows and as indexes into self.items.
        rows: list[Gtk.TreeIter] = []
        above: list[int] = []
        self._parent: list[int] = []
        for index, item in enumerate(self.items):
            del rows[item.depth :]
            del above[item.depth :]
            self._parent.append(above[-1] if above else -1)
            icon = Gio.ThemedIcon.new("folder" if item.is_folder else "text-x-generic")
            row = self.store.append(
                rows[-1] if rows else None,
                [True, icon, item.name, "", False, None, index, True, None],
            )
            self._rows.append(row)
            if item.is_folder:
                rows.append(row)
                above.append(index)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_column(SHOWN)
        self.view = Gtk.TreeView(model=self.filtered, enable_tree_lines=True)
        self.view.set_tooltip_column(TOOLTIP)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_toggled)
        original = Gtk.TreeViewColumn(_("Original"))
        original.pack_start(toggle, False)
        original.add_attribute(toggle, "active", SELECTED)
        icon = Gtk.CellRendererPixbuf()
        original.pack_start(icon, False)
        original.set_cell_data_func(icon, self._show_icon)
        name = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.MIDDLE)
        original.pack_start(name, True)
        original.add_attribute(name, "text", NAME)
        original.set_expand(True)
        original.set_resizable(True)
        self.view.append_column(original)

        renamed = Gtk.TreeViewColumn(_("Renamed"))
        status = Gtk.CellRendererPixbuf()
        renamed.pack_start(status, False)
        renamed.set_cell_data_func(status, self._show_warning)
        new = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.MIDDLE)
        renamed.pack_start(new, True)
        renamed.add_attribute(new, "text", NEW)
        renamed.set_expand(True)
        renamed.set_resizable(True)
        self.view.append_column(renamed)
        self.view.expand_all()

        scrolled = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scrolled.add(self.view)
        return scrolled

    def _show_icon(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        row: Gtk.TreeIter,
        *_data: object,
    ) -> None:
        thumbnail = model[row][THUMBNAIL]
        if thumbnail is not None:
            cell.set_property("gicon", None)
            cell.set_property("surface", thumbnail)
        else:
            cell.set_property("surface", None)
            cell.set_property("gicon", model[row][ICON])

    def _show_warning(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        row: Gtk.TreeIter,
        *_data: object,
    ) -> None:
        cell.set_property("surface", self._warning_sign() if model[row][WARNING] else None)

    def _warning_sign(self) -> object:
        """The warning sign in the theme's warning colour, amber in Mint-Y, as the search
        field shows it.
        """
        if getattr(self, "_sign", None) is None:
            scale = self.get_scale_factor()
            found, colour = self.get_style_context().lookup_color("warning_color")
            lookup = Gtk.IconTheme.get_default().lookup_icon_for_scale(
                WARNING_ICON, 16, scale, Gtk.IconLookupFlags.FORCE_SYMBOLIC
            )
            if lookup is None:
                return None
            if not found:
                colour = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            pixbuf, _symbolic = lookup.load_symbolic(colour, None, None, None)
            self._sign = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale, None)
        return self._sign

    def _load_icons(self) -> bool:
        """Puts each item's own icon or thumbnail in, a few rows at a time."""
        scale = self.get_scale_factor()
        end = min(self._next_icon + ICONS_AT_ONCE, len(self.items))
        for index in range(self._next_icon, end):
            item = self.items[index]
            icon, thumbnail = look(Path(item.folder, item.name), scale)
            row = self._rows[index]
            if icon is not None:
                self.store[row][ICON] = icon
            if thumbnail is not None:
                surface = Gdk.cairo_surface_create_from_pixbuf(thumbnail, scale, None)
                self.store[row][THUMBNAIL] = surface
        self._next_icon = end
        return end < len(self.items)

    def _on_toggled(self, _toggle: Gtk.CellRendererToggle, path: str) -> None:
        row = self.filtered.convert_iter_to_child_iter(self.filtered.get_iter(path))
        self.store[row][SELECTED] = not self.store[row][SELECTED]
        self.refresh()

    # Working out the new names.

    @property
    def flags(self) -> dict[str, object]:
        return {
            "regex": self.regex.get_active(),
            "match_all": self.match_all.get_active(),
            "case_sensitive": self.case_sensitive.get_active(),
            "apply_to": self.apply_to.get_active_id() or "both",
            "text_case": (self.text_case.get_active_id() or "-").strip("-"),
            "enumerate": self.enumerate.get_active(),
            "randomize": self.randomize.get_active(),
            "include_files": self.include_files.get_active(),
            "include_folders": self.include_folders.get_active(),
            "include_subfolders": self.include_subfolders.get_active(),
        }

    def refresh_soon(self) -> None:
        """Works the names out again once typing pauses."""
        if self._waiting:
            GLib.source_remove(self._waiting)
        self._waiting = GLib.timeout_add(WAIT_MS, self._refresh_now)

    def _refresh_now(self) -> bool:
        self._waiting = 0
        self.refresh()
        return False

    def refresh(self) -> None:
        options = self.options.update(self.flags)
        rules = options.rules(self.search.get_text(), self.replace.get_text())
        include = Include(
            options.include_files, options.include_folders, options.include_subfolders
        )
        selected = self._selected()
        items = [
            Item(i.folder, i.name, i.is_folder, i.depth, i.when, selected[index])
            for index, i in enumerate(self.items)
        ]
        try:
            self.outcomes = plan(items, rules, include, files.taken)
            problem = ""
        except PatternError as error:
            self.outcomes = [Outcome(UNCHANGED)] * len(items)
            problem = _("This is not a regular expression: {error}").format(error=error)
        self.search.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, WARNING_ICON if problem else None
        )
        self.search.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, problem or None)
        self._show_outcomes()

    def _selected(self) -> list[bool]:
        selected = [True] * len(self.items)

        def visit(model: Gtk.TreeModel, _path: object, row: Gtk.TreeIter) -> bool:
            selected[model[row][INDEX]] = model[row][SELECTED]
            return False

        self.store.foreach(visit)
        return selected

    def _show_outcomes(self) -> None:
        texts = {
            INVALID: _("This name cannot be used."),
            TOO_LONG: _("This name is too long."),
            CLASH: _("This name is taken."),
        }

        # With "Show only items that change", an item that changes and the folders above it.
        shown = [not self.only_changing.get_active()] * len(self.items)
        for index, outcome in enumerate(self.outcomes):
            while outcome.status not in (UNCHANGED, SKIPPED) and index >= 0 and not shown[index]:
                shown[index] = True
                index = self._parent[index]

        def visit(model: Gtk.TreeModel, _path: object, row: Gtk.TreeIter) -> bool:
            index = model[row][INDEX]
            outcome = self.outcomes[index]
            problem = texts.get(outcome.status)
            model[row][NEW] = outcome.new_name
            model[row][WARNING] = bool(problem)
            model[row][TOOLTIP] = GLib.markup_escape_text(problem) if problem else None
            model[row][SHOWN] = shown[index]
            return False

        self.store.foreach(visit)
        self.filtered.refilter()
        self.view.expand_all()
        renamed = count(self.outcomes)
        total = len(self.items)
        summary = ngettext(
            "{renamed} of {total} item will be renamed.",
            "{renamed} of {total} items will be renamed.",
            total,
        ).format(renamed=renamed, total=total)
        if self.cut:
            summary += " " + _("Some items inside the folders are not listed.")
        self.summary.set_text(summary)
        self.rename_button.set_sensitive(renamed > 0)

    # Renaming.

    def start(self) -> None:
        self.refresh()
        moves = [
            files.Move(item.folder, item.name, outcome.new_name, item.depth)
            for item, outcome in zip(self.items, self.outcomes, strict=True)
            if outcome.status == RENAME
        ]
        if not moves:
            return
        self._save()
        self.stack.set_visible_child_name("working")
        if self._in_background:
            threading.Thread(target=self._work, args=(moves,), daemon=True).start()
        else:
            self._work(moves)

    def _work(self, moves: list[files.Move]) -> None:
        _done, failed = self._rename(moves)
        if self._in_background:
            GLib.idle_add(lambda: self._finish(failed) and False)
        else:
            self._finish(failed)

    def _working_page(self) -> Gtk.Widget:
        box = Gtk.Box(spacing=12, margin=18, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        spinner = Gtk.Spinner(active=True)
        box.pack_start(spinner, False, False, 0)
        box.pack_start(Gtk.Label(label=_("Renaming…")), False, False, 0)
        return box

    def _done_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        heading = Gtk.Label(xalign=0, wrap=True)
        heading.set_markup(bold(_("Some items could not be renamed.")))
        box.pack_start(heading, False, False, 0)
        self.failures = Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=True)
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.add(self.failures)
        box.pack_start(scrolled, True, True, 0)
        buttons = Gtk.Box()
        close = Gtk.Button(label=_("Close"))
        close.connect("clicked", lambda _button: self.close())
        buttons.pack_end(close, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    def _finish(self, failed: list[files.Failure]) -> None:
        self.failed = failed
        if not failed:
            self.close()
            return
        lines = []
        for failure in failed:
            reason = failure.reason or _("The new name was taken meanwhile.")
            lines.append(f"{failure.name}: {reason}")
            if failure.left_as:
                lines.append(
                    _("It is now called {hidden} in {folder}.").format(
                        hidden=failure.left_as, folder=failure.folder
                    )
                )
        self.failures.set_text("\n".join(lines))
        self.stack.set_visible_child_name("done")

    # Settings, through the daemon when it is there.

    def _load(self) -> Options:
        if self._client is None:
            return Options()
        try:
            return Options.read(self._client.module_settings("renameplus"))
        except (NotRunning, ModuleOff, Refused):
            return Options()

    def _save(self) -> None:
        changes = dict(self.flags)
        changes["recent_search"] = remember(self.options.recent_search, self.search.get_text())
        changes["recent_replace"] = remember(self.options.recent_replace, self.replace.get_text())
        if self._client is None:
            return
        # Remembering the choices is a convenience; renaming goes on without it.
        with suppress(NotRunning, ModuleOff, Refused):
            self._client.set_module_settings("renameplus", changes)

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape and self.stack.get_visible_child_name() != "working":
            self.close()
            return True
        return False
