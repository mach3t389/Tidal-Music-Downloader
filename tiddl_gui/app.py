"""pywebview entry point wiring commands.py, runner.py, tiddl_api.py and
progress.py together behind a JS-callable Api class. Not covered by
automated tests — verified manually (see the plan's manual checklist)."""
from __future__ import annotations

import json
import os
import queue
from pathlib import Path
from tkinter import Tk, filedialog

import webview

from tiddl_gui.commands import (
    DEFAULT_DOWNLOAD_PATH,
    QUALITY_LABELS,
    build_favorites_command,
    build_login_command,
    build_url_command,
)
from tiddl_gui.progress import parse_track_line
from tiddl_gui.runner import DownloadRunner
from tiddl_gui.tiddl_api import NotLoggedInError
from tiddl_gui.tiddl_api import get_preview as fetch_preview
from tiddl_gui.tiddl_api import get_profile as fetch_profile

WEB_DIR = Path(__file__).parent / "web"


class Api:
    def __init__(self) -> None:
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._runner = DownloadRunner(self._queue)
        self._current_kind: str | None = None
        self._cancel_requested = False

    # -- called from JS --------------------------------------------------

    def get_defaults(self) -> dict:
        return {"quality_labels": QUALITY_LABELS, "default_path": DEFAULT_DOWNLOAD_PATH}

    def get_profile(self) -> dict:
        try:
            profile = fetch_profile()
            return {"ok": True, "email": profile.email, "country_code": profile.country_code}
        except NotLoggedInError as exc:
            return {"ok": False, "error": str(exc)}

    def get_preview(self, url: str) -> dict:
        try:
            tracks = fetch_preview(url)
            return {
                "ok": True,
                "tracks": [
                    {
                        "title": t.title,
                        "artist": t.artist,
                        "duration_seconds": t.duration_seconds,
                    }
                    for t in tracks
                ],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def start_login(self) -> dict:
        return self._start(build_login_command(), kind="login")

    def start_favorites(self, quality_label: str, download_path: str) -> dict:
        command = build_favorites_command(quality_label, download_path)
        return self._start(command, kind="download")

    def start_url(self, url: str, quality_label: str, download_path: str) -> dict:
        command = build_url_command(url, quality_label, download_path)
        return self._start(command, kind="download")

    def cancel(self) -> dict:
        self._cancel_requested = True
        self._runner.cancel()
        return {"ok": True}

    def open_folder(self, path: str) -> dict:
        try:
            os.startfile(path)
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def browse_folder(self, current_path: str) -> dict:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(
            initialdir=current_path or os.path.expanduser("~")
        )
        root.destroy()
        return {"ok": True, "path": chosen} if chosen else {"ok": False}

    # -- internal ---------------------------------------------------------

    def _start(self, command: list[str], kind: str) -> dict:
        if self._runner.is_running():
            return {"ok": False, "error": "Un telechargement est deja en cours."}
        self._current_kind = kind
        self._cancel_requested = False
        self._runner.start(command)
        return {"ok": True}

    def poll_loop(self, window: "webview.Window") -> None:
        """Runs in the background thread pywebview starts via
        `webview.start(api.poll_loop, window)`. Drains the runner's queue
        and pushes each message into the page via `evaluate_js`, which is
        safe to call from any thread."""
        while True:
            try:
                kind, payload = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if kind == "line":
                event = parse_track_line(str(payload))
                message = {
                    "type": "line",
                    "text": str(payload),
                    "track_event": (
                        {"title": event.title, "status": event.status} if event else None
                    ),
                }
            else:
                message = {
                    "type": "done",
                    "code": payload,
                    "kind": self._current_kind,
                    "cancelled": self._cancel_requested,
                }

            window.evaluate_js(f"window.onTiddlEvent({json.dumps(message)})")


def main() -> None:
    api = Api()
    window = webview.create_window(
        "Tiddl",
        str(WEB_DIR / "index.html"),
        js_api=api,
        width=1000,
        height=700,
        background_color="#121212",
    )
    webview.start(api.poll_loop, window, debug=False)


if __name__ == "__main__":
    main()
