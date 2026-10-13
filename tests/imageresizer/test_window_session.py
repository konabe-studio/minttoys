"""Image Resizer's window with real GTK, a stand-in for the resizing and for the daemon.
Needs a display: xvfb in CI, the desktop otherwise.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)
pytest.importorskip("PIL", reason="Pillow is not installed")

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from minttoys.api import NotRunning  # noqa: E402
from minttoys.imageresizer.window import ResizeWindow  # noqa: E402
from minttoys.modules.imageresizer.options import Options, Size  # noqa: E402
from minttoys.modules.imageresizer.resize import Unsupported  # noqa: E402


class FakeClient:
    def __init__(self, settings: dict | None = None, running: bool = True) -> None:
        self.settings = settings if settings is not None else Options().settings()
        self.saved: list[dict] = []
        self.running = running

    def module_settings(self, module_id: str) -> dict:
        if not self.running:
            raise NotRunning
        return dict(self.settings)

    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None:
        if not self.running:
            raise NotRunning
        self.saved.append(dict(changes))


class Resizer:
    def __init__(self, fail: dict[str, Exception] | None = None) -> None:
        self.calls: list[tuple[str, Size, Options]] = []
        self.fail = fail or {}

    def __call__(self, picture: Path, size: Size, options: Options) -> None:
        self.calls.append((picture.name, size, options))
        if picture.name in self.fail:
            raise self.fail[picture.name]


def open_window(
    client: FakeClient | None, resizer: Resizer, pictures: tuple[str, ...] = ("/p/a.jpg",)
) -> ResizeWindow:
    return ResizeWindow(None, pictures, client, resizer, in_background=False)


def test_it_starts_on_the_size_last_used() -> None:
    client = FakeClient(Options(selected=2).settings())
    window = open_window(client, Resizer())
    assert window.size_buttons[2].get_active()
    assert window.size.name == "$large$"
    assert not window.custom.get_sensitive()


def test_resize_with_a_size_and_remember_the_choices() -> None:
    client, resizer = FakeClient(), Resizer()
    window = open_window(client, resizer, ("/p/a.jpg", "/p/b.png"))
    window.size_buttons[1].set_active(True)
    window.shrink_only.set_active(True)
    window.start()
    assert [name for name, _size, _options in resizer.calls] == ["a.jpg", "b.png"]
    assert resizer.calls[0][1].name == "$medium$"
    assert resizer.calls[0][2].shrink_only
    assert client.saved[0]["selected"] == 1
    assert client.saved[0]["shrink_only"] is True
    assert window.failed == []


def test_a_size_of_ones_own() -> None:
    client, resizer = FakeClient(), Resizer()
    window = open_window(client, resizer)
    window.custom_button.set_active(True)
    assert window.custom.get_sensitive()
    window.fit.set_active_id("fill")
    window.width.set_value(500)
    window.height.set_value(0)
    window.unit.set_active_id("px")
    window.start()
    size = resizer.calls[0][1]
    assert (size.fit, size.width, size.height, size.unit) == ("fill", 500, 0, "px")
    assert client.saved[0]["custom"] == ("fill", 500.0, 0.0, "px")
    assert client.saved[0]["selected"] == 4


def test_a_size_of_ones_own_needs_a_side() -> None:
    window = open_window(FakeClient(), Resizer())
    window.custom_button.set_active(True)
    window.width.set_value(0)
    window.height.set_value(0)
    assert not window.resize_button.get_sensitive()


def test_failures_are_listed() -> None:
    resizer = Resizer({"a.jpg": Unsupported("ICO"), "b.jpg": OSError(13, "Permission denied")})
    window = open_window(FakeClient(), resizer, ("/p/a.jpg", "/p/b.jpg", "/p/c.jpg"))
    window.start()
    assert window.stack.get_visible_child_name() == "done"
    text = window.failures.get_text()
    assert "a.jpg: This kind of picture cannot be saved." in text
    assert "b.jpg: Permission denied" in text
    assert "c.jpg" not in text


def test_without_the_daemon_it_starts_from_the_defaults() -> None:
    resizer = Resizer()
    window = open_window(FakeClient(running=False), resizer)
    assert window.size_buttons[0].get_active()
    window.start()
    assert len(resizer.calls) == 1
