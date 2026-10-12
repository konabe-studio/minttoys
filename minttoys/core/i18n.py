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


SYSTEM_LOCALE = Path("/usr/share/locale")


def _localedir() -> Path | None:
    return CHECKOUT_LOCALE if CHECKOUT_LOCALE.is_dir() else None


def translation() -> gettext.NullTranslations:
    """The catalogue for the user's language, from the checkout when it has been built
    there, otherwise from the system.
    """
    return gettext.translation(DOMAIN, _localedir(), fallback=True)


def N_(message: str) -> str:
    """Marks a message for translation without translating it, for in_every_language()."""
    return message


def in_every_language(message: str) -> dict[str, str]:
    """`message` in every language MintToys has a catalogue for, by language code, for
    files other programs read in the user's language, such as a Nemo action. Languages
    that leave it in English are left out.
    """
    localedir = _localedir() or SYSTEM_LOCALE
    found = {}
    for catalogue in sorted(localedir.glob(f"*/LC_MESSAGES/{DOMAIN}.mo")):
        language = catalogue.parents[1].name
        text = gettext.translation(DOMAIN, localedir, [language], fallback=True).gettext(message)
        if text != message:
            found[language] = text
    return found


_translation = translation()
_ = _translation.gettext
ngettext = _translation.ngettext
