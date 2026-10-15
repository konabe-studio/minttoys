# TuxToys

**Power-user utilities for Linux Mint Cinnamon. One package, one settings window.**

<a href="https://github.com/konabe-studio/tuxtoys/actions/workflows/ci.yml"><img src="https://github.com/konabe-studio/tuxtoys/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="License: GPL-3.0-or-later"></a>

---

TuxToys is a set of small desktop tools for Linux Mint Cinnamon, inspired by Microsoft
PowerToys. You install it once and switch each tool on or off from a single settings app.

Every tool is built on what Cinnamon already provides (Muffin, Nemo, gsettings and D-Bus),
so it follows your theme and behaves like the rest of the system. Where Cinnamon already
does something well, TuxToys leaves it alone, and each tool says what it adds over the
built-in one.

> **Status: early development.** Release 0.2.0 carries five tools: Awake, and the first
> milestone's Light Switch, Always on Top, File Locksmith and New+. Up to that release
> TuxToys was called MintToys; the next release is the first under the new name.

## The tools

### Awake

Keeps your computer from going to sleep while a long download, backup or render runs,
without touching your power settings.

- **Until you turn it off**, **for a set time** (30 minutes, 1 hour, 2 hours or your own),
  or **until a time of day**, even one past midnight.
- **Keep the screen on, or not.** With the screen allowed to turn off, Awake only stops the
  computer from sleeping.
- **From the panel.** One click turns it on or off, the icon shows the mode, the tooltip
  shows the time left, and a notification tells you when a timer runs out.
- **Nothing left behind.** Awake starts off after every login, and if TuxToys stops for
  any reason, your usual power settings apply again within seconds.

### Light Switch

Switches the desktop between Linux Mint's dark mode and its day mode (Mixed or Light),
the same way the Themes window does.

- **On a schedule:** Night Light's, sunset to sunrise included, or hours of your own.
- **Right now:** Super+Ctrl+Shift+D switches until the schedule next changes.

### Hosts File Editor

Edits `/etc/hosts`, which maps names to addresses on this computer, in a window: from
its page in the settings window, the applications menu or `tuxtoys hosts`.

- **Entries** with their address, host names and comment, each switched on or off, added,
  edited, duplicated, moved and deleted. A bad address or host name, or a host name
  another entry has too, is marked. Filters, and a ping for each.
- **Your file stays yours:** lines you do not touch stay exactly as they are, comments
  included, and a change made elsewhere is never written over.
- **Saving asks for an administrator's password** through pkexec; the window itself never
  runs as root. Before the first save of a session the file is backed up into
  `/var/backups/tuxtoys`, and old backups are deleted as you set it.

### Always on Top

Keeps a window above all the others, with Muffin's own Super+Ctrl+T.

- **A frame** around every pinned window, in your theme's accent color or a color of your
  own, with its width, opacity and rounded corners to set.
- **Opacity:** Super+Ctrl+Page Up and Page Down make a pinned window more or less opaque.
- **A sound** on pinning and letting go, if you want one, and **applications to leave
  out**, which are never kept on top.

### File Locksmith

Right-click a file or folder in Nemo and choose **What is using this?** to see which of
your processes hold it open, and end them if you need to.

### New+

Makes files and folders from your own templates. Right-click inside a folder in Nemo and
choose **New from template…**, pick a template and give the new item its name.

- **Folder templates**, copied whole, such as a project skeleton.
- **Variables in names**, if you want them: `$YYYY-$MM-$DD Notes.txt` becomes
  `2026-10-12 Notes.txt`. The date and time, the folder an item lands in, and environment
  variables such as `%USER%` are there.
- **Your order:** start the names with numbers, `1. Letter.odt`, and leave the numbers out
  of the names shown and made.
- **Manage them** in the settings window, or right-click a file in Nemo and choose **Save
  as template**. Nemo's own **Create New Document** keeps offering your file templates.

### Image Resizer

Choose one or more pictures in Nemo, right-click them and choose **Resize with Image
Resizer**.

- **Sizes to pick from**, Small, Medium, Large and Phone to start with, or one of your own
  in pixels, percent, centimeters or inches. Each one fits, fills or stretches.
- **Copies beside the originals**, named `photo (Small).jpg` or as you set it, or the
  originals themselves if you choose so. Nothing else is ever written over.
