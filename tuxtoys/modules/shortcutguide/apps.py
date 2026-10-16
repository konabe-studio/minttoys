"""The apps Shortcut Guide knows the shortcuts of, a sheet each, and the shortcuts most
applications share.

Nemo's, Xed's and the Terminal's labels are those of the apps' own menus, taken with their
keys from the apps' sources (nemo-window-menus.c and nemo-view.c, xed-ui.h,
terminal-accels.cc), so they come in the apps' own words, from their gettext domains. The
Terminal keeps its shortcuts in GSettings, where the user may have changed them, so they
are read from there. Firefox has no gettext catalogue: its labels are TuxToys' own.
"""

from tuxtoys.core.i18n import N_
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Setting, Sheet, Text


def _item(domain: str, id: str, label: str, *keys: str) -> Item:
    return Item(id, Text(label, domain), keys)


def _nemo(id: str, label: str, *keys: str) -> Item:
    return _item("nemo", id, label, *keys)


def _xed(id: str, label: str, *keys: str) -> Item:
    return _item("xed", id, label, *keys)


def _ours(id: str, label: str, *keys: str) -> Item:
    return _item("", id, label, *keys)


TERMINAL_SCHEMA = "org.gnome.Terminal.Legacy.Keybindings"
TERMINAL_PATH = "/org/gnome/terminal/legacy/keybindings/"


def _terminal(key: str, label: str) -> Item:
    return Item(
        key,
        Text(label, "gnome-terminal"),
        setting=Setting(TERMINAL_SCHEMA, key, TERMINAL_PATH),
    )


COMMON = Group(
    # TRANSLATORS: a heading in Shortcut Guide over the shortcuts that work the same in
    # most applications, such as Ctrl+C to copy.
    Text(N_("Most applications")),
    (
        _ours("copy", N_("Copy"), "<Primary>c"),
        _ours("cut", N_("Cut"), "<Primary>x"),
        _ours("paste", N_("Paste"), "<Primary>v"),
        _ours("undo", N_("Undo"), "<Primary>z"),
        _ours("select-all", N_("Select all"), "<Primary>a"),
        _ours("find", N_("Find"), "<Primary>f"),
        _ours("save", N_("Save"), "<Primary>s"),
        _ours("print", N_("Print"), "<Primary>p"),
        _ours("close", N_("Close the window or tab"), "<Primary>w"),
        _ours("quit", N_("Quit the application"), "<Primary>q"),
        _ours("help", N_("Help"), "F1"),
        _ours("menubar", N_("Open the menu bar"), "F10"),
        _ours("context-menu", N_("Open the context menu"), "<Shift>F10", "Menu"),
        _ours("next-control", N_("Move to the next control"), "Tab"),
        _ours("previous-control", N_("Move to the previous control"), "<Shift>Tab"),
        _ours("fullscreen", N_("Full screen"), "F11"),
    ),
)

NEMO = Sheet(
    "nemo",
    "Nemo",
    ("system-file-manager-symbolic", "nemo"),
    (
        Group(
            Text("_File", "nemo"),
            (
                _nemo("NewWindow", "New _Window", "<Primary>n"),
                _nemo("NewTab", "New _Tab", "<Primary>t"),
                _nemo("NewFolder", "Create New _Folder", "<Primary><Shift>n"),
                _nemo("OpenInTerminal", "Open in Terminal", "<Shift>F4"),
                _nemo("Properties", "_Properties", "<Alt>Return", "<Primary>i"),
                _nemo("Close", "_Close", "<Primary>w"),
                _nemo("CloseAll", "Close _All Windows", "<Primary>q"),
            ),
        ),
        Group(
            Text("_Edit", "nemo"),
            (
                _nemo("Cut", "Cu_t", "<Primary>x"),
                _nemo("Copy", "_Copy", "<Primary>c"),
                _nemo("Paste", "_Paste", "<Primary>v"),
                _nemo("Undo", "_Undo", "<Primary>z"),
                _nemo("Redo", "_Redo", "<Primary>y"),
                _nemo("SelectAll", "Select _All", "<Primary>a"),
                _nemo("SelectPattern", "Select I_tems Matching...", "<Primary>s"),
                _nemo("InvertSelection", "_Invert Selection", "<Primary><Shift>i"),
                _nemo("Rename", "_Rename...", "F2"),
                _nemo("MakeLink", "Ma_ke Link", "<Primary>m"),
                _nemo("Trash", "Mo_ve to Trash", "Delete"),
                _nemo("Delete", "_Delete", "<Shift>Delete"),
                _nemo("Search", "_Search for Files...", "<Primary>f"),
            ),
        ),
        Group(
            Text("_View", "nemo"),
            (
                _nemo("Reload", "_Reload", "<Primary>r"),
                _nemo("ShowHidden", "Show _Hidden Files", "<Primary>h"),
                _nemo("ShowSidebar", "_Show Sidebar", "F9"),
                _nemo("ExtraPane", "E_xtra Pane", "F3"),
                _nemo("IconView", "Icon View", "<Primary>1"),
                _nemo("ListView", "List View", "<Primary>2"),
                _nemo("CompactView", "Compact View", "<Primary>3"),
                _nemo("ZoomIn", "Zoom _In", "<Primary>plus"),
                _nemo("ZoomOut", "Zoom _Out", "<Primary>minus"),
                _nemo("ZoomNormal", "Normal Si_ze", "<Primary>0"),
            ),
        ),
        Group(
            Text("_Go", "nemo"),
            (
                _nemo("Up", "Open _Parent", "<Alt>Up"),
                _nemo("Back", "_Back", "<Alt>Left"),
                _nemo("Forward", "_Forward", "<Alt>Right"),
                _nemo("Home", "_Home", "<Alt>Home"),
                _nemo("EditLocation", "Toggle _Location Entry", "<Primary>l"),
                _nemo("OtherPane", "S_witch to Other Pane", "F6"),
                _nemo("SameLocation", "Sa_me Location as Other Pane", "<Alt>s"),
                _nemo("PreviousTab", "_Previous Tab", "<Primary>Page_Up"),
                _nemo("NextTab", "_Next Tab", "<Primary>Page_Down"),
            ),
        ),
        Group(
            Text("_Bookmarks", "nemo"),
            (
                _nemo("AddBookmark", "_Add Bookmark", "<Primary>d"),
                _nemo("EditBookmarks", "_Edit Bookmarks...", "<Primary>b"),
            ),
        ),
    ),
    ("nemo", "nemo-desktop"),
)

