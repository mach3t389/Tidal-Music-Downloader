"""Parses tiddl's per-track subprocess output lines into structured
events, so the GUI can mark preview rows as downloaded/skipped without
requiring the user to read the raw log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

_DOWNLOADED_RE = re.compile(r"^(['\"])(.*)\1 • [\d.]+ Mbps • [\d.]+ MB$")
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
