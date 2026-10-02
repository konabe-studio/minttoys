import json
from pathlib import Path

import pytest

from minttoys.core import config
from minttoys.core.config import Config


class TestDefaultPath:
    def test_follows_xdg_config_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert config.default_path() == tmp_path / "minttoys" / "config.json"

    @pytest.mark.parametrize("value", ["", "relative/path"])
    def test_falls_back_to_dot_config(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", value)
        assert config.default_path() == Path.home() / ".config" / "minttoys" / "config.json"

    def test_falls_back_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert config.default_path() == Path.home() / ".config" / "minttoys" / "config.json"


class TestConfig:
    def test_a_missing_section_is_empty(self) -> None:
        assert Config().module("awake") == {}

    def test_module_returns_a_copy(self) -> None:
        settings = Config({"modules": {"awake": {"enabled": True}}})
        settings.module("awake")["enabled"] = False
        assert settings.module("awake") == {"enabled": True}

    @pytest.mark.parametrize(
        "data", [{"modules": []}, {"modules": {"awake": "on"}}, {"modules": None}]
    )
    def test_a_malformed_section_reads_as_empty(self, data: dict) -> None:
        assert Config(data).module("awake") == {}

    def test_set_module_replaces_one_section(self) -> None:
        settings = Config({"modules": {"awake": {"enabled": True}, "other": {"x": 1}}})
        settings.set_module("awake", {"enabled": False})
        assert settings.module("awake") == {"enabled": False}
        assert settings.module("other") == {"x": 1}

    def test_set_module_repairs_a_malformed_modules_key(self) -> None:
        settings = Config({"modules": []})
        settings.set_module("awake", {"enabled": True})
        assert settings.module("awake") == {"enabled": True}


class TestLoad:
    def test_a_missing_file_is_an_empty_config(self, tmp_path: Path) -> None:
        assert config.load(tmp_path / "config.json").module("awake") == {}

    def test_reads_a_module_section(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"modules": {"awake": {"enabled": false}}}', encoding="utf-8")
        assert config.load(path).module("awake") == {"enabled": False}

    @pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b'"text"', b"", b"\xff\xfe{}"])
    def test_moves_an_unreadable_file_aside(self, tmp_path: Path, content: bytes) -> None:
        path = tmp_path / "config.json"
        path.write_bytes(content)
        assert config.load(path).module("awake") == {}
        assert not path.exists()
        assert (tmp_path / "config.json.broken").read_bytes() == content


class TestSave:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        settings = Config()
        settings.set_module("awake", {"enabled": True, "default_minutes": 60})
        config.save(settings, path)
        assert config.load(path).module("awake") == {"enabled": True, "default_minutes": 60}

    def test_creates_the_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "minttoys" / "config.json"
        config.save(Config(), path)
        assert path.exists()

    def test_keeps_keys_it_does_not_know(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"future": [1], "modules": {"later": {"a": 1}}}', encoding="utf-8")
        settings = config.load(path)
        settings.set_module("awake", {"enabled": True})
        config.save(settings, path)
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["future"] == [1]
        assert saved["modules"]["later"] == {"a": 1}

    def test_writes_utf8(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        settings = Config()
        settings.set_module("awake", {"reason": "ébren tartás"})
        config.save(settings, path)
        assert "ébren tartás" in path.read_text(encoding="utf-8")

    def test_a_failed_write_leaves_the_old_file_and_no_temporary_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"modules": {"awake": {"enabled": true}}}', encoding="utf-8")

        def fail(self: Config) -> str:
            raise OSError("disk full")

        monkeypatch.setattr(Config, "to_json", fail)
        with pytest.raises(OSError, match="disk full"):
            config.save(Config(), path)
        assert path.read_text(encoding="utf-8") == '{"modules": {"awake": {"enabled": true}}}'
        assert [entry.name for entry in tmp_path.iterdir()] == ["config.json"]
