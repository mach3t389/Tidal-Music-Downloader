"""Runs one tiddl command at a time in a background thread and streams
its output through a thread-safe queue.

Tkinter widgets must only be touched from the main thread, so this module
never calls into the GUI directly — it only pushes messages onto the
queue given at construction time. The GUI polls that queue from the main
thread with `root.after(...)`.
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading


class DownloadRunner:
    def __init__(self, output_queue: "queue.Queue[tuple[str, object]]") -> None:
        self._queue = output_queue
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._starting = False

    def is_running(self) -> bool:
        if self._starting:
            return True
        return self._process is not None and self._process.poll() is None

    def start(self, command: list[str]) -> None:
        with self._lock:
            if self.is_running():
                raise RuntimeError("A download is already running")
            self._starting = True
        self._thread = threading.Thread(target=self._run, args=(command,), daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        if self._process is not None and self._process.poll() is None:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                capture_output=True,
            )

    def _run(self, command: list[str]) -> None:
        returncode = -1
        try:
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            self._starting = False
            assert self._process.stdout is not None
            for line in self._process.stdout:
                self._queue.put(("line", line.rstrip("\n")))
            returncode = self._process.wait()
        except Exception as exc:
            self._starting = False
            self._queue.put(("line", f"[erreur] {exc}"))
        finally:
            self._queue.put(("done", returncode))
