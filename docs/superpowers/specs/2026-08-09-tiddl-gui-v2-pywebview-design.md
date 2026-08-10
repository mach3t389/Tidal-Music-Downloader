# tiddl-gui v2 — pywebview redesign

## Context

The v1 Tkinter GUI (merged to `main` in commit `db330c2`) works but the user found it visually incomplete after real use: scattered buttons, no visible connection status beyond a text label, no track-level feedback, and the raw log was the only source of truth for what happened. This spec redesigns the interface as a `pywebview` app (native window rendering local HTML/CSS/JS) while reusing the already-tested Python backend.

## Goal

A dark-themed, sidebar-based interface that: shows who's connected (email + country), previews a playlist/album's track list the moment a valid link is pasted, tracks each song's status (pending / downloaded / already-present / failed) live during a run, surfaces a plain-language status banner instead of requiring the user to read the raw log, and keeps the incremental "only download what's missing" behavior — which `tiddl` already does natively — visible to the user instead of buried in scrollback.

## What stays unchanged

- `tiddl_gui/commands.py` — pure argv builders (`build_login_command`, `build_favorites_command`, `build_url_command`, `quality_to_flag`, `TIDDL_EXE`, `DEFAULT_DOWNLOAD_PATH`, `QUALITY_LABELS`). No changes.
- `tiddl_gui/runner.py` — `DownloadRunner` subprocess/thread/queue wrapper, including the hardening from the v1 final review (guaranteed `("done", ...)` signal, UTF-8-safe decoding, race-free `start()`, `taskkill /F /T` on cancel). No changes to its public interface; only a new consumer (the line-parsing layer) reads its `("line", str)` messages.
- `tiddl_gui/app.py` — replaced entirely by the new pywebview-based entry point (see Components). The Tkinter code is deleted, not kept as a fallback.

## New capability: profile + preview via `TidalApi`

`tiddl`'s own dependency stack ships a `TidalApi` class (`tiddl.api.TidalApi`) with `getPlaylist`, `getPlaylistItems`, `getAlbum`, `getAlbumItems`, `getTrack`, and a raw generic `fetch(model, endpoint, params)` method — all usable directly from Python, no subprocess needed. The cached login token lives in `~/tiddl.json` (`AuthConfig.token`, `user_id`, `country_code` — read via `tiddl.config.Config.fromFile()`).

Confirmed live during design: `GET https://api.tidal.com/v1/users/{user_id}` (using the cached token) returns `username` (the account email) and `countryCode`. No profile picture field is populated for this account — the profile card shows text only (email + country + a green "Connecté" badge), not an avatar.

