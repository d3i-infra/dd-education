"""Unit tests for the Facebook extractors added (or re-enabled) in Task 15d
(story edu-curation): the "what Facebook holds from old permissions"
flagship — contacts Facebook has connected to the account, and the
friend-suggestion tables. Each gets a small in-memory zip built from
synthetic json and, where the extractor reads one, synthetic html — no real
names, numbers, or e-mail addresses anywhere in this file (ADR-0014): names
are generic placeholders, phone numbers use the NANP fictional block
555-0100..555-0199 (RFC-style convention for fiction), e-mail addresses use
the ``.test`` domain (RFC 2606).

Built the same way ``test_facebook_held_tables.py`` builds its in-memory zip
and synthetic pages.

Every extractor also gets an "absent file(s)" and an "empty file" case, per
ADR-0024: missing source files or a present-but-empty one (an empty zip
member) must both yield an empty DataFrame without incrementing the error
counter.
"""
import io
import zipfile
from collections import Counter
from types import SimpleNamespace

from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.validate import DDPFiletype
from port.platforms import facebook as F


def _reader(*entries: tuple[str, str], errors: Counter | None = None) -> ZipArchiveReader:
    """In-memory archive reader over *entries* (member path -> text content)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries:
            zf.writestr(name, content)
    buf.seek(0)
    return ZipArchiveReader(buf, [name for name, _ in entries], errors if errors is not None else Counter())


_HTML_VALIDATION = SimpleNamespace(current_ddp_category=SimpleNamespace(ddp_filetype=DDPFiletype.HTML))

_BEFORE_2021_JSON = "export/personal_information/profile_information/contacts_uploaded_before_2021.json"
_BEFORE_2021_HTML = "export/personal_information/profile_information/contacts_uploaded_before_2021.html"
_IMPORTED_JSON = "export/personal_information/other_personal_information/your_imported_contacts.json"
_IMPORTED_HTML = "export/personal_information/other_personal_information/your_imported_contacts.html"
_FROM_PHONE_JSON = "export/personal_information/other_personal_information/contacts_uploaded_from_your_phone.json"
_FROM_PHONE_HTML = "export/personal_information/other_personal_information/contacts_uploaded_from_your_phone.html"

_PEOPLE_YOU_MAY_KNOW_JSON = "export/connections/friends/people_you_may_know.json"
_PEOPLE_YOU_MAY_KNOW_HTML = "export/connections/friends/people_you_may_know.html"
_SUGGESTED_FRIENDS_JSON = "export/connections/friends/suggested_friends.json"
_SUGGESTED_FRIENDS_HTML = "export/connections/friends/suggested_friends.html"
_FRIENDS_YOU_SEE_LESS_JSON = "export/connections/friends/friends_you_see_less.json"
_FRIENDS_YOU_SEE_LESS_HTML = "export/connections/friends/friends_you_see_less.html"
_YOUR_FRIENDS_JSON = "export/connections/friends/your_friends.json"


# ---------------------------------------------------------------------------
# facebook_uploaded_contacts: three source files, one merged table
# ---------------------------------------------------------------------------

_BEFORE_2021_PAYLOAD = """
{
  "media": [],
  "label_values": [
    {
      "label": "Contacts",
      "vec": [
        {"dict": [
          {"label": "user_id", "value": "1000000001"},
          {"label": "Contact point", "value": "friend.one@example.test"},
          {"label": "Time of first import", "timestamp_value": 1600000000},
          {"label": "Time of latest import", "timestamp_value": 1600000000},
          {"label": "Name", "value": "Test Contact One"}
        ]}
      ]
    }
  ],
  "fbid": "9999999999"
}
"""

_IMPORTED_PAYLOAD = """
[
  {"timestamp": 1700000000, "media": [], "label_values": [
      {"label": "Update time", "timestamp_value": 1700000000},
      {"label": "Contact name", "value": "Test Import One"},
      {"label": "Contact point", "value": "555-0101"}
  ], "fbid": "2000000001"}
]
"""

_FROM_PHONE_PAYLOAD = """
[
  {"media": [], "label_values": [
      {"label": "Name", "value": "Test Phone One"},
      {"label": "Upload time", "timestamp_value": 1680000000},
      {"label": "Creation time", "timestamp_value": 0}
  ], "fbid": "3000000001"},
  {"media": [], "label_values": [
      {"label": "Name", "value": "Test Phone Two"},
      {"label": "Upload time", "timestamp_value": 0},
      {"label": "Creation time", "timestamp_value": 1670000000}
  ], "fbid": "3000000002"}
]
"""

_BEFORE_2021_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">user_id</td><td class="_a6_r">1000000001</td></tr>
<tr><td class="_a6_q">Contact point</td><td class="_a6_r">friend.one@example.test</td></tr>
<tr><td class="_a6_q">Time of first import</td><td class="_a6_r">Sep 13, 2020 12:00:00 pm</td></tr>
<tr><td class="_a6_q">Time of latest import</td><td class="_a6_r">Sep 13, 2020 12:00:00 pm</td></tr>
<tr><td class="_a6_q">Name</td><td class="_a6_r">Test Contact One</td></tr>
</table></div></section>
</main></body></html>"""

