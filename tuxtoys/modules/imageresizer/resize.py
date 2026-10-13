"""Resizing one picture with Pillow (python3-pil), as Image Resizer's window asks.

The picture is turned upright first, by its EXIF orientation, so that what is resized is
what people see. Its colour profile always goes along, since it changes how the picture
looks; its other metadata (EXIF, with the camera and any GPS position, and XMP) goes too
unless removing it was asked for. An animated GIF or WebP keeps all its frames.

The resized copy is written under a hidden name beside where it goes, then given its name
in one step, which fails when the name is taken by then; only "replace the original"
writes over a file, and only over the original.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from tuxtoys.modules.imageresizer import naming, sizing
from tuxtoys.modules.imageresizer.options import Options, Size

_HIDDEN = ".tuxtoys-resize-"
# Formats Pillow can write, by the format it read, and the extension that goes with each.
_WRITABLE = {"JPEG", "PNG", "WEBP", "TIFF", "BMP", "GIF"}


class Unsupported(Exception):
    """A picture Pillow can read but not write back in its own format."""


@dataclass(frozen=True)
class Done:
    path: Path
    width: int
    height: int


def resize(source: Path, size: Size, options: Options) -> Done:
    """Resizes one picture and returns where it went. OSError, or Pillow's own errors,
    when it cannot be read or written; Unsupported for a format that cannot be written.
    """
    with Image.open(source) as picture:
        image_format = picture.format or ""
        frames = [_upright(frame) for frame in ImageSequence.Iterator(picture)]
        if image_format == "MPO":
            # A camera's JPEG with a second, smaller picture inside: the first is the photo.
            image_format, frames = "JPEG", frames[:1]
        if image_format not in _WRITABLE:
            raise Unsupported(image_format or source.suffix)
        dpi = tuple(float(value) for value in picture.info.get("dpi", ())[:2]) or (
            sizing.DEFAULT_DPI,
            sizing.DEFAULT_DPI,
        )
        first = frames[0]
        made = sizing.plan(first.size, size, options.shrink_only, options.ignore_orientation, dpi)
        resized = [
            frame.resize(made.scaled, Image.Resampling.LANCZOS).crop(made.crop) for frame in frames
        ]
        extra = _save_options(picture, first, image_format, options, len(resized) > 1)

    if options.replace_original:
        destination = source
    else:
        name = naming.format_name(
            options.file_name,
            source.name,
            size.shown_name,
            made.asked,
            (made.width, made.height),
        )
        destination = naming.target(source, name)
        destination.parent.mkdir(parents=True, exist_ok=True)

    handle, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=_HIDDEN, suffix=source.suffix
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        resized[0].save(
            temporary, image_format, save_all=len(resized) > 1, append_images=resized[1:], **extra
        )
        if options.keep_date:
            stat = source.stat()
            os.utime(temporary, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        if options.replace_original:
            os.replace(temporary, destination)
        else:
            destination = _place(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return Done(destination, made.width, made.height)


def _upright(frame: Image.Image) -> Image.Image:
    """The frame turned as its EXIF orientation says, in a mode that resizes smoothly: a
    palette goes to full colour, and saving brings a GIF back to a palette.
    """
    upright = ImageOps.exif_transpose(frame.copy())
    if upright.mode in ("P", "1", "LA", "PA"):
        upright = upright.convert("RGBA")
    return upright


def _save_options(
    picture: Image.Image, first: Image.Image, image_format: str, options: Options, animated: bool
) -> dict:
    extra: dict = {}
    profile = picture.info.get("icc_profile")
    if profile:
        extra["icc_profile"] = profile
    if not options.remove_metadata:
        exif = first.getexif()  # already upright, so without its orientation
        if exif and image_format in ("JPEG", "PNG", "WEBP", "TIFF"):
            extra["exif"] = exif.tobytes()
        xmp = picture.info.get("xmp")
        if xmp and image_format in ("JPEG", "WEBP"):
            extra["xmp"] = xmp
    if image_format in ("JPEG", "WEBP"):
        extra["quality"] = options.jpeg_quality
    if animated:
        for key in ("duration", "loop", "disposal"):
            if key in picture.info:
                extra[key] = picture.info[key]
    return extra


def _place(temporary: Path, destination: Path) -> Path:
    """Gives the resized copy its name, or the next free one if it was taken meanwhile."""
    while True:
        try:
            os.link(temporary, destination)
            return destination
        except FileExistsError:
            destination = naming.target(destination, destination.name)
        except OSError:
            # A file system without hard links: check, then rename.
            if destination.exists():
                destination = naming.target(destination, destination.name)
                continue
            os.rename(temporary, destination)
            return destination
