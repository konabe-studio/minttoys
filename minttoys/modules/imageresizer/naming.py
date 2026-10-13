"""The name a resized picture is saved under, from Image Resizer's file name format, as
PowerToys has it. Free of images.

%1 the original name without its extension, %2 the size's name, %3 and %4 the width and
the height asked for, %5 the height and %6 the width it comes out at. The extension stays
the original's. A slash makes a folder beside the original: "%2/%1" puts "photo.jpg" in
"Small/photo.jpg". A name already there is never written over: "photo (Small) (2).jpg".
"""

from pathlib import Path

from minttoys.modules.newplus.names import split_extension
from minttoys.modules.newplus.templates import free_name


def format_name(
    pattern: str, original: str, size_name: str, asked: tuple[int, int], made: tuple[int, int]
) -> str:
    """The pattern filled in, the original's extension after it. Each part of the path
    is a plain name: a "." or ".." that a value brings in becomes "_".
    """
    stem, extension = split_extension(original)
    values = {
        "1": stem,
        "2": size_name.replace("/", "_"),
        "3": str(asked[0]),
        "4": str(asked[1]),
        "5": str(made[1]),
        "6": str(made[0]),
    }
    out, index = [], 0
    while index < len(pattern):
        if pattern[index] == "%" and index + 1 < len(pattern) and pattern[index + 1] in values:
            out.append(values[pattern[index + 1]])
            index += 2
        else:
            out.append(pattern[index])
            index += 1
    parts = [
        "_" if part in ("", ".", "..") else part
        for part in "".join(out).replace("\0", "_").split("/")
    ]
    parts[-1] += extension
    return "/".join(parts)


def target(original: Path, name: str) -> Path:
    """Where to save, beside the original, at a free name."""
    path = original.parent / name
    return path.parent / free_name(path.parent, path.name)
