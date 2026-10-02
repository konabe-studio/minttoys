"""Translations, in the gettext domain "minttoys".

The package installs the compiled catalogues into /usr/share/locale. A checkout uses its
own, which `make mo` builds into build/locale. Without a catalogue for the language, every
string stays in English.
"""

import gettext
from pathlib import Path

DOMAIN = "minttoys"

# The checkout's catalogues. Installed, this would be /usr/lib/minttoys/build/locale,
# which does not exist, so the system's locale directory is used.
CHECKOUT_LOCALE = Path(__file__).resolve().parents[2] / "build" / "locale"


def translation() -> gettext.NullTranslations:
    """The catalogue for the user's language, from the checkout when it has been built
    there, otherwise from the system.
    """
    localedir = CHECKOUT_LOCALE if CHECKOUT_LOCALE.is_dir() else None
    return gettext.translation(DOMAIN, localedir, fallback=True)


_translation = translation()
_ = _translation.gettext
ngettext = _translation.ngettext
