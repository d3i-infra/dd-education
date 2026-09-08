"""Canary over a real LinkedIn export at tests/ddp/linkedin_*.zip (skips if
absent). One ``ExtractorSpec`` per ``EXTRACTOR_REGISTRY`` entry, built
generically from the registry so a newly-registered extractor is picked up
automatically.

The fixture on hand (``linkedin_basic_*.zip``) is LinkedIn's *basic* archive.
It lacks the search/reactions/comments/shares/ads-clicked files the
*complete* export adds — real absences on this fixture, not extractor
defects — so those registry entries stay in ``EXPECTED_EMPTY`` until
tests/ddp/linkedin_complete_*.zip exists.
"""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms import linkedin as L

#: Registry entries that legitimately return an empty DataFrame against the
#: basic-archive fixture: their source files ship only in LinkedIn's complete
#: export, which is not yet on disk (see module docstring).
EXPECTED_EMPTY = {
    "reactions_to_df",
    "comments_to_df",
    "shares_to_df",
    "search_queries_to_df",
    "ads_clicked_to_df",
    "member_follows_to_df",
}

SPECS = [ExtractorSpec(name=n, extractor=fn) for n, fn in L.EXTRACTOR_REGISTRY.items()]


@pytest.fixture(scope="module")
def reader():
    f = find_fixture("linkedin")
    if f is None:
        pytest.skip("No linkedin_*.zip fixture in tests/ddp/")
    return make_reader(f, L.DDP_CATEGORIES)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_extractor_not_empty(spec, reader):
    if spec.name in EXPECTED_EMPTY:
        pytest.skip(f"{spec.name} is expected empty for the basic-archive fixture — see EXPECTED_EMPTY")
    assert not spec.run(reader).empty
