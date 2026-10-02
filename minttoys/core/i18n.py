"""Translations, in the gettext domain "minttoys".

Until a package installs the compiled catalogues, every string stays in English.
"""

import gettext

_translation = gettext.translation("minttoys", fallback=True)
_ = _translation.gettext
ngettext = _translation.ngettext
