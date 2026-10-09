"""Linux Mint's styles, as the Themes window's simplified settings know them, and how it moves
between their light, dark and mixed modes. Free of GTK and D-Bus.

The styles are JSON files in /usr/share/cinnamon/styles.d. Each style (Mint-Y, Mint-L) has
up to three modes, and each mode a list of colour variants, each naming four themes: the
applications' (gtk), the icons, the desktop's (cinnamon) and the cursor. This follows
Cinnamon's own cs_themes.py: a variant whose themes are not all installed is left out, and
a mode switch keeps the variant of the same name (Aqua stays Aqua), else takes the mode's
default.
"""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

STYLES_DIR = Path("/usr/share/cinnamon/styles.d")
MODES = ("mixed", "dark", "light")
# org.x.apps.portal color-scheme for each mode, as Cinnamon's Themes module sets it.
COLOR_SCHEMES = {"mixed": "default", "dark": "prefer-dark", "light": "prefer-light"}


@dataclass(frozen=True)
class Look:
    """The four themes a variant sets, which together are what the desktop looks like."""

    gtk: str
    icons: str
    cinnamon: str
    cursor: str


@dataclass(frozen=True)
class Variant:
    name: str
    look: Look


@dataclass
class Style:
    name: str
    # Each mode the style has, with its variants, the first one the default.
    modes: dict[str, list[Variant]] = field(default_factory=dict)


def parse(text: str, installed: Callable[[Look], bool]) -> list[Style]:
    """The styles of one .styles file. Raises ValueError for a file that is not one."""
    try:
        document = json.loads(text)
        styles = []
        for style_json in document["styles"]:
            style = Style(style_json["name"])
            for mode in MODES:
                variants = []
                for variant_json in style_json.get(mode, []):
                    variant = _variant(variant_json)
                    if variant is None or not installed(variant.look):
                        continue
                    if variant_json.get("default") == "true":
                        variants.insert(0, variant)
                    else:
                        variants.append(variant)
                if variants:
                    style.modes[mode] = variants
            if style.modes:
                styles.append(style)
        return styles
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError(f"not a styles file: {error}") from error


def _variant(variant_json: dict) -> Variant | None:
    themes = variant_json.get("themes")
    names = {key: variant_json.get(key, themes) for key in ("gtk", "icons", "cinnamon", "cursor")}
    if not all(isinstance(name, str) for name in names.values()):
        return None
    return Variant(str(variant_json["name"]), Look(**names))


def load(installed: Callable[[Look], bool], directory: Path = STYLES_DIR) -> list[Style]:
    """Every style Mint offers here, in the order of its files. A file that cannot be read
    or parsed is skipped, as the Themes window skips it.
    """
    styles = []
    for path in sorted(directory.glob("*.styles")):
        try:
            styles.extend(parse(path.read_text(encoding="utf-8"), installed))
        except (OSError, ValueError):
            continue
    return styles


def active(styles: Iterable[Style], current: Look) -> tuple[Style, str, Variant] | None:
    """The style, mode and variant the current themes are, if any. Like the Themes window,
    the last match wins.
    """
    found = None
    for style in styles:
        for mode, variants in style.modes.items():
            for variant in variants:
                if variant.look == current:
                    found = (style, mode, variant)
    return found


def variant_for(style: Style, mode: str, current: Variant) -> Variant | None:
    """The variant a switch to `mode` sets: the one of the same name, else the mode's
    default. None when the style has no such mode.
    """
    variants = style.modes.get(mode)
    if not variants:
        return None
    for variant in variants:
        if variant.name == current.name:
            return variant
    return variants[0]


class Installed:
    """Whether a look's four themes are installed, by Cinnamon's rules: a GTK theme has a
    gtk-3.* folder with a gtk.css, a desktop theme a cinnamon folder (or is the built-in
    "cinnamon"), an icon theme an index.theme with Directories= and not Hidden=true, and a
    cursor theme a cursors folder.
    """

    def __init__(self, home: Path, data_home: Path, data_dirs: Iterable[Path]) -> None:
        dirs = list(data_dirs)
        self._themes = [home / ".themes", data_home / "themes"] + [d / "themes" for d in dirs]
        self._icons = [home / ".icons", data_home / "icons"] + [d / "icons" for d in dirs]

    def __call__(self, look: Look) -> bool:
        return (
            self._gtk(look.gtk)
            and self._cinnamon(look.cinnamon)
            and self._icon(look.icons)
            and self._cursor(look.cursor)
        )

    def _gtk(self, name: str) -> bool:
        return any(
            (gtk3 / "gtk.css").is_file()
            for folder in self._themes
            for gtk3 in (folder / name).glob("gtk-3.*")
        )

    def _cinnamon(self, name: str) -> bool:
        return name == "cinnamon" or any((f / name / "cinnamon").exists() for f in self._themes)

    def _icon(self, name: str) -> bool:
        for folder in self._icons:
            try:
                lines = (folder / name / "index.theme").read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line in lines:
                if line.startswith("Hidden=true"):
                    break
                if line.startswith("Directories="):
                    return True
        return False

    def _cursor(self, name: str) -> bool:
        return any((folder / name / "cursors").exists() for folder in self._icons)
