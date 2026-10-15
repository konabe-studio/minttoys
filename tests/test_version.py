import re
import tomllib
from pathlib import Path

from tuxtoys import VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_the_version_is_the_same_everywhere() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == VERSION
    first = (ROOT / "debian" / "changelog").read_text(encoding="utf-8").splitlines()[0]
    debian = re.search(r"\((.+?)\)", first)[1]
    assert debian.replace("~dev", ".dev0") == VERSION
