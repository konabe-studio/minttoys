"""The words Image Resizer shows for its sizes, shared by its window and its page. Free of
GTK.
"""

from tuxtoys.core.i18n import _
from tuxtoys.modules.imageresizer.options import Size


def fit_name(fit: str) -> str:
    return {
        # TRANSLATORS: Image Resizer's fit: the size covered, what sticks out cut off.
        "fill": _("Fill"),
        # TRANSLATORS: Image Resizer's fit: the whole picture inside the size.
        "fit": _("Fit"),
        # TRANSLATORS: Image Resizer's fit: exactly the size, out of proportion if need be.
        "stretch": _("Stretch"),
    }.get(fit, fit)


def unit_name(unit: str) -> str:
    return {
        "px": _("Pixels"),
        "percent": _("Percent"),
        "cm": _("Centimeters"),
        "in": _("Inches"),
    }.get(unit, unit)


def _short_unit(unit: str) -> str:
    return {
        # TRANSLATORS: after a size in pixels, as in "854 × 480 px".  # noqa: RUF003
        "px": _("px"),
        "percent": "%",
        # TRANSLATORS: after a size in centimeters.
        "cm": _("cm"),
        # TRANSLATORS: after a size in inches.
        "in": _("in"),
    }.get(unit, unit)


def _number(value: float) -> str:
    # TRANSLATORS: in place of a width or a height left empty, which follows from the other.
    return f"{value:g}" if value else _("auto")


def describe(size: Size) -> str:
    """What a size is, under its name: "Fit · 854 × 480 px"."""  # noqa: RUF002
    return _("{fit} · {width} × {height} {unit}").format(  # noqa: RUF001
        fit=fit_name(size.fit),
        width=_number(size.width),
        height=_number(size.height),
        unit=_short_unit(size.unit),
    )
