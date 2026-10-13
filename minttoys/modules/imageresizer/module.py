"""Image Resizer, as the daemon runs it: it keeps its Nemo action in place (see
core.nemo_action) and serves its settings. The window the action opens is a program of its
own (minttoys.imageresizer), which reads and saves the settings through the daemon.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from minttoys.api import IMAGERESIZER_SETTINGS
from minttoys.core.i18n import N_, _
from minttoys.core.nemo_action import NemoAction
from minttoys.modules.base import Context, Module
from minttoys.modules.imageresizer.options import Options

# The pictures Pillow reads and writes back in their own format. Nemo compares them with
# the end of the name, in any case.
EXTENSIONS = "jpg;jpeg;jpe;png;webp;tif;tiff;bmp;gif;"


def menu_item() -> NemoAction:
    return NemoAction(
        file_name="io.github.konabe_studio.MintToys.imageresizer.nemo_action",
        # TRANSLATORS: Image Resizer's item in Nemo's right-click menu, on pictures.
        name=N_("Resize with Image Resizer"),
        # TRANSLATORS: the tooltip of Image Resizer's item in Nemo's right-click menu.
        comment=N_("Makes resized copies of the chosen pictures."),
        launcher="minttoys-image-resizer",
        module="minttoys.imageresizer",
        icon="image-x-generic-symbolic",
        extensions=EXTENSIONS,
    )


class ImageResizer(Module):
    id: ClassVar[str] = "imageresizer"
    name: ClassVar[str] = _("Image Resizer")
    description: ClassVar[str] = _("Resizes pictures from Nemo's right-click menu.")
    settings_types: ClassVar[Mapping[str, str]] = IMAGERESIZER_SETTINGS

    def __init__(self, adapt: Callable[[NemoAction], NemoAction] = lambda action: action) -> None:
        """The daemon writes the action where Nemo reads it; the tests `adapt` it to a
        folder of their own.
        """
        self.action = adapt(menu_item())

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self.action.write()

    def disable(self) -> None:
        pass  # the action stays across sessions; see switched_off()

    def switched_off(self) -> None:
        self.action.remove()
