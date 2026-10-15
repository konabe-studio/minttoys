import hashlib
import io
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tuxtoys.core.rootfile import BAD, CHANGED, SAVED
from tuxtoys.modules.base import Context
from tuxtoys.modules.envvars import userfile, variables
from tuxtoys.modules.envvars.module import EnvironmentVariables
from tuxtoys.modules.envvars.options import Options, Profile
from tuxtoys.modules.envvars.save import save
from tuxtoys.modules.envvars.systemfile import SystemFile, line, parse_line

# /etc/environment as Ubuntu writes it, and as LMDE 7 has it: empty but for a comment.
UBUNTU = 'PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'


def test_names_and_values() -> None:
    assert variables.is_name("JAVA_HOME")
    assert variables.is_name("_x1")
    assert not variables.is_name("1X")
    assert not variables.is_name("MY-VAR")
    assert variables.is_value("a b $HOME")
    assert not variables.is_value("two\nlines")
    assert variables.is_list("PATH")
    assert variables.is_list("MY_DIRS", "/a/b:/c/d")
    assert not variables.is_list("EDITOR", "nano")
    assert variables.split_list("/a:/b") == ["/a", "/b"]
    assert variables.join_list(["/a", "", "/b"]) == "/a:/b"


def test_expand_and_quote() -> None:
    environment = {"HOME": "/home/lmde", "PATH": "/usr/bin"}
    assert variables.expand("$HOME/bin:${PATH}:$NOPE", environment) == "/home/lmde/bin:/usr/bin:"
    assert variables.expand("costs $5", environment) == "costs $5"
    assert variables.shell_quoted("$HOME/bin:${PATH}") == '"$HOME/bin:${PATH}"'
    assert variables.shell_quoted('a "b" `c` \\d $(rm) $5') == (
        '"a \\"b\\" \\`c\\` \\\\d \\$(rm) \\$5"'
    )


def test_what_applies() -> None:
    system = [("PATH", "/usr/bin"), ("LANG", "hu_HU.UTF-8")]
    user = [("PATH", "$HOME/bin:$PATH"), ("EDITOR", "nano")]
    profile = [("EDITOR", "vim"), ("JAVA_HOME", "$HOME/jdk")]
    applied = variables.applied(system, user, profile, {"HOME": "/home/b", "PATH": "/bin"})
    assert applied["PATH"] == "/home/b/bin:/usr/bin"
    assert applied["EDITOR"] == "vim"
    assert applied["JAVA_HOME"] == "/home/b/jdk"
    assert variables.origins(system, user, profile) == {
        "PATH": "user",
        "LANG": "system",
        "EDITOR": "profile",
        "JAVA_HOME": "profile",
    }


def test_the_user_file() -> None:
    text = userfile.render([("PATH", "$HOME/bin:$PATH")], [("EDITOR", "vim")])
    assert text.startswith("# Written by TuxToys")
    assert '    PATH="$HOME/bin:$PATH"\n' in text
    assert "    export PATH EDITOR\n" in text
    assert userfile.render([], []).count("export TUXTOYS_ENVIRONMENT=") == 1


@pytest.mark.skipif(shutil.which("sh") is None or os.name == "nt", reason="needs sh")
def test_the_user_file_runs_in_sh_once_per_version(tmp_path: Path) -> None:
    path = tmp_path / "environment"
    path.write_text(userfile.render([("PATH", "/opt/x:$PATH"), ("GREETING", 'say "hi" $5')], []))
    script = f'. "{path}"; . "{path}"; printf "%s|%s" "$PATH" "$GREETING"'
    out = subprocess.run(
        ["sh", "-c", script], capture_output=True, text=True, check=True, env={"PATH": "/bin"}
    ).stdout
    assert out == '/opt/x:/bin|say "hi" $5'


def test_the_loading_line() -> None:
    line_ = userfile.hook("/home/b/.config/tuxtoys/environment")
    assert line_ == (
        '[ -r "/home/b/.config/tuxtoys/environment" ] && '
        '. "/home/b/.config/tuxtoys/environment"  # TuxToys: Environment Variables'
    )
    text = userfile.with_hook("export A=1\n\n", line_)
    assert text == f"export A=1\n\n{line_}\n"
    assert userfile.with_hook(text, line_) == text
    assert userfile.without_hook(text) == "export A=1\n"
    assert userfile.with_hook("", line_) == f"{line_}\n"
    assert userfile.without_hook(f"{line_}\n") == ""


