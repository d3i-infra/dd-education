"""Unit tests for the new ChatGPT extractor (task 15c), over a small
in-memory zip built from a synthetic ``user.json`` — no real names, emails,
or phone numbers anywhere in this file.

Built the same way ``test_netflix_extractors.py`` builds its in-memory zip: a
``ZipArchiveReader`` directly over a ``zipfile.ZipFile`` written to a
``io.BytesIO`` buffer, skipping the full ``DDPCategory`` validation pass that
``extractor_integration_helpers.make_reader`` additionally exercises.
"""
import io
import json
import zipfile
from collections import Counter

from port.helpers.extraction_helpers import ZipArchiveReader, epoch_to_iso
from port.platforms.chatgpt import account_info_to_df, conversations_to_df, messages_to_df, models_used_to_df

USER_JSON = json.dumps({
    "chatgpt_plus_user": True,
    "email": "test-account@example.test",
    "id": "user-0000000000000000000000",
    "phone_number": "+31000000000",
})


def _reader_for(files: dict[str, str]) -> ZipArchiveReader:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return ZipArchiveReader(buf, list(files), Counter())


def _turn_node(role: str, model: str | None, text: str, create_time: int, *, hidden: bool = False) -> dict:
    """Build one synthetic ``mapping`` node in the shape a real ChatGPT
    conversations export uses — no real conversation text anywhere here."""
    metadata: dict = {}
    if model:
        metadata["model_slug"] = model
    if hidden:
        metadata["is_visually_hidden_from_conversation"] = True
    return {
        "id": f"node-{role}-{create_time}",
        "message": {
            "id": f"msg-{role}-{create_time}",
            "author": {"role": role},
            "content": {"content_type": "text", "parts": [text]},
            "create_time": create_time,
            "metadata": metadata,
        },
        "parent": None,
        "children": [],
    }


#: A synthetic two-conversation export: conversation A has one user turn and
#: one assistant turn; conversation B has one user turn and two assistant
#: turns answered by a different model, plus one hidden assistant turn that
#: must be excluded entirely from both extractors' output.
CONVERSATIONS_JSON = json.dumps([
    {
        "title": "Test conversation A",
        "mapping": {
            "n1": _turn_node("user", None, "Test question one", 1700000000),
            "n2": _turn_node("assistant", "gpt-test-large", "Test answer one", 1700000010),
        },
    },
    {
        "title": "Test conversation B",
        "mapping": {
            "n3": _turn_node("user", None, "Test question two", 1700000100),
            "n4": _turn_node("assistant", "gpt-test-large", "Test answer two", 1700000110),
            "n5": _turn_node("assistant", "gpt-test-mini", "Test answer three", 1700000120),
            "n6": _turn_node("assistant", "gpt-test-hidden", "Hidden answer", 1700000130, hidden=True),
        },
    },
])


