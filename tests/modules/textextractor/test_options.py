import pytest

from tuxtoys.modules.textextractor.options import Options


def test_the_defaults() -> None:
    assert Options.read({}).settings() == {"shortcut": True, "language": ""}


def test_a_bad_value_in_the_config_gives_its_default() -> None:
    assert Options.read({"language": "../../etc", "shortcut": "yes"}) == Options()
    assert Options.read({"language": "chi_sim"}).language == "chi_sim"


@pytest.mark.parametrize(
    "changes",
    [{"language": "hu n"}, {"language": 5}, {"shortcut": 1}, {"other": True}],
    ids=["space", "number", "flag", "unknown"],
)
def test_a_change_is_checked(changes: dict) -> None:
    with pytest.raises(ValueError, match=r"not|unknown"):
        Options().update(changes)