def test_etc_environment() -> None:
    assert parse_line('PATH="/usr/bin:/bin"').value == "/usr/bin:/bin"
    assert parse_line("export LANG='hu_HU.UTF-8'").name == "LANG"
    assert parse_line("# A=1").name == ""
    assert parse_line("not a variable").name == ""
    system = SystemFile("# comment\n" + UBUNTU)
    assert [(n, v) for _i, n, v in system.variables()] == [
        ("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    ]
    index = system.add("JAVA_HOME", "/usr/lib/jvm/default")
    system.set(1, "PATH", "/usr/bin")
    assert system.text() == '# comment\nPATH="/usr/bin"\nJAVA_HOME="/usr/lib/jvm/default"\n'
    system.remove(index)
    with pytest.raises(ValueError, match="not a variable"):
        system.remove(0)
    assert line("A", 'say "hi"') == "A='say \"hi\"'"
    with pytest.raises(ValueError, match="both kinds"):
        line("A", "\"'")
    assert SystemFile("").text() == ""


def test_options() -> None:
    options = Options().update(
        {
            "variables": [["PATH", "$HOME/bin:$PATH"]],
            "profiles": [["Work", [["JAVA_HOME", "/opt/jdk"]]]],
            "active_profile": "Work",
        }
    )
    assert options.applied == (("JAVA_HOME", "/opt/jdk"),)
    assert Options.read(options.settings()) == options
    assert options.update({"profiles": []}).active_profile == ""
    assert options.profiles == (Profile("Work", (("JAVA_HOME", "/opt/jdk"),)),)
    for bad, message in (
        ({"variables": [["1A", "x"]]}, "not a variable name"),
        ({"variables": [["A", "x"], ["A", "y"]]}, "twice"),
        ({"variables": [["A", "a\nb"]]}, "one line"),
        ({"profiles": [["", []]]}, "needs a name"),
        ({"profiles": [["P", []], ["P", []]]}, "same name"),
        ({"active_profile": "Home"}, "no profile"),
        ({"other": 1}, "unknown setting"),
    ):
        with pytest.raises(ValueError, match=message):
            options.update(bad)


def test_the_root_helper(tmp_path: Path) -> None:
    environment = tmp_path / "environment"
    environment.write_text(UBUNTU, newline="\n")
    expect = hashlib.sha256(UBUNTU.encode()).hexdigest()
    new = UBUNTU + 'JAVA_HOME="/opt/jdk"\n'
    backups = tmp_path / "backups"
    now = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    status = save(
        ["--expect", expect, "--backup"], io.BytesIO(new.encode()), environment, backups, now
    )
    assert status == (SAVED, "")
    assert environment.read_text() == new
    assert [p.name for p in backups.iterdir()] == ["environment-20261015-090000"]
    assert save(["--expect", expect], io.BytesIO(b"x"), environment, backups)[0] == CHANGED
    assert save(["--expect", expect], io.BytesIO(b"x" * 300_000), environment, backups)[0] == BAD


def module_here(tmp_path: Path) -> EnvironmentVariables:
    return EnvironmentVariables(home=lambda: tmp_path / "home", config=lambda: tmp_path / "config")


def test_the_module_writes_its_file_and_lines(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text("alias ll='ls -l'\n")
    module = module_here(tmp_path)
    settings = Options(variables=(("EDITOR", "nano"),)).settings()
    module.enable(Context(None, settings))
    assert '    EDITOR="nano"\n' in module.file.read_text()
    session = (home / ".xsessionrc").read_text()
    assert session == userfile.hook(str(module.file)) + "\n"
    assert (home / ".bashrc").read_text().startswith("alias ll='ls -l'\n\n[ -r ")
    module.apply_settings(Options(variables=(("EDITOR", "vim"),)).settings())
    assert '    EDITOR="vim"\n' in module.file.read_text()
    module.disable()
    assert module.file.exists()
    module.switched_off()
    assert not module.file.exists()
    assert not (home / ".xsessionrc").exists()
    assert (home / ".bashrc").read_text() == "alias ll='ls -l'\n"


def test_an_xsessionrc_of_ones_own_is_kept(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".xsessionrc").write_text("export QT_QPA_PLATFORMTHEME=gtk2\n")
    module = module_here(tmp_path)
    module.enable(Context(None, Options().settings()))
    assert not (home / ".bashrc").exists()  # never made one
    module.switched_off()
    assert (home / ".xsessionrc").read_text() == "export QT_QPA_PLATFORMTHEME=gtk2\n"


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_a_linked_bashrc_stays_a_link(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    real = tmp_path / "dotfiles-bashrc"
    real.write_text("# mine\n")
    (home / ".bashrc").symlink_to(real)
    module = module_here(tmp_path)
    module.enable(Context(None, Options().settings()))
    assert (home / ".bashrc").is_symlink()
    assert "TuxToys" in real.read_text()


def test_off_by_default() -> None:
    assert EnvironmentVariables.enabled_by_default is False


def test_login_path() -> None:
    assert variables.login_path("# x\nENV_PATH\tPATH=/usr/bin:/bin\n") == "/usr/bin:/bin"
    assert variables.login_path("") == variables.DEFAULT_PATH
