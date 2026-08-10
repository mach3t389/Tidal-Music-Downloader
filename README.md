# Tiddl GUI

Dark, sidebar-based desktop app (built with `pywebview`) for the
[tiddl](https://pypi.org/project/tiddl/) Tidal downloader — connection
profile card, instant playlist/album preview, per-track download status,
and a plain-language status banner instead of a raw log.

## Requirements

- The `tiddl` CLI's cached login at `~/tiddl.json` (created by `tiddl auth
  login` — see the sibling `tiddl` project at
  `D:\Vibe Coding\Tidal\tiddl\.venv\Scripts\tiddl.exe`, whose hardcoded path is
  referenced by `tiddl_gui/commands.py` for the actual download/login
  subprocess calls).
- Python 3.12+ on Windows.
- This project's own venv has its own copy of the `tiddl` Python package
  (installed via `requirements.txt`) purely to reuse its `TidalApi`
  client for previews — it reads the same `~/tiddl.json` token file
  regardless of which venv's copy of `tiddl` is running.

## Run

    & "D:\Vibe Coding\tiddl-gui\.venv\Scripts\python.exe" "D:\Vibe Coding\tiddl-gui\main.py"

## Run the tests

    & "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests" -v

## Manual test checklist

1. **Connexion** — click "Se connecter"; a `link.tidal.com` URL appears
   in the collapsed log (expand "Voir les details" to see it); after
   authorizing in the browser, the sidebar switches to the profile card
   showing your email and country.
2. **Apercu d'une playlist** — paste a Tidal playlist or album URL into
   the "Lien" panel; the track list appears below the form within about
   half a second of pausing typing, each row showing "en attente".
3. **Telechargement par lien** — click "Telecharger ce lien"; as tracks
   finish, their preview rows switch to "telechargee" (or "deja
   presente" if the file already existed); the status banner shows a
   completion message when done.
4. **Telechargement incremental** — re-run the same playlist link after
   it has already fully downloaded once; the preview rows should mostly
   show "deja presente" quickly rather than re-downloading everything.
5. **Telechargement des favoris** — click "Telecharger mes favoris"; the
   status banner updates, the collapsed log shows per-item progress.
6. **Annulation** — start a download, click "Annuler" before it
   finishes; the banner shows "Telechargement annule", not an error.
7. **Ouvrir le dossier** — after a successful download, click "Ouvrir le
   dossier"; Explorer opens on the destination folder.
8. **Changer de dossier** — click "Parcourir...", pick a different
   folder; the next download uses the new path.
