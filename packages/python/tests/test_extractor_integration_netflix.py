"""Canary over a real Netflix export at tests/ddp/netflix_*.zip (skips if absent).

Covers all ten ``EXTRACTOR_REGISTRY`` entries as of task 15a — the three
original usage extractors (ratings, viewing activity, search history) plus
the seven surprise extractors added by that task (clickstream, indicated
preferences, IP addresses, devices, account and billing, profile
demographics, My List). One ``ExtractorSpec`` per registry entry, built
generically from the registry so a newly-registered extractor is picked up
automatically.

``first_user`` is the first profile alphabetically on the fixture. Every
registry entry returns a non-empty frame for that profile on this fixture,
so ``EXPECTED_EMPTY`` is unused here — add it, with a reason, if a future
extractor is legitimately empty for this account (mirroring
``test_extractor_integration_facebook.py``'s ``EXPECTED_EMPTY_JSON``).
"""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms.netflix import DDP_CATEGORIES, EXTRACTOR_REGISTRY, extract_users

#: Registry entries that legitimately return an empty DataFrame for the
#: 2026-03 test-account export, rather than weakening the non-empty
#: assertion for the rest. Empty on this fixture — none currently.
EXPECTED_EMPTY: set[str] = set()


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
    if name in EXPECTED_EMPTY:
        pytest.skip(f"{name} is expected empty for this fixture — see EXPECTED_EMPTY")
    spec = ExtractorSpec(name=name, extractor=EXTRACTOR_REGISTRY[name], kwargs={"selected_user": first_user})
    assert not spec.run(netflix_reader).empty
