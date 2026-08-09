import pytest

from tiddl_gui.commands import (
    TIDDL_EXE,
    build_favorites_command,
    build_login_command,
    build_url_command,
    quality_to_flag,
)


def test_quality_to_flag_maps_known_labels():
    assert quality_to_flag("Normal") == "normal"
    assert quality_to_flag("High") == "high"
    assert quality_to_flag("Master") == "master"


def test_quality_to_flag_rejects_unknown_label():
    with pytest.raises(ValueError):
        quality_to_flag("Ultra")


def test_build_login_command():
    assert build_login_command() == [TIDDL_EXE, "auth", "login"]


def test_build_favorites_command():
    cmd = build_favorites_command("High", r"C:\Music")
    assert cmd == [
        TIDDL_EXE, "fav", "-r", "track", "download",
        "-q", "high", "-p", r"C:\Music",
    ]


def test_build_url_command():
    cmd = build_url_command("https://tidal.com/browse/track/1", "Master", r"C:\Music")
    assert cmd == [
        TIDDL_EXE, "url", "https://tidal.com/browse/track/1", "download",
        "-q", "master", "-p", r"C:\Music",
    ]
