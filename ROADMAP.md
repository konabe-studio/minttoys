# Roadmap

MintToys grows one milestone at a time. Each milestone brings in one new layer of
integration with Cinnamon, and it is done when every tool in it meets its own acceptance
criteria. There are no dates.

Tools carry the names of their PowerToys counterparts for now, so the two lists are easy
to compare. Final names may differ.

## M0: groundwork and Awake (done, released as 0.1.0)

The settings app, the background service, the panel icon, configuration, the `.deb`
package and translations, built end to end around a single tool.

| Tool | What it does |
|---|---|
| Awake | Keeps the computer awake until turned off, for a set time, or until a time of day |

## M1: quick wins

Brings in global keyboard shortcuts and the first Nemo action.

| Tool | What it does |
|---|---|
| Always on Top | Pins a window above all others with a shortcut |
| Light Switch | Switches between light and dark themes by time of day |
| New+ | Manages the file and folder templates in Nemo's right-click menu |
| File Locksmith | Shows which processes are holding a file |

## M2: Nemo pack

Brings in privileged actions, through `pkexec` and a narrow polkit policy.

| Tool | What it does |
|---|---|
| Image Resizer | Resizes images from Nemo's right-click menu |
| PowerRename | Renames files in bulk with regular expressions, a preview and undo |
| Hosts File Editor | Edits `/etc/hosts` in a window |
| Environment Variables | Manages environment variables, with profiles |

## M3: screen tools

Brings in a shared overlay and screen region selection.

| Tool | What it does |
|---|---|
| Color Picker | Picks a color from anywhere on screen, in several formats |
| Text Extractor | Copies the text in any part of the screen (OCR) |
| Shortcut Guide | Shows the keyboard shortcuts in an overlay |
| Screen Ruler | Measures distances on screen in pixels |

## M4: input and clipboard

Brings in global key monitoring.

| Tool | What it does |
|---|---|
| Advanced Paste | Pastes clipboard content as plain text, JSON or Markdown |
| Quick Accent | Offers accented characters on a long key press |
| Mouse Utilities | Pointer finder, click highlighter, crosshairs and pointer jump |
| PowerDisplay | Brightness, contrast and input of external monitors in one panel (DDC/CI) |
| Peek | Previews a file with a single key |
| File Explorer Add-ons | Thumbnails and previews for SVG, Markdown and source code in Nemo |

## M5: the big ones

Brings in a Cinnamon extension running inside the window manager.

| Tool | What it does |
|---|---|
| FancyZones | Custom window zones that windows snap into |
| Workspaces | Saves and restores apps and their window layout in one click |
| Command Palette | An extensible launcher and command search |
| Keyboard Manager | Remaps keys and shortcuts |
| ZoomIt | Zoom, on-screen drawing and a break timer for presentations |
| Crop And Lock | Shows a live, cropped part of another window in a window of its own |
| Window Hopper | Switches windows with previews |

## Left out on purpose

- **Grab And Move.** Cinnamon already moves windows with Alt and drag.
- **Command Not Found.** Debian's `command-not-found` package does this.
- **Registry Preview.** Linux has no registry.
- **Mouse Without Borders.** [Input Leap](https://github.com/input-leap/input-leap) and
  [Deskflow](https://github.com/deskflow/deskflow) already do it well, and the settings app
  will point to them.

## Not planned for 1.0

- Wayland sessions
- Desktops other than Cinnamon
- Flatpak or Snap packages
