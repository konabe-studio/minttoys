import pytest

from tuxtoys.modules.imageresizer.naming import format_name, target
from tuxtoys.modules.imageresizer.options import DEFAULT_SIZES, Options, Size, check_size
from tuxtoys.modules.imageresizer.sizing import in_pixels, plan


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert [(s.width, s.height) for s in DEFAULT_SIZES] == [
        (854, 480),
        (1366, 768),
        (1920, 1080),
        (320, 568),
    ]
    assert [s.shown_name for s in DEFAULT_SIZES] == ["Small", "Medium", "Large", "Phone"]
    assert options.jpeg_quality == 90
    assert options.file_name == "%1 (%2)"
    assert options.ignore_orientation
    assert not options.shrink_only
    assert not options.replace_original
    assert options.chosen == DEFAULT_SIZES[0]


def test_settings_round_trip() -> None:
    options = Options().update(
        {
            "sizes": [("Web", "fill", 800, 0, "px")],
            "selected": 1,
            "custom": ("stretch", 50, 50, "percent"),
            "jpeg_quality": 75,
        }
    )
    assert Options.read(options.settings()) == options
    assert options.chosen == Size("", "stretch", 50, 50, "percent")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sizes": [("", "fit", 1, 1, "px")]}, "needs a name"),
        ({"sizes": [("A", "crop", 1, 1, "px")]}, "fill, fit or stretch"),
        ({"sizes": [("A", "fit", 1, 1, "mm")]}, "px, percent, cm or in"),
        ({"sizes": [("A", "fit", 0, 0, "px")]}, "width, a height, or both"),
        ({"sizes": [("A", "fit", -1, 1, "px")]}, "0 to"),
        ({"jpeg_quality": 0}, "1 to 100"),
        ({"file_name": "../%1"}, ". or .."),
        ({"file_name": " "}, "such as"),
        ({"keep_date": 1}, "true or false"),
        ({"colour": True}, "unknown setting"),
    ],
)
def test_bad_settings(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Options().update(changes)


def test_a_bad_value_in_the_config_gives_its_default() -> None:
    options = Options.read({"jpeg_quality": "high", "file_name": "%1-small"})
    assert options.jpeg_quality == 90
    assert options.file_name == "%1-small"


def test_selected_past_the_sizes_starts_over() -> None:
    assert Options().update({"sizes": [("A", "fit", 10, 0, "px")], "selected": 4}).selected == 0


def test_check_size_keeps_floats() -> None:
    assert check_size(["Print", "fit", 10.5, 0, "cm"]) == Size("Print", "fit", 10.5, 0.0, "cm")


@pytest.mark.parametrize(
    ("value", "unit", "own", "pixels"),
    [
        (800, "px", 4000, 800),
        (25, "percent", 4000, 1000),
        (2, "in", 4000, 192),
        (2.54, "cm", 4000, 96),
        (0, "px", 4000, 0),
    ],
)
def test_in_pixels(value: float, unit: str, own: int, pixels: float) -> None:
    assert in_pixels(value, unit, own, 96) == pytest.approx(pixels)


def test_fit_keeps_proportions_inside() -> None:
    made = plan((4000, 3000), Size("", "fit", 854, 480))
    assert made.scaled == (640, 480)
    assert (made.width, made.height) == (640, 480)


def test_fill_covers_and_cuts_evenly() -> None:
    made = plan((4000, 3000), Size("", "fill", 854, 480))
    assert made.scaled == (854, 640)
    assert made.crop == (0, 80, 854, 560)


def test_stretch_is_exact() -> None:
    made = plan((4000, 3000), Size("", "stretch", 854, 480))
    assert (made.width, made.height) == (854, 480)


def test_an_empty_side_follows_the_other() -> None:
    assert plan((4000, 3000), Size("", "fit", 800, 0)).scaled == (800, 600)
    assert plan((4000, 3000), Size("", "stretch", 0, 300)).scaled == (400, 300)


def test_a_portrait_picture_gets_the_sizes_turned() -> None:
    assert plan((3000, 4000), Size("", "fit", 854, 480)).scaled == (480, 640)
    assert plan((3000, 4000), Size("", "fit", 854, 480), ignore_orientation=False).scaled == (
        360,
        480,
    )


def test_shrink_only_leaves_a_small_picture() -> None:
    assert plan((400, 300), Size("", "fit", 854, 480), shrink_only=True).scaled == (400, 300)
    assert plan((400, 300), Size("", "fit", 854, 480)).scaled == (640, 480)


def test_percent() -> None:
    assert plan((4000, 3000), Size("", "fit", 50, 0, "percent")).scaled == (2000, 1500)


def test_format_name() -> None:
    assert format_name("%1 (%2)", "photo.jpg", "Small", (854, 480), (640, 480)) == (
        "photo (Small).jpg"
    )
    assert format_name("%1_%4", "photo.jpg", "Medium", (1366, 768), (1024, 768)) == (
        "photo_768.jpg"
    )
    assert format_name("%2/%1", "photo.jpg", "Small", (1, 1), (1, 1)) == "Small/photo.jpg"
    assert format_name("%1 %6x%5", "a.b.png", "S", (1, 1), (640, 480)) == "a.b 640x480.png"
    assert format_name("%2/%1", "x.jpg", "a/..", (1, 1), (1, 1)) == "a_../x.jpg"
    assert format_name("100%", "x.jpg", "S", (1, 1), (1, 1)) == "100%.jpg"


def test_target_never_overwrites(tmp_path) -> None:  # noqa: ANN001
    original = tmp_path / "photo.jpg"
    (tmp_path / "photo (Small).jpg").write_bytes(b"")
    assert target(original, "photo (Small).jpg") == tmp_path / "photo (Small) (2).jpg"
    assert target(original, "Small/photo.jpg") == tmp_path / "Small" / "photo.jpg"
