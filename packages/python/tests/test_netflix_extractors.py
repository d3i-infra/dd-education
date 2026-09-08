"""Unit tests for the new Netflix extractors (task 15a), each over a small
in-memory zip built from synthetic two-row CSVs — no real names, emails, or
card details anywhere in this file.

Built the same way ``test_instagram_saved_posts.py`` builds its in-memory
zip: a ``ZipArchiveReader`` directly over a ``zipfile.ZipFile`` written to a
``io.BytesIO`` buffer, skipping the full ``DDPCategory`` validation pass
that ``extractor_integration_helpers.make_reader`` additionally exercises.
"""
import io
import zipfile
from collections import Counter

import pandas as pd

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms.netflix import (
    MARKETING_CONSENT_COLUMNS,
    account_and_billing_to_df,
    clickstream_to_df,
    devices_to_df,
    indicated_preferences_to_df,
    ip_addresses_to_df,
    my_list_to_df,
    profile_demographics_to_df,
)

INDICATED_PREFERENCES_CSV = (
    "Profile Name,Is Interested,Event Date,Show,Has Watched\n"
    "Alex,true,2024-01-01,Show A,false\n"
    "Sam,false,2024-01-02,Show B,true\n"
)

IP_ADDRESSES_LOGIN_CSV = (
    "Country,Esn,Ip,Device Description,Ts,Region Code\n"
    "NL,ESN-LOGIN-1,203.0.113.10,Test TV,2024-01-01 10:00:00,10\n"
    "DE,ESN-LOGIN-2,203.0.113.11,Test Laptop,2024-01-02 11:00:00,20\n"
)

IP_ADDRESSES_STREAMING_CSV = (
    "Localized Device Description,Country,Esn,Region Code Display Name,Ip,Device Description,Ts,Near Location\n"
    "Chrome,NL,ESN-STREAM-1,Utrecht,203.0.113.12,Test Chromebook,2024-01-03 12:00:00,UTRECHT\n"
    "Chrome,DE,ESN-STREAM-2,Berlin,203.0.113.13,Test Phone,2024-01-04 13:00:00,BERLIN\n"
)

DEVICES_CSV = (
    "Profile Name,Esn,Profile First Playback Date,Profile Last Playback Date,Device Type\n"
    "Alex,ESN-DEV-1,2023-01-01,2023-06-01,Smart TV\n"
    "Sam,ESN-DEV-2,2023-02-01,2023-07-01,Laptop\n"
)

ACCESS_AND_DEVICES_CSV = (
    "Date,Esn,Devices,Part Of Netflix Household\n"
    "2023-03-01,ESN-ACC-1,Streaming Stick,Yes\n"
    "2023-04-01,ESN-ACC-2,Game Console,No\n"
)

PROFILES_CSV = (
    "Profile Name,Gender,Date Of Birth,Maturity Level,Primary Lang\n"
    "Alex,,,ADULTS,en-NL\n"
    "Sam,Female,1990-01-01,ADULTS,nl-NL\n"
)

MY_LIST_CSV = (
    "Profile Name,Country,Utc Title Add Date,Title Name\n"
    "Alex,Netherlands,2024-02-01,Test Movie One\n"
    "Sam,Germany,2024-02-02,Test Movie Two\n"
)

CLICKSTREAM_CSV = (
    "Profile Name,Navigation Level,Webpage Url,Source,Click Utc Ts,Referrer Url\n"
    "Alex,browseTitles,/browse,www,2024-03-01 09:00:00,/home\n"
    "Sam,playback,/watch/123,www,2024-03-02 10:00:00,/browse\n"
)

_MARKETING_FLAG_HEADER = ",".join(MARKETING_CONSENT_COLUMNS)
_MARKETING_FLAG_VALUES = ",".join(
    "YES" if i % 2 == 0 else "NO" for i in range(len(MARKETING_CONSENT_COLUMNS))
)

