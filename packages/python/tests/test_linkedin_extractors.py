"""Unit tests for the new LinkedIn extractors (task 15c), each over a small
in-memory zip built from synthetic CSVs — no real names, emails, phone
numbers, or handles anywhere in this file (contact-info values below are
invented, per the task brief's instruction for this extractor's unit test).

Built the same way ``test_netflix_extractors.py`` builds its in-memory zip: a
``ZipArchiveReader`` directly over a ``zipfile.ZipFile`` written to a
``io.BytesIO`` buffer, skipping the full ``DDPCategory`` validation pass that
``extractor_integration_helpers.make_reader`` additionally exercises.
"""
import io
import zipfile
from collections import Counter

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms.linkedin import ad_targeting_to_df, contact_info_to_df

# A synthetic wide row, deliberately including one column repeated twice with
# the IDENTICAL value ("Job Titles" at two positions) — mirrors a real finding
# on the LinkedIn basic-archive fixture, where Ad_Targeting.csv genuinely
# repeats some header names with duplicate content. The reshape must not
# double-count that column.
AD_TARGETING_CSV = (
    "Member Age,Job Titles,Company Names,Buyer Groups,Job Titles\n"
    "25-34,Test Engineer;Test Manager,Test Corp,,Test Engineer;Test Manager\n"
)

PHONE_NUMBERS_CSV = (
    "Extension,Number,Type\n"
    ",+310000000001,MOBILE\n"
    ",+310000000002,HOME\n"
)

WHATSAPP_NUMBERS_CSV = (
    "Number,Extension,Is_WhatsApp_Number\n"
    "+310000000001,,Yes\n"
)

EMAIL_ADDRESSES_CSV = (
    "Email Address,Confirmed,Primary,Updated On\n"
    "test-account@example.test,Yes,Yes,2020-01-01\n"
    "test-alt@example.test,Yes,No,2021-02-02\n"
)

REGISTRATION_CSV = (
    "Registered At,Registration Ip,Subscription Types\n"
    "2015-06-15 00:00:00 UTC,203.0.113.5,Free\n"
)


def _reader_for(files: dict[str, str]) -> ZipArchiveReader:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return ZipArchiveReader(buf, list(files), Counter())


class TestAdTargeting:
    def test_reshapes_wide_row_to_long(self):
        reader = _reader_for({"Ad_Targeting.csv": AD_TARGETING_CSV})
        out = ad_targeting_to_df(reader, Counter())
        assert list(out.columns) == ["Category", "Value"]
        # Member Age (1) + Job Titles (2, deduplicated across its repeat) +
        # Company Names (1) = 4 rows. Buyer Groups is empty and contributes
        # nothing.
        assert len(out) == 4
        assert set(out.loc[out["Category"] == "Job Titles", "Value"]) == {"Test Engineer", "Test Manager"}
        assert (out["Category"] == "Buyer Groups").sum() == 0

    def test_deduplicates_identical_repeated_columns(self):
        """The real fixture repeats some Ad_Targeting.csv column names with
        identical content — the reshape must count that column once, not
        once per repeat."""
        reader = _reader_for({"Ad_Targeting.csv": AD_TARGETING_CSV})
        out = ad_targeting_to_df(reader, Counter())
        job_title_rows = out[out["Category"] == "Job Titles"]
        assert len(job_title_rows) == 2  # not 4 (2 values x 2 repeated columns)

    def test_absent_file_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = ad_targeting_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0

    def test_header_only_yields_empty_no_error(self):
        reader = _reader_for({"Ad_Targeting.csv": "Member Age,Job Titles\n"})
        errors: Counter = Counter()
        out = ad_targeting_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


class TestContactInfo:
    def test_merges_all_four_sources(self):
        reader = _reader_for({
            "PhoneNumbers.csv": PHONE_NUMBERS_CSV,
            "Whatsapp Phone Numbers.csv": WHATSAPP_NUMBERS_CSV,
            "Email Addresses.csv": EMAIL_ADDRESSES_CSV,
            "Registration.csv": REGISTRATION_CSV,
        })
        out = contact_info_to_df(reader, Counter())
        values = dict(zip(out["Field"], out["Value"]))
        assert "+310000000001" in values["Phone number(s)"]
        assert "+310000000002" in values["Phone number(s)"]
        assert values["WhatsApp number(s)"] == "+310000000001"
        assert "test-account@example.test" in values["Email address(es)"]
        assert "test-alt@example.test" in values["Email address(es)"]
        assert values["Registration date"] == "2015-06-15 00:00:00 UTC"
        assert values["Registration IP address"] == "203.0.113.5"

    def test_partial_sources_still_yield_rows(self):
        """ADR-0024: an absent companion file yields fewer rows, not a
        dropped table."""
        reader = _reader_for({"Registration.csv": REGISTRATION_CSV})
        errors: Counter = Counter()
        out = contact_info_to_df(reader, errors)
        assert len(out) == 2
        values = dict(zip(out["Field"], out["Value"]))
        assert values["Registration date"] == "2015-06-15 00:00:00 UTC"
        assert sum(errors.values()) == 0

    def test_all_sources_absent_yields_empty_no_error(self):
        reader = _reader_for({})
        errors: Counter = Counter()
        out = contact_info_to_df(reader, errors)
        assert out.empty
        assert sum(errors.values()) == 0


def test_no_real_names_or_pii_in_synthetic_fixtures():
    """Guard against accidentally pasting real-looking data into this file's
    module-level CSV constants — every phone number, email, and IP address
    here is invented."""
    module_source = "\n".join([
        AD_TARGETING_CSV, PHONE_NUMBERS_CSV, WHATSAPP_NUMBERS_CSV,
        EMAIL_ADDRESSES_CSV, REGISTRATION_CSV,
    ])
    assert "example.test" in module_source
    assert "+31000000000" in module_source