_IMPORTED_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">Update time</td><td class="_a6_r">Nov 14, 2023 12:00:00 pm</td></tr>
<tr><td class="_a6_q">Contact name</td><td class="_a6_r">Test Import One</td></tr>
<tr><td class="_a6_q">Contact point</td><td class="_a6_r">555-0101</td></tr>
</table></div></section></div>
<footer><div class="_a72d">Nov 14, 2023 12:00:00 pm</div></footer></section>
</main></body></html>"""

_FROM_PHONE_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">Name</td><td class="_a6_r">Test Phone One</td></tr>
<tr><td class="_a6_q">Upload time</td><td class="_a6_r">Mar 30, 2023 12:00:00 pm</td></tr>
</table></div></section></div>
<footer><div class="_a72d"></div></footer></section>
<section class="_a6-g"><div class="_a6-p"><section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">Name</td><td class="_a6_r">Test Phone Two</td></tr>
<tr><td class="_a6_q">Creation time</td><td class="_a6_r">Dec 09, 2022 12:00:00 pm</td></tr>
</table></div></section></div>
<footer><div class="_a72d"></div></footer></section>
</main></body></html>"""


class TestFacebookUploadedContacts:
    def test_merges_three_sources_json(self):
        reader = _reader(
            (_BEFORE_2021_JSON, _BEFORE_2021_PAYLOAD),
            (_IMPORTED_JSON, _IMPORTED_PAYLOAD),
            (_FROM_PHONE_JSON, _FROM_PHONE_PAYLOAD),
        )
        out = F.facebook_uploaded_contacts_to_df(reader, Counter())
        assert len(out) == 4
        assert list(out.columns) == ["Source", "Name", "Number", "Timestamp"]
        assert set(out["Source"]) == {
            "Contacts uploaded before 2021",
            "Your imported contacts",
            "Contacts uploaded from your phone",
        }
        # The phone-upload rows carry no Contact point in the source file.
        phone_rows = out[out["Source"] == "Contacts uploaded from your phone"]
        assert len(phone_rows) == 2
        assert set(phone_rows["Number"]) == {""}
        before_2021_row = out[out["Source"] == "Contacts uploaded before 2021"].iloc[0]
        assert before_2021_row["Name"] == "Test Contact One"
        assert before_2021_row["Number"] == "friend.one@example.test"
        # Newest first.
        assert list(out["Timestamp"]) == sorted(out["Timestamp"], reverse=True)

    def test_from_phone_falls_back_to_creation_time_when_upload_time_is_zero(self):
        reader = _reader((_FROM_PHONE_JSON, _FROM_PHONE_PAYLOAD))
        out = F.facebook_uploaded_contacts_to_df(reader, Counter())
        by_name = dict(zip(out["Name"], out["Timestamp"]))
        assert by_name["Test Phone One"] == "2023-03-28 12:40:00"  # Upload time (nonzero)
        assert by_name["Test Phone Two"] == "2022-12-02 17:53:20"  # Creation time (Upload time is 0)

    def test_only_one_source_present(self):
        reader = _reader((_IMPORTED_JSON, _IMPORTED_PAYLOAD))
        out = F.facebook_uploaded_contacts_to_df(reader, Counter())
        assert len(out) == 1
        assert out.iloc[0]["Source"] == "Your imported contacts"

    def test_absent_files_yield_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.facebook_uploaded_contacts_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_files_yield_empty_no_error(self):
        reader = _reader(
            (_BEFORE_2021_JSON, ""), (_IMPORTED_JSON, ""), (_FROM_PHONE_JSON, ""),
        )
        errors: Counter = Counter()
        out = F.facebook_uploaded_contacts_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_merges_three_sources_html(self):
        reader = _reader(
            (_BEFORE_2021_HTML, _BEFORE_2021_PAGE),
            (_IMPORTED_HTML, _IMPORTED_PAGE),
            (_FROM_PHONE_HTML, _FROM_PHONE_PAGE),
        )
        out = F.facebook_uploaded_contacts_to_df(reader, Counter(), validation=_HTML_VALIDATION)
        assert len(out) == 4
        assert list(out.columns) == ["Source", "Name", "Number", "Timestamp"]
        assert set(out["Source"]) == {
            "Contacts uploaded before 2021",
            "Your imported contacts",
            "Contacts uploaded from your phone",
        }
        phone_rows = out[out["Source"] == "Contacts uploaded from your phone"]
        assert set(phone_rows["Number"]) == {""}

    def test_absent_html_files_yield_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.facebook_uploaded_contacts_to_df(reader, errors, validation=_HTML_VALIDATION)
        assert out.empty
        assert sum(errors.values()) == 0


