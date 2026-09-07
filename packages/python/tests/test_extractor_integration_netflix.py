"""Canary over a real Netflix export at tests/ddp/netflix_*.zip (skips if absent)."""
import pytest

from extractor_integration_helpers import find_fixture, make_reader
from port.platforms.netflix import DDP_CATEGORIES, extract_users, extraction


@pytest.fixture(scope="module")
def netflix_reader():
    fixture = find_fixture("netflix")
    if fixture is None:
        pytest.skip("No netflix_*.zip fixture found in tests/ddp/")
    return make_reader(fixture, DDP_CATEGORIES)


def test_every_table_non_empty_for_first_profile(netflix_reader):
    users = extract_users(netflix_reader)
    assert users
    result = extraction(netflix_reader, users[0])
    assert {t.id for t in result.tables} == {"netflix_ratings", "netflix_viewing_activity", "netflix_search_history"}
    assert all(not t.data_frame.empty for t in result.tables)