ACCOUNT_DETAILS_CSV = (
    f"Membership Status,Country Of Registration,{_MARKETING_FLAG_HEADER}\n"
    f"CURRENT_MEMBER,NL,{_MARKETING_FLAG_VALUES}\n"
)

SUBSCRIPTION_HISTORY_CSV = (
    "Signup Plan Category,Plan Change New Category,Plan Change Date\n"
    "BASIC,PREMIUM,20240101\n"
)

# Rows deliberately out of file order: the earlier plan change (BASIC ->
# STANDARD) is listed *after* the later one (STANDARD -> PREMIUM), so a test
# picking "the last row" instead of "the latest Plan Change Date" would get
# the wrong plan.
SUBSCRIPTION_HISTORY_MULTI_CSV = (
    "Signup Plan Category,Plan Change New Category,Plan Change Date\n"
    "STANDARD,PREMIUM,20240301\n"
    "BASIC,STANDARD,20240101\n"
)

BILLING_HISTORY_CSV = (
    "Transaction Date,Gross Sale Amt,Currency,Payment Type\n"
    "2024-01-05,9.99,EUR,IDEAL\n"
    "2024-02-05,9.99,EUR,IDEAL\n"
)


def _reader_for(files: dict[str, str]) -> ZipArchiveReader:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return ZipArchiveReader(buf, list(files), Counter())


class TestIndicatedPreferences:
    def test_filters_to_selected_profile(self):
        reader = _reader_for({"IndicatedPreferences.csv": INDICATED_PREFERENCES_CSV})
        out = indicated_preferences_to_df(reader, Counter(), selected_user="Alex")
        assert len(out) == 1
        assert list(out.columns) == ["Show", "Is Interested", "Has Watched", "Event Date"]
        assert out.iloc[0]["Show"] == "Show A"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = indicated_preferences_to_df(reader, errors, selected_user="Alex")
        assert out.empty
        assert sum(errors.values()) == 0


class TestIpAddresses:
    def test_merges_login_and_streaming(self):
        reader = _reader_for({
            "IpAddressesLogin.csv": IP_ADDRESSES_LOGIN_CSV,
            "IpAddressesStreaming.csv": IP_ADDRESSES_STREAMING_CSV,
        })
        out = ip_addresses_to_df(reader, Counter())
        assert len(out) == 4
        assert set(out.columns) == {"Country", "Region", "Ip", "Device Description", "Ts", "Event Type"}
        assert set(out["Event Type"]) == {"Login", "Streaming"}
        assert "203.0.113.10" in set(out["Ip"])

    def test_region_normalises_login_region_code_and_streaming_display_name(self):
        reader = _reader_for({
            "IpAddressesLogin.csv": IP_ADDRESSES_LOGIN_CSV,
            "IpAddressesStreaming.csv": IP_ADDRESSES_STREAMING_CSV,
        })
        out = ip_addresses_to_df(reader, Counter())
        login_row = out[out["Event Type"] == "Login"].iloc[0]
        streaming_row = out[out["Event Type"] == "Streaming"].iloc[0]
        # Login's Region Code (numeric-looking) and streaming's Region Code
        # Display Name (a place name) both land in the one Region column.
        assert str(login_row["Region"]) in {"10", "20"}
        assert streaming_row["Region"] in {"Utrecht", "Berlin"}

    def test_only_one_source_present(self):
        reader = _reader_for({"IpAddressesLogin.csv": IP_ADDRESSES_LOGIN_CSV})
        out = ip_addresses_to_df(reader, Counter())
        assert len(out) == 2
        assert set(out["Event Type"]) == {"Login"}
        assert {str(v) for v in out["Region"]} == {"10", "20"}

    def test_absent_files_yield_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = ip_addresses_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestDevices:
    def test_merges_profile_devices_and_account_wide_access(self):
        reader = _reader_for({
            "Devices.csv": DEVICES_CSV,
            "AccessAndDevices.csv": ACCESS_AND_DEVICES_CSV,
        })
        out = devices_to_df(reader, Counter(), selected_user="Alex")
        # 1 profile-filtered row from Devices.csv + 2 account-wide rows from
        # AccessAndDevices.csv (unfiltered — it carries no profile column).
        assert len(out) == 3
        assert set(out["Source"]) == {"Devices.csv", "AccessAndDevices.csv"}
        assert "Smart TV" in set(out["Device Type"])
        assert "Streaming Stick" in set(out["Device Type"])

    def test_access_date_and_playback_dates_are_not_conflated(self):
        """Finding 5: AccessAndDevices' Date is an access-event timestamp,
        not a playback date — it must not be mislabelled as one."""
        reader = _reader_for({
            "Devices.csv": DEVICES_CSV,
            "AccessAndDevices.csv": ACCESS_AND_DEVICES_CSV,
        })
        out = devices_to_df(reader, Counter(), selected_user="Alex")
        assert "Access Date" in out.columns

        devices_row = out[out["Source"] == "Devices.csv"].iloc[0]
        assert devices_row["First Playback Date"] == "2023-01-01"
        assert devices_row["Last Playback Date"] == "2023-06-01"
        assert devices_row["Access Date"] == ""

        access_row = out[out["Source"] == "AccessAndDevices.csv"].iloc[0]
        assert access_row["First Playback Date"] == ""
        assert access_row["Last Playback Date"] == ""
        assert access_row["Access Date"] == "2023-03-01"

    def test_absent_files_yield_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = devices_to_df(reader, errors, selected_user="Alex")
        assert out.empty
        assert sum(errors.values()) == 0


