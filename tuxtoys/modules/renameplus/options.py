"""Rename+'s settings, read and checked without GTK or D-Bus.

The rename window's choices, which it starts from next time when `restore_flags` is on
(PowerRename's "Restore flags on launch"); the last searches and replacements, offered as
the user types and, with `show_recent`, filled in; and `nemo_rename`, which makes Nemo's
Rename on several items open Rename+ instead of Bulky. `previous_tool` is what Nemo
opened before, put back when that ends; the page does not show it.
"""

from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.renameplus.pattern import APPLY_TO, TEXT_CASES, Rules

MOST_RECENT = 10
MOST_TEXT = 1000

# The window's choices, remembered between runs.
FLAGS = (
    "regex",
    "match_all",
    "case_sensitive",
    "apply_to",
    "text_case",
    "enumerate",
    "randomize",
    "include_files",
    "include_folders",
    "include_subfolders",
)


@dataclass(frozen=True)
class Options:
    regex: bool = False
    match_all: bool = False
    case_sensitive: bool = False
    apply_to: str = "both"
    text_case: str = ""
    enumerate: bool = True
    randomize: bool = False
    include_files: bool = True
    include_folders: bool = True
    include_subfolders: bool = True
    recent_search: tuple[str, ...] = ()
    recent_replace: tuple[str, ...] = ()
    restore_flags: bool = True
    show_recent: bool = False
    nemo_rename: bool = False
    previous_tool: str = ""

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From Rename+'s section of the config; a value of the wrong kind gives its
        default, so a config edited by hand cannot keep the tool from working.
        """
        options = cls()
        for key in _CHECKS:
            if key in settings:
                with suppress(ValueError, TypeError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take.
        """
        fields = {}
        for key, value in changes.items():
            if key not in _CHECKS:
                raise ValueError(f"unknown setting: {key!r}")
            fields[key] = _CHECKS[key](value)
        return replace(self, **fields)

    def settings(self) -> dict[str, Any]:
        values = {key: getattr(self, key) for key in _CHECKS}
        values["recent_search"] = list(self.recent_search)
        values["recent_replace"] = list(self.recent_replace)
        return values

    def flags(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in FLAGS}

    def rules(self, search: str, replace: str) -> Rules:
        return Rules(
            search=search,
            replace=replace,
            regex=self.regex,
            match_all=self.match_all,
            case_sensitive=self.case_sensitive,
            apply_to=self.apply_to,
            text_case=self.text_case,
            enumerate=self.enumerate,
            randomize=self.randomize,
        )


def remember(recent: Sequence[str], text: str) -> list[str]:
    """`recent` with `text` first, once, and at most MOST_RECENT in all."""
    if not text:
        return list(recent)
    return [text, *(old for old in recent if old != text)][:MOST_RECENT]


def _flag(key: str):  # noqa: ANN202
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _one_of(key: str, choices: Sequence[str]):  # noqa: ANN202
    def check(value: object) -> str:
        if value not in choices:
            raise ValueError(f"{key} is one of {', '.join(map(repr, choices))}, not {value!r}")
        return value  # type: ignore[return-value]

    return check


def _texts(key: str):  # noqa: ANN202
    def check(value: object) -> tuple[str, ...]:
        if (
            not isinstance(value, list | tuple)
            or len(value) > MOST_RECENT
            or not all(isinstance(text, str) and len(text) <= MOST_TEXT for text in value)
        ):
            raise ValueError(f"{key} is a list of at most {MOST_RECENT} texts, not {value!r}")
        return tuple(value)

    return check


def _text(key: str):  # noqa: ANN202
    def check(value: object) -> str:
        if not isinstance(value, str) or len(value) > MOST_TEXT or "\0" in value:
            raise ValueError(f"{key} is a text, not {value!r}")
        return value

    return check


_CHECKS = {
    "regex": _flag("regex"),
    "match_all": _flag("match_all"),
    "case_sensitive": _flag("case_sensitive"),
    "apply_to": _one_of("apply_to", APPLY_TO),
    "text_case": _one_of("text_case", TEXT_CASES),
    "enumerate": _flag("enumerate"),
    "randomize": _flag("randomize"),
    "include_files": _flag("include_files"),
    "include_folders": _flag("include_folders"),
    "include_subfolders": _flag("include_subfolders"),
    "recent_search": _texts("recent_search"),
    "recent_replace": _texts("recent_replace"),
    "restore_flags": _flag("restore_flags"),
    "show_recent": _flag("show_recent"),
    "nemo_rename": _flag("nemo_rename"),
    "previous_tool": _text("previous_tool"),
}
