"""Colors near a color, for the editor's bar of similar colors, as PowerToys shows two
lighter and two darker ones on either side of the color picked. Free of GTK.
"""

import colorsys

from tuxtoys.modules.colorpicker.colors import Color

STEPS = (0.30, 0.15, 0.0, -0.15, -0.30)


def shades(color: Color) -> list[Color]:
    """Lighter to darker, the color itself in the middle; each lightness kept inside 0-1."""
    hue, lightness, saturation = colorsys.rgb_to_hls(color.r / 255, color.g / 255, color.b / 255)
    made = []
    for step in STEPS:
        if step == 0:
            made.append(color)
            continue
        r, g, b = colorsys.hls_to_rgb(hue, min(max(lightness + step, 0.0), 1.0), saturation)
        made.append(Color(round(r * 255), round(g * 255), round(b * 255)))
    return made
