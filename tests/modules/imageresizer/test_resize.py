"""Resizing real pictures with Pillow, made by the tests themselves."""

import os
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image", reason="Pillow is not installed")

from tuxtoys.modules.imageresizer.options import Options, Size  # noqa: E402
from tuxtoys.modules.imageresizer.resize import Unsupported, resize  # noqa: E402

SMALL = Size("$small$", "fit", 854, 480)
ORIENTATION = 0x0112
GPS = 0x8825


def photo(path: Path, size: tuple[int, int] = (4000, 3000), **exif_tags: int) -> Path:
    picture = Image.new("RGB", size, (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "Camera"  # Make
    for key, value in exif_tags.items():
        exif[int(key[1:], 16)] = value
    picture.save(path, "JPEG", exif=exif.tobytes(), quality=95)
    return path


def test_a_copy_beside_the_original(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    done = resize(source, SMALL, Options())
    assert done.path == tmp_path / "photo (Small).jpg"
    with Image.open(done.path) as made:
        assert made.size == (640, 480)
        assert made.getexif()[0x010F] == "Camera"
    with Image.open(source) as original:
        assert original.size == (4000, 3000)
    assert sorted(os.listdir(tmp_path)) == ["photo (Small).jpg", "photo.jpg"]


def test_a_second_run_does_not_overwrite_the_first(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    resize(source, SMALL, Options())
    assert resize(source, SMALL, Options()).path == tmp_path / "photo (Small) (2).jpg"


def test_turned_upright_by_its_orientation(tmp_path: Path) -> None:
    # Orientation 6: stored landscape, shown portrait.
    source = photo(tmp_path / "phone.jpg", x0112=6)
    done = resize(source, SMALL, Options())
    with Image.open(done.path) as made:
        assert made.size == (480, 640)
        assert ORIENTATION not in made.getexif()


def test_metadata_removed(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    done = resize(source, SMALL, Options(remove_metadata=True))
    with Image.open(done.path) as made:
        assert 0x010F not in made.getexif()


def test_replace_the_original(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    done = resize(source, SMALL, Options(replace_original=True))
    assert done.path == source
    with Image.open(source) as made:
        assert made.size == (640, 480)
    assert os.listdir(tmp_path) == ["photo.jpg"]


def test_keep_the_date(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    os.utime(source, (1_000_000_000, 1_000_000_000))
    done = resize(source, SMALL, Options(keep_date=True))
    assert done.path.stat().st_mtime == 1_000_000_000


def test_into_a_folder_of_the_size(tmp_path: Path) -> None:
    source = photo(tmp_path / "photo.jpg")
    done = resize(source, SMALL, Options(file_name="%2/%1"))
    assert done.path == tmp_path / "Small" / "photo.jpg"


def test_an_animated_gif_keeps_its_frames(tmp_path: Path) -> None:
    frames = [Image.new("RGB", (400, 400), (90 * i, 0, 0)).convert("P") for i in range(3)]
    source = tmp_path / "spin.gif"
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)
    done = resize(source, Size("", "fit", 100, 100), Options())
    with Image.open(done.path) as made:
        assert made.size == (100, 100)
        assert made.n_frames == 3


def test_a_png_keeps_its_transparency(tmp_path: Path) -> None:
    source = tmp_path / "icon.png"
    Image.new("RGBA", (400, 400), (0, 0, 0, 0)).save(source)
    done = resize(source, Size("", "fit", 100, 100), Options())
    with Image.open(done.path) as made:
        assert made.mode == "RGBA"
        assert made.getpixel((50, 50))[3] == 0


def test_a_format_that_cannot_be_written(tmp_path: Path) -> None:
    source = tmp_path / "old.ico"
    Image.new("RGB", (64, 64)).save(source, "ICO")
    with pytest.raises(Unsupported):
        resize(source, Size("", "fit", 32, 32), Options())


def test_not_a_picture(tmp_path: Path) -> None:
    source = tmp_path / "notes.jpg"
    source.write_text("not a picture", encoding="utf-8")
    with pytest.raises(OSError, match="cannot identify"):
        resize(source, SMALL, Options())