- **Upright and private:** pictures are turned the way they are shown, and the camera and
  location data can be removed.

### Rename+

Choose files or folders in Nemo, right-click them and choose **Rename with Rename+**.

- **Search and replace** plain text or a regular expression, in the name, the extension or
  both, the first match or every one. Every new name shows in a preview before anything
  is renamed, and any item can be left out.
- **More than a search:** counters with a start, a step and leading zeros, random text,
  the date and time an item was made, and lowercase, uppercase or capitalized words.
- **Folders and what is inside them**, all the way down, or files or folders alone.
- **Nothing is written over:** a name that is taken is shown, and swapping two names works.
- **Nemo's Rename (F2)** on several items can open Rename+ instead of Bulky, if you switch
  it on.

Every tool except Awake starts switched off, so nothing on your desktop changes until you
pick it. Everything planned next, grouped into milestones, is in the
[roadmap](ROADMAP.md).

## Install

Download the `.deb` from the
[latest release](https://github.com/konabe-studio/tuxtoys/releases/latest) and
double-click it, or install it from a terminal in the folder you downloaded it to:

```sh
sudo apt install ./tuxtoys_*_all.deb
```

Then log out and back in. The coffee cup appears in the panel, and TuxToys is in the
menu.

To remove TuxToys:

```sh
sudo apt purge tuxtoys
```

The panel icon stays until you log out. Your own settings stay in `~/.config/tuxtoys/`
and `~/.local/state/tuxtoys/`, yours to keep or delete. A keyboard shortcut a tool added
to Cinnamon, such as Light Switch's or Always on Top's, stays in the Keyboard settings too: switch the tool
off in TuxToys before removing the package, or delete the shortcut there. The same goes
for Nemo's Rename, if you let Rename+ take it over: switch Rename+ off first.

## Platform

| | |
|---|---|
| **Desktop** | Linux Mint Cinnamon: LMDE 7 first, the Ubuntu-based Linux Mint 22 as well |
| **Session** | X11. Wayland is not supported in 1.0 |
| **Package** | `.deb`. Several tools need system integration a Flatpak or Snap sandbox does not allow |
| **Built with** | Python 3 and GTK 3, like Linux Mint's own XApps |
| **Languages** | English and Hungarian from the first release |

## Development

The development tools are pinned in `requirements-dev.txt`. Install them into a virtual
environment, then run the same checks CI runs:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check && .venv/bin/ruff format --check && .venv/bin/pytest
```

To run TuxToys from a checkout, start the daemon and the panel icon from the checkout's
folder, each in a terminal of its own. The panel finds the icons by name only once they are
installed; until then, `scripts/dev-install.sh` links them into `~/.local/share`, and
`scripts/dev-install.sh --remove` takes them out again.

```sh
python3 -m tuxtoys.daemon
python3 -m tuxtoys.tray
python3 -m tuxtoys.settings
python3 -m tuxtoys awake status
```

The translations are in `po/`: the template `tuxtoys.pot`, and a `.po` file for each
language listed in `po/LINGUAS`. After a change to the text in the code, `make update-po`
brings them up to date. A checkout shows a translation once `make mo` has compiled it into
`build/locale`:

```sh
sudo apt install gettext make
make mo
LANGUAGE=hu python3 -m tuxtoys awake status
```

To add a language, copy the template to `po/<language>.po`, translate it, and add the
language to `po/LINGUAS`.

To build the Debian package, on LMDE or Linux Mint, from the checkout's folder:

```sh
sudo apt install debhelper dh-python gettext python3-pytest
dpkg-buildpackage --build=binary --no-sign
```

The package lands next to the checkout's folder. CI builds the same package on every pull
request, installs it, tries it and purges it again.

## Feedback

Ideas and bug reports are welcome in the
[issues](https://github.com/konabe-studio/tuxtoys/issues).

## License

TuxToys is free software, released under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE).

## Built with

Built with AI assistance (Claude Code), human-reviewed and maintained by Kōnabe Studio.

---

<p align="center"><sub>TuxToys is an independent project, not affiliated with or endorsed by Microsoft or the Linux Mint project. PowerToys is a trademark of Microsoft Corporation.</sub></p>
