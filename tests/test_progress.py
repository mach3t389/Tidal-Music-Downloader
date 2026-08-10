from tiddl_gui.progress import TrackEvent, parse_track_line


def test_parses_a_downloaded_line_with_single_quoted_title():
    event = parse_track_line("'Georgia' • 87.16 Mbps • 8.83 MB")
    assert event == TrackEvent(title="Georgia", status="downloaded")


def test_parses_a_downloaded_line_with_double_quoted_title_containing_apostrophe():
    line = "\"Don't You Give Up On Me Yet\" • 77.93 Mbps • 7.55 MB"
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
