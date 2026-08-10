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

        def getPlaylistItems(self, playlist_id, limit=50, offset=0):
            assert playlist_id == "abc-123"
            if offset == 0:
                return SimpleNamespace(items=[track_entry, video_entry])
            return SimpleNamespace(items=[])

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

        def getAlbumItems(self, album_id, limit=100, offset=0):
            assert album_id == "999"
            if offset == 0:
                return SimpleNamespace(items=[track_entry])
            return SimpleNamespace(items=[])

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/album/999")

    assert tracks == [
        tiddl_api.TrackInfo(title="Album Track", artist="Artist B", duration_seconds=210)
    ]


def test_get_preview_paginates_through_all_album_pages(monkeypatch):
    monkeypatch.setattr(tiddl_api, "Config", FakeConfig)

    page_one = [
        SimpleNamespace(type="track", item=_track(f"Track {i}", "Artist", 100))
        for i in range(100)
    ]
    page_two = [SimpleNamespace(type="track", item=_track("Track 100", "Artist", 100))]

    class FakeApi:
        def __init__(self, token, user_id, country_code):
            pass

        def getAlbumItems(self, album_id, limit=100, offset=0):
            assert album_id == "999"
            if offset == 0:
                return SimpleNamespace(items=page_one)
            return SimpleNamespace(items=page_two)

    monkeypatch.setattr(tiddl_api, "TidalApi", FakeApi)

    tracks = tiddl_api.get_preview("https://tidal.com/browse/album/999")

    assert len(tracks) == 101
    assert tracks[0].title == "Track 0"
    assert tracks[100].title == "Track 100"


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