# ---------------------------------------------------------------------------
# facebook_people_you_may_know
# ---------------------------------------------------------------------------

_PEOPLE_YOU_MAY_KNOW_PAYLOAD = """
{
  "media": [],
  "label_values": [
    {"label": "When these suggestions were created", "timestamp_value": 1700000000},
    {"label": "Friend suggestions", "vec": [
      {"value": "Test Suggestion One"},
      {"value": "Test Suggestion Two"}
    ]}
  ],
  "fbid": "9999999998"
}
"""

_PEOPLE_YOU_MAY_KNOW_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">When these suggestions were created</td><td class="_a6_r">Nov 14, 2023 12:00:00 pm</td></tr>
<tr><td colspan="2" class="_a6_q">Friend suggestions<div><div><div>
<section class="_a6-g"><div class="_a6-p">Test Suggestion One</div></section>
</div><div><section class="_a6-g"><div class="_a6-p">Test Suggestion Two</div></section></div>
</div></div></td></tr>
</table></div></section>
</main></body></html>"""


class TestPeopleYouMayKnow:
    def test_two_suggestions_share_the_batch_timestamp_json(self):
        reader = _reader((_PEOPLE_YOU_MAY_KNOW_JSON, _PEOPLE_YOU_MAY_KNOW_PAYLOAD))
        out = F.people_you_may_know_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Name", "Timestamp"]
        assert set(out["Name"]) == {"Test Suggestion One", "Test Suggestion Two"}
        assert set(out["Timestamp"]) == {"2023-11-14 23:13:20"}

    def test_two_suggestions_share_the_batch_timestamp_html(self):
        reader = _reader((_PEOPLE_YOU_MAY_KNOW_HTML, _PEOPLE_YOU_MAY_KNOW_PAGE))
        out = F.people_you_may_know_to_df(reader, Counter(), validation=_HTML_VALIDATION)
        assert len(out) == 2
        assert set(out["Name"]) == {"Test Suggestion One", "Test Suggestion Two"}
        assert len(set(out["Timestamp"])) == 1

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.people_you_may_know_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader((_PEOPLE_YOU_MAY_KNOW_JSON, ""))
        errors: Counter = Counter()
        out = F.people_you_may_know_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


# ---------------------------------------------------------------------------
# facebook_suggested_friends
# ---------------------------------------------------------------------------

_SUGGESTED_FRIENDS_PAYLOAD = """
[
  {"media": [], "label_values": [
      {"label": "Creation time", "timestamp_value": 1680000000},
      {"label": "Last modified time", "timestamp_value": 1680000000},
      {"label": "Suggestion sent time", "timestamp_value": 1680000000},
      {"dict": [{"dict": [{"label": "Name", "value": "Test Friend One"}], "title": ""}], "title": "Name"}
  ], "fbid": "4000000001"}
]
"""

_SUGGESTED_FRIENDS_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">Creation time</td><td class="_a6_r">Mar 28, 2023 8:00:00 am</td></tr>
<tr><td class="_a6_q">Last modified time</td><td class="_a6_r">Mar 28, 2023 8:00:00 am</td></tr>
<tr><td class="_a6_q">Suggestion sent time</td><td class="_a6_r">Mar 28, 2023 8:00:00 am</td></tr>
<tr><td colspan="2" class="_a6_q"><div>
<section class="_a6-g" aria-labelledby="x"><h2 id="x">Name</h2><div class="_a6-p"><div>
<div class="_2ph_ _a6_q">Name</div><div><div>
<section class="_a6-g"><div class="_a6-p">Test Friend One</div></section>
</div></div></div></div></section>
</div></td></tr>
</table></div></section></div>
<footer><div class="_a72d"></div></footer></section>
</main></body></html>"""


