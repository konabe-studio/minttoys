# MintToys

**Power-user utilities for Linux Mint Cinnamon. One package, one settings window.**

<a href="https://github.com/konabe-studio/minttoys/actions/workflows/ci.yml"><img src="https://github.com/konabe-studio/minttoys/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue" alt="License: GPL-3.0-or-later"></a>

---

MintToys is a set of small desktop tools for Linux Mint Cinnamon, inspired by Microsoft
PowerToys. You install it once and switch each tool on or off from a single settings app.

Every tool is built on what Cinnamon already provides (Muffin, Nemo, gsettings and D-Bus),
so it follows your theme and behaves like the rest of the system. Where Cinnamon already
does something well, MintToys leaves it alone, and each tool says what it adds over the
built-in one.

> **Status: early development.** There is nothing to install yet. The first release
> carries a single tool, Awake, together with the groundwork every later tool builds on.

## The first tool: Awake

Awake keeps your computer from going to sleep while a long download, backup or render runs,
without touching your power settings.

- **Until you turn it off**, **for a set time** (30 minutes, 1 hour, 2 hours or your own),
  or **until a time of day**, even one past midnight.
- **Keep the screen on, or not.** With the screen allowed to turn off, Awake only stops the
  computer from sleeping.
- **From the panel.** One click turns it on or off, the tooltip shows the time left, and a
  notification tells you when a timer runs out.
- **Nothing left behind.** Awake starts off after every login, and if MintToys stops for
  any reason, your usual power settings apply again within seconds.

Everything planned after it, grouped into milestones, is in the [roadmap](ROADMAP.md).

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

To run MintToys from a checkout, start the daemon and the panel icon from the checkout's
folder, each in a terminal of its own. The panel finds the icons by name only once they are
installed; until then, `scripts/dev-install.sh` links them into `~/.local/share`, and
`scripts/dev-install.sh --remove` takes them out again.

```sh
python3 -m minttoys.daemon
python3 -m minttoys.tray
python3 -m minttoys.settings
python3 -m minttoys awake status
```

The translations are in `po/`: the template `minttoys.pot`, and a `.po` file for each
language listed in `po/LINGUAS`. After a change to the text in the code, `make update-po`
brings them up to date. A checkout shows a translation once `make mo` has compiled it into
`build/locale`:

```sh
sudo apt install gettext make
make mo
LANGUAGE=hu python3 -m minttoys awake status
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
[issues](https://github.com/konabe-studio/minttoys/issues).

## License

MintToys is free software, released under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE).

## Built with

Built with AI assistance (Claude Code), human-reviewed and maintained by Kōnabe Studio.

---

<p align="center"><sub>MintToys is an independent project, not affiliated with or endorsed by Microsoft or the Linux Mint project. PowerToys is a trademark of Microsoft Corporation.</sub></p>