XED = Sheet(
    "xed",
    "Xed",
    ("accessories-text-editor-symbolic", "xed"),
    (
        Group(
            Text("_File", "xed"),
            (
                _xed("FileNew", "_New", "<Primary>n"),
                _xed("FileOpen", "_Open...", "<Primary>o"),
                _xed("FileSave", "_Save", "<Primary>s"),
                _xed("FileSaveAs", "Save _As...", "<Primary><Shift>s"),
                _xed("FileSaveAll", "_Save All", "<Primary><Shift>l"),
                _xed("FilePrint", "_Print...", "<Primary>p"),
                _xed("FileClose", "_Close", "<Primary>w"),
                _xed("FileCloseAll", "_Close All", "<Primary><Shift>w"),
                _xed("FileQuit", "_Quit", "<Primary>q"),
            ),
        ),
        Group(
            Text("_Edit", "xed"),
            (
                _xed("EditUndo", "_Undo", "<Primary>z"),
                _xed("EditRedo", "_Redo", "<Primary>y"),
                _xed("EditDuplicate", "_Duplicate", "<Primary><Shift>d"),
                _xed("EditToggleComment", "_Toggle Comment", "<Primary>slash"),
                _xed("EditSelectAll", "Select _All", "<Primary>a"),
            ),
        ),
        Group(
            Text("_View", "xed"),
            (
                _xed("ViewSidePane", "Side _Pane", "F9"),
                _xed("ViewBottomPane", "_Bottom Pane", "<Primary>F9"),
                _xed("ViewWordWrap", "_Word wrap", "<Primary>r"),
                _xed("ViewOverviewMap", "_Overview Map", "F12"),
                _xed("ViewFullscreen", "Fullscreen", "F11"),
                _xed("ViewHighlightMode", "_Highlight Mode", "<Primary><Shift>h"),
            ),
        ),
        Group(
            Text("_Search", "xed"),
            (
                _xed("SearchFind", "_Find", "<Primary>f"),
                _xed("SearchFindNext", "Find Ne_xt", "<Primary>g"),
                _xed("SearchFindPrevious", "Find Pre_vious", "<Primary><Shift>g"),
                _xed("SearchReplace", "_Replace", "<Primary>h"),
                _xed("SearchGoToLine", "Go to _Line...", "<Primary>i"),
            ),
        ),
        Group(
            Text("_Documents", "xed"),
            (
                _xed("PreviousDocument", "_Previous Document", "<Primary><Alt>Page_Up"),
                _xed("NextDocument", "_Next Document", "<Primary><Alt>Page_Down"),
            ),
        ),
    ),
    ("xed",),
)

