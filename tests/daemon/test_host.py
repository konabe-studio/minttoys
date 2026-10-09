from collections.abc import Mapping
from typing import Any, ClassVar

import pytest

from minttoys.api import ModuleInfo
from minttoys.core.config import Config
from minttoys.daemon.host import ModuleHost, ModuleLoader, State, lazy
from minttoys.modules.base import Context, Module

BUS = object()


class Recorder:
    """What the fake modules did, in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.contexts: dict[str, Context] = {}


def fake(
    module_id: str,
    recorder: Recorder,
    *,
    default: bool = True,
    fail_enable: bool = False,
    fail_disable: bool = False,
) -> ModuleLoader:
    class Fake(Module):
        id: ClassVar[str] = module_id
        name: ClassVar[str] = module_id
        description: ClassVar[str] = ""
        enabled_by_default: ClassVar[bool] = default

        def enable(self, context: Context) -> None:
            recorder.calls.append(f"enable {module_id}")
            recorder.contexts[module_id] = context
            if fail_enable:
                raise RuntimeError("enable broke")

        def disable(self) -> None:
            recorder.calls.append(f"disable {module_id}")
            if fail_disable:
                raise RuntimeError("disable broke")

        @classmethod
        def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
            return {"x": int(section["x"])} if "x" in section else {}

        def apply_settings(self, settings: Mapping[str, Any]) -> None:
            recorder.calls.append(f"settings {module_id} {dict(settings)}")

    return lambda: Fake


def broken_import() -> type[Module]:
    raise ImportError("no typelib")


def settings(**modules: dict) -> Config:
    return Config({"modules": modules})


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


def test_switches_on_a_module_that_is_on_by_default(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder)})
    host.apply(Config(), BUS)
    assert recorder.calls == ["enable a"]
    assert host.states == {"a": State.ON}


def test_leaves_off_a_module_that_is_off_by_default(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder, default=False)})
    host.apply(Config(), BUS)
    assert recorder.calls == []
    assert host.states == {"a": State.OFF}


def test_the_config_overrides_the_default(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder, default=False)})
    host.apply(settings(a={"enabled": False}, b={"enabled": True}), BUS)
    assert recorder.calls == ["enable b"]


def test_a_value_that_is_not_true_or_false_means_the_default(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder)})
    host.apply(settings(a={"enabled": "no"}), BUS)
    assert host.states == {"a": State.ON}


def test_hands_each_module_the_bus_and_its_own_settings_as_it_reads_them(
    recorder: Recorder,
) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder)})
    host.apply(settings(a={"x": "30", "enabled": True}, b={"x": 90}), BUS)
    assert recorder.contexts["a"].bus is BUS
    assert recorder.contexts["a"].settings == {"x": 30}
    assert recorder.contexts["b"].settings == {"x": 90}


def test_applying_the_same_config_again_changes_nothing(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder)})
    host.apply(Config(), BUS)
    host.apply(Config(), BUS)
    assert recorder.calls == ["enable a"]


def test_switches_off_a_module_the_config_turned_off(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder)})
    host.apply(Config(), BUS)
    host.apply(settings(a={"enabled": False}), BUS)
    assert recorder.calls == ["enable a", "disable a"]
    assert host.states == {"a": State.OFF}


def test_a_module_that_fails_to_switch_on_is_cleaned_up_and_the_rest_carry_on(
    recorder: Recorder,
) -> None:
    host = ModuleHost({"a": fake("a", recorder, fail_enable=True), "b": fake("b", recorder)})
    host.apply(Config(), BUS)
    assert recorder.calls == ["enable a", "disable a", "enable b"]
    assert host.states == {"a": State.FAILED, "b": State.ON}
    assert host.errors == {"a": "RuntimeError: enable broke"}


def test_a_failed_module_is_tried_again_on_the_next_apply(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder, fail_enable=True)})
    host.apply(Config(), BUS)
    host.apply(Config(), BUS)
    assert recorder.calls.count("enable a") == 2


def test_a_module_that_fails_to_import_fails_alone(recorder: Recorder) -> None:
    host = ModuleHost({"a": broken_import, "b": fake("b", recorder)})
    host.apply(Config(), BUS)
    assert host.states == {"a": State.FAILED, "b": State.ON}
    assert host.errors == {"a": "ImportError: no typelib"}


def test_a_module_that_failed_to_import_is_not_imported_again() -> None:
    attempts: list[str] = []

    def counting_import() -> type[Module]:
        attempts.append("import")
        raise ImportError("no typelib")

    host = ModuleHost({"a": counting_import})
    host.apply(Config(), BUS)
    host.apply(Config(), BUS)
    assert attempts == ["import"]


def test_stop_all_switches_off_in_reverse_order(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder)})
    host.apply(Config(), BUS)
    host.stop_all()
    assert recorder.calls == ["enable a", "enable b", "disable b", "disable a"]
    assert host.states == {"a": State.OFF, "b": State.OFF}


def test_a_module_that_fails_to_switch_off_does_not_stop_the_others(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder, fail_disable=True)})
    host.apply(Config(), BUS)
    host.stop_all()
    assert recorder.calls[-2:] == ["disable b", "disable a"]
    assert host.states == {"a": State.OFF, "b": State.FAILED}


def test_lazy_imports_only_when_called() -> None:
    load = lazy("minttoys.no_such_module:Nothing")
    with pytest.raises(ModuleNotFoundError):
        load()


def test_lazy_finds_the_class() -> None:
    assert lazy("minttoys.modules.base:Module")() is Module


def test_describe_lists_every_module_with_its_state(recorder: Recorder) -> None:
    host = ModuleHost(
        {"a": fake("a", recorder), "b": fake("b", recorder, fail_enable=True), "c": broken_import}
    )
    host.apply(Config(), BUS)
    assert host.describe() == [
        ModuleInfo("a", "a", "", "on", ""),
        ModuleInfo("b", "b", "", "failed", "RuntimeError: enable broke"),
        ModuleInfo("c", "c", "", "failed", "ImportError: no typelib"),
    ]


def test_describe_before_any_apply_shows_every_module_off(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder)})
    assert host.describe() == [ModuleInfo("a", "a", "", "off", "")]
    assert recorder.calls == []


def test_module_ids(recorder: Recorder) -> None:
    assert ModuleHost({"a": fake("a", recorder), "b": broken_import}).module_ids == ("a", "b")


def test_a_module_sets_its_settings_through_the_host_under_its_own_id(recorder: Recorder) -> None:
    calls: list[tuple] = []
    host = ModuleHost({"a": fake("a", recorder)}, set_settings=lambda *call: calls.append(call))
    host.apply(Config(), BUS)
    recorder.contexts["a"].set_settings({"x": 1})
    assert calls == [("a", {"x": 1})]


def test_module_class(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": broken_import})
    assert host.module_class("a").id == "a"
    with pytest.raises(ValueError, match="unknown module"):
        host.module_class("nope")
    with pytest.raises(RuntimeError, match="ImportError: no typelib"):
        host.module_class("b")


def test_settings_reach_a_module_only_while_it_is_on(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder, default=False)})
    host.apply(Config(), BUS)
    host.apply_settings("a", {"x": 2})
    host.apply_settings("b", {"x": 3})
    assert recorder.calls == ["enable a", "settings a {'x': 2}"]


def test_a_module_is_off_unless_it_says_otherwise() -> None:
    assert Module.enabled_by_default is False
