"""Tests for reading the timestamps out of the Instagram html export.

Trimmed from algosoc-2026's ``test_meta_html_timestamps.py``, which also
covered Facebook: dd-education has not ported the algosoc Facebook module (a
different, un-ported ``facebook.py`` lives in this repo), so every Facebook
case — the shared ``eh.meta_html_timestamp_to_datetime_string`` reader
(Instagram wraps its own copy of the same regex instead, see
``instagram._html_timestamp``), the "clock is left alone" cases, and the
end-to-end extractor check — has been dropped along with the import of
``port.platforms.facebook``.

Instagram renders its html export at a fixed eight hours behind UTC, so its
html can be converted and made to agree with its json. That finding comes
from ``scripts/meta_html_timezone_probe.py``, which matches records held in
both export formats and reports the difference; the records below are real
pairs taken from a donated archive.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

import port.helpers.extraction_helpers as eh
from port.platforms import instagram


#: Records from a donated Instagram archive, each held in both export formats: what the
#: html shows, and the epoch the json records for the same record. They span winter and
#: summer, and three of them fall inside US daylight saving.
INSTAGRAM_PAIRS = [
    ("Aug 09, 2026 9:49 am", 1786297781),
    ("Apr 05, 2024 3:43 pm", 1712360599),
    ("Mar 11, 2026 2:49 am", 1773226198),
    ("Dec 29, 2025 1:46 pm", 1767044795),
    ("Aug 16, 2026 5:52 am", 1786888345),
]


class TestReadingTheShape:
    """The reading of the text itself."""

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_absent_timestamp_is_not_an_error(self, empty):
        errors = Counter()

        assert instagram._html_timestamp(empty, errors) == ""
        assert errors == Counter()

    @pytest.mark.parametrize("timestamp", ["nonsense", "15 mei 2026 20:30", "Xyz 26, 2026 9:05 am"])
    def test_what_cannot_be_read_is_kept_and_counted(self, timestamp):
        """Kept as it was rather than guessed at, and counted so the rate can be seen."""
        errors = Counter()

        assert instagram._html_timestamp(timestamp, errors) == timestamp
        assert errors["TimestampParseError"] == 1

    def test_the_result_reads_back_as_a_time(self):
        value = instagram._html_timestamp("Jun 26, 2026 9:05:20 am")

        assert datetime.strptime(value, eh.DATETIME_FORMAT)


class TestInstagramIsConverted:
    """Instagram renders at ``HTML_EXPORT_UTC_OFFSET``, so its html can be placed in the
    reference zone exactly."""

    @pytest.mark.parametrize("shown,epoch", INSTAGRAM_PAIRS)
    def test_the_html_lands_where_the_json_does(self, shown, epoch):
        """The point of the conversion: one record, two export formats, one answer.

        Instagram writes no seconds in the html, so the two agree to the minute.
        """
        from_html = instagram._html_timestamp(shown)
        from_json = eh.epoch_to_datetime_string(epoch)

        assert from_html[:16] == from_json[:16], f"{shown} does not land where {epoch} does"

    @pytest.mark.parametrize("shown,expected", [
        ("Aug 09, 2026 9:49 am", "2026-08-09 19:49:00"),   # summer, +2 in the reference zone
        ("Dec 29, 2025 1:46 pm", "2025-12-29 22:46:00"),   # winter, +1
    ])
    def test_the_reference_zone_keeps_its_daylight_saving(self, shown, expected):
        assert instagram._html_timestamp(shown) == expected

    @pytest.mark.parametrize("shown,epoch", [p for p in INSTAGRAM_PAIRS if p[0].startswith(("Apr", "Mar", "Aug 16"))])
    def test_the_offset_is_fixed_rather_than_us_pacific(self, shown, epoch):
        """These records fall inside US daylight saving, where Pacific stands seven hours
        behind UTC rather than eight. Reading them as Pacific would put them an hour out,
        so the conversion must not apply a daylight saving rule of its own."""
        instant = datetime.fromtimestamp(epoch, tz=timezone.utc)
        as_pacific = instant.astimezone(timezone(timedelta(hours=-7))).strftime("%I:%M %p").lower()

        assert not shown.lower().endswith(as_pacific.lstrip("0"))
        assert instagram._html_timestamp(shown)[:16] == eh.epoch_to_datetime_string(epoch)[:16]

    @pytest.mark.parametrize("shown,expected", [
        # A 12-hour clock counts midnight as 12 am and noon as 12 pm, and the shift can
        # carry a record into the next day.
        ("Dec 31, 2026 12:00:00 am", "2026-12-31 09:00:00"),
        ("Jan 01, 2026 12:30 pm", "2026-01-01 21:30:00"),
        # The meridiem is optional, so a 24-hour locale reads too.
        ("Jun 26, 2026 21:05:20", "2026-06-27 07:05:20"),
    ])
    def test_the_shape_is_read_before_it_is_shifted(self, shown, expected):
        assert instagram._html_timestamp(shown) == expected


class TestTheExtractorsUseIt:
    def test_every_html_extractor_with_a_date_column_reads_it(self):
        """A new html extractor is easy to add without converting its date, so the wiring
        is checked rather than trusted."""
        import re

        missing = []
        source = open(instagram.__file__, encoding="utf-8").read()
        for part in re.split(r"(?=\ndef )", source):
            name = part.lstrip("\n").split("(")[0].replace("def ", "").strip()
            if not name.endswith("_html"):
                continue
            # Commented-out extractors trail some of these functions, and the columns
            # they name are not columns anything produces.
            live = "\n".join(
                line for line in part.split("\n") if not line.lstrip().startswith("#")
            )
            columns = " ".join(re.findall(r"columns=\[([^\]]*)\]", live))
            converts = re.search(r"_html_timestamp\(", live)
            if re.search(r'"(Date|Timestamp)"', columns) and not converts:
                missing.append(f"instagram.{name}")

        assert missing == [], f"html extractors that do not convert their date: {missing}"
