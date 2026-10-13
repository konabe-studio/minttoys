"""The words Rename+ shows for its choices and its variables, shared by its window and its
page. Free of GTK.
"""

from tuxtoys.core.i18n import _


def apply_to_names() -> dict[str, str]:
    return {
        # TRANSLATORS: Rename+'s "Apply to" choice: the whole name searched.
        "both": _("Name and extension"),
        # TRANSLATORS: Rename+'s "Apply to" choice: the name without its extension.
        "name": _("Name only"),
        # TRANSLATORS: Rename+'s "Apply to" choice: the extension alone.
        "extension": _("Extension only"),
    }


def text_case_names() -> dict[str, str]:
    return {
        # TRANSLATORS: Rename+'s text case choice: names keep their letters as they are.
        "": _("Keep as it is"),
        # TRANSLATORS: Rename+'s text case choice, shown in lowercase on purpose.
        "lower": _("lowercase"),
        # TRANSLATORS: Rename+'s text case choice, shown in uppercase on purpose.
        "upper": _("UPPERCASE"),
        # TRANSLATORS: Rename+'s text case choice: every word capitalized but short ones
        # such as "of" and "the", which are English rules.
        "title": _("Title Case"),
        # TRANSLATORS: Rename+'s text case choice: every word with a capital letter.
        "words": _("Capitalize Every Word"),
    }


def variables() -> list[tuple[str, list[tuple[str, str]]]]:
    """What can go in the replace text, by heading, each with what it stands for."""
    return [
        (
            # TRANSLATORS: a heading over Rename+'s counters, such as ${start=1}.
            _("Counters"),
            [
                ("${}", _("A number counting the renamed items, from 0")),
                ("${start=1}", _("Counting from 1")),
                ("${increment=10}", _("Counting in steps of 10")),
                ("${padding=3}", _("At least 3 digits, with zeros in front")),
                ("${start=1;padding=3}", _("Both: 001, 002, 003")),
            ],
        ),
        (
            # TRANSLATORS: a heading over Rename+'s random text, such as ${ruuidv4}.
            _("Random text"),
            [
                ("${rstringalnum=8}", _("8 letters and digits")),
                ("${rstringalpha=8}", _("8 letters")),
                ("${rstringdigit=8}", _("8 digits")),
                ("${ruuidv4}", _("A random UUID")),
            ],
        ),
        (
            # TRANSLATORS: a heading over Rename+'s date variables, such as $YYYY.
            _("When the item was made"),
            [
                ("$YYYY", _("Year, 4 digits")),
                ("$YY", _("Year, 2 digits")),
                ("$MMMM", _("Name of the month")),
                ("$MMM", _("Short name of the month")),
                ("$MM", _("Month, 2 digits")),
                ("$DDDD", _("Name of the day")),
                ("$DDD", _("Short name of the day")),
                ("$DD", _("Day of the month, 2 digits")),
                ("$hh", _("Hour, 2 digits")),
                ("$mm", _("Minutes, 2 digits")),
                ("$ss", _("Seconds, 2 digits")),
                ("$fff", _("Milliseconds, 3 digits")),
            ],
        ),
        (
            # TRANSLATORS: a heading over what a regular expression's replacement can hold.
            _("With regular expressions"),
            [
                ("$1", _("What the first group in brackets found")),
                ("$0", _("Everything the search found")),
                ("$$", _("A dollar sign")),
            ],
        ),
    ]
