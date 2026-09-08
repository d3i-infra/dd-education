"""Canary over a real ChatGPT export at tests/ddp/chatgpt_*.zip (skips if
absent). One ``ExtractorSpec`` per ``EXTRACTOR_REGISTRY`` entry, built
generically from the registry so a newly-registered extractor is picked up
automatically.
"""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms.chatgpt import DDP_CATEGORIES, EXTRACTOR_REGISTRY

#: Registry entries that legitimately return an empty DataFrame for the
#: 2026-08 test-account export — none currently.
EXPECTED_EMPTY: set[str] = set()


@pytest.fixture(scope="module")
def chatgpt_reader():
    fixture = find_fixture("chatgpt")
    if fixture is None:
        pytest.skip("No chatgpt_*.zip fixture found in tests/ddp/")
    return make_reader(fixture, DDP_CATEGORIES)


@pytest.mark.parametrize("name", list(EXTRACTOR_REGISTRY), ids=lambda n: n)
def test_extractor_not_empty(name, chatgpt_reader):
    if name in EXPECTED_EMPTY:
        pytest.skip(f"{name} is expected empty for this fixture — see EXPECTED_EMPTY")
    spec = ExtractorSpec(name=name, extractor=EXTRACTOR_REGISTRY[name])
    df = spec.run(chatgpt_reader)
    assert not df.empty, (
        f"{spec.name} returned an empty DataFrame — the extractor may have "
        "crashed, found no matching file, or the DDP format changed."
    )
