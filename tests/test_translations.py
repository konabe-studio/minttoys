"""The translations in po/: in step with the sources, complete, and well formed.

A catalogue is data nothing else checks. A message missing from it shows in English, and a
translation that names a placeholder the code does not pass makes .format() raise, both
only on a desktop in that language.
"""

import ast
import gettext
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PO = ROOT / "po"
TEMPLATE = PO / "minttoys.pot"
LANGUAGES = (PO / "LINGUAS").read_text(encoding="utf-8").split()
# The keys of a desktop entry that xgettext extracts and msgfmt translates.
DESKTOP_KEYS = ("Name", "GenericName", "Comment", "Keywords")


@dataclass
class Entry:
    msgid: str
    plural: str | None = None
    msgstr: list[str] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)


def read_po(path: Path) -> dict[str, Entry]:
    """The entries of a .po or .pot file by msgid, without the header and the obsolete
    ones. As much of the format as xgettext and msgmerge write: flags, plurals, no contexts.
    """
    entries: dict[str, Entry] = {}
    fields: dict[str, str] = {}
    flags: set[str] = set()
    last = ""

    def finish() -> None:
        if fields.get("msgid"):
            if fields["msgid"] in entries:
                # msgfmt refuses a catalogue with a message in it twice.
                raise ValueError(f"{path.name}: {fields['msgid']!r} is there twice")
            forms = sorted(key for key in fields if key.startswith("msgstr"))
            entries[fields["msgid"]] = Entry(
                fields["msgid"],
                fields.get("msgid_plural"),
                [fields[key] for key in forms],
                set(flags),
            )
        fields.clear()
        flags.clear()

    for line in [*path.read_text(encoding="utf-8").splitlines(), ""]:
        if not line.strip():
            finish()
        elif line.startswith("#,"):
            flags.update(flag.strip() for flag in line[2:].split(","))
        elif line.startswith("#"):
            continue  # comments, and obsolete entries ("#~")
        elif line.startswith('"'):
            fields[last] += ast.literal_eval(line)
        else:
            last, _, text = line.partition(" ")
            fields[last] = ast.literal_eval(text)
    return entries


def source_messages() -> dict[str, str | None]:
    """Every message the sources mark, as msgid -> its plural (None for none): the
    arguments of _() and ngettext() in the package, and the translated keys of the
    desktop entries.
    """
    found: dict[str, str | None] = {}
    for path in sorted((ROOT / "minttoys").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            count = {"_": 1, "ngettext": 2}.get(node.func.id)
            if count is None:
                continue
            texts = [
                arg.value
                for arg in node.args[:count]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            where = f"{path.relative_to(ROOT)}:{node.lineno}"
            assert len(texts) == count, f"{where}: not a string literal, so xgettext skips it"
            found[texts[0]] = texts[1] if count == 2 else None
    for path in sorted((ROOT / "data").glob("*/*.desktop.in")):
        for line in path.read_text(encoding="utf-8").splitlines():
            key, equals, value = line.partition("=")
            if equals and key in DESKTOP_KEYS:
                found[value] = None
    return found


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w*)\}", text))


def messages(entries: dict[str, Entry]) -> dict[str, str | None]:
    return {msgid: entry.plural for msgid, entry in entries.items()}


@pytest.mark.parametrize("name", ["minttoys.pot", *(f"{lang}.po" for lang in LANGUAGES)])
def test_no_message_is_there_twice(name: str) -> None:
    read_po(PO / name)  # raises for a message that is


def test_the_template_has_every_message_of_the_sources_and_no_other() -> None:
    sources, template = source_messages(), messages(read_po(TEMPLATE))
    missing = {msgid for msgid in sources if template.get(msgid, "") != sources[msgid]}
    stale = {msgid for msgid in template if msgid not in sources}
    assert not missing, f"not in po/minttoys.pot, run make update-po: {sorted(missing)}"
    assert not stale, f"no longer in the sources, run make update-po: {sorted(stale)}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_translation_has_the_messages_of_the_template(language: str) -> None:
    template = messages(read_po(TEMPLATE))
    translation = messages(read_po(PO / f"{language}.po"))
    assert translation == template, "run make update-po"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_message_is_translated_and_none_is_fuzzy(language: str) -> None:
    entries = read_po(PO / f"{language}.po").values()
    untranslated = [entry.msgid for entry in entries if not all(entry.msgstr)]
    fuzzy = [entry.msgid for entry in entries if "fuzzy" in entry.flags]
    assert not untranslated
    assert not fuzzy


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_translation_keeps_the_placeholders(language: str) -> None:
    wrong = []
    for entry in read_po(PO / f"{language}.po").values():
        if entry.plural is None:
            # Every one, and only those: a dropped one loses the number or the time.
            if placeholders(entry.msgstr[0]) != placeholders(entry.msgid):
                wrong.append(entry.msgid)
        else:
            # A plural form may leave the number out ("one minute"), but no form may name
            # a placeholder the code does not pass.
            passed = placeholders(entry.msgid) | placeholders(entry.plural)
            if any(placeholders(form) - passed for form in entry.msgstr):
                wrong.append(entry.msgid)
    assert not wrong


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_translation_has_no_long_dashes(language: str) -> None:
    # The English text splits a sentence rather than joining it with a dash; so does every
    # translation. A hyphen, as in a range, is fine.
    dashed = [
        entry.msgid
        for entry in read_po(PO / f"{language}.po").values()
        if any(dash in form for dash in ("\N{EM DASH}", "\N{EN DASH}") for form in entry.msgstr)
    ]
    assert not dashed


@pytest.mark.skipif(shutil.which("msgfmt") is None, reason="gettext is not installed")
@pytest.mark.parametrize("language", LANGUAGES)
def test_msgfmt_compiles_a_translation_python_reads(language: str, tmp_path: Path) -> None:
    compiled = tmp_path / "minttoys.mo"
    subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", compiled, PO / f"{language}.po"],
        check=True,
    )
    with compiled.open("rb") as file:
        catalogue = gettext.GNUTranslations(file)  # raises on a bad Plural-Forms
    for entry in read_po(PO / f"{language}.po").values():
        if entry.plural is None:
            assert catalogue.gettext(entry.msgid) == entry.msgstr[0]
        else:
            for count in (1, 2, 5):
                assert catalogue.ngettext(entry.msgid, entry.plural, count) in entry.msgstr


@pytest.mark.skipif(
    shutil.which("make") is None or shutil.which("xgettext") is None,
    reason="make and gettext are not installed",
)
def test_make_pot_extracts_what_the_template_has(tmp_path: Path) -> None:
    extracted = tmp_path / "minttoys.pot"
    subprocess.run(["make", "-s", "pot", f"POT={extracted}"], cwd=ROOT, check=True)
    assert messages(read_po(extracted)) == messages(read_po(TEMPLATE))