class TestProfileDemographics:
    def test_filters_to_selected_profile(self):
        reader = _reader_for({"Profiles.csv": PROFILES_CSV})
        out = profile_demographics_to_df(reader, Counter(), selected_user="Sam")
        assert len(out) == 1
        assert list(out.columns) == ["Gender", "Date Of Birth", "Maturity Level", "Primary Lang"]
        assert out.iloc[0]["Gender"] == "Female"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = profile_demographics_to_df(reader, errors, selected_user="Sam")
        assert out.empty
        assert sum(errors.values()) == 0


class TestMyList:
    def test_filters_to_selected_profile(self):
        reader = _reader_for({"MyList.csv": MY_LIST_CSV})
        out = my_list_to_df(reader, Counter(), selected_user="Sam")
        assert len(out) == 1
        assert out.iloc[0]["Title Name"] == "Test Movie Two"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = my_list_to_df(reader, errors, selected_user="Sam")
        assert out.empty
        assert sum(errors.values()) == 0


class TestClickstream:
    def test_filters_to_selected_profile_and_drops_profile_name(self):
        reader = _reader_for({"Clickstream.csv": CLICKSTREAM_CSV})
        out = clickstream_to_df(reader, Counter(), selected_user="Alex")
        assert len(out) == 1
        assert "Profile Name" not in out.columns
        assert out.iloc[0]["Navigation Level"] == "browseTitles"

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = clickstream_to_df(reader, errors, selected_user="Alex")
        assert out.empty
        assert sum(errors.values()) == 0


