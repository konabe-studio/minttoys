import json
from pathlib import Path

import pytest

from minttoys.modules.lightswitch import styles
from minttoys.modules.lightswitch.styles import Installed, Look, Variant

# The shape of Mint's styles files, cut down: Mint-Y with two colours in its mixed mode.
MINT_Y = {
    "styles": [
        {
            "name": "Mint-Y",
            "default": "mixed",
            "mixed": [
                {
                    "name": "Aqua",
                    "gtk": "Mint-Y-Aqua",
                    "icons": "Mint-Y-Sand",
                    "cinnamon": "Mint-Y-Dark-Aqua",
                    "cursor": "Bibata-Modern-Classic",
                    "color": "#6cabcd",
                },
                {
                    "name": "Blue",
                    "gtk": "Mint-Y-Blue",
                    "icons": "Mint-Y-Blue",
                    "cinnamon": "Mint-Y-Dark-Blue",
                    "cursor": "Bibata-Modern-Classic",
                    "color": "#5b73c4",
                    "default": "true",
                },
            ],
            "dark": [
                {
                    "name": "Aqua",
                    "gtk": "Mint-Y-Dark-Aqua",
                    "icons": "Mint-Y-Sand",
                    "cinnamon": "Mint-Y-Dark-Aqua",
                    "cursor": "Bibata-Modern-Classic",
                    "color": "#6cabcd",
                }
            ],
            "light": [
                {
                    "name": "Blue",
                    "themes": "Mint-Y-Blue",
                    "cursor": "Bibata-Modern-Classic",
                    "color": "#5b73c4",
                }
            ],
        }
    ]
}
AQUA_MIXED = Look("Mint-Y-Aqua", "Mint-Y-Sand", "Mint-Y-Dark-Aqua", "Bibata-Modern-Classic")
AQUA_DARK = Look("Mint-Y-Dark-Aqua", "Mint-Y-Sand", "Mint-Y-Dark-Aqua", "Bibata-Modern-Classic")


def everything(look: Look) -> bool:
    return True


@pytest.fixture
def mint_y() -> styles.Style:
    (style,) = styles.parse(json.dumps(MINT_Y), everything)
    return style


def test_parse_reads_the_modes_and_puts_the_default_first(mint_y: styles.Style) -> None:
    assert list(mint_y.modes) == ["mixed", "dark", "light"]
    assert [variant.name for variant in mint_y.modes["mixed"]] == ["Blue", "Aqua"]


def test_themes_names_every_theme_but_those_given_apart(mint_y: styles.Style) -> None:
    (blue,) = mint_y.modes["light"]
    assert blue.look == Look("Mint-Y-Blue", "Mint-Y-Blue", "Mint-Y-Blue", "Bibata-Modern-Classic")


def test_a_variant_that_is_not_installed_is_left_out() -> None:
    (style,) = styles.parse(json.dumps(MINT_Y), lambda look: look.gtk != "Mint-Y-Blue")
    assert [variant.name for variant in style.modes["mixed"]] == ["Aqua"]
    assert "light" not in style.modes


def test_a_file_that_is_not_a_styles_file_is_refused() -> None:
    with pytest.raises(ValueError, match="not a styles file"):
        styles.parse("[1, 2]", everything)


def test_load_skips_what_it_cannot_read(tmp_path: Path) -> None:
    (tmp_path / "10_broken.styles").write_text("{", encoding="utf-8")
    (tmp_path / "20_mint.styles").write_text(json.dumps(MINT_Y), encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a style", encoding="utf-8")
    assert [style.name for style in styles.load(everything, tmp_path)] == ["Mint-Y"]


def test_active_finds_the_style_mode_and_variant(mint_y: styles.Style) -> None:
    style, mode, variant = styles.active([mint_y], AQUA_MIXED)
    assert (style.name, mode, variant.name) == ("Mint-Y", "mixed", "Aqua")


def test_active_finds_nothing_for_a_custom_look(mint_y: styles.Style) -> None:
    assert styles.active([mint_y], Look("Arc", "Papirus", "Arc", "DMZ")) is None


def test_a_switch_keeps_the_colour(mint_y: styles.Style) -> None:
    aqua = Variant("Aqua", AQUA_MIXED)
    assert styles.variant_for(mint_y, "dark", aqua) == Variant("Aqua", AQUA_DARK)


def test_a_switch_takes_the_default_when_the_colour_is_missing(mint_y: styles.Style) -> None:
    aqua = Variant("Aqua", AQUA_MIXED)
    assert styles.variant_for(mint_y, "light", aqua).name == "Blue"


def test_a_switch_to_a_mode_the_style_lacks_is_none() -> None:
    style = styles.Style("Plain", {"mixed": [Variant("Aqua", AQUA_MIXED)]})
    assert styles.variant_for(style, "dark", Variant("Aqua", AQUA_MIXED)) is None


def test_every_mode_has_its_color_scheme() -> None:
    assert set(styles.COLOR_SCHEMES) == set(styles.MODES)


def make_theme(root: Path, name: str, part: str, text: str = "") -> None:
    path = root / name / part
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_installed_follows_cinnamons_rules(tmp_path: Path) -> None:
    system = tmp_path / "usr" / "share"
    make_theme(system / "themes", "Mint-Y-Aqua", "gtk-3.0/gtk.css")
    make_theme(system / "themes", "Mint-Y-Dark-Aqua", "cinnamon/cinnamon.css")
    make_theme(system / "icons", "Mint-Y-Sand", "index.theme", "Directories=16x16\n")
    make_theme(tmp_path / "home" / ".icons", "Bibata-Modern-Classic", "cursors/left_ptr")
    installed = Installed(tmp_path / "home", tmp_path / "home" / ".local" / "share", [system])
    assert installed(AQUA_MIXED)
    assert not installed(AQUA_DARK)  # no Mint-Y-Dark-Aqua for GTK
    assert installed(Look("Mint-Y-Aqua", "Mint-Y-Sand", "cinnamon", "Bibata-Modern-Classic"))


def test_a_hidden_icon_theme_is_not_installed(tmp_path: Path) -> None:
    make_theme(tmp_path / "icons", "Secret", "index.theme", "Hidden=true\nDirectories=16x16\n")
    make_theme(tmp_path / "icons", "Secret", "cursors/left_ptr")
    installed = Installed(tmp_path / "home", tmp_path / "data", [tmp_path])
    make_theme(tmp_path / "themes", "Plain", "gtk-3.0/gtk.css")
    assert not installed(Look("Plain", "Secret", "cinnamon", "Secret"))
