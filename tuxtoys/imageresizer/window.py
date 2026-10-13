"""Image Resizer's window: the sizes to pick from, the four choices PowerToys offers, then
the pictures resized one after another, with a way to stop.
"""

import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _, ngettext  # noqa: E402
from tuxtoys.modules.imageresizer import resize as resizing  # noqa: E402
from tuxtoys.modules.imageresizer.options import FITS, UNITS, Options, Size  # noqa: E402
from tuxtoys.modules.imageresizer.text import describe, fit_name, unit_name  # noqa: E402

type Resizer = Callable[[Path, Size, Options], object]


def bold(text: str) -> str:
    """Markup for a heading. The message is passed in, never written inside an f-string,
    where xgettext would not find it.
    """
    return f"<b>{GLib.markup_escape_text(text)}</b>"


class Client(Protocol):
    def module_settings(self, module_id: str) -> dict: ...
    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None: ...


class ResizeWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        pictures: Sequence[str],
        client: Client | None,
        resize: Resizer = resizing.resize,
        in_background: bool = True,
    ) -> None:
        """Without a client, the window starts from the defaults and saves nothing. The
        tests hand in their own resize and run it in the foreground.
        """
        super().__init__(application=application, title=_("Image Resizer"))
        self.set_icon_name(APP_ID)
        self.set_default_size(460, -1)
        self.set_resizable(False)
        self.connect("key-press-event", self._on_key)
        self._pictures = [Path(picture) for picture in pictures]
        self._client = client
        self._resize = resize
        self._in_background = in_background
        self._stop = threading.Event()
        self.failed: list[tuple[str, str]] = []
        self.options = self._load()

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._choose_page(), "choose")
        self.stack.add_named(self._progress_page(), "progress")
        self.stack.add_named(self._done_page(), "done")
        self.add(self.stack)
        self.stack.show_all()
        self._show_custom()

    # The first page: what to do.

    def _choose_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        heading = Gtk.Label(xalign=0)
        heading.set_markup(bold(_("Resize your pictures")))
        box.pack_start(heading, False, False, 0)
        count = len(self._pictures)
        what = (
            self._pictures[0].name
            if count == 1
            else ngettext("{count} picture", "{count} pictures", count).format(count=count)
        )
        chosen = Gtk.Label(label=what, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        chosen.get_style_context().add_class("dim-label")
        box.pack_start(chosen, False, False, 0)

        sizes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.size_buttons: list[Gtk.RadioButton] = []
        group = None
        for size in self.options.sizes:
            button = self._size_button(group, size.shown_name, describe(size))
            group = group or button
            sizes.pack_start(button, False, False, 0)
        self.custom_button = self._size_button(group, _("Custom"), "")
        sizes.pack_start(self.custom_button, False, False, 0)
        self.size_buttons[min(self.options.selected, len(self.size_buttons) - 1)].set_active(True)
        box.pack_start(sizes, False, False, 0)

        self.custom = self._custom_row()
        box.pack_start(self.custom, False, False, 0)

        self.shrink_only = Gtk.CheckButton(
            label=_("Make pictures smaller but not larger"), active=self.options.shrink_only
        )
        self.replace_original = Gtk.CheckButton(
            label=_("Resize the original pictures (don't create copies)"),
            active=self.options.replace_original,
        )
        self.ignore_orientation = Gtk.CheckButton(
            label=_("Ignore the orientation of pictures"),
            active=self.options.ignore_orientation,
        )
        self.ignore_orientation.set_tooltip_text(
            _("The smaller number goes to the shorter side, so tall and wide pictures match.")
        )
        self.remove_metadata = Gtk.CheckButton(
            label=_("Remove metadata that doesn't affect rendering"),
            active=self.options.remove_metadata,
        )
        self.remove_metadata.set_tooltip_text(
            _("Such as the camera, the date taken and the place, in the EXIF and XMP data.")
        )
        for check in (
            self.shrink_only,
            self.replace_original,
            self.ignore_orientation,
            self.remove_metadata,
        ):
            box.pack_start(check, False, False, 0)

        buttons = Gtk.Box(spacing=6, margin_top=6)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _button: self.close())
        self.resize_button = Gtk.Button(label=_("Resize"), can_default=True)
        self.resize_button.get_style_context().add_class("suggested-action")
        self.resize_button.connect("clicked", lambda _button: self.start())
        buttons.pack_end(self.resize_button, False, False, 0)
        buttons.pack_end(cancel, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    def _size_button(
        self, group: Gtk.RadioButton | None, name: str, detail: str
    ) -> Gtk.RadioButton:
        button = Gtk.RadioButton.new_from_widget(group)
        label = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label.pack_start(Gtk.Label(label=name, xalign=0), False, False, 0)
        if detail:
            small = Gtk.Label(label=detail, xalign=0)
            small.get_style_context().add_class("dim-label")
            label.pack_start(small, False, False, 0)
        button.add(label)
        button.connect("toggled", lambda _button: self._show_custom())
        self.size_buttons.append(button)
        return button

    def _custom_row(self) -> Gtk.Widget:
        custom = self.options.custom
        grid = Gtk.Box(spacing=6, margin_start=24)
        self.fit = Gtk.ComboBoxText()
        for fit in FITS:
            self.fit.append(fit, fit_name(fit))
        self.fit.set_active_id(custom.fit)
        self.width = Gtk.SpinButton.new_with_range(0, 100_000, 1)
        self.width.set_value(custom.width)
        self.width.set_digits(2 if custom.unit in ("cm", "in") else 0)
        self.height = Gtk.SpinButton.new_with_range(0, 100_000, 1)
        self.height.set_value(custom.height)
        self.height.set_digits(self.width.get_digits())
        self.unit = Gtk.ComboBoxText()
        for unit in UNITS:
            self.unit.append(unit, unit_name(unit))
        self.unit.set_active_id(custom.unit)
        self.unit.connect("changed", self._on_unit)
        for field in (self.width, self.height):
            field.set_width_chars(6)
            field.set_tooltip_text(_("Leave it at 0 to keep the proportions."))
            field.connect("value-changed", lambda _field: self._check())
        grid.pack_start(self.fit, False, False, 0)
        grid.pack_start(self.width, False, False, 0)
        grid.pack_start(Gtk.Label(label="×"), False, False, 0)  # noqa: RUF001
        grid.pack_start(self.height, False, False, 0)
        grid.pack_start(self.unit, False, False, 0)
        return grid

    def _on_unit(self, _combo: Gtk.ComboBoxText) -> None:
        digits = 2 if self.unit.get_active_id() in ("cm", "in") else 0
        self.width.set_digits(digits)
        self.height.set_digits(digits)

    def _show_custom(self) -> None:
        if not hasattr(self, "resize_button"):
            return  # a radio button toggled while the page is still being built
        self.custom.set_sensitive(self.custom_button.get_active())
        self._check()

    def _check(self) -> None:
        """Resize can be pressed unless the size of one's own has neither side."""
        own = self.custom_button.get_active()
        self.resize_button.set_sensitive(
            not own or bool(self.width.get_value() or self.height.get_value())
        )

    @property
    def size(self) -> Size:
        for index, button in enumerate(self.size_buttons[:-1]):
            if button.get_active():
                return self.options.sizes[index]
        return Size(
            _("Custom"),
            self.fit.get_active_id() or "fit",
            self.width.get_value(),
            self.height.get_value(),
            self.unit.get_active_id() or "px",
        )

    # Resizing.

    def start(self) -> None:
        choices = {
            "selected": next(i for i, b in enumerate(self.size_buttons) if b.get_active()),
            "shrink_only": self.shrink_only.get_active(),
            "replace_original": self.replace_original.get_active(),
            "ignore_orientation": self.ignore_orientation.get_active(),
            "remove_metadata": self.remove_metadata.get_active(),
        }
        size = self.size
        if self.custom_button.get_active():
            choices["custom"] = (size.fit, size.width, size.height, size.unit)
        try:
            self.options = self.options.update(choices)
        except ValueError:
            return
        self._save(choices)
        self.stack.set_visible_child_name("progress")
        if self._in_background:
            threading.Thread(target=self._work, args=(size,), daemon=True).start()
        else:
            self._work(size)

    def _work(self, size: Size) -> None:
        total = len(self._pictures)
        for index, picture in enumerate(self._pictures):
            if self._stop.is_set():
                break
            self._later(self._show_progress, index, total, picture.name)
            try:
                self._resize(picture, size, self.options)
            except resizing.Unsupported:
                self.failed.append((picture.name, _("This kind of picture cannot be saved.")))
            except Exception as error:  # Pillow raises its own as well as OSError
                reason = getattr(error, "strerror", None) or str(error)
                self.failed.append((picture.name, reason))
        self._later(self._finish)

    def _later(self, function: Callable, *arguments: object) -> None:
        if self._in_background:
            GLib.idle_add(lambda: function(*arguments) and False)
        else:
            function(*arguments)

    def _progress_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        self.progress_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        box.pack_start(self.progress_label, False, False, 0)
        self.progress = Gtk.ProgressBar()
        box.pack_start(self.progress, False, False, 0)
        buttons = Gtk.Box()
        stop = Gtk.Button(label=_("Stop"))
        stop.connect("clicked", lambda _button: self._stop.set())
        buttons.pack_end(stop, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    def _show_progress(self, index: int, total: int, name: str) -> None:
        self.progress_label.set_text(_("Resizing {name}…").format(name=name))
        self.progress.set_fraction(index / total if total else 1)

    def _done_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        heading = Gtk.Label(xalign=0, wrap=True)
        heading.set_markup(bold(_("Some pictures could not be resized.")))
        box.pack_start(heading, False, False, 0)
        self.failures = Gtk.Label(xalign=0, wrap=True, selectable=True)
        box.pack_start(self.failures, False, False, 0)
        buttons = Gtk.Box()
        close = Gtk.Button(label=_("Close"))
        close.connect("clicked", lambda _button: self.close())
        buttons.pack_end(close, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        return box

    def _finish(self) -> None:
        if not self.failed:
            self.close()
            return
        self.failures.set_text("\n".join(f"{name}: {reason}" for name, reason in self.failed))
        self.stack.set_visible_child_name("done")

    # Settings, through the daemon when it is there.

    def _load(self) -> Options:
        if self._client is None:
            return Options()
        try:
            return Options.read(self._client.module_settings("imageresizer"))
        except (NotRunning, ModuleOff, Refused):
            return Options()

    def _save(self, choices: Mapping[str, object]) -> None:
        if self._client is None:
            return
        # Remembering the choices is a convenience; resizing goes on without it.
        with suppress(NotRunning, ModuleOff, Refused):
            self._client.set_module_settings("imageresizer", choices)

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape and self.stack.get_visible_child_name() != "progress":
            self.close()
            return True
        return False
