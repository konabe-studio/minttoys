from pathlib import Path

from tuxtoys.newitem.main import target_of


def test_target_of(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert target_of(str(tmp_path), []) == tmp_path
    assert target_of(str(tmp_path), [str(tmp_path / "a")]) == tmp_path / "a"
    assert target_of(str(tmp_path), [str(tmp_path / "a"), str(tmp_path / "b")]) == tmp_path
    assert target_of("", []) is None
