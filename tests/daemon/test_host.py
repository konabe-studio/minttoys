from typing import ClassVar

import pytest

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


def test_hands_each_module_the_bus_and_its_own_settings(recorder: Recorder) -> None:
    host = ModuleHost({"a": fake("a", recorder), "b": fake("b", recorder)})
    host.apply(settings(a={"minutes": 30}, b={"minutes": 90}), BUS)
    assert recorder.contexts["a"].bus is BUS
    assert recorder.contexts["a"].settings == {"minutes": 30}
    assert recorder.contexts["b"].settings == {"minutes": 90}


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
