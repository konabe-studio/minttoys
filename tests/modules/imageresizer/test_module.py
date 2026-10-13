from dataclasses import replace
from pathlib import Path

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.imageresizer.module import ImageResizer
from tuxtoys.modules.imageresizer.options import Size
from tuxtoys.modules.imageresizer.text import describe


def here(tmp_path: Path) -> ImageResizer:
    return ImageResizer(
        lambda action: replace(action, folder=lambda: tmp_path / "actions", package_root=tmp_path)
    )


def test_the_action_is_offered_on_pictures(tmp_path: Path) -> None:
    module = here(tmp_path)
    module.enable(Context(None, ImageResizer.read_settings({})))
    text = module.action.path.read_text(encoding="utf-8")
    assert "Name=Resize with Image Resizer\n" in text
    assert "Selection=notnone\n" in text
    assert "Extensions=jpg;jpeg;jpe;png;webp;tif;tiff;bmp;gif;\n" in text
    assert "-m tuxtoys.imageresizer %F\n" in text
    module.disable()
    assert module.action.path.exists()
    module.switched_off()
    assert not module.action.path.exists()


def test_off_by_default() -> None:
    assert ImageResizer.enabled_by_default is False


def test_settings_are_checked() -> None:
    settings = ImageResizer.read_settings({})
    assert settings["jpeg_quality"] == 90
    assert settings["sizes"][0] == ("$small$", "fit", 854, 480, "px")
    with pytest.raises(ValueError, match="1 to 100"):
        ImageResizer.check_settings(settings, {"jpeg_quality": 101})
    changed = ImageResizer.check_settings(settings, {"sizes": [["Web", "fill", 800, 0, "px"]]})
    assert changed["sizes"] == [("Web", "fill", 800.0, 0.0, "px")]


def test_describe() -> None:
    assert describe(Size("$small$", "fit", 854, 480)) == "Fit · 854 × 480 px"  # noqa: RUF001
    assert describe(Size("A", "fill", 10.5, 0, "cm")) == "Fill · 10.5 × auto cm"  # noqa: RUF001
    assert describe(Size("B", "stretch", 50, 50, "percent")) == "Stretch · 50 × 50 %"  # noqa: RUF001
