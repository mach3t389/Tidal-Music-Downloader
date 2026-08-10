"""Tkinter window wiring the tiddl command builders and subprocess runner
together. Not covered by automated tests — verified manually (see the
plan's Task 5 checklist)."""
from __future__ import annotations

import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

from tiddl_gui.commands import (
    DEFAULT_DOWNLOAD_PATH,
    QUALITY_LABELS,
    build_favorites_command,
    build_login_command,
    build_url_command,
)
from tiddl_gui.runner import DownloadRunner


class TiddlGuiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tiddl - Telechargeur Tidal")
        self.root.geometry("700x500")

        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._runner = DownloadRunner(self._queue)
        self._current_kind: str | None = None
        self._cancel_requested = False

        self._download_path = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        self._quality = tk.StringVar(value="High")
        self._url = tk.StringVar()
        self._status = tk.StringVar(value="Non connecte")

        self._build_login_section()
        self._build_download_section()
        self._build_log_section()

        self.root.after(100, self._poll_queue)

    # -- UI construction ----------------------------------------------

    def _build_login_section(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill="x")

        self.login_button = tk.Button(frame, text="Se connecter", command=self._on_login)
        self.login_button.pack(side="left")

        tk.Label(frame, textvariable=self._status).pack(side="left", padx=10)

    def _build_download_section(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=5)
        frame.pack(fill="x")

        self.favorites_button = tk.Button(
            frame, text="Telecharger mes favoris", command=self._on_download_favorites
        )
        self.favorites_button.grid(row=0, column=0, columnspan=3, sticky="w", pady=5)

        tk.Label(frame, text="Lien Tidal :").grid(row=1, column=0, sticky="w")
        tk.Entry(frame, textvariable=self._url, width=50).grid(row=1, column=1, sticky="we")
        self.url_button = tk.Button(
            frame, text="Telecharger ce lien", command=self._on_download_url
        )
        self.url_button.grid(row=1, column=2, padx=5)

        tk.Label(frame, text="Qualite :").grid(row=2, column=0, sticky="w", pady=5)
        tk.OptionMenu(frame, self._quality, *QUALITY_LABELS).grid(row=2, column=1, sticky="w")

        tk.Label(frame, text="Dossier :").grid(row=3, column=0, sticky="w")
        tk.Entry(frame, textvariable=self._download_path, width=50).grid(
            row=3, column=1, sticky="we"
        )
        tk.Button(frame, text="Parcourir...", command=self._on_browse).grid(
            row=3, column=2, padx=5
        )

        actions = tk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=3, sticky="w", pady=10)
        self.cancel_button = tk.Button(
            actions, text="Annuler", command=self._on_cancel, state="disabled"
        )
        self.cancel_button.pack(side="left")
        self.open_folder_button = tk.Button(
            actions, text="Ouvrir le dossier", command=self._on_open_folder, state="disabled"
        )
        self.open_folder_button.pack(side="left", padx=5)

        frame.columnconfigure(1, weight=1)

    def _build_log_section(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            frame, wrap="word", yscrollcommand=scrollbar.set, state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

    # -- Button handlers ------------------------------------------------

    def _on_login(self) -> None:
        self._start(build_login_command(), kind="login")

    def _on_download_favorites(self) -> None:
        command = build_favorites_command(self._quality.get(), self._download_path.get())
        self._start(command, kind="download")

    def _on_download_url(self) -> None:
        url = self._url.get().strip()
        if not url:
            messagebox.showwarning("Lien manquant", "Colle un lien Tidal avant de telecharger.")
            return
        command = build_url_command(url, self._quality.get(), self._download_path.get())
        self._start(command, kind="download")

    def _on_browse(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=self._download_path.get() or os.path.expanduser("~")
        )
        if chosen:
            self._download_path.set(chosen)

    def _on_cancel(self) -> None:
        self._cancel_requested = True
        self._runner.cancel()

    def _on_open_folder(self) -> None:
        os.startfile(self._download_path.get())

    # -- Process lifecycle ------------------------------------------------

    def _start(self, command: list[str], kind: str) -> None:
        if self._runner.is_running():
            messagebox.showinfo(
                "Telechargement en cours", "Attends la fin du telechargement actuel."
            )
            return
        self._current_kind = kind
        self._cancel_requested = False
        self._append_log("$ " + " ".join(command))
        self._set_running_state(True)
        self._runner.start(command)

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.login_button.config(state=state)
        self.favorites_button.config(state=state)
        self.url_button.config(state=state)
        self.cancel_button.config(state="normal" if running else "disabled")

    def _poll_queue(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                self._append_log(str(payload))
            elif kind == "done":
                self._set_running_state(False)
                if payload == 0:
                    if self._current_kind == "login":
                        self._status.set("Connecte")
                    else:
                        self.open_folder_button.config(state="normal")
                    self._append_log(f"[termine, code {payload}]")
                    if self._current_kind != "login":
                        messagebox.showinfo(
                            "Telechargement termine",
                            "Le telechargement est termine avec succes.",
                        )
                elif self._cancel_requested:
                    self._append_log("[annule]")
                else:
                    self._append_log(f"[termine, code {payload}]")
                    messagebox.showerror(
                        "Echec",
                        f"L'operation a echoue (code {payload}). Consulte le journal pour plus de details.",
                    )
                self._cancel_requested = False
        self.root.after(100, self._poll_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    TiddlGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
