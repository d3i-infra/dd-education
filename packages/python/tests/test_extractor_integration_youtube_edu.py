"""Canary: the education YouTube entry over a single HTML Takeout zip (skips if absent).

The four ``youtube_*`` table ids are the entry's whole "registry" (the
tables ``YouTubeOnlyGoogleFlow`` filters ``GoogleFlow`` down to, per
``YOUTUBE_TABLE_PREFIX`` in ``education.py``); every one of them gets an
assertion here, individually, plus the mandatory lab-requirement ordering
(watch history first).
"""
import pytest
from extractor_integration_helpers import DiskPart, find_fixture
from port.helpers.archive_set import ArchiveSet
from port.platforms.education import YouTubeOnlyGoogleFlow

YOUTUBE_TABLE_IDS = ("youtube_watch_history", "youtube_search_history", "youtube_subscriptions", "youtube_comments")


@pytest.fixture(scope="module")
def result():
    f = find_fixture("youtube")
    if f is None:
        pytest.skip("No youtube_*.zip fixture in tests/ddp/")
    aset = ArchiveSet([DiskPart(f)])   # DiskPart: file-like part with .name/.size, from the helpers
    flow = YouTubeOnlyGoogleFlow("s")
    v = flow.validate_file(aset)
    assert v.get_status_code_id() == 0
    return flow.extract_data(aset, v)


def test_only_youtube_tables_present(result):
    ids = {t.id for t in result.tables}
    assert ids <= set(YOUTUBE_TABLE_IDS)
    assert all(not t.data_frame.empty for t in result.tables)


def test_watch_history_table_is_first(result):
    """Lab requirement: the watch-history table leads the YouTube menu entry."""
    assert result.tables[0].id == "youtube_watch_history"


@pytest.mark.parametrize("table_id", YOUTUBE_TABLE_IDS, ids=lambda t: t)
def test_every_youtube_table_present_and_not_empty(table_id, result):
    by_id = {t.id: t for t in result.tables}
    assert table_id in by_id, f"{table_id} missing from the YouTube menu entry's tables"
    assert not by_id[table_id].data_frame.empty


def test_watch_history_monthly_timeline_is_explicit():
    """Lab requirement: the watch-history area chart's dateFormat is
    explicitly 'month', not 'auto'."""
    from port.helpers.port_config_validator import read_config

    tables = read_config("google")["tables"]
    watch_history = next(t for t in tables if t["id"] == "youtube_watch_history")
    area = next(v for v in watch_history["visualizations"] if v["type"] == "area")
    assert area["group"]["dateFormat"] == "month"
