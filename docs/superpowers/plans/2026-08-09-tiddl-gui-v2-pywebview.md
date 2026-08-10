# tiddl-gui v2 (pywebview) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Tkinter GUI with a dark-themed, sidebar-based `pywebview` app: a profile card showing who's connected, an instant track-list preview when a Tidal link is pasted, per-track download/skip status during a run, and a plain-language status banner as the primary feedback — with the raw log collapsed by default.

**Architecture:** `commands.py` and `runner.py` are reused unchanged. Two new pure modules — `tiddl_api.py` (talks to Tidal's HTTP API directly using `tiddl`'s own `TidalApi` client and cached token) and `progress.py` (parses `tiddl`'s per-track output lines) — are unit tested the same way `commands.py`/`runner.py` were. `app.py` is rewritten as a pywebview `Api` class exposed to a static HTML/CSS/JS frontend in `tiddl_gui/web/`; a background thread (started via `webview.start(api.poll_loop, window)`) drains the runner's queue and pushes events into the page with `window.evaluate_js(...)`.

**Tech Stack:** Python 3.12, `pywebview` 6.2.1 (confirmed working on this machine — launches, exposes `js_api`, and `evaluate_js` from a background thread all verified live during design), `tiddl` 3.4.4 (installed as a normal dependency of this project's own venv, reused for its `TidalApi`/`Config`/`TidalResource` classes), `requests`. Frontend: vanilla HTML/CSS/JS, no framework.

## Global Constraints

- Target platform: Windows only.
- `tiddl_gui/commands.py` and `tiddl_gui/runner.py` are NOT modified by this plan — reused exactly as merged in the v1 branch (hardcoded `TIDDL_EXE`, `DEFAULT_DOWNLOAD_PATH`, `QUALITY_LABELS = ["Normal", "High", "Master"]`, single-concurrent-download guard, guaranteed done-signal, UTF-8-safe decoding, `taskkill /F /T` on cancel).
- Only one download may run at a time (enforced by the unchanged `DownloadRunner`).
- The profile card shows text only (email + country code) — no avatar. Confirmed live during design: Tidal's `users/{id}` endpoint has no populated picture field for this account.
- The "only download what's missing" behavior is already native to `tiddl` (confirmed in its own `cli/download/__init__.py:332-344`, which skips files matching an existing filename and logs `Item 'X' skipped - exists`). This plan does not add that behavior — it only surfaces it in the UI by parsing that exact log line shape.
- Duplicate track titles within one playlist are an accepted, unresolved limitation of matching preview rows to log lines by title — not engineered around further.
- `tiddl_gui/app.py` and everything under `tiddl_gui/web/` have NO automated tests — verified manually only, per the same policy as v1. `tiddl_api.py` and `progress.py` are pure modules and MUST have automated tests.
- Packaging as a distributable `.exe` (PyInstaller) is out of scope for this plan.

---

### Task 1: Add runtime dependencies

**Files:**
- Create: `D:\Vibe Coding\tiddl-gui\requirements.txt`

**Interfaces:**
- Produces: nothing importable — this task only makes `webview`, `tiddl`, and `requests` available in the project's venv for Tasks 2-5 to import.

- [ ] **Step 1: Create `requirements.txt`**

`D:\Vibe Coding\tiddl-gui\requirements.txt`:
```
tiddl==3.4.4
pywebview==6.2.1
requests
```

- [ ] **Step 2: Install into the project's venv**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pip.exe" install -r "D:\Vibe Coding\tiddl-gui\requirements.txt"
```
Expected: successful install, ending with a line like `Successfully installed ... pywebview-6.2.1 ... tiddl-3.4.4 ...`

- [ ] **Step 3: Verify the imports this plan depends on actually resolve**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\python.exe" -c "import webview; from tiddl.api import TidalApi; from tiddl.config import Config; from tiddl.utils import TidalResource; print('imports ok')"
```
Expected: `imports ok`

- [ ] **Step 4: Confirm the existing test suite still passes (new dependencies must not break anything)**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests" -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add requirements.txt
git commit -m "chore: add pywebview, tiddl, and requests as runtime dependencies"
```

---

### Task 2: `tiddl_api.py` — profile and playlist/album/track preview

**Files:**
- Create: `D:\Vibe Coding\tiddl-gui\tiddl_gui\tiddl_api.py`
- Test: `D:\Vibe Coding\tiddl-gui\tests\test_tiddl_api.py`

**Interfaces:**
- Consumes: `tiddl.api.TidalApi`, `tiddl.config.Config`, `tiddl.utils.TidalResource` (from the `tiddl` package installed in Task 1), and the `requests` package.
- Produces (used by Task 5's `app.py`):
  - `class NotLoggedInError(Exception)`
  - `@dataclass ProfileInfo` — fields `email: str`, `country_code: str`
  - `@dataclass TrackInfo` — fields `title: str`, `artist: str`, `duration_seconds: int`
  - `get_profile() -> ProfileInfo` — raises `NotLoggedInError` if no cached token or the profile fetch fails
  - `get_preview(url: str) -> list[TrackInfo]` — raises `ValueError` for an unsupported resource type (e.g. artist, video)

- [ ] **Step 1: Write the failing tests**

`D:\Vibe Coding\tiddl-gui\tests\test_tiddl_api.py`:
```python
from types import SimpleNamespace

import pytest

from tiddl_gui import tiddl_api


class FakeAuth:
    def __init__(self, token="tok", user_id="123", country_code="CA"):
        self.token = token
        self.user_id = user_id
        self.country_code = country_code


class FakeConfig:
    def __init__(self, auth):
        self.auth = auth

    @classmethod
    def fromFile(cls):
        return cls(FakeAuth())


class FakeConfigNoAuth:
    def __init__(self):
        self.auth = FakeAuth(token="", user_id="")

    @classmethod
    def fromFile(cls):
        return cls()


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def test_get_profile_returns_profile_info(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    def fake_get(url, headers, timeout):
        assert "123" in url
        assert headers["Authorization"] == "Bearer tok"
        return FakeResponse(200, {"username": "me@example.com", "countryCode": "CA"})

    monkeypatch.setattr(tiddl_api.requests, "get", fake_get)

    profile = tiddl_api.get_profile()

    assert profile.email == "me@example.com"
    assert profile.country_code == "CA"


def test_get_profile_raises_when_not_logged_in(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfigNoAuth)

    with pytest.raises(tiddl_api.NotLoggedInError):
        tiddl_api.get_profile()


def test_get_profile_raises_on_bad_status(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)
    monkeypatch.setattr(
        tiddl_api.requests, "get", lambda url, headers, timeout: FakeResponse(401, {})
    )

    with pytest.raises(tiddl_api.NotLoggedInError):
        tiddl_api.get_profile()


def _track(title, artist_name, duration):
    return SimpleNamespace(
        title=title,
        duration=duration,
        artist=SimpleNamespace(name=artist_name),
        artists=[SimpleNamespace(name=artist_name)],
    )


def test_get_preview_for_a_single_track(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

        def getTrack(self, track_id):
            assert track_id == "111"
            return _track("Solo Song", "Solo Artist", 200)

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/track/111")

    assert tracks == [
        tiddl_api.TrackInfo(title="Solo Song", artist="Solo Artist", duration_seconds=200)
    ]


def test_get_preview_for_a_playlist_filters_out_videos(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    track_entry = SimpleNamespace(type="track", item=_track("Track One", "Artist A", 180))
    video_entry = SimpleNamespace(type="video", item=SimpleNamespace(title="A Video"))

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

        def getPlaylistItems(self, playlist_id):
            assert playlist_id == "abc-123"
            return SimpleNamespace(items=[track_entry, video_entry])

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/playlist/abc-123")

    assert tracks == [
        tiddl_api.TrackInfo(title="Track One", artist="Artist A", duration_seconds=180)
    ]


def test_get_preview_for_an_album(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    track_entry = SimpleNamespace(type="track", item=_track("Album Track", "Artist B", 210))

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

        def getAlbumItems(self, album_id):
            assert album_id == "999"
            return SimpleNamespace(items=[track_entry])

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/album/999")

    assert tracks == [
        tiddl_api.TrackInfo(title="Album Track", artist="Artist B", duration_seconds=210)
    ]


def test_get_preview_falls_back_to_artists_list_when_artist_is_none(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    track = SimpleNamespace(
        title="No Primary Artist",
        duration=150,
        artist=None,
        artists=[SimpleNamespace(name="Featured Artist")],
    )

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

        def getTrack(self, track_id):
            return track

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/track/222")

    assert tracks[0].artist == "Featured Artist"


def test_get_preview_rejects_unsupported_resource_type(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    with pytest.raises(ValueError):
        tiddl_api.get_preview("https://tidal.com/browse/artist/555")
```

- [ ] **Step 2: Run tests to verify they fail**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests\test_tiddl_api.py" -v
```
Expected: `ModuleNotFoundError: No module named 'tiddl_gui.tiddl_api'`

- [ ] **Step 3: Write the implementation**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\tiddl_api.py`:
```python
"""Fetches Tidal profile info and playlist/album/track previews using
tiddl's own TidalApi client and cached login token.

Read-only, no subprocess calls — this module talks to Tidal's HTTP API
directly, reusing the same ~/tiddl.json token the tiddl CLI already
writes on login.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests
from tiddl.api import TidalApi
from tiddl.config import Config
from tiddl.utils import TidalResource


class NotLoggedInError(Exception):
    pass


@dataclass
class ProfileInfo:
    email: str
    country_code: str


@dataclass
class TrackInfo:
    title: str
    artist: str
    duration_seconds: int


def _load_auth():
    config = Config.fromFile()
    if not config.auth.token or not config.auth.user_id:
        raise NotLoggedInError("No cached Tidal login found. Log in first.")
    return config.auth


def get_profile() -> ProfileInfo:
    auth = _load_auth()
    headers = {"Authorization": f"Bearer {auth.token}", "Accept": "application/json"}
    response = requests.get(
        f"https://api.tidal.com/v1/users/{auth.user_id}", headers=headers, timeout=10
    )
    if response.status_code != 200:
        raise NotLoggedInError(f"Could not fetch profile (status {response.status_code}).")
    data = response.json()
    return ProfileInfo(email=data["username"], country_code=data["countryCode"])


def _api() -> TidalApi:
    auth = _load_auth()
    return TidalApi(token=auth.token, user_id=auth.user_id, country_code=auth.country_code)


def _track_info_from_item(item) -> TrackInfo:
    artist_name = item.artist.name if item.artist else (
        item.artists[0].name if item.artists else ""
    )
    return TrackInfo(title=item.title, artist=artist_name, duration_seconds=item.duration)


def get_preview(url: str) -> list[TrackInfo]:
    resource = TidalResource.fromString(url)
    api = _api()

    if resource.type == "track":
        track = api.getTrack(resource.id)
        return [_track_info_from_item(track)]

    if resource.type == "album":
        album_items = api.getAlbumItems(resource.id)
        return [
            _track_info_from_item(entry.item)
            for entry in album_items.items
            if entry.type == "track"
        ]

    if resource.type == "playlist":
        playlist_items = api.getPlaylistItems(resource.id)
        return [
            _track_info_from_item(entry.item)
            for entry in playlist_items.items
            if entry.type == "track"
        ]

    raise ValueError(f"Preview not supported for resource type: {resource.type!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests\test_tiddl_api.py" -v
```
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add tiddl_gui/tiddl_api.py tests/test_tiddl_api.py
git commit -m "feat: add Tidal profile and playlist/album/track preview fetching"
```

---

### Task 3: `progress.py` — parse per-track lines from tiddl's output

**Files:**
- Create: `D:\Vibe Coding\tiddl-gui\tiddl_gui\progress.py`
- Test: `D:\Vibe Coding\tiddl-gui\tests\test_progress.py`

**Interfaces:**
- Consumes: nothing (pure module, stdlib `re` and `dataclasses` only).
- Produces (used by Task 5's `app.py`):
  - `@dataclass TrackEvent` — fields `title: str`, `status: Literal["downloaded", "skipped"]`
  - `parse_track_line(line: str) -> TrackEvent | None`

- [ ] **Step 1: Write the failing tests**

`D:\Vibe Coding\tiddl-gui\tests\test_progress.py`:
```python
from tiddl_gui.progress import TrackEvent, parse_track_line


def test_parses_a_downloaded_line_with_single_quoted_title():
    event = parse_track_line("'Georgia' \u2022 87.16 Mbps \u2022 8.83 MB")
    assert event == TrackEvent(title="Georgia", status="downloaded")


def test_parses_a_downloaded_line_with_double_quoted_title_containing_apostrophe():
    line = "\"Don't You Give Up On Me Yet\" \u2022 77.93 Mbps \u2022 7.55 MB"
    event = parse_track_line(line)
    assert event == TrackEvent(title="Don't You Give Up On Me Yet", status="downloaded")


def test_parses_a_skipped_line():
    event = parse_track_line("Item 'Georgia' skipped - exists")
    assert event == TrackEvent(title="Georgia", status="skipped")


def test_parses_a_skipped_line_with_double_quoted_title():
    line = "Item \"Don't You Give Up On Me Yet\" skipped - exists"
    event = parse_track_line(line)
    assert event == TrackEvent(title="Don't You Give Up On Me Yet", status="skipped")


def test_returns_none_for_unrelated_lines():
    assert parse_track_line("[INFO] Starting login process...") is None
    assert parse_track_line("") is None
    assert parse_track_line("[termine, code 0]") is None
```

Note: `\u2022` is the bullet character `•` that appears literally in `tiddl`'s real output (e.g. `'Georgia' • 87.16 Mbps • 8.83 MB`).

- [ ] **Step 2: Run tests to verify they fail**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests\test_progress.py" -v
```
Expected: `ModuleNotFoundError: No module named 'tiddl_gui.progress'`

- [ ] **Step 3: Write the implementation**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\progress.py`:
```python
"""Parses tiddl's per-track subprocess output lines into structured
events, so the GUI can mark preview rows as downloaded/skipped without
requiring the user to read the raw log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

_DOWNLOADED_RE = re.compile(r"^(['\"])(.*)\1 \u2022 [\d.]+ Mbps \u2022 [\d.]+ MB$")
_SKIPPED_RE = re.compile(r"^Item (['\"])(.*)\1 skipped - exists$")


@dataclass
class TrackEvent:
    title: str
    status: Literal["downloaded", "skipped"]


def parse_track_line(line: str) -> Optional[TrackEvent]:
    match = _DOWNLOADED_RE.match(line)
    if match:
        return TrackEvent(title=match.group(2), status="downloaded")

    match = _SKIPPED_RE.match(line)
    if match:
        return TrackEvent(title=match.group(2), status="skipped")

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests\test_progress.py" -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add tiddl_gui/progress.py tests/test_progress.py
git commit -m "feat: parse tiddl's per-track output lines into structured events"
```

---

### Task 4: Frontend static files (HTML/CSS/JS)

**Files:**
- Create: `D:\Vibe Coding\tiddl-gui\tiddl_gui\web\index.html`
- Create: `D:\Vibe Coding\tiddl-gui\tiddl_gui\web\style.css`
- Create: `D:\Vibe Coding\tiddl-gui\tiddl_gui\web\app.js`

**Interfaces:**
- Consumes (at runtime, once Task 5 wires up the window): `window.pywebview.api.*` methods — `get_defaults()`, `get_profile()`, `get_preview(url)`, `start_login()`, `start_favorites(quality_label, download_path)`, `start_url(url, quality_label, download_path)`, `cancel()`, `open_folder(path)`, `browse_folder(current_path)`.
- Produces: `window.onTiddlEvent(message)` — a global function Task 5's background poll loop calls via `evaluate_js` with `{"type": "line", "text": str, "track_event": {"title": str, "status": str} | null}` or `{"type": "done", "code": int, "kind": "login"|"download", "cancelled": bool}`.
- No automated tests for this task (per Global Constraints) — verified manually in Task 5 once `app.py` can actually open the window.

- [ ] **Step 1: Write `index.html`**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\web\index.html`:
```html
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Tiddl</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="profile-card" id="profile-card">
      <button id="login-button" class="sidebar-button">Se connecter</button>
      <div id="profile-info" class="profile-info hidden">
        <span class="status-dot"></span>
        <div>
          <div id="profile-email" class="profile-email"></div>
          <div id="profile-country" class="profile-country"></div>
        </div>
      </div>
    </div>
    <nav class="nav">
      <button id="nav-favorites" class="nav-button active">Favoris</button>
      <button id="nav-link" class="nav-button">Lien</button>
    </nav>
  </aside>

  <main class="main">
    <section id="panel-favorites" class="panel">
      <h1>Telecharger mes favoris</h1>
      <p class="muted">Telecharge toutes tes pistes, albums, artistes et playlists favoris.</p>
      <div class="controls">
        <label>Qualite
          <select id="favorites-quality"></select>
        </label>
        <label>Dossier
          <div class="path-row">
            <input id="favorites-path" type="text">
            <button id="favorites-browse">Parcourir...</button>
          </div>
        </label>
        <button id="favorites-start" class="primary">Telecharger mes favoris</button>
      </div>
    </section>

    <section id="panel-link" class="panel hidden">
      <h1>Telecharger un lien</h1>
      <div class="controls">
        <label>Lien Tidal
          <input id="link-url" type="text" placeholder="https://tidal.com/browse/playlist/...">
        </label>
        <label>Qualite
          <select id="link-quality"></select>
        </label>
        <label>Dossier
          <div class="path-row">
            <input id="link-path" type="text">
            <button id="link-browse">Parcourir...</button>
          </div>
        </label>
        <button id="link-start" class="primary">Telecharger ce lien</button>
      </div>

      <div id="preview-list" class="preview-list hidden"></div>
    </section>

    <div id="status-banner" class="status-banner hidden">
      <span id="status-text"></span>
      <button id="cancel-button" class="hidden">Annuler</button>
      <button id="open-folder-button" class="hidden">Ouvrir le dossier</button>
    </div>

    <details id="log-details" class="log-details">
      <summary>Voir les details</summary>
      <pre id="log-output"></pre>
    </details>
  </main>
</div>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `style.css`**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\web\style.css`:
```css
:root {
  --bg: #121212;
  --panel: #1e1e1e;
  --sidebar: #181818;
  --text: #e6e6e6;
  --muted: #9a9a9a;
  --accent: #1db954;
  --danger: #e74c3c;
  --border: #2a2a2a;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", system-ui, sans-serif;
}

.app { display: flex; height: 100vh; }

.sidebar {
  width: 220px;
  background: var(--sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 24px;
}

.sidebar-button, .nav-button {
  width: 100%;
  padding: 10px;
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  margin-bottom: 8px;
}

.nav-button.active { background: var(--accent); color: #0a0a0a; font-weight: 600; }

.profile-info { display: flex; align-items: center; gap: 8px; }
.hidden { display: none !important; }

.status-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--accent); flex-shrink: 0;
}

.profile-email { font-weight: 600; font-size: 13px; }
.profile-country { color: var(--muted); font-size: 12px; }

.main { flex: 1; padding: 24px; overflow-y: auto; }

.panel h1 { font-size: 20px; margin-bottom: 4px; }
.muted { color: var(--muted); font-size: 13px; }

.controls { display: flex; flex-direction: column; gap: 12px; max-width: 480px; margin-top: 16px; }
.controls label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); }

input[type="text"], select {
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  font-size: 14px;
}

.path-row { display: flex; gap: 8px; }
.path-row input { flex: 1; }

button.primary {
  background: var(--accent);
  color: #0a0a0a;
  border: none;
  border-radius: 6px;
  padding: 10px;
  font-weight: 600;
  cursor: pointer;
}

button { font-family: inherit; }

.preview-list {
  margin-top: 20px;
  max-width: 480px;
  border: 1px solid var(--border);
  border-radius: 6px;
  max-height: 300px;
  overflow-y: auto;
}

.track-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.track-row:last-child { border-bottom: none; }
.track-status { color: var(--muted); }
.track-status.downloaded { color: var(--accent); }
.track-status.skipped { color: #f0ad4e; }

.status-banner {
  margin-top: 20px;
  padding: 12px 16px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 480px;
}
.status-banner.error { border-color: var(--danger); }

.log-details { margin-top: 24px; max-width: 640px; }
.log-details summary { cursor: pointer; color: var(--muted); font-size: 13px; }
#log-output {
  background: #0a0a0a;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  max-height: 240px;
  overflow-y: auto;
  font-size: 12px;
  white-space: pre-wrap;
}
```

- [ ] **Step 3: Write `app.js`**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\web\app.js`:
```javascript
const state = {
  qualityLabels: [],
  defaultPath: "",
  previewTracks: [],
  running: false,
};

function el(id) { return document.getElementById(id); }

function populateQualitySelect(select) {
  select.innerHTML = "";
  for (const label of state.qualityLabels) {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    if (label === "High") option.selected = true;
    select.appendChild(option);
  }
}

function setBanner(text, kind) {
  const banner = el("status-banner");
  banner.classList.remove("hidden", "error");
  if (kind === "error") banner.classList.add("error");
  el("status-text").textContent = text;
}

function hideBanner() {
  el("status-banner").classList.add("hidden");
  el("cancel-button").classList.add("hidden");
  el("open-folder-button").classList.add("hidden");
}

function appendLog(text) {
  const out = el("log-output");
  out.textContent += text + "\n";
  out.scrollTop = out.scrollHeight;
}

function renderPreview(tracks) {
  state.previewTracks = tracks;
  const container = el("preview-list");
  container.classList.remove("hidden");
  container.innerHTML = "";
  for (const track of tracks) {
    const row = document.createElement("div");
    row.className = "track-row";
    row.dataset.title = track.title;
    row.innerHTML = `<span>${track.artist} - ${track.title}</span><span class="track-status">en attente</span>`;
    container.appendChild(row);
  }
}

function markTrack(title, status) {
  const rows = document.querySelectorAll("#preview-list .track-row");
  for (const row of rows) {
    if (row.dataset.title === title) {
      const statusEl = row.querySelector(".track-status");
      statusEl.textContent = status === "downloaded" ? "telechargee" : "deja presente";
      statusEl.className = "track-status " + status;
      return;
    }
  }
}

function setRunning(running) {
  state.running = running;
  el("favorites-start").disabled = running;
  el("link-start").disabled = running;
  el("login-button").disabled = running;
  el("cancel-button").classList.toggle("hidden", !running);
}

async function loadDefaults() {
  const defaults = await window.pywebview.api.get_defaults();
  state.qualityLabels = defaults.quality_labels;
  state.defaultPath = defaults.default_path;
  populateQualitySelect(el("favorites-quality"));
  populateQualitySelect(el("link-quality"));
  el("favorites-path").value = state.defaultPath;
  el("link-path").value = state.defaultPath;
}

async function refreshProfile() {
  const result = await window.pywebview.api.get_profile();
  if (result.ok) {
    el("login-button").classList.add("hidden");
    el("profile-info").classList.remove("hidden");
    el("profile-email").textContent = result.email;
    el("profile-country").textContent = result.country_code;
  } else {
    el("login-button").classList.remove("hidden");
    el("profile-info").classList.add("hidden");
  }
}

function switchPanel(name) {
  el("panel-favorites").classList.toggle("hidden", name !== "favorites");
  el("panel-link").classList.toggle("hidden", name !== "link");
  el("nav-favorites").classList.toggle("active", name === "favorites");
  el("nav-link").classList.toggle("active", name === "link");
}

let previewDebounce = null;

function onLinkInput() {
  clearTimeout(previewDebounce);
  const url = el("link-url").value.trim();
  if (!url) {
    el("preview-list").classList.add("hidden");
    return;
  }
  previewDebounce = setTimeout(async () => {
    const result = await window.pywebview.api.get_preview(url);
    if (result.ok) {
      renderPreview(result.tracks);
    } else {
      el("preview-list").classList.add("hidden");
    }
  }, 500);
}

async function startFavorites() {
  hideBanner();
  const result = await window.pywebview.api.start_favorites(
    el("favorites-quality").value,
    el("favorites-path").value
  );
  if (result.ok) {
    setRunning(true);
    setBanner("Telechargement en cours...", "info");
  } else {
    setBanner(result.error, "error");
  }
}

async function startLink() {
  hideBanner();
  const url = el("link-url").value.trim();
  if (!url) {
    setBanner("Colle un lien Tidal avant de telecharger.", "error");
    return;
  }
  const result = await window.pywebview.api.start_url(
    url,
    el("link-quality").value,
    el("link-path").value
  );
  if (result.ok) {
    setRunning(true);
    setBanner("Telechargement en cours...", "info");
  } else {
    setBanner(result.error, "error");
  }
}

async function browsePath(inputId) {
  const result = await window.pywebview.api.browse_folder(el(inputId).value);
  if (result.ok) {
    el(inputId).value = result.path;
  }
}

window.onTiddlEvent = function (message) {
  if (message.type === "line") {
    appendLog(message.text);
    if (message.track_event) {
      markTrack(message.track_event.title, message.track_event.status);
    }
    return;
  }

  setRunning(false);
  appendLog(`[termine, code ${message.code}]`);

  if (message.code === 0) {
    if (message.kind === "login") {
      refreshProfile();
      hideBanner();
    } else {
      setBanner("Telechargement termine avec succes.", "success");
      el("open-folder-button").classList.remove("hidden");
    }
  } else if (message.cancelled) {
    setBanner("Telechargement annule.", "info");
  } else {
    setBanner(`Echec (code ${message.code}). Voir les details.`, "error");
  }
};

window.addEventListener("pywebviewready", async () => {
  await loadDefaults();
  await refreshProfile();

  el("login-button").addEventListener("click", async () => {
    hideBanner();
    await window.pywebview.api.start_login();
    setRunning(true);
    setBanner("Connexion en cours, regarde le lien dans les details...", "info");
  });

  el("nav-favorites").addEventListener("click", () => switchPanel("favorites"));
  el("nav-link").addEventListener("click", () => switchPanel("link"));

  el("favorites-start").addEventListener("click", startFavorites);
  el("link-start").addEventListener("click", startLink);
  el("favorites-browse").addEventListener("click", () => browsePath("favorites-path"));
  el("link-browse").addEventListener("click", () => browsePath("link-path"));
  el("link-url").addEventListener("input", onLinkInput);

  el("cancel-button").addEventListener("click", async () => {
    await window.pywebview.api.cancel();
  });

  el("open-folder-button").addEventListener("click", async () => {
    const path = el("panel-favorites").classList.contains("hidden")
      ? el("link-path").value
      : el("favorites-path").value;
    await window.pywebview.api.open_folder(path);
  });
});
```

- [ ] **Step 4: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add tiddl_gui/web/index.html tiddl_gui/web/style.css tiddl_gui/web/app.js
git commit -m "feat: add dark sidebar frontend (HTML/CSS/JS) for tiddl-gui v2"
```

(No test-run step here — this task has no automated tests per Global Constraints; the frontend is exercised for the first time in Task 5, once `app.py` can actually open a window pointing at it.)

---

### Task 5: Rewrite `app.py` as the pywebview entry point

**Files:**
- Modify: `D:\Vibe Coding\tiddl-gui\tiddl_gui\app.py` (full rewrite — delete all existing Tkinter code, replace with the code below)

**Interfaces:**
- Consumes:
  - From `commands.py`: `DEFAULT_DOWNLOAD_PATH`, `QUALITY_LABELS`, `build_favorites_command`, `build_login_command`, `build_url_command`
  - From `runner.py`: `DownloadRunner(output_queue)`, `.is_running()`, `.start(command)`, `.cancel()`
  - From `tiddl_api.py` (Task 2): `NotLoggedInError`, `get_preview`, `get_profile`
  - From `progress.py` (Task 3): `parse_track_line`
  - From `web/` (Task 4): `index.html`, `style.css`, `app.js` — loaded as the window's URL; `app.js` calls every `Api` method below and expects `window.onTiddlEvent(message)` to exist as a global.
- Produces: `tiddl_gui.app.main() -> None` — same entry point name as v1, still called by the unmodified `main.py`.

- [ ] **Step 1: Write the new `app.py`**

`D:\Vibe Coding\tiddl-gui\tiddl_gui\app.py` (replace the entire file):
```python
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
```

- [ ] **Step 2: Launch the app and smoke-test it manually**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\python.exe" "D:\Vibe Coding\tiddl-gui\main.py"
```
Expected: a native window titled "Tiddl" opens on a dark background, with the sidebar (a "Se connecter" button or, if already logged in from v1's testing, a profile card with an email + country) and the "Favoris" panel showing the quality dropdown and destination path pre-filled with `C:\Users\BUREAU-ALEXIS\Music\Tiddl`. Close the window when done looking (or wait for it — nothing auto-closes, so close it manually via the window's close button).

- [ ] **Step 3: Run the full automated test suite to confirm nothing broke**

Run (PowerShell):
```
& "D:\Vibe Coding\tiddl-gui\.venv\Scripts\pytest.exe" "D:\Vibe Coding\tiddl-gui\tests" -v
```
Expected: `22 passed` (9 from `commands.py`/`runner.py`, 8 from `tiddl_api.py`, 5 from `progress.py`)

- [ ] **Step 4: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add tiddl_gui/app.py
git commit -m "feat: rewrite app.py as a pywebview window wiring the new modules together"
```

---

### Task 6: README update and manual end-to-end checklist

**Files:**
- Modify: `D:\Vibe Coding\tiddl-gui\README.md` (replace the "Run" section and the manual checklist; keep the "Requirements" and "Run the tests" sections, updating them if paths changed)

**Interfaces:**
- Consumes: nothing new — documents Tasks 1-5's output.
- Produces: nothing consumed by other tasks (final task).

- [ ] **Step 1: Rewrite `README.md`**

`D:\Vibe Coding\tiddl-gui\README.md` (replace the entire file):
```markdown
# Tiddl GUI

Dark, sidebar-based desktop app (built with `pywebview`) for the
[tiddl](https://pypi.org/project/tiddl/) Tidal downloader — connection
profile card, instant playlist/album preview, per-track download status,
and a plain-language status banner instead of a raw log.

## Requirements

- The `tiddl` CLI's cached login at `~/tiddl.json` (created by `tiddl auth
  login` — see the sibling `tiddl` project at
  `D:\Vibe Coding\tiddl\.venv\Scripts\tiddl.exe`, whose hardcoded path is
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
```

- [ ] **Step 2: Walk through the manual checklist above against the running app**

Run the app as in Task 5 Step 2, and go through checklist items 1-8 by hand.
Expected: each item behaves as described. Note any deviation before committing.

Note: items 1, 3, 4, 5, and 6 require a real Tidal account/browser session and
cannot be executed by an agent in a non-interactive environment — verify what's
mechanically checkable (item 2's preview rendering, item 7's folder-opening
code path, item 8's path field update) and leave the rest for the project
owner's own pass, exactly as was done for Task 5 of the v1 plan.

- [ ] **Step 3: Commit**

```bash
cd "/d/Vibe Coding/tiddl-gui"
git add README.md
git commit -m "docs: update README and manual test checklist for the pywebview rewrite"
```