TERMINAL = Sheet(
    "terminal",
    "Terminal",
    ("utilities-terminal-symbolic", "org.gnome.Terminal"),
    (
        Group(
            Text("File", "gnome-terminal"),
            (
                _terminal("new-tab", "New Tab"),
                _terminal("new-window", "New Window"),
                _terminal("close-tab", "Close Tab"),
                _terminal("close-window", "Close Window"),
            ),
        ),
        Group(
            Text("Edit", "gnome-terminal"),
            (
                _terminal("copy", "Copy"),
                _terminal("paste", "Paste"),
                _terminal("select-all", "Select All"),
                _terminal("preferences", "Preferences"),
            ),
        ),
        Group(
            Text("View", "gnome-terminal"),
            (
                _terminal("full-screen", "Full Screen"),
                _terminal("zoom-in", "Zoom In"),
                _terminal("zoom-out", "Zoom Out"),
                _terminal("zoom-normal", "Normal Size"),
            ),
        ),
        Group(
            Text("Search", "gnome-terminal"),
            (
                _terminal("find", "Find"),
                _terminal("find-next", "Find Next"),
                _terminal("find-previous", "Find Previous"),
                _terminal("find-clear", "Clear Highlight"),
            ),
        ),
        Group(
            Text("Tabs", "gnome-terminal"),
            (
                _terminal("prev-tab", "Switch to Previous Tab"),
                _terminal("next-tab", "Switch to Next Tab"),
                _terminal("move-tab-left", "Move Tab to the Left"),
                _terminal("move-tab-right", "Move Tab to the Right"),
                _terminal("detach-tab", "Detach Tab"),
            ),
        ),
    ),
    ("gnome-terminal", "gnome-terminal-server"),
)

FIREFOX = Sheet(
    "firefox",
    "Firefox",
    ("firefox-symbolic", "firefox", "web-browser-symbolic"),
    (
        Group(
            # TRANSLATORS: a heading in Shortcut Guide's Firefox list.
            Text(N_("Tabs and windows")),
            (
                _ours("new-tab", N_("Open a new tab"), "<Primary>t"),
                _ours("close-tab", N_("Close the tab"), "<Primary>w"),
                _ours("reopen-tab", N_("Reopen the closed tab"), "<Primary><Shift>t"),
                _ours("next-tab", N_("Next tab"), "<Primary>Tab", "<Primary>Page_Down"),
                _ours(
                    "previous-tab",
                    N_("Previous tab"),
                    "<Primary><Shift>Tab",
                    "<Primary>Page_Up",
                ),
                _ours("new-window", N_("Open a new window"), "<Primary>n"),
                _ours("private-window", N_("Open a new private window"), "<Primary><Shift>p"),
            ),
        ),
        Group(
            # TRANSLATORS: a heading in Shortcut Guide's Firefox list.
            Text(N_("Navigation")),
            (
                _ours("address", N_("Go to the address bar"), "<Primary>l", "<Alt>d", "F6"),
                _ours("back", N_("Back"), "<Alt>Left"),
                _ours("forward", N_("Forward"), "<Alt>Right"),
                _ours("home", N_("Home page"), "<Alt>Home"),
                _ours("reload", N_("Reload"), "F5", "<Primary>r"),
                _ours(
                    "reload-skip-cache",
                    N_("Reload, skipping the cache"),
                    "<Primary>F5",
                    "<Primary><Shift>r",
                ),
            ),
        ),
        Group(
            # TRANSLATORS: a heading in Shortcut Guide's Firefox list.
            Text(N_("Page")),
            (
                _ours("find", N_("Find in the page"), "<Primary>f"),
                _ours("zoom-in", N_("Zoom in"), "<Primary>plus"),
                _ours("zoom-out", N_("Zoom out"), "<Primary>minus"),
                _ours("zoom-reset", N_("Reset the zoom"), "<Primary>0"),
                _ours("save", N_("Save the page"), "<Primary>s"),
                _ours("print", N_("Print"), "<Primary>p"),
                _ours("fullscreen", N_("Full screen"), "F11"),
            ),
        ),
        Group(
            # TRANSLATORS: a heading in Shortcut Guide's Firefox list.
            Text(N_("Bookmarks and tools")),
            (
                _ours("bookmark", N_("Bookmark the page"), "<Primary>d"),
                _ours("bookmarks", N_("Show all bookmarks"), "<Primary><Shift>o"),
                _ours("history", N_("History sidebar"), "<Primary>h"),
                _ours("downloads", N_("Downloads"), "<Primary><Shift>y"),
                _ours("devtools", N_("Web developer tools"), "<Primary><Shift>i", "F12"),
            ),
        ),
    ),
    ("firefox", "firefox-esr"),
)

APPS = (NEMO, XED, TERMINAL, FIREFOX)


def for_window(wm_class: str) -> Sheet | None:
    """The sheet for a window of this class, if there is one."""
    wanted = wm_class.lower()
    return next((sheet for sheet in APPS if wanted in sheet.wm_classes), None)
