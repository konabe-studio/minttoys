"""Environment Variables' settings, read and checked without GTK or D-Bus.

The user's variables, in order, as D-Bus a(ss); the profiles, each a name and its
variables, as a(sa(ss)); and the profile applied, by name, "" for none: one at a time, as
PowerToys has it. The system's variables are not settings: they are /etc/environment.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.envvars.variables import is_name, is_value

MOST_VARIABLES = 500
MOST_PROFILES = 50
MOST_PROFILE_NAME = 100

type Pairs = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Profile:
    name: str
    variables: Pairs = ()


@dataclass(frozen=True)
class Options:
    variables: Pairs = ()
    profiles: tuple[Profile, ...] = ()
    active_profile: str = ""

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From the tool's section of the config; a value of the wrong kind gives its
        default, so a config edited by hand cannot keep the tool from working.
        """
        options = cls()
        for key in ("variables", "profiles", "active_profile"):
            if key in settings:
                with suppress(ValueError, TypeError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take. A profile applied that is no longer there is
        applied no more.
        """
        fields: dict[str, Any] = {}
        for key, value in changes.items():
            if key == "variables":
                fields[key] = _pairs(value, "variables")
            elif key == "profiles":
                fields[key] = _profiles(value)
            elif key == "active_profile":
                if not isinstance(value, str):
                    raise ValueError(f"active_profile is a profile's name, not {value!r}")
                fields[key] = value
            else:
                raise ValueError(f"unknown setting: {key!r}")
        options = replace(self, **fields)
        names = {profile.name for profile in options.profiles}
        if options.active_profile and options.active_profile not in names:
            if "active_profile" in changes:
                raise ValueError(f"there is no profile {options.active_profile!r}")
            options = replace(options, active_profile="")
        return options

    def settings(self) -> dict[str, Any]:
        return {
            "variables": [list(pair) for pair in self.variables],
            "profiles": [
                [profile.name, [list(pair) for pair in profile.variables]]
                for profile in self.profiles
            ],
            "active_profile": self.active_profile,
        }

    @property
    def applied(self) -> Pairs:
        """The applied profile's variables, none when no profile is applied."""
        for profile in self.profiles:
            if profile.name == self.active_profile:
                return profile.variables
        return ()


def _pairs(value: object, key: str) -> Pairs:
    if not isinstance(value, list | tuple) or len(value) > MOST_VARIABLES:
        raise ValueError(f"{key} is a list of at most {MOST_VARIABLES} variables")
    pairs = []
    for pair in value:
        if not isinstance(pair, list | tuple) or len(pair) != 2:
            raise ValueError(f"a variable is a name and a value, not {pair!r}")
        name, text = pair
        if not isinstance(name, str) or not is_name(name):
            raise ValueError(f"not a variable name: {name!r}")
        if not isinstance(text, str) or not is_value(text):
            raise ValueError(f"{name}'s value is one line of text, not {text!r}")
        pairs.append((name, text))
    if len({name for name, _text in pairs}) != len(pairs):
        raise ValueError(f"a name is in {key} twice")
    return tuple(pairs)


def _profiles(value: object) -> tuple[Profile, ...]:
    if not isinstance(value, list | tuple) or len(value) > MOST_PROFILES:
        raise ValueError(f"profiles is a list of at most {MOST_PROFILES}")
    profiles = []
    for entry in value:
        if not isinstance(entry, list | tuple) or len(entry) != 2:
            raise ValueError(f"a profile is a name and its variables, not {entry!r}")
        name, variables = entry
        if not isinstance(name, str) or not name.strip() or len(name) > MOST_PROFILE_NAME:
            raise ValueError(f"a profile needs a name, not {name!r}")
        profiles.append(Profile(name.strip(), _pairs(variables, f"profile {name!r}")))
    if len({profile.name for profile in profiles}) != len(profiles):
        raise ValueError("two profiles have the same name")
    return tuple(profiles)
