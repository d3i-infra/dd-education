"""Canary: the education YouTube entry over a single HTML Takeout zip (skips if absent)."""
import pytest
from extractor_integration_helpers import DiskPart, find_fixture
from port.helpers.archive_set import ArchiveSet
from port.platforms.education import YouTubeOnlyGoogleFlow


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


def test_only_youtube_tables_and_history_present(result):
    ids = {t.id for t in result.tables}
    assert ids <= {"youtube_watch_history", "youtube_search_history", "youtube_subscriptions", "youtube_comments"}
    assert "youtube_watch_history" in ids
    assert all(not t.data_frame.empty for t in result.tables)