class TestSuggestedFriends:
    def test_reads_name_creation_and_sent_time_json(self):
        reader = _reader((_SUGGESTED_FRIENDS_JSON, _SUGGESTED_FRIENDS_PAYLOAD))
        out = F.suggested_friends_to_df(reader, Counter())
        assert len(out) == 1
        assert list(out.columns) == ["Name", "Creation time", "Suggestion sent time"]
        row = out.iloc[0]
        assert row["Name"] == "Test Friend One"
        assert row["Creation time"] == row["Suggestion sent time"] == "2023-03-28 12:40:00"

    def test_reads_name_creation_and_sent_time_html(self):
        reader = _reader((_SUGGESTED_FRIENDS_HTML, _SUGGESTED_FRIENDS_PAGE))
        out = F.suggested_friends_to_df(reader, Counter(), validation=_HTML_VALIDATION)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["Name"] == "Test Friend One"
        assert row["Creation time"] == row["Suggestion sent time"] == "2023-03-28 08:00:00"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.suggested_friends_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader((_SUGGESTED_FRIENDS_JSON, ""))
        errors: Counter = Counter()
        out = F.suggested_friends_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


# ---------------------------------------------------------------------------
# facebook_friends_you_see_less
# ---------------------------------------------------------------------------

_FRIENDS_YOU_SEE_LESS_PAYLOAD = """
{
  "timestamp": 1584322128,
  "media": [],
  "label_values": [{"label": "Name", "value": "Test Friend Two"}],
  "fbid": "5000000001"
}
"""

_FRIENDS_YOU_SEE_LESS_PAGE = """<html><body><main>
<section class="_a6-g"><div class="_a6-p"><section class="_a6-g"><div class="_a6-p"><table>
<tr><td class="_a6_q">Name</td><td class="_a6_r">Test Friend Two</td></tr>
</table></div></section></div>
<footer><div class="_a72d">Mar 16, 2020 2:28:48 am</div></footer></section>
</main></body></html>"""


class TestFriendsYouSeeLess:
    def test_single_record_json(self):
        reader = _reader((_FRIENDS_YOU_SEE_LESS_JSON, _FRIENDS_YOU_SEE_LESS_PAYLOAD))
        out = F.friends_you_see_less_to_df(reader, Counter())
        assert len(out) == 1
        assert list(out.columns) == ["Name", "Timestamp"]
        assert out.iloc[0]["Name"] == "Test Friend Two"
        assert out.iloc[0]["Timestamp"] == "2020-03-16 02:28:48"

    def test_single_record_html(self):
        reader = _reader((_FRIENDS_YOU_SEE_LESS_HTML, _FRIENDS_YOU_SEE_LESS_PAGE))
        out = F.friends_you_see_less_to_df(reader, Counter(), validation=_HTML_VALIDATION)
        assert len(out) == 1
        assert out.iloc[0]["Name"] == "Test Friend Two"
        assert out.iloc[0]["Timestamp"] == "2020-03-16 02:28:48"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.friends_you_see_less_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader((_FRIENDS_YOU_SEE_LESS_JSON, ""))
        errors: Counter = Counter()
        out = F.friends_you_see_less_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


# ---------------------------------------------------------------------------
# facebook_your_friends (re-enabled in the registry — Task 15d): json-only,
# unchanged extraction logic, now takes an (unused) ``validation`` kwarg for
# calling-convention parity with the rest of the registry.
# ---------------------------------------------------------------------------

_YOUR_FRIENDS_PAYLOAD = """
{"friends_v2": [
  {"name": "Test Friend A"},
  {"name": "Test Friend B"},
  {"name": "Test Friend C"}
]}
"""


class TestYourFriends:
    def test_counts_friends_json(self):
        reader = _reader((_YOUR_FRIENDS_JSON, _YOUR_FRIENDS_PAYLOAD))
        out = F.your_friends_to_df(reader, Counter())
        assert len(out) == 1
        assert out.iloc[0]["Number of friends"] == 3

    def test_accepts_validation_kwarg_without_using_it(self):
        """Every table in the registry is called with ``validation=...`` by
        ``extraction()`` (Task 15d re-enabled this extractor into the
        registry) — it must accept the kwarg even though it never reads it."""
        reader = _reader((_YOUR_FRIENDS_JSON, _YOUR_FRIENDS_PAYLOAD))
        out = F.your_friends_to_df(reader, Counter(), validation=_HTML_VALIDATION)
        assert out.iloc[0]["Number of friends"] == 3

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader()
        errors: Counter = Counter()
        out = F.your_friends_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0
