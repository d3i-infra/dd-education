"""Canary over a real LinkedIn export at tests/ddp/linkedin_*.zip (skips if absent).

The basic archive (``linkedin_basic_*.zip``) only yields company follows and
connections. The complete export adds ads_clicked, comments, shares,
reactions, search_queries, member_follows — extend SPECS when
tests/ddp/linkedin_complete_*.zip exists.
"""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms import linkedin as L

SPECS = [
    ExtractorSpec(name=n, extractor=getattr(L, n))
    for n in ("company_follows_to_df", "connections_to_df")
]


@pytest.fixture(scope="module")
def reader():
    f = find_fixture("linkedin")
    if f is None:
        pytest.skip("No linkedin_*.zip fixture in tests/ddp/")
    return make_reader(f, L.DDP_CATEGORIES)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_extractor_not_empty(spec, reader):
    assert not spec.run(reader).empty
