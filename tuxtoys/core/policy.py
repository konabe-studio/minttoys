"""The polkit actions that let a tool save a system file through its root helper, as
.policy files. Free of GTK.

Their texts are messages in po/ like any other, and `make` writes each file with every
language there is a catalogue for: polkit shows the one in the user's language in its
password dialog. Rendering them here keeps that out of gettext's ITS rules, which differ
between gettext versions.

Users at the machine are asked for an administrator's password, which polkit then
remembers for a few minutes (auth_admin_keep); anyone else is asked every time.

    python3 -m tuxtoys.core.policy ACTION LOCALE_DIR HELPER > the.policy
"""

import gettext
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from tuxtoys import APP_ID
from tuxtoys.core.i18n import N_


@dataclass(frozen=True)
class Action:
    id: str
    description: str  # what the password is for
    message: str  # the line above the password field


ACTIONS = {
    "hosts": Action(
        f"{APP_ID}.hosts.save",
        # TRANSLATORS: what polkit's password dialog says the password is for.
        N_("Save the hosts file"),
        # TRANSLATORS: the line polkit's password dialog shows above the password field.
        N_("Authentication is required to save the hosts file"),
    ),
    "environment": Action(
        f"{APP_ID}.environment.save",
        # TRANSLATORS: what polkit's password dialog says the password is for.
        N_("Save the system's environment variables"),
        # TRANSLATORS: the line polkit's password dialog shows above the password field.
        N_("Authentication is required to save the system's environment variables"),
    ),
}


def render(
    action: Action,
    descriptions: Mapping[str, str],
    messages: Mapping[str, str],
    helper: str,
) -> str:
    """The .policy file. `descriptions` and `messages` map a language to its text, "" to
    the English one.
    """

    def texts(tag: str, values: Mapping[str, str]) -> list[str]:
        lines = [f"    <{tag}>{escape(values[''])}</{tag}>"]
        for language, text in sorted(values.items()):
            if language:
                lines.append(f"    <{tag} xml:lang={quoteattr(language)}>{escape(text)}</{tag}>")
        return lines

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration'
        ' 1.0//EN"',
        ' "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">',
        "<policyconfig>",
        "  <vendor>TuxToys</vendor>",
        "  <vendor_url>https://github.com/konabe-studio/tuxtoys</vendor_url>",
        f"  <icon_name>{APP_ID}</icon_name>",
        f"  <action id={quoteattr(action.id)}>",
        *texts("description", descriptions),
        *texts("message", messages),
        "    <defaults>",
        "      <allow_any>auth_admin</allow_any>",
        "      <allow_inactive>auth_admin</allow_inactive>",
        "      <allow_active>auth_admin_keep</allow_active>",
        "    </defaults>",
        f'    <annotate key="org.freedesktop.policykit.exec.path">{escape(helper)}</annotate>',
        "  </action>",
        "</policyconfig>",
    ]
    return "\n".join(lines) + "\n"


def translated(locale_dir: Path, languages: Sequence[str], text: str) -> dict[str, str]:
    """`text` in English and in each language whose catalogue translates it."""
    found = {"": text}
    for language in languages:
        catalogue = gettext.translation(
            "tuxtoys", localedir=locale_dir, languages=[language], fallback=True
        )
        if (translation := catalogue.gettext(text)) != text:
            found[language] = translation
    return found


def main(argv: list[str]) -> int:
    action, locale_dir, helper = ACTIONS[argv[0]], Path(argv[1]), argv[2]
    languages = sorted(path.name for path in locale_dir.iterdir() if path.is_dir())
    sys.stdout.write(
        render(
            action,
            translated(locale_dir, languages, action.description),
            translated(locale_dir, languages, action.message),
            helper,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
