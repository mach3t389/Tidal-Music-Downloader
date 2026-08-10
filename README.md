# Tiddl GUI

Simple Tkinter GUI for the [tiddl](https://pypi.org/project/tiddl/) Tidal
downloader — login, download favorites or a link, pick quality and
destination, live log.

## Requirements

- The `tiddl` CLI installed at `D:\Vibe Coding\tiddl\.venv\Scripts\tiddl.exe`
  (this path is hardcoded in `tiddl_gui/commands.py`).
- Python 3.12+ on Windows.

## Run

    & "D:\Vibe Coding\tiddl-gui\.venv\Scripts\python.exe" "D:\Vibe Coding\tiddl-gui\main.py"

## Run the tests

    & "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests" -v

## Manual test checklist

1. **Connexion** — click "Se connecter"; a `link.tidal.com` URL appears in
   the log; after authorizing in the browser, the status label switches to
   "Connecte".
2. **Telechargement par lien** — paste a Tidal track URL, click
   "Telecharger ce lien"; the file appears in the destination folder.
3. **Telechargement des favoris** — click "Telecharger mes favoris"; the
   log shows per-track progress.
4. **Annulation** — start a download, click "Annuler" before it finishes;
   the process stops and the buttons return to their idle state.
5. **Ouvrir le dossier** — after a successful download, click "Ouvrir le
   dossier"; Explorer opens on the destination folder.
6. **Changer de dossier** — click "Parcourir...", pick a different folder;
   the next download uses the new path.