New module `tiddl_gui/tiddl_api.py` wraps this:
- `get_profile() -> ProfileInfo` — dataclass with `email: str`, `country_code: str`. Raises a clear exception if no cached token exists (not logged in) or the token is expired (caller should prompt re-login).
- `get_preview(url: str) -> list[TrackInfo]` — parses the URL to determine resource type (track/album/playlist/artist — same detection tiddl's own CLI does) and resource ID, calls the matching `TidalApi` getter, and returns a flat list of `TrackInfo` dataclasses: `title: str`, `artist: str`, `duration_seconds: int`. For an album or playlist URL this is the full track listing; for a single track URL it's a one-item list.

Both functions are pure with respect to the GUI (no widget/JS calls) — testable by mocking the `TidalApi` instance or the HTTP layer, following the same pattern as `commands.py`.

## New capability: live line parsing for track-level status

`tiddl`'s subprocess output has three recognizable per-track line shapes (confirmed from real runs in this session):
- Downloaded: `'Track Title' • 123.45 Mbps • 9.87 MB`
- Skipped (already exists): `Item 'Track Title' skipped - exists`
- Any other line is either a header/info line or an error — treated as "unstructured" and only shown in the raw log, not matched to a track.

New module `tiddl_gui/progress.py`:
- `parse_track_line(line: str) -> TrackEvent | None` — pure function, returns a `TrackEvent(title: str, status: Literal["downloaded", "skipped"])` if the line matches one of the two known shapes, else `None`.
- Matching a `TrackEvent.title` back to a previewed `TrackInfo` is done by exact string equality after a simple normalize (strip, casefold) — the only signal available from tiddl's output. Duplicate track titles within the same playlist are a known, accepted limitation: they'll all be marked together when either's line appears. This is not solvable without a different data source, so it's not being engineered around further.

This module is pure and unit-testable — no subprocess, no I/O.

## Components

**`tiddl_gui/tiddl_api.py`** (new) — `get_profile()`, `get_preview(url)`, dataclasses `ProfileInfo`, `TrackInfo`. Depends on `tiddl`'s own installed package (already a dependency of the sibling `tiddl` venv — see Global Constraints for the exact import path setup needed since `tiddl-gui` has its own separate venv).

**`tiddl_gui/progress.py`** (new) — `parse_track_line(line)`, dataclass `TrackEvent`.

**`tiddl_gui/app.py`** (rewritten) — pywebview entry point. A Python `Api` class exposed to JS via `pywebview.create_window(..., js_api=api)`, with methods: `get_profile()`, `get_preview(url)`, `start_favorites(quality, path)`, `start_url(url, quality, path)`, `cancel()`, `open_folder(path)`, `browse_folder()`, `pick_default_path()`. Internally still owns one `DownloadRunner` and a background poll (pywebview doesn't need Tkinter's `root.after` — a `threading.Timer`-based poll or a dedicated polling thread that calls back into JS via `window.evaluate_js(...)` is used instead; exact mechanism decided at implementation time based on pywebview's callback threading rules, documented inline).

**`tiddl_gui/web/`** (new directory) — static frontend: `index.html`, `style.css` (dark theme), `app.js` (calls `window.pywebview.api.*`, renders sidebar/profile card/preview list/status banner/collapsible log).

## Data flow

1. App launch → `Api.get_profile()` called from JS on load. If it raises (not logged in), sidebar shows only "Se connecter"; profile card hidden.
2. User clicks "Se connecter" → same `build_login_command()` + `DownloadRunner` flow as v1, output streamed to the (collapsed) log; on success, JS re-calls `get_profile()` to populate the card.
3. User pastes a URL → JS debounces input, calls `Api.get_preview(url)` → renders the track list with all rows in "pending" state.
4. User clicks "Télécharger ce lien" (or "Télécharger mes favoris", which has no preview step since favorites aren't a single resource URL) → `DownloadRunner.start(command)` as before.
5. Each `("line", str)` from the queue is passed through `parse_track_line`; matched lines update the corresponding row's status client-side; the status banner aggregates counts ("X nouvelles, Y déjà présentes, Z restantes"). Unmatched lines still append to the (collapsed) raw log.
6. On `("done", code)` — same success/error/cancel distinction as v1 (guaranteed exactly once, cancel-vs-error flag) — the banner shows a final summary instead of a popup.

## Error handling

- `get_profile()` / `get_preview()` failures (network error, expired token, invalid URL) surface as an inline error message in the relevant UI region — not a popup, consistent with the "real status messages on screen" requirement — and never crash the app.
- All `runner.py`-level hardening from v1 (guaranteed done-signal, UTF-8 decoding, race-free start, full process-tree kill on cancel) is unchanged and still the safety net under this new UI layer.

## Testing

- `tiddl_gui/tiddl_api.py` — unit tests mocking the HTTP/`TidalApi` layer (no real network calls in tests): `get_profile()` returns expected `ProfileInfo` on a valid response, raises on missing/expired token; `get_preview()` correctly dispatches by URL shape (track/album/playlist) and flattens results into `TrackInfo` list.
- `tiddl_gui/progress.py` — unit tests for `parse_track_line()`: matches the two known line shapes exactly, returns `None` for headers/unrelated lines, handles titles containing apostrophes or the `•` separator itself without breaking the match.
- `tiddl_gui/app.py` and `tiddl_gui/web/*` — no automated tests, manual verification only (same policy as v1's `app.py`), since this is UI wiring and real browser/webview rendering.
- `tiddl_gui/commands.py` and `tiddl_gui/runner.py` — existing 9 tests carry over unchanged, still the regression net for the subprocess layer.

## Hors scope (explicitly excluded)

- Profile picture / avatar — confirmed unavailable from the Tidal API for this account; not pursued further.
- Byte-accurate per-file progress bars — track-level pending/downloaded/skipped status is the agreed granularity; `tiddl`'s own output doesn't expose byte-level progress per file mid-download.
- Disambiguating duplicate track titles within one playlist for status matching — accepted limitation (see progress.py section).
- Multi-account support, playlist editing, or any Tidal write operations — this remains a read/download-only tool.
- Packaging as a distributable `.exe` (PyInstaller) — noted as a later step, not part of this implementation plan; the deliverable here is a working `python main.py`-launched pywebview app.

## Open questions resolved during design

- Whether `tiddl` already supports incremental "skip existing" downloads: **yes**, confirmed in `tiddl/cli/download/__init__.py:332-344` — no backend change needed, only surfacing it in the UI.
- Whether a Tidal profile picture is available: **no**, confirmed via a live authenticated call to `users/{id}`; the profile card is text-only.
