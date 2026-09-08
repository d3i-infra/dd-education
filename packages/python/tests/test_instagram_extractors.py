"""Unit tests for the eight Instagram extractors added in Task 15b (story
edu-curation), each over a small in-memory zip built from synthetic two-item
JSON — no real names, handles, or URLs with real domains anywhere in this
file (URLs use the ``.test`` domain per RFC 2606; IP addresses use the
TEST-NET-3 documentation range, 203.0.113.0/24, per RFC 5737).

Built the same way ``test_instagram_saved_posts.py`` builds its in-memory
zip: a ``ZipArchiveReader`` directly over a ``zipfile.ZipFile`` written to an
``io.BytesIO`` buffer, skipping the full ``DDPCategory`` validation pass that
``extractor_integration_helpers.make_reader`` additionally exercises.

Every extractor also gets an "absent file" and an "empty file" case, per
ADR-0024: a missing source file or a present-but-empty one (an empty zip
member — the shape a zero-byte real export file takes once
``ZipArchiveReader.json`` reads it) must both yield an empty DataFrame
without incrementing the error counter.
"""
import io
import json
import zipfile
from collections import Counter

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms.instagram import (
    account_info_to_df,
    ad_targeting_categories_to_df,
    camera_info_to_df,
    link_history_to_df,
    locations_of_interest_to_df,
    login_activity_to_df,
    off_meta_activity_to_df,
    profile_based_in_to_df,
)

ACCOUNT_INFO_PATH = "instagram-testaccount-2026-01-01/personal_information/personal_information/personal_information.json"
AD_TARGETING_PATH = "instagram-testaccount-2026-01-01/ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json"
LINK_HISTORY_PATH = "instagram-testaccount-2026-01-01/logged_information/link_history/link_history.json"
LOGIN_ACTIVITY_PATH = "instagram-testaccount-2026-01-01/security_and_login_information/login_and_profile_creation/login_activity.json"
LOCATIONS_OF_INTEREST_PATH = "instagram-testaccount-2026-01-01/personal_information/information_about_you/locations_of_interest.json"
OFF_META_ACTIVITY_PATH = "instagram-testaccount-2026-01-01/apps_and_websites_off_of_instagram/apps_and_websites/your_activity_off_meta_technologies_settings.json"
PROFILE_BASED_IN_PATH = "instagram-testaccount-2026-01-01/personal_information/information_about_you/profile_based_in.json"
CAMERA_INFO_PATH = "instagram-testaccount-2026-01-01/personal_information/device_information/camera_information.json"


