# MintToys

**Power-user utilities for Linux Mint Cinnamon. One package, one settings window.**

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
