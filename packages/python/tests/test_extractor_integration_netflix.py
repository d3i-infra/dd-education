"""Canary over a real Netflix export at tests/ddp/netflix_*.zip (skips if absent)."""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms.netflix import DDP_CATEGORIES, EXTRACTOR_REGISTRY, extract_users


@pytest.fixture(scope="module")
def netflix_reader():
    fixture = find_fixture("netflix")
    if fixture is None:
        pytest.skip("No netflix_*.zip fixture found in tests/ddp/")
    return make_reader(fixture, DDP_CATEGORIES)


@pytest.fixture(scope="module")
def first_user(netflix_reader):
    users = extract_users(netflix_reader)
    if not users:
        pytest.skip("No profiles found in Netflix fixture")
    return users[0]


def test_profiles_detected(netflix_reader):
    assert extract_users(netflix_reader)


@pytest.mark.parametrize("name", list(EXTRACTOR_REGISTRY), ids=lambda n: n)
def test_extractor_not_empty(name, netflix_reader, first_user):
    spec = ExtractorSpec(name=name, extractor=EXTRACTOR_REGISTRY[name], kwargs={"selected_user": first_user})
    assert not spec.run(netflix_reader).empty
