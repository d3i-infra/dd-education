"""Canary over a real WhatsApp export at tests/ddp/whatsapp_*.zip (skips if absent).

``test_all_timestamps_are_iso`` asserts the timestamp defect tracked for
Task 9 and is expected to FAIL until that parser fix lands.

WhatsApp extractors take ``(df, errors)`` rather than ``(reader, errors)``
(the chat file is pre-parsed once, see ``whatsapp.py``'s module docstring),
so ``test_extractor_not_empty`` runs each ``EXTRACTOR_REGISTRY`` entry
directly over the filtered chat DataFrame the real flow builds, rather than
going through ``ExtractorSpec``.
"""
import io
from collections import Counter

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


@pytest.fixture(scope="module")
def filtered_chat_df(chat_df):
    """The chat DataFrame the way ``WhatsAppFlow.extract_data`` hands it to
    ``extraction()``: empty rows dropped, then filtered to detected users."""
    df = W.remove_empty_chats(chat_df)
    users = W.extract_users(df)
    return W.keep_users(df, users)


def test_messages_parsed(chat_df):
    assert len(chat_df) > 100


def test_all_timestamps_are_iso(chat_df):
    bad = chat_df["date"].astype(str).str.contains("avonds|ochtends|middags|nachts|--")
    assert bad.sum() == 0, f"{bad.sum()} unparsed timestamps"


@pytest.mark.parametrize("name", list(W.EXTRACTOR_REGISTRY), ids=lambda n: n)
def test_extractor_not_empty(name, filtered_chat_df):
    errors: Counter = Counter()
    df = W.EXTRACTOR_REGISTRY[name](filtered_chat_df, errors)
    assert not df.empty
