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
        entries = _fetch_all_items(api.getAlbumItems, resource.id, limit=100)
        return [_track_info_from_item(e.item) for e in entries if e.type == "track"]

    if resource.type == "playlist":
        entries = _fetch_all_items(api.getPlaylistItems, resource.id, limit=50)
        return [_track_info_from_item(e.item) for e in entries if e.type == "track"]

    raise ValueError(f"Preview not supported for resource type: {resource.type!r}")


def _fetch_all_items(getter, resource_id: str, limit: int) -> list:
    entries = []
    offset = 0
    while True:
        page = getter(resource_id, limit=limit, offset=offset)
        entries.extend(page.items)
        if len(page.items) < limit:
            break
        offset += limit
    return entries
