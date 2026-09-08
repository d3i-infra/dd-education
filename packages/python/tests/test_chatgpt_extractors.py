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

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms.chatgpt import account_info_to_df

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


def test_no_real_names_or_pii_in_synthetic_fixtures():
    """Guard against accidentally pasting real-looking data into this file's
    module-level JSON constant."""
    assert "@example.test" in USER_JSON
    assert "uu.nl" not in USER_JSON
