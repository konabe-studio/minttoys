"""Translations, in the gettext domain "minttoys".

Until a package installs the compiled catalogues, every string stays in English.
"""

import gettext

_ = gettext.translation("minttoys", fallback=True).gettext
