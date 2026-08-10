"""Pure functions that build tiddl CLI command argument lists.

No subprocess calls happen here — this module only builds argv lists so
they can be unit tested without spawning a real process.
"""
from __future__ import annotations

TIDDL_EXE = r"D:\Vibe Coding\Tidal\tiddl\.venv\Scripts\tiddl.exe"
DEFAULT_DOWNLOAD_PATH = r"C:\Users\BUREAU-ALEXIS\Music\Tiddl"

QUALITY_LABELS = ["Normal", "High", "Master"]
_QUALITY_FLAGS = {"Normal": "normal", "High": "high", "Master": "master"}


def quality_to_flag(label: str) -> str:
    if label not in _QUALITY_FLAGS:
        raise ValueError(f"Unknown quality label: {label!r}")
    return _QUALITY_FLAGS[label]


def build_login_command() -> list[str]:
    return [TIDDL_EXE, "auth", "login"]


def build_favorites_command(quality_label: str, download_path: str) -> list[str]:
    return [
        TIDDL_EXE, "fav", "download",
        "-q", quality_to_flag(quality_label),
        "-p", download_path,
    ]


def build_url_command(url: str, quality_label: str, download_path: str) -> list[str]:
    return [
        TIDDL_EXE, "url", url, "download",
        "-q", quality_to_flag(quality_label),
        "-p", download_path,
    ]