class TestAccountAndBilling:
    def test_broadcasts_account_fields_onto_every_billing_row(self):
        reader = _reader_for({
            "AccountDetails.csv": ACCOUNT_DETAILS_CSV,
            "SubscriptionHistory.csv": SUBSCRIPTION_HISTORY_CSV,
            "BillingHistory.csv": BILLING_HISTORY_CSV,
        })
        out = account_and_billing_to_df(reader, Counter())
        assert len(out) == 2
        assert set(out["Membership Status"]) == {"CURRENT_MEMBER"}
        assert set(out["Country Of Registration"]) == {"NL"}
        assert set(out["Plan"]) == {"PREMIUM"}
        assert set(out["Currency"]) == {"EUR"}
        assert set(out["Payment Type"]) == {"IDEAL"}
        for column in MARKETING_CONSENT_COLUMNS:
            assert column in out.columns
        # Never card details: no card-number-shaped column made it through.
        assert not any("card" in c.lower() or "mop" in c.lower() for c in out.columns)

    def test_billing_absent_others_present_still_yields_one_row(self):
        """Finding 2: a zero-transaction account (BillingHistory.csv absent
        or empty) must not lose the whole table — it gets one row of
        account/plan fields with the billing columns blank."""
        reader = _reader_for({
            "AccountDetails.csv": ACCOUNT_DETAILS_CSV,
            "SubscriptionHistory.csv": SUBSCRIPTION_HISTORY_CSV,
        })
        errors: Counter = Counter()
        out = account_and_billing_to_df(reader, errors)
        assert len(out) == 1
        assert out.iloc[0]["Membership Status"] == "CURRENT_MEMBER"
        assert out.iloc[0]["Country Of Registration"] == "NL"
        assert out.iloc[0]["Plan"] == "PREMIUM"
        for column in ["Transaction Date", "Gross Sale Amt", "Currency", "Payment Type"]:
            assert out.iloc[0][column] == ""
        assert sum(errors.values()) == 0

    def test_all_three_sources_absent_yields_empty_no_error(self):
        """ADR-0024: only when every source is absent/empty is the table
        itself empty."""
        reader = _reader_for({})
        errors: Counter = Counter()
        out = account_and_billing_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_billing_present_but_account_details_absent_still_yields_rows(self):
        """ADR-0024: an absent companion file yields blanks for its columns,
        not a dropped table — the billing rows are still the reveal."""
        reader = _reader_for({"BillingHistory.csv": BILLING_HISTORY_CSV})
        errors: Counter = Counter()
        out = account_and_billing_to_df(reader, errors)
        assert len(out) == 2
        assert set(out["Membership Status"]) == {""}
        assert set(out["Plan"]) == {""}
        assert sum(errors.values()) == 0

    def test_plan_picked_by_latest_plan_change_date_not_last_row(self):
        """Minor fix: pick the plan by the latest parseable Plan Change
        Date, not by file row order."""
        reader = _reader_for({
            "AccountDetails.csv": ACCOUNT_DETAILS_CSV,
            "SubscriptionHistory.csv": SUBSCRIPTION_HISTORY_MULTI_CSV,
            "BillingHistory.csv": BILLING_HISTORY_CSV,
        })
        out = account_and_billing_to_df(reader, Counter())
        # The last row in file order is the BASIC -> STANDARD change
        # (2024-01-01); the latest by date is STANDARD -> PREMIUM
        # (2024-03-01). The plan must reflect the latter.
        assert set(out["Plan"]) == {"PREMIUM"}

    def test_plan_falls_back_to_last_row_when_date_column_missing(self):
        reader = _reader_for({
            "AccountDetails.csv": ACCOUNT_DETAILS_CSV,
            "SubscriptionHistory.csv": "Signup Plan Category,Plan Change New Category\nBASIC,STANDARD\n",
            "BillingHistory.csv": BILLING_HISTORY_CSV,
        })
        out = account_and_billing_to_df(reader, Counter())
        assert set(out["Plan"]) == {"STANDARD"}


def test_no_real_names_or_pii_in_synthetic_fixtures():
    """Guard against accidentally pasting real-looking data into this file's
    module-level CSV constants."""
    module_source = "\n".join([
        INDICATED_PREFERENCES_CSV, IP_ADDRESSES_LOGIN_CSV, IP_ADDRESSES_STREAMING_CSV,
        DEVICES_CSV, ACCESS_AND_DEVICES_CSV, PROFILES_CSV, MY_LIST_CSV, CLICKSTREAM_CSV,
        ACCOUNT_DETAILS_CSV, SUBSCRIPTION_HISTORY_CSV, SUBSCRIPTION_HISTORY_MULTI_CSV,
        BILLING_HISTORY_CSV,
    ])
    assert "@" not in module_source
    assert pd is not None  # pandas import is exercised via the extractors above
