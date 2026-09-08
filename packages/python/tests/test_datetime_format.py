"""Tests for the one datetime format the extractors write.

Ported from algosoc-2026, trimmed to the cases relevant here: Instagram is the
only platform in this repo whose extractors call this format today (its json
export writes epoch seconds, its html export a bare local string eight hours
behind UTC), so the Facebook/TikTok/Google-flavoured cases from the source
file are dropped. The helpers themselves (``resolve_timezone``,
``zone_time_to_datetime_string``, ``utc_timestamp_to_datetime_string``) are
still exercised here even where Instagram does not call them directly — they
are part of what this task ported into ``extraction_helpers``, and a future
platform is expected to reuse them rather than reinvent the format.

Every one of them writes ``YYYY-MM-DD HH:MM:SS`` in one reference zone, so
that the column would mean the same thing whichever platform a row came from.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import port.helpers.extraction_helpers as eh


AMSTERDAM = ZoneInfo("Europe/Amsterdam")


class TestTheReferenceZone:
    """The reference zone's rules come from ``zoneinfo``, the same IANA database used to
    check it here — this class exists to catch a transcription error in
    ``REFERENCE_TIMEZONE`` or ``_to_reference`` itself, not to test ``zoneinfo``."""

    @pytest.mark.parametrize("year", range(2005, 2031))
    def test_the_clocks_change_when_the_database_says_they_do(self, year):
        """Every hour of both changeover weekends, against ``zoneinfo`` itself."""
        for month in (3, 10):
            for day in range(23, 32):
                for hour in range(24):
                    moment = datetime(year, month, day, hour, tzinfo=timezone.utc)

                    assert eh._to_reference(moment) == moment.astimezone(AMSTERDAM).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ), f"{moment} is read differently from the timezone database"

    @pytest.mark.parametrize("moment,expected", [
        (datetime(2026, 1, 15, 12, tzinfo=timezone.utc), "2026-01-15 13:00:00"),  # winter, +1
        (datetime(2026, 7, 15, 12, tzinfo=timezone.utc), "2026-07-15 14:00:00"),  # summer, +2
        (datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc), "2026-03-29 01:59:00"),  # before
        (datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc), "2026-03-29 03:00:00"),  # the jump
        (datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc), "2026-10-25 02:59:00"),  # before
        (datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc), "2026-10-25 02:00:00"),  # falling back
    ])
    def test_the_hour_either_side_of_a_changeover(self, moment, expected):
        assert eh._to_reference(moment) == expected


class TestEpochTimestamps:
    """What Instagram's json export writes. Epoch seconds name an absolute instant, so
    nothing about the participant has to be assumed to place them."""

    def test_an_instant_is_placed_in_the_reference_zone(self):
        assert eh.epoch_to_datetime_string(1632139200) == "2021-09-20 14:00:00"

    def test_a_number_written_as_text_reads_the_same(self):
        assert eh.epoch_to_datetime_string("1632139200") == "2021-09-20 14:00:00"

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_absent_timestamp_is_not_an_error(self, empty):
        errors = Counter()

        assert eh.epoch_to_datetime_string(empty, errors=errors) == ""
        assert errors == Counter()

    def test_what_cannot_be_read_is_kept_and_counted(self):
        errors = Counter()

        assert eh.epoch_to_datetime_string("not a number", errors=errors) == "not a number"
        assert errors["TimestampParseError"] == 1


class TestTimestampStrings:
    """What an export that writes an ISO 8601 string, rather than epoch seconds, looks
    like — ported ahead of any platform in this repo calling it directly."""

    @pytest.mark.parametrize("timestamp", [
        "2026-05-02 10:09:50 UTC",   # the zone spelled out
        "2026-05-02 10:09:50",       # the zone left implicit (read as UTC)
        "2026-05-02T10:09:50Z",
        "2026-05-02T10:09:50.123Z",  # with a fractional second
        "2026-05-02T10:09:50+00:00",
        "2026-05-02 10:09:50 utc",
    ])
    def test_every_way_of_writing_one_utc_moment(self, timestamp):
        """All of these name the same instant, so all of them come out the same."""
        assert eh.utc_timestamp_to_datetime_string(timestamp) == "2026-05-02 12:09:50"

    def test_an_offset_that_is_named_is_honoured_rather_than_assumed(self):
        assert eh.utc_timestamp_to_datetime_string("2026-05-02T10:09:50+05:00") == "2026-05-02 07:09:50"

    def test_winter_and_summer_differ_by_the_hour_the_clocks_move(self):
        assert eh.utc_timestamp_to_datetime_string("2026-01-02 10:09:50 UTC") == "2026-01-02 11:09:50"
        assert eh.utc_timestamp_to_datetime_string("2026-05-02 10:09:50 UTC") == "2026-05-02 12:09:50"

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_absent_timestamp_is_not_an_error(self, empty):
        errors = Counter()

        assert eh.utc_timestamp_to_datetime_string(empty, errors=errors) == ""
        assert errors == Counter()

    def test_a_zone_that_cannot_be_read_is_kept_and_counted(self):
        """Rather than guessed at — an abbreviation that means several zones would move the
        activity by hours if the wrong one were picked."""
        errors = Counter()
        timestamp = "2026-05-02 10:09:50 CST"

        assert eh.utc_timestamp_to_datetime_string(timestamp, errors=errors) == timestamp
        assert errors["TimestampParseError"] == 1


class TestLocalTimes:
    """What Instagram's html export writes: a bare local time with no zone named beside
    it, at a fixed offset from UTC (see ``instagram.HTML_EXPORT_UTC_OFFSET``)."""

    def test_an_account_in_the_reference_zone_is_left_where_it_is(self):
        moment = datetime(2026, 6, 15, 20, 30, 41)

        assert eh.local_time_to_datetime_string(moment, timedelta(hours=2)) == "2026-06-15 20:30:41"

    def test_an_account_somewhere_else_is_moved_into_it(self):
        moment = datetime(2026, 8, 17, 22, 14, 48)

        assert eh.local_time_to_datetime_string(moment, timedelta(hours=3)) == "2026-08-17 21:14:48"

    def test_a_conversion_can_cross_the_day(self):
        moment = datetime(2026, 8, 18, 0, 30, 0)

        assert eh.local_time_to_datetime_string(moment, timedelta(hours=9)) == "2026-08-17 17:30:00"


class TestOneFormatAcrossTheHelpers:
    def test_the_same_moment_reads_the_same_however_it_was_written(self):
        """The point of the exercise: one instant, recorded three ways, one column value."""
        epoch = eh.epoch_to_datetime_string(1781548241)
        utc_string = eh.utc_timestamp_to_datetime_string("2026-06-15T18:30:41.000Z")
        local = eh.local_time_to_datetime_string(
            datetime(2026, 6, 15, 20, 30, 41), timedelta(hours=2)
        )

        assert epoch == "2026-06-15 20:30:41"
        assert {utc_string, local} == {epoch}

    @pytest.mark.parametrize("value", [
        eh.epoch_to_datetime_string(1781548241),
        eh.utc_timestamp_to_datetime_string("2026-06-15T18:30:41Z"),
        eh.local_time_to_datetime_string(datetime(2026, 6, 15, 20, 30, 41), timedelta(hours=2)),
    ])
    def test_the_value_reads_back_as_a_time(self, value):
        """It has to survive the round trip into pandas and R, which is the whole reason
        for choosing this shape."""
        assert datetime.strptime(value, eh.DATETIME_FORMAT) == datetime(2026, 6, 15, 20, 30, 41)

    def test_the_existing_sort_key_still_reads_the_format(self):
        """Tables are ordered newest first on these strings."""
        import pandas as pd

        column = pd.Series(["2026-06-15 20:30:41", "", "2026-06-16 20:30:41"])

        keys = eh.sort_isotimestamp_empty_timestamp_last(column)

        assert keys[2] < keys[0] < keys[1]

    def test_the_format_sorts_the_same_as_plain_text(self):
        """Fixed-width numbers throughout, so a lexicographic sort is a chronological one."""
        moments = [
            eh.epoch_to_datetime_string(epoch)
            for epoch in (1600000000, 1781548241, 1700000000, 1500000000)
        ]

        assert sorted(moments) == sorted(moments, key=lambda m: datetime.strptime(m, eh.DATETIME_FORMAT))


class TestZoneTimes:
    """A local time whose zone is named the IANA way is converted through the zone's own
    rules — daylight saving included."""

    def test_an_account_in_london_moves_an_hour_forward_in_summer(self):
        assert eh.zone_time_to_datetime_string(datetime(2025, 6, 4, 18, 46, 10), "Europe/London") == "2025-06-04 19:46:10"

    def test_and_in_winter_too(self):
        assert eh.zone_time_to_datetime_string(datetime(2025, 1, 4, 18, 46, 10), "Europe/London") == "2025-01-04 19:46:10"

    def test_the_reference_zone_itself_is_unchanged(self):
        assert eh.zone_time_to_datetime_string(datetime(2025, 6, 4, 18, 46, 10), "Europe/Amsterdam") == "2025-06-04 18:46:10"

    def test_a_zone_that_is_not_in_the_database_is_none(self):
        assert eh.resolve_timezone("Mars/Olympus_Mons") is None
        assert eh.resolve_timezone("") is None
