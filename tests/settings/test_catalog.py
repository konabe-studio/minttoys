from minttoys.settings import catalog


def test_every_tool_has_a_heading() -> None:
    headings = catalog.headings()
    for tool in catalog.TOOLS:
        assert tool.category in headings, tool.id


def test_tool_ids_are_unique() -> None:
    ids = [tool.id for tool in catalog.TOOLS]
    assert len(ids) == len(set(ids))


def test_grouped_keeps_the_order_and_leaves_out_empty_headings() -> None:
    groups = catalog.grouped()
    assert [heading for heading, _ in groups] == ["System"]
    assert [tool.id for _, tools in groups for tool in tools] == ["awake"]


def test_every_module_the_daemon_has_is_listed() -> None:
    from minttoys.modules import AVAILABLE

    assert {tool.id for tool in catalog.TOOLS} == set(AVAILABLE)
