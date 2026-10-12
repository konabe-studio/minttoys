"""What MintToys asks of X11, kept in one place so that it can be swapped for Wayland later.

Which windows Muffin keeps above the others and where they are, through libwnck, which reads
the window manager's EWMH hints; and a window's opacity, through python3-xlib, as the
_NET_WM_WINDOW_OPACITY hint Muffin draws windows with.
"""

from collections.abc import Callable, Iterable
from typing import Any

from minttoys.modules.alwaysontop.frame import Rect, step_opacity

type Changed = Callable[[dict[int, Rect], set[int]], None]


class AboveWindows:
    """Follows the windows kept above the others on the current workspace, and calls
    `changed` with their frames (decorations included) by X window id, and the ids of all
    open windows, whenever any of that changes. Windows of `excluded` applications, by
    WM_CLASS, are let go of as soon as they are pinned.
    """

    def __init__(self, changed: Changed, excluded: Iterable[str] = ()) -> None:
        import gi

        gi.require_version("Wnck", "3.0")
        from gi.repository import Wnck

        self._changed = changed
        self._excluded = {app.casefold() for app in excluded}
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
            if self._is_excluded(window):
                window.unmake_above()
                continue
            if workspace is not None and not window.is_visible_on_workspace(workspace):
                continue
            x, y, width, height = window.get_geometry()
            found[window.get_xid()] = Rect(x, y, width, height)
        return found

    def tell(self) -> None:
        open_ids = {window.get_xid() for window in self._screen.get_windows()}
        self._changed(self.above(), open_ids)

    def _is_excluded(self, window: Any) -> bool:  # noqa: ANN401, a Wnck.Window
        names = (window.get_class_group_name(), window.get_class_instance_name())
        return any(name and name.casefold() in self._excluded for name in names)

    def _watch(self, window: Any, tell: bool = True) -> None:  # noqa: ANN401, a Wnck.Window
        for signal in ("state-changed", "geometry-changed", "workspace-changed"):
            window.connect(signal, lambda *_: self.tell())
        if tell:
            self.tell()


def step_active_opacity(up: bool) -> bool:
    """Makes the active window one step more or less opaque, if Muffin keeps it above the
    others. Returns whether it did.
    """
    from Xlib import X, Xatom, display

    screen = display.Display()
    try:
        root = screen.screen().root
        active = root.get_full_property(screen.intern_atom("_NET_ACTIVE_WINDOW"), X.AnyPropertyType)
        if not active or not active.value or not active.value[0]:
            return False
        window = screen.create_resource_object("window", active.value[0])
        state = window.get_full_property(screen.intern_atom("_NET_WM_STATE"), Xatom.ATOM)
        above = screen.intern_atom("_NET_WM_STATE_ABOVE")
        if not state or above not in state.value:
            return False
        opacity = screen.intern_atom("_NET_WM_WINDOW_OPACITY")
        current = window.get_full_property(opacity, Xatom.CARDINAL)
        value = step_opacity(current.value[0] if current and current.value else None, up)
        window.change_property(opacity, Xatom.CARDINAL, 32, [value])
        screen.sync()
        return True
    finally:
        screen.close()