def _reader_for(files: dict[str, str]) -> ZipArchiveReader:
    """Build a ``ZipArchiveReader`` over an in-memory zip holding *files*
    (member path -> raw text content, already JSON-encoded by the caller)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return ZipArchiveReader(buf, list(files), Counter())


class TestAccountInfo:
    def test_two_fields(self):
        payload = {
            "profile_user": [
                {
                    "title": "User information",
                    "string_map_data": {
                        "Username": {"href": "", "value": "test_user_one", "timestamp": 0},
                        "Email address": {"href": "", "value": "person@example.test", "timestamp": 0},
                    },
                }
            ]
        }
        reader = _reader_for({ACCOUNT_INFO_PATH: json.dumps(payload)})
        out = account_info_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Field", "Value"]
        values = dict(zip(out["Field"], out["Value"]))
        assert values["Username"] == "test_user_one"
        assert values["Email address"] == "person@example.test"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = account_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({ACCOUNT_INFO_PATH: ""})
        errors: Counter = Counter()
        out = account_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestAdTargetingCategories:
    def test_two_categories(self):
        payload = {
            "label_values": [
                {
                    "label": "Name",
                    "vec": [
                        {"value": "Birthday in June"},
                        {"value": "Owns: Test Phone Model"},
                    ],
                }
            ]
        }
        reader = _reader_for({AD_TARGETING_PATH: json.dumps(payload)})
        out = ad_targeting_categories_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Category"]
        assert set(out["Category"]) == {"Birthday in June", "Owns: Test Phone Model"}

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = ad_targeting_categories_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({AD_TARGETING_PATH: ""})
        errors: Counter = Counter()
        out = ad_targeting_categories_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestLinkHistory:
    def test_two_visits_keep_full_url_and_compute_a_duration(self):
        payload = [
            {
                "timestamp": 1700000100,
                "label_values": [
                    {"label": "Website link that you visited", "value": "https://shop.example.test/deal?utm_source=instagram&utm_campaign=test"},
                    {"label": "Title of website page that you visited", "value": "Example Test Shop"},
                    {"label": "Website session start time", "value": "Jan 1, 2024 10:00:00am"},
                    {"label": "Website session end time", "value": "Jan 1, 2024 10:00:05am"},
                ],
            },
            {
                "timestamp": 1700000200,
                "label_values": [
                    {"label": "Website link that you visited", "value": "https://news.example.test/article?fbclid=abc123"},
                    {"label": "Title of website page that you visited", "value": "Example Test News"},
                    {"label": "Website session start time", "value": "Jan 1, 2024 10:01:30am"},
                    {"label": "Website session end time", "value": "Jan 1, 2024 10:01:40am"},
                ],
            },
        ]
        reader = _reader_for({LINK_HISTORY_PATH: json.dumps(payload)})
        out = link_history_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Page title", "URL", "Visit start", "Visit end"]

        urls = set(out["URL"])
        assert "https://shop.example.test/deal?utm_source=instagram&utm_campaign=test" in urls
        assert "https://news.example.test/article?fbclid=abc123" in urls

        shop_row = out[out["URL"].str.contains("shop.example.test")].iloc[0]
        assert shop_row["Page title"] == "Example Test Shop"
        # A 5-second visit: start strictly precedes end once the duration
        # between the file's own local start/end strings is applied.
        assert shop_row["Visit start"] < shop_row["Visit end"]

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = link_history_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({LINK_HISTORY_PATH: ""})
        errors: Counter = Counter()
        out = link_history_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestLoginActivity:
    def test_two_logins_keep_ip_drop_port_and_cookie(self):
        payload = {
            "account_history_login_history": [
                {
                    "title": "2024-01-01T10:00:00+00:00",
                    "string_map_data": {
                        "Cookie name": {"href": "", "value": "***masked-one***", "timestamp": 0},
                        "IP address": {"href": "", "value": "203.0.113.5", "timestamp": 0},
                        "Port": {"href": "", "value": "12345", "timestamp": 0},
                        "Language code": {"href": "", "value": "en", "timestamp": 0},
                        "Time": {"href": "", "value": "", "timestamp": 1700000000},
                    },
                },
                {
                    "title": "2024-01-02T11:00:00+00:00",
                    "string_map_data": {
                        "Cookie name": {"href": "", "value": "***masked-two***", "timestamp": 0},
                        "IP address": {"href": "", "value": "203.0.113.6", "timestamp": 0},
                        "Port": {"href": "", "value": "54321", "timestamp": 0},
                        "Language code": {"href": "", "value": "nl", "timestamp": 0},
                        "Time": {"href": "", "value": "", "timestamp": 1700010000},
                    },
                },
            ]
        }
        reader = _reader_for({LOGIN_ACTIVITY_PATH: json.dumps(payload)})
        out = login_activity_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Timestamp", "IP address", "Language code"]
        assert set(out["IP address"]) == {"203.0.113.5", "203.0.113.6"}
        assert set(out["Language code"]) == {"en", "nl"}

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = login_activity_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({LOGIN_ACTIVITY_PATH: ""})
        errors: Counter = Counter()
        out = login_activity_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestLocationsOfInterest:
    def test_two_locations_skip_usage_explanation(self):
        payload = {
            "label_values": [
                {
                    "label": "Locations of interest",
                    "vec": [
                        {"value": "Testville, Test Region"},
                        {"value": "Sampletown, Sample Region"},
                    ],
                },
                {"label": "Usage explanation", "value": "How this list is used."},
            ]
        }
        reader = _reader_for({LOCATIONS_OF_INTEREST_PATH: json.dumps(payload)})
        out = locations_of_interest_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Location"]
        assert set(out["Location"]) == {"Testville, Test Region", "Sampletown, Sample Region"}

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = locations_of_interest_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({LOCATIONS_OF_INTEREST_PATH: ""})
        errors: Counter = Counter()
        out = locations_of_interest_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestOffMetaActivity:
    def test_two_flat_settings_skip_nested_dict_entry(self):
        payload = {
            "timestamp": 1700000000,
            "label_values": [
                {"label": "Profile association state", "value": "Account association enabled"},
                {"label": "Number of times you used clear history settings", "value": "2"},
                {"label": "Your latest and upcoming profile association states", "dict": []},
            ],
        }
        reader = _reader_for({OFF_META_ACTIVITY_PATH: json.dumps(payload)})
        out = off_meta_activity_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Label", "Value"]
        values = dict(zip(out["Label"], out["Value"]))
        assert values["Profile association state"] == "Account association enabled"
        assert values["Number of times you used clear history settings"] == "2"

    def test_timestamp_value_field_is_converted(self):
        """The ``timestamp_value`` branch (an epoch stored under a different
        key than the ``value``/``timestamp`` pair every other field in this
        file uses) — untested until now."""
        payload = {
            "label_values": [
                {"label": "Latest last activity time", "timestamp_value": 1700000000},
            ],
        }
        reader = _reader_for({OFF_META_ACTIVITY_PATH: json.dumps(payload)})
        out = off_meta_activity_to_df(reader, Counter())
        assert len(out) == 1
        assert out.iloc[0]["Label"] == "Latest last activity time"
        assert out.iloc[0]["Value"] == "2023-11-14 23:13:20"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = off_meta_activity_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({OFF_META_ACTIVITY_PATH: ""})
        errors: Counter = Counter()
        out = off_meta_activity_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestProfileBasedIn:
    def test_two_nested_fields(self):
        payload = {
            "label_values": [
                {
                    "label": "Location",
                    "dict": [
                        {"label": "Country", "value": "Testland"},
                        {"label": "City", "value": "Testville"},
                    ],
                }
            ]
        }
        reader = _reader_for({PROFILE_BASED_IN_PATH: json.dumps(payload)})
        out = profile_based_in_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Field", "Value"]
        values = dict(zip(out["Field"], out["Value"]))
        assert values["Country"] == "Testland"
        assert values["City"] == "Testville"

    def test_group_with_both_value_and_dict_is_not_double_counted(self):
        """A group carrying both a flat ``value`` and a nested ``dict`` must
        take exactly one branch (the flat value, checked first) rather than
        emitting a row for each — the same if/elif shape ``camera_info_to_df``
        already uses."""
        payload = {
            "label_values": [
                {
                    "label": "Region",
                    "value": "Test Region",
                    "dict": [{"label": "Sub-region", "value": "Should not appear"}],
                }
            ]
        }
        reader = _reader_for({PROFILE_BASED_IN_PATH: json.dumps(payload)})
        out = profile_based_in_to_df(reader, Counter())
        assert len(out) == 1
        assert out.iloc[0]["Field"] == "Region"
        assert out.iloc[0]["Value"] == "Test Region"
        assert "Sub-region" not in set(out["Field"])

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = profile_based_in_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({PROFILE_BASED_IN_PATH: ""})
        errors: Counter = Counter()
        out = profile_based_in_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestCameraInfo:
    def test_flat_and_nested_field(self):
        payload = {
            "timestamp": 1700000000,
            "label_values": [
                {"label": "Device ID", "value": "test-device-id-0001"},
                {
                    "label": "Metadata",
                    "dict": [{"label": "Supported SDK versions", "value": "1.0,2.0"}],
                },
            ],
        }
        reader = _reader_for({CAMERA_INFO_PATH: json.dumps(payload)})
        out = camera_info_to_df(reader, Counter())
        assert len(out) == 2
        assert list(out.columns) == ["Field", "Value"]
        values = dict(zip(out["Field"], out["Value"]))
        assert values["Device ID"] == "test-device-id-0001"
        assert values["Supported SDK versions"] == "1.0,2.0"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = camera_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_empty_file_yields_empty_no_error(self):
        reader = _reader_for({CAMERA_INFO_PATH: ""})
        errors: Counter = Counter()
        out = camera_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0
