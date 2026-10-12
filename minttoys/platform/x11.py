"""What MintToys asks of X11, kept in one place so that it can be swapped for Wayland later.

Through libwnck, which reads the window manager's EWMH hints: which windows Muffin keeps
above the others, and where they are.
"""

from collections.abc import Callable

import gi

gi.require_version("Wnck", "3.0")

from gi.repository import Wnck  # noqa: E402

from minttoys.modules.alwaysontop.frame import Rect  # noqa: E402


class AboveWindows:
    """Follows the windows kept above the others on the current workspace, and calls
    `changed` with their frames (decorations included) whenever any of that changes.
    """

    def __init__(self, changed: Callable[[dict[int, Rect]], None]) -> None:
        self._changed = changed
        self._screen = Wnck.Screen.get_default()
        self._screen.force_update()
        for signal in ("window-closed", "active-workspace-changed", "window-stacking-changed"):
            self._screen.connect(signal, lambda *_: self.tell())
        self._screen.connect("window-opened", lambda _screen, window: self._watch(window))
        for window in self._screen.get_windows():
            self._watch(window, tell=False)
        self.tell()

    def above(self) -> dict[int, Rect]:
        """The frames of the windows kept above, by their X window id."""
        workspace = self._screen.get_active_workspace()
        found = {}
        for window in self._screen.get_windows():
            if not window.is_above() or window.is_minimized():
                continue
            if workspace is not None and not window.is_visible_on_workspace(workspace):
                continue
            x, y, width, height = window.get_geometry()
            found[window.get_xid()] = Rect(x, y, width, height)
        return found

    def tell(self) -> None:
        self._changed(self.above())

    def _watch(self, window: Wnck.Window, tell: bool = True) -> None:
        for signal in ("state-changed", "geometry-changed", "workspace-changed"):
            window.connect(signal, lambda *_: self.tell())
        if tell:
            self.tell()
