from minttoys.modules.locksmith import text


def test_heading_names_one_item() -> None:
    assert text.heading(["/home/ben/report.odt"]) == "What is using report.odt"
    assert text.heading(["/home/ben/Music/"]) == "What is using Music"


def test_heading_counts_several() -> None:
    assert text.heading(["/a", "/b"]) == "What is using 2 items"


def test_held_inside_a_folder_is_shown_from_that_folder() -> None:
    held = text.held(["/home/ben/Music/rock/song.ogg"], ["/home/ben/Music"])
    assert held == "rock/song.ogg"


def test_held_files_are_shown_by_name() -> None:
    assert text.held(["/home/ben/a.txt", "/home/ben/b.txt"], ["/home/ben/a.txt"]) == "a.txt, b.txt"
