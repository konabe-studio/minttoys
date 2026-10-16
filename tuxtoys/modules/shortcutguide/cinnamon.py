"""Cinnamon's own shortcuts, as its Keyboard settings list them: the same groups, labels and
settings keys, from cinnamon-settings' KeybindingTable.py (cs_keyboard.py in older
versions), so the labels come in Cinnamon's own words, from its gettext domain. The keys
are read from the settings when the window opens, so they are the ones the user has.

A label Cinnamon later rewords is shown in English until this table follows.
"""

from tuxtoys.modules.shortcutguide.sheets import Group, Item, Setting, Sheet, Text

DOMAIN = "cinnamon"
WM = "org.cinnamon.desktop.keybindings.wm"
MEDIA = "org.cinnamon.desktop.keybindings.media-keys"
CINNAMON = "org.cinnamon.desktop.keybindings"


def _group(title: str, rows: tuple[tuple[str, str, str], ...]) -> Group:
    return Group(
        Text(title, DOMAIN),
        tuple(
            Item(key, Text(label, DOMAIN), setting=Setting(schema, key))
            for label, schema, key in rows
        ),
    )


GROUPS = (
    _group(
        "General",
        (
            ("Show the window selection screen", WM, "toggle-window-selection"),
            ("Show the workspace selection screen", WM, "toggle-workspace-selection"),
            ("Show desktop", WM, "show-desktop"),
            ("Show Desklets", CINNAMON, "show-desklets"),
            ("Show panels over a fullscreen window", CINNAMON, "show-panels"),
            ("Cycle through open windows", WM, "switch-windows"),
            ("Cycle backwards through open windows", WM, "switch-windows-backward"),
            ("Cycle through windows from all workspaces", WM, "switch-panels"),
            ("Cycle backwards through windows from all workspaces", WM, "switch-panels-backward"),
            ("Cycle through open windows of the same application", WM, "switch-group"),
            (
                "Cycle backwards through open windows of the same application",
                WM,
                "switch-group-backward",
            ),
            ("Run dialog", WM, "panel-run-dialog"),
        ),
    ),
    _group(
        "Pointer",
        (
            ("Move pointer to the next monitor", CINNAMON, "pointer-next-monitor"),
            ("Move pointer to the previous monitor", CINNAMON, "pointer-previous-monitor"),
        ),
    ),
    _group("Troubleshooting", (("Toggle Looking Glass", CINNAMON, "looking-glass-keybinding"),)),
    _group(
        "Keyboard",
        (
            ("Switch to next layout", WM, "switch-input-source"),
            ("Switch to previous layout", WM, "switch-input-source-backward"),
            ("Switch to first layout", WM, "switch-input-source-0"),
            ("Switch to second layout", WM, "switch-input-source-1"),
            ("Switch to third layout", WM, "switch-input-source-2"),
            ("Switch to fourth layout", WM, "switch-input-source-3"),
        ),
    ),
    _group(
        "Windows",
        (
            ("Maximize window", WM, "maximize"),
            ("Unmaximize window", WM, "unmaximize"),
            ("Minimize window", WM, "minimize"),
            ("Close window", WM, "close"),
            ("Activate window menu", WM, "activate-window-menu"),
            ("Raise window", WM, "raise"),
            ("Lower window", WM, "lower"),
            ("Toggle maximization state", WM, "toggle-maximized"),
            ("Toggle fullscreen state", WM, "toggle-fullscreen"),
            ("Toggle shaded state", WM, "toggle-shaded"),
            ("Toggle always on top", WM, "toggle-above"),
            ("Toggle showing window on all workspaces", WM, "toggle-on-all-workspaces"),
            ("Increase opacity", WM, "increase-opacity"),
            ("Decrease opacity", WM, "decrease-opacity"),
            ("Toggle vertical maximization", WM, "maximize-vertically"),
            ("Toggle horizontal maximization", WM, "maximize-horizontally"),
        ),
    ),
    _group(
        "Positioning",
        (
            ("Resize window", WM, "begin-resize"),
            ("Move window", WM, "begin-move"),
            ("Center window in screen", WM, "move-to-center"),
            ("Move window to upper-right", WM, "move-to-corner-ne"),
            ("Move window to upper-left", WM, "move-to-corner-nw"),
            ("Move window to lower-right", WM, "move-to-corner-se"),
            ("Move window to lower-left", WM, "move-to-corner-sw"),
            ("Move window to right edge", WM, "move-to-side-e"),
            ("Move window to top edge", WM, "move-to-side-n"),
            ("Move window to bottom edge", WM, "move-to-side-s"),
            ("Move window to left edge", WM, "move-to-side-w"),
        ),
    ),
    _group(
        "Tiling and Snapping",
        (
            ("Push tile left", WM, "push-tile-left"),
            ("Push tile right", WM, "push-tile-right"),
            ("Push tile up", WM, "push-tile-up"),
            ("Push tile down", WM, "push-tile-down"),
        ),
    ),
    _group(
        "Inter-workspace",
        (
            ("Move window to new workspace", WM, "move-to-workspace-new"),
            ("Move window to left workspace", WM, "move-to-workspace-left"),
            ("Move window to right workspace", WM, "move-to-workspace-right"),
            ("Move window to workspace 1", WM, "move-to-workspace-1"),
            ("Move window to workspace 2", WM, "move-to-workspace-2"),
            ("Move window to workspace 3", WM, "move-to-workspace-3"),
            ("Move window to workspace 4", WM, "move-to-workspace-4"),
            ("Move window to workspace 5", WM, "move-to-workspace-5"),
            ("Move window to workspace 6", WM, "move-to-workspace-6"),
            ("Move window to workspace 7", WM, "move-to-workspace-7"),
            ("Move window to workspace 8", WM, "move-to-workspace-8"),
            ("Move window to workspace 9", WM, "move-to-workspace-9"),
            ("Move window to workspace 10", WM, "move-to-workspace-10"),
            ("Move window to workspace 11", WM, "move-to-workspace-11"),
            ("Move window to workspace 12", WM, "move-to-workspace-12"),
        ),
    ),
    _group(
        "Inter-monitor",
        (
            ("Move window to left monitor", WM, "move-to-monitor-left"),
            ("Move window to right monitor", WM, "move-to-monitor-right"),
            ("Move window to monitor above", WM, "move-to-monitor-up"),
            ("Move window to monitor below", WM, "move-to-monitor-down"),
        ),
    ),
    _group(
        "Workspaces",
        (
            ("Switch to left workspace", WM, "switch-to-workspace-left"),
            ("Switch to right workspace", WM, "switch-to-workspace-right"),
        ),
    ),
    _group(
        "Direct Navigation",
        (
            ("Switch to workspace 1", WM, "switch-to-workspace-1"),
            ("Switch to workspace 2", WM, "switch-to-workspace-2"),
            ("Switch to workspace 3", WM, "switch-to-workspace-3"),
            ("Switch to workspace 4", WM, "switch-to-workspace-4"),
            ("Switch to workspace 5", WM, "switch-to-workspace-5"),
            ("Switch to workspace 6", WM, "switch-to-workspace-6"),
            ("Switch to workspace 7", WM, "switch-to-workspace-7"),
            ("Switch to workspace 8", WM, "switch-to-workspace-8"),
            ("Switch to workspace 9", WM, "switch-to-workspace-9"),
            ("Switch to workspace 10", WM, "switch-to-workspace-10"),
            ("Switch to workspace 11", WM, "switch-to-workspace-11"),
            ("Switch to workspace 12", WM, "switch-to-workspace-12"),
        ),
    ),
    _group(
        "System",
        (
            ("Log out", MEDIA, "logout"),
            ("Shut down", MEDIA, "shutdown"),
            ("Lock screen", MEDIA, "screensaver"),
            ("Suspend", MEDIA, "suspend"),
            ("Hibernate", MEDIA, "hibernate"),
            ("Restart Cinnamon", MEDIA, "restart-cinnamon"),
        ),
    ),
    _group(
        "Hardware",
        (
            ("Switch monitor configurations", WM, "switch-monitor"),
            ("Rotate display", WM, "rotate-monitor"),
            ("Orientation Lock", MEDIA, "video-rotation-lock"),
            ("Increase screen brightness", MEDIA, "screen-brightness-up"),
            ("Decrease screen brightness", MEDIA, "screen-brightness-down"),
            ("Toggle keyboard backlight", MEDIA, "kbd-brightness-toggle"),
            ("Increase keyboard backlight level", MEDIA, "kbd-brightness-up"),
            ("Decrease keyboard backlight level", MEDIA, "kbd-brightness-down"),
            ("Toggle touchpad state", MEDIA, "touchpad-toggle"),
            ("Turn touchpad on", MEDIA, "touchpad-on"),
            ("Turn touchpad off", MEDIA, "touchpad-off"),
            ("Show power statistics", MEDIA, "battery"),
        ),
    ),
    _group(
        "Screenshots and Recording",
        (
            ("Take a screenshot of an area", MEDIA, "area-screenshot"),
            ("Copy a screenshot of an area to clipboard", MEDIA, "area-screenshot-clip"),
            ("Take a screenshot", MEDIA, "screenshot"),
            ("Copy a screenshot to clipboard", MEDIA, "screenshot-clip"),
            ("Take a screenshot of a window", MEDIA, "window-screenshot"),
            ("Copy a screenshot of a window to clipboard", MEDIA, "window-screenshot-clip"),
            ("Toggle recording desktop (must restart Cinnamon)", WM, "toggle-recording"),
        ),
    ),
    _group(
        "Launchers",
        (
            ("Launch terminal", MEDIA, "terminal"),
            ("Launch help browser", MEDIA, "help"),
            ("Launch calculator", MEDIA, "calculator"),
            ("Launch email client", MEDIA, "email"),
            ("Launch web browser", MEDIA, "www"),
            ("Home folder", MEDIA, "home"),
            ("Search", MEDIA, "search"),
        ),
    ),
    _group(
        "Sound and Media",
        (
            ("Volume mute", MEDIA, "volume-mute"),
            ("Volume down", MEDIA, "volume-down"),
            ("Volume up", MEDIA, "volume-up"),
            ("Mic mute", MEDIA, "mic-mute"),
            ("Launch media player", MEDIA, "media"),
            ("Play", MEDIA, "play"),
            ("Pause playback", MEDIA, "pause"),
            ("Stop playback", MEDIA, "stop"),
            ("Previous track", MEDIA, "previous"),
            ("Next track", MEDIA, "next"),
            ("Eject", MEDIA, "eject"),
            ("Rewind", MEDIA, "audio-rewind"),
            ("Fast-forward", MEDIA, "audio-forward"),
            ("Repeat", MEDIA, "audio-repeat"),
            ("Shuffle", MEDIA, "audio-random"),
        ),
    ),
    _group(
        "Quiet Keys",
        (
            ("Volume mute (Quiet)", MEDIA, "mute-quiet"),
            ("Volume down (Quiet)", MEDIA, "volume-down-quiet"),
            ("Volume up (Quiet)", MEDIA, "volume-up-quiet"),
        ),
    ),
    _group(
        "Universal Access",
        (
            ("Zoom in", CINNAMON, "magnifier-zoom-in"),
            ("Zoom out", CINNAMON, "magnifier-zoom-out"),
            ("Reset zoom", CINNAMON, "magnifier-zoom-reset"),
            ("Turn screen reader on or off", MEDIA, "screenreader"),
            ("Turn on-screen keyboard on or off", MEDIA, "on-screen-keyboard"),
            ("Turn hover click on or off", CINNAMON, "hoverclick-toggle"),
            ("Increase text size", MEDIA, "increase-text-size"),
            ("Decrease text size", MEDIA, "decrease-text-size"),
            ("High contrast on or off", MEDIA, "toggle-contrast"),
        ),
    ),
)

# Cinnamon's heading over the user's own shortcuts in its Keyboard settings.
CUSTOM_TITLE = Text("Custom Shortcuts", DOMAIN)

SHEET = Sheet("cinnamon", "Cinnamon", "cinnamon-symbolic", GROUPS)
