"""Canary over a real WhatsApp export at tests/ddp/whatsapp_*.zip (skips if absent).

``test_all_timestamps_are_iso`` asserts the timestamp defect tracked for
Task 9 and is expected to FAIL until that parser fix lands.
"""
import io

import pytest

from extractor_integration_helpers import find_fixture
from port.platforms import whatsapp as W


@pytest.fixture(scope="module")
def chat_df():
    f = find_fixture("whatsapp")
    if f is None:
        pytest.skip("No whatsapp_*.zip fixture in tests/ddp/")
    with open(f, "rb") as fh:
        df = W.parse_chat(io.BytesIO(fh.read()))
    return df


def test_messages_parsed(chat_df):
    assert len(chat_df) > 100


def test_all_timestamps_are_iso(chat_df):
    bad = chat_df["date"].astype(str).str.contains("avonds|ochtends|middags|nachts|--")
    assert bad.sum() == 0, f"{bad.sum()} unparsed timestamps"