class TestAccountInfo:
    def test_reads_all_four_fields(self):
        reader = _reader_for({"user.json": USER_JSON})
        out = account_info_to_df(reader, Counter())
        assert list(out.columns) == ["Field", "Value"]
        assert len(out) == 4
        values = dict(zip(out["Field"], out["Value"]))
        assert values["ChatGPT Plus subscriber"] == "Yes"
        assert values["Account ID"] == "user-0000000000000000000000"
        assert values["Email on file"] == "test-account@example.test"
        assert values["Phone on file"] == "+31000000000"

    def test_non_plus_subscriber_reads_as_no(self):
        non_plus = json.dumps({
            "chatgpt_plus_user": False,
            "email": "another-test@example.test",
            "id": "user-1111111111111111111111",
            "phone_number": "",
        })
        reader = _reader_for({"user.json": non_plus})
        out = account_info_to_df(reader, Counter())
        values = dict(zip(out["Field"], out["Value"]))
        assert values["ChatGPT Plus subscriber"] == "No"
        assert values["Phone on file"] == ""

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = account_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        """A zero-byte user.json (ADR-0024: present-but-empty is not an
        error) must not surface as four blank-value rows."""
        reader = _reader_for({"user.json": ""})
        errors: Counter = Counter()
        out = account_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestConversations:
    """conversations_to_df now returns one row per conversation, aggregated
    from the same turns messages_to_df returns per-row (task 21b)."""

    def test_one_row_per_conversation_in_first_appearance_order(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = conversations_to_df(reader, Counter())
        assert list(out.columns) == ["Conversation title", "Started", "Last message", "Turns", "Models"]
        assert list(out["Conversation title"]) == ["Test conversation A", "Test conversation B"]

    def test_turns_counts_every_visible_turn_including_user(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = conversations_to_df(reader, Counter())
        turns = dict(zip(out["Conversation title"], out["Turns"]))
        assert turns["Test conversation A"] == 2  # 1 user + 1 assistant
        assert turns["Test conversation B"] == 3  # 1 user + 2 assistant (hidden node excluded)

    def test_started_and_last_message_are_the_conversation_s_min_and_max_turn_time(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = conversations_to_df(reader, Counter())
        row_a = out[out["Conversation title"] == "Test conversation A"].iloc[0]
        assert row_a["Started"] == epoch_to_iso(1700000000)  # n1, user turn
        assert row_a["Last message"] == epoch_to_iso(1700000010)  # n2, assistant turn

        row_b = out[out["Conversation title"] == "Test conversation B"].iloc[0]
        assert row_b["Started"] == epoch_to_iso(1700000100)  # n3, user turn
        assert row_b["Last message"] == epoch_to_iso(1700000120)  # n5, latest non-hidden turn

    def test_models_is_the_comma_joined_distinct_assistant_models(self):
        """Conversation A has one assistant model; conversation B has two,
        joined and sorted. The hidden turn's model ('gpt-test-hidden') never
        appears — it is excluded from the turns entirely, upstream of this
        aggregation."""
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = conversations_to_df(reader, Counter())
        models = dict(zip(out["Conversation title"], out["Models"]))
        assert models["Test conversation A"] == "gpt-test-large"
        assert models["Test conversation B"] == "gpt-test-large, gpt-test-mini"
        assert "gpt-test-hidden" not in models["Test conversation B"]

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = conversations_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestMessages:
    """messages_to_df is the per-turn frame conversations_to_df used to
    return directly, now under its own table with Title Case columns
    (task 21b) — see also the thread visualization in the config, which
    reads these exact column names as groupColumn/roleColumn/etc."""

    def test_column_order(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = messages_to_df(reader, Counter())
        assert list(out.columns) == ["Time", "Conversation title", "Role", "Message", "Model"]

    def test_still_includes_blank_model_user_turns(self):
        """Unchanged behaviour from the pre-split conversations_to_df: every
        turn is kept, user included, with a blank model on user turns."""
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = messages_to_df(reader, Counter())
        assert len(out) == 5  # 2 user + 3 assistant (hidden node excluded)
        user_rows = out[out["Role"] == "user"]
        assert len(user_rows) == 2
        assert set(user_rows["Model"]) == {""}

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = messages_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestModelsUsed:
    def test_one_row_per_assistant_turn(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = models_used_to_df(reader, Counter())
        assert list(out.columns) == ["model", "timestamp", "conversation title"]
        assert len(out) == 3  # 3 non-hidden assistant turns; user turns excluded
        assert set(out["model"]) == {"gpt-test-large", "gpt-test-mini"}

    def test_hidden_turns_excluded(self):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = models_used_to_df(reader, Counter())
        assert "gpt-test-hidden" not in set(out["model"])

    def test_no_blank_models(self):
        """The bug this table exists to fix: no row's model is ever blank,
        unlike conversations_to_df's user turns."""
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        out = models_used_to_df(reader, Counter())
        assert (out["model"] == "").sum() == 0

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = models_used_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestTheConversationsAreParsedOnce:
    """``conversations-*.json`` is the biggest member of a ChatGPT export, and three
    extractors in the same flow (task 21b: conversations, messages, models_used) want
    the same turns out of it. Only the first one actually parses it."""

    def test_three_extractors_on_one_reader_read_the_file_once(self, monkeypatch):
        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        errors = Counter()

        calls: list[str] = []
        original = ZipArchiveReader.json_all

        def spy_json_all(self, pattern, *args, **kwargs):
            calls.append(pattern)
            return original(self, pattern, *args, **kwargs)

        monkeypatch.setattr(ZipArchiveReader, "json_all", spy_json_all)

        conversations = conversations_to_df(reader, errors)
        messages = messages_to_df(reader, errors)
        models = models_used_to_df(reader, errors)

        assert len(calls) == 1, "the second and third extractors reuse the first extractor's parse"
        assert not conversations.empty and not messages.empty and not models.empty

    def test_a_second_reader_gets_its_own_parse(self):
        """The memo is keyed on the reader, so a different upload is a different parse
        — not a stale answer from the last one."""
        first = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        second = _reader_for({})

        assert not conversations_to_df(first, Counter()).empty
        assert conversations_to_df(second, Counter()).empty

    def test_the_memo_does_not_outlive_the_reader(self):
        """Weakly keyed: dropping the reader drops an export's worth of turn dicts."""
        import gc

        from port.platforms.chatgpt import _TURNS_BY_READER

        reader = _reader_for({"conversations-000.json": CONVERSATIONS_JSON})
        conversations_to_df(reader, Counter())
        assert len(_TURNS_BY_READER) >= 1

        del reader
        gc.collect()

        assert len(_TURNS_BY_READER) == 0


def test_no_real_names_or_pii_in_synthetic_fixtures():
    """Guard against accidentally pasting real-looking data into this file's
    module-level JSON constants."""
    assert "@example.test" in USER_JSON
    assert "uu.nl" not in USER_JSON
    assert "@" not in CONVERSATIONS_JSON
