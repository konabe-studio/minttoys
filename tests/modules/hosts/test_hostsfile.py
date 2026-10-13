import pytest

from tuxtoys.modules.hosts.hostsfile import (
    Entry,
    HostsFile,
    duplicates,
    is_address,
    is_host,
    parse_line,
)

# /etc/hosts as LMDE 7 writes it.
LMDE = """127.0.0.1\tlocalhost
127.0.1.1\tlmde

# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
"""


def test_the_file_reads_and_writes_back_unchanged() -> None:
    hosts = HostsFile(LMDE)
    assert hosts.text() == LMDE
    assert [entry.address for _index, entry in hosts.entries()] == [
        "127.0.0.1",
        "127.0.1.1",
        "::1",
        "ff02::1",
        "ff02::2",
    ]
    assert HostsFile("a\n\nb").text() == "a\n\nb"
    assert HostsFile("").text() == ""


@pytest.mark.parametrize(
    ("line", "entry"),
    [
        ("10.0.0.1 db db.local", Entry("10.0.0.1", ("db", "db.local"))),
        ("  10.0.0.1\tdb   # the database", Entry("10.0.0.1", ("db",), "the database")),
        ("# 10.0.0.1 db", Entry("10.0.0.1", ("db",), active=False)),
        ("#10.0.0.1 db #old", Entry("10.0.0.1", ("db",), "old", active=False)),
        ("fe80::1%eth0 router", Entry("fe80::1%eth0", ("router",))),
        # Active lines stay entries with a bad host, to be marked; comments do not.
        ("10.0.0.1 bad_host! ok", Entry("10.0.0.1", ("bad_host!", "ok"))),
        ("# 10.0.0.1 is the gateway, do not change it", None),
        ("# The following lines are desirable", None),
        ("10.0.0.1", None),
        ("server 10.0.0.1", None),
        ("", None),
    ],
)
def test_parse_line(line: str, entry: Entry | None) -> None:
    assert parse_line(line).entry == entry


def test_checks() -> None:
    assert is_address("192.168.1.1")
    assert is_address("::1")
    assert not is_address("999.1.1.1")
    assert not is_address("localhost")
    assert is_host("my-server.local")
    assert is_host("_service.example.com.")
    assert not is_host("-bad")
    assert not is_host("a..b")
    assert not is_host("x" * 64)
    assert Entry("10.0.0.1", ("a",)).valid
    assert not Entry("10.0.0.1", ()).valid_hosts
    assert not Entry("10.0.0", ("a",)).valid_address


def test_add_goes_to_the_top_of_the_entries() -> None:
    hosts = HostsFile("# My hosts\n\n127.0.0.1 localhost\n")
    index = hosts.add(Entry("10.0.0.1", ("db",), "work"))
    assert index == 2
    assert hosts.text() == "# My hosts\n\n10.0.0.1\tdb\t# work\n127.0.0.1 localhost\n"
    empty = HostsFile("# only a comment\n")
    empty.add(Entry("10.0.0.1", ("db",)))
    assert empty.text() == "# only a comment\n10.0.0.1\tdb\n"
    nothing = HostsFile("")
    nothing.add(Entry("10.0.0.1", ("db",)))
    assert nothing.text() == "10.0.0.1\tdb\n"


def test_switching_off_and_on_keeps_the_line() -> None:
    hosts = HostsFile("10.0.0.1     db   # keep my spacing\n")
    index, entry = next(hosts.entries())
    hosts.set(index, Entry(entry.address, entry.hosts, entry.comment, active=False))
    assert hosts.text() == "# 10.0.0.1     db   # keep my spacing\n"
    hosts = HostsFile(hosts.text())
    index, entry = next(hosts.entries())
    assert not entry.active
    hosts.set(index, Entry(entry.address, entry.hosts, entry.comment, active=True))
    assert hosts.text() == "10.0.0.1     db   # keep my spacing\n"


def test_editing_writes_the_line_anew_and_nothing_else() -> None:
    hosts = HostsFile(LMDE)
    hosts.set(1, Entry("127.0.1.1", ("lmde", "lmde.local")))
    assert hosts.text() == LMDE.replace("127.0.1.1\tlmde\n", "127.0.1.1\tlmde lmde.local\n")
    with pytest.raises(ValueError, match="not an entry"):
        hosts.set(2, Entry("1.1.1.1", ("x",)))


def test_remove_and_move() -> None:
    hosts = HostsFile("1.1.1.1 a\n# note\n2.2.2.2 b\n3.3.3.3 c\n")
    assert hosts.move(0, up=False) == 2
    assert hosts.text() == "2.2.2.2 b\n# note\n1.1.1.1 a\n3.3.3.3 c\n"
    assert hosts.move(0, up=True) == 0
    assert hosts.move(3, up=False) == 3
    hosts.remove(2)
    assert hosts.text() == "2.2.2.2 b\n# note\n3.3.3.3 c\n"
    with pytest.raises(ValueError, match="not an entry"):
        hosts.remove(1)


def test_duplicates() -> None:
    hosts = HostsFile(
        "127.0.0.1 localhost dev\n"
        "127.0.1.1 dev\n"
        "10.0.0.1 db\n"
        "10.0.0.2 DB.\n"
        "# 10.0.0.3 db\n"
        "::1 localhost\n"
        "fd00::1 db\n"
    )
    assert duplicates(hosts) == {2, 3}
    assert duplicates(hosts, loopback=True) == {0, 1, 2, 3}
