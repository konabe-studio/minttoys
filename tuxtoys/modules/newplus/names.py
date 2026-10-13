"""The names of templates and of what is made from them, as PowerToys' New+ has them. Free
of GTK.

- Order: folders first, then by name, with numbers in a name compared as numbers, so
  "2. Letter" comes before "10. Invoice". Leading digits are the way to order templates.
- The number a template's name starts with can be left out of the name shown and the
  name offered, with one dot or space after it: "1. Letter.odt" is offered as
  "Letter.odt". Only the template's own name: the names inside a folder template stay.
- Variables in a name are replaced when an item is made from it: the date and time
  ($YYYY, $MM, $DD, $hh and the others PowerRename knows, case-sensitive),
  $PARENT_FOLDER_NAME (the name of the folder the item lands in), and %VARIABLE% from the
  environment (any case). The month and day names follow the locale in use.
"""

import re
from collections.abc import Mapping
from datetime import datetime

_LEADING = re.compile(r"[0-9]+(?:\. ?| \.?)?")
_NUMBER = re.compile(r"(\d+)")
_DATE_TOKENS = "PARENT_FOLDER_NAME|YYYY|YY|Y|MMMM|MMM|MM|M|DDDD|DDD|DD|D|hh|h|mm|m|ss|s|fff|ff|f"
# One pass for both kinds, so a value put in is never read again for variables.
_ANY = re.compile(rf"\$({_DATE_TOKENS})|%([A-Za-z_][A-Za-z0-9_]*)%")


def order_key(name: str, folder: bool) -> tuple:
    """Sorts folders first, then names as people read them: numbers by their value."""
    parts = _NUMBER.split(name.casefold())
    return (not folder, [int(part) if part.isdigit() else part for part in parts], name)


def without_leading_digits(name: str, folder: bool) -> str:
    """The name without the number it starts with and the dot or space after it, as
    PowerToys' New+ has it: "01. First.txt", "03 Third" and "05.Fifth.txt" lose "01. ",
    "03 " and "05.". A name that is only a number keeps it: "001231.txt", or a folder
    "001231"; a folder "0123.Name" becomes "Name".
    """
    stem, extension = split_extension(name)
    if stem.isascii() and stem.isdigit() and (not folder or not extension):
        return name
    match = _LEADING.match(name)
    rest = name[match.end() :] if match else name
    return rest or name


def split_extension(name: str) -> tuple[str, str]:
    """Splits "Letter.odt" into "Letter" and ".odt". A name with no dot, or only a leading
    one, has no extension.
    """
    dot = name.rfind(".")
    return (name[:dot], name[dot:]) if dot > 0 else (name, "")


def expand(name: str, now: datetime, parent: str, environ: Mapping[str, str]) -> str:
    """`name` with its variables replaced. A slash a value brings in becomes a space, since
    it cannot be part of a file name.
    """

    def value(match: re.Match[str]) -> str:
        if match[2] is not None:
            key = match[2]
            if key in environ:
                return _clean(environ[key])
            for other, found in environ.items():
                if other.casefold() == key.casefold():
                    return _clean(found)
            return match[0]
        token = match[1]
        return _clean(parent if token == "PARENT_FOLDER_NAME" else _DATE[token](now))

    return _ANY.sub(value, name)


def has_variables(name: str) -> bool:
    return bool(_ANY.search(name))


def _clean(value: str) -> str:
    return value.replace("/", " ").replace("\0", " ")


_DATE = {
    "YYYY": lambda now: f"{now.year:04d}",
    "YY": lambda now: f"{now.year % 100:02d}",
    "Y": lambda now: str(now.year % 10),
    "MMMM": lambda now: now.strftime("%B"),
    "MMM": lambda now: now.strftime("%b"),
    "MM": lambda now: f"{now.month:02d}",
    "M": lambda now: str(now.month),
    "DDDD": lambda now: now.strftime("%A"),
    "DDD": lambda now: now.strftime("%a"),
    "DD": lambda now: f"{now.day:02d}",
    "D": lambda now: str(now.day),
    "hh": lambda now: f"{now.hour:02d}",
    "h": lambda now: str(now.hour),
    "mm": lambda now: f"{now.minute:02d}",
    "m": lambda now: str(now.minute),
    "ss": lambda now: f"{now.second:02d}",
    "s": lambda now: str(now.second),
    "fff": lambda now: f"{now.microsecond // 1000:03d}",
    "ff": lambda now: f"{now.microsecond // 10000:02d}",
    "f": lambda now: str(now.microsecond // 100000),
}
