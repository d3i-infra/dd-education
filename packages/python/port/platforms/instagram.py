"""
Instagram

This module contains an example flow of a Instagram data donation study

Assumptions:
It handles DDPs in the english language with filetype JSON.

Timestamps
----------
Every date column is written as ``YYYY-MM-DD HH:MM:SS`` in the reference timezone named by
``extraction_helpers.REFERENCE_TIMEZONE``, so that a date means the same thing here as it
does in the TikTok, Facebook and Google tables.

The json export records epoch seconds, which name an absolute instant, so placing them in
that zone is exact.

The html export names no timezone, but it is not written in the timezone of the
participant either: it is rendered eight hours behind UTC, always. Knowing that offset is
what makes it convertible, so the two export formats now agree rather than sitting nine or
ten hours apart.

That offset was measured, not assumed. ``scripts/meta_html_timezone_probe.py`` matches
records held in both formats and reports the difference; run over two donated archives it
put every source at -8 — eight sources apiece, one archive reaching back to 2012, with no
exception anywhere. It is a *fixed* -8 rather than US Pacific, which it otherwise resembles:
records falling inside US daylight saving, where Pacific stands seven hours behind, are
eight hours behind here too, so no daylight saving rule of its own is needed.

It also belongs to Instagram rather than to the person. The Facebook export of those same
two accounts is on a different clock again — Amsterdam for one, UTC for the other — which
is why ``facebook.py`` cannot do the same thing and leaves its html clock alone.

Configuration
-------------
The ``extraction`` function is driven by ``port_config.json``.  Generate one with::

    pnpm generate-config instagram

Each extractor function carries its own table config in a ``Table config::``
JSON block inside its docstring.  The generator reads those blocks and
assembles the JSON file.

Platform info::

    {
        "name": "Instagram",
        "filetypes": ["json", "html"],
        "languages": ["en", "nl"],
        "description": "Note that supported DDP language also includes Dutch and probably other languages as well. You get an english DDP regardless of the Dutch language setting. These data donation flows have not been tested yet, if you find anything wrong with them report to datadonation@uu.nl and they will be fixed!",
        "time_last_tested": "not yet implemented"
    }
"""

import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable

from lxml import etree

import pandas as pd

import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
)
from port.api.d3i_props import ExtractionResult
from port.api.file_utils import SeekableBinaryReader
from port.helpers.table_extractor import (
    load_port_config,
    run_extraction,
)

logger = logging.getLogger(__name__)


#: Months by the first three letters of how the html export abbreviates them, lowercased,
#: across the languages it is written in that use Latin script. An account writes its export
#: in whatever language it is set to, which is not always the language of the study, so the
#: same table the Google extractor reads its html dates with is used here.
_HTML_MONTHS = {
    "jan": 1, "oca": 1, "ene": 1,
    "feb": 2, "şub": 2, "sub": 2,
    "mar": 3, "mrt": 3, "mär": 3, "mrz": 3,
    "apr": 4, "nis": 4, "abr": 4,
    "may": 5, "mei": 5, "mai": 5,
    "jun": 6, "haz": 6,
    "jul": 7, "tem": 7,
    "aug": 8, "ağu": 8, "agu": 8, "ago": 8,
    "sep": 9, "eyl": 9, "set": 9,
    "oct": 10, "okt": 10, "eki": 10,
    "nov": 11, "kas": 11,
    "dec": 12, "dez": 12, "ara": 12, "dic": 12,
}

#: ``Aug 09, 2026 9:49 am`` — how the html export writes a timestamp: the month as a word, a 12-hour
#: clock in lower case, and the seconds left off. The meridiem is optional so that a
#: 24-hour locale reads too.
_HTML_TIMESTAMP = re.compile(
    r"^([^\s\d]+)\.?\s+(\d{1,2}),?\s+(\d{4})[\s,]+(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r"(?:\s*([AaPp])\.?[Mm]\.?)?\s*$"
)


#: How far the html export stands behind UTC. It names no timezone, so this was measured
#: rather than assumed: ``scripts/meta_html_timezone_probe.py`` matched records held in both
#: export formats across two donated archives — eight sources apiece, one of them reaching
#: back to 2012 — and every one of them came out eight hours behind UTC.
#:
#: It is not the timezone of the participant. The Facebook export of the same two accounts
#: is on a different clock again (Amsterdam for one, UTC for the other), so this belongs to
#: Instagram rather than to the person or the account.
#:
#: Nor is it US Pacific, which the offset otherwise resembles. Records falling inside US
#: daylight saving, where Pacific stands seven hours behind, are eight hours behind here
#: too — so the offset is fixed and needs no daylight saving rule of its own.
HTML_EXPORT_UTC_OFFSET = timedelta(hours=-8)


def _html_timestamp(timestamp: str, errors: Counter | None = None) -> str:
    """Write a timestamp read out of the html export in the shared datetime format.

    The html names no timezone and is not written in the timezone of the participant; it is
    rendered at the fixed ``HTML_EXPORT_UTC_OFFSET`` measured above. Knowing that offset is
    what lets this column be converted like any other, so an html donation now agrees with
    a json one rather than sitting nine or ten hours away from it.

    Args:
        timestamp: Text of the date element, e.g. ``Aug 09, 2026 9:49 am``.
        errors: Optional counter that aggregates error types.

    Returns:
        str: The formatted timestamp, ``""`` for an absent one, or the input unchanged
        when it cannot be read.

    Examples::

        >>> _html_timestamp("Aug 09, 2026 9:49 am")   # 2026-08-09 17:49 UTC
        "2026-08-09 19:49:00"
    """
    if not timestamp or not isinstance(timestamp, str):
        return ""

    match = _HTML_TIMESTAMP.match(timestamp.strip())
    if match:
        month, day, year, hour, minute, second, meridiem = match.groups()
        number = _HTML_MONTHS.get(month[:3].lower())

        if number is not None:
            hour = int(hour)
            if meridiem:
                # A 12-hour clock counts noon as 12 pm and midnight as 12 am.
                hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
            try:
                moment = datetime(int(year), number, int(day), hour, int(minute), int(second or 0))
            except ValueError:
                moment = None

            if moment is not None:
                return eh.local_time_to_datetime_string(
                    moment, HTML_EXPORT_UTC_OFFSET, errors=errors
                )

    logger.error("Could not read an html timestamp: %s", timestamp)
    if errors is not None:
        errors["TimestampParseError"] += 1

    return timestamp


DDP_CATEGORIES = [
    DDPCategory(
        id="json_en",
        ddp_filetype=DDPFiletype.JSON,
        language=Language.EN,
        known_files=[
            "secret_conversations.json",
            "personal_information.json",
            "account_privacy_changes.json",
            "account_based_in.json",
            "recently_deleted_content.json",
            "liked_posts.json",
            "stories.json",
            "profile_photos.json",
            "followers.json",
            "signup_information.json",
            "comments_allowed_from.json",
            "login_activity.json",
            "your_topics.json",
            "camera_information.json",
            "recent_follow_requests.json",
            "devices.json",
            "professional_information.json",
            "follow_requests_you've_received.json",
            "eligibility.json",
            "pending_follow_requests.json",
            "videos_watched.json",
            "ads_viewed.json",
            "ads_clicked.json",
            "ads_interests.json",
            "account_searches.json",
            "profile_searches.json",
            "followers_1.json",
            "saved_posts.json",
            "following.json",
            "posts_viewed.json",
            "post_comments_1.json",
            "recently_unfollowed_accounts.json",
            "post_comments.json",
            "account_information.json",
            "accounts_you're_not_interested_in.json",
            "liked_comments.json",
            "story_likes.json",
            "threads_viewed.json",
            "use_cross-app_messaging.json",
            "profile_changes.json",
            "reels.json",
        ],
    ),
    DDPCategory(
        id="html_en",
        ddp_filetype=DDPFiletype.HTML,
        language=Language.EN,
        known_files=[
            "ads_viewed.html",
            "ads_clicked.html",
            "followers_1.html",
            "following.html", 
            "follow_requests_you've_received.html", 
            "recent_follow_requests.html", 
            "recently_unfollowed_profiles.html", 
            "removed_suggestions.html", 
            "posts_viewed.html", 
            "posts_you're_not_interested_in.html", 
            "videos_watched.html", 
            "advertisers_using_your_activity_or_information.html", 
            "other_categories_used_to_reach_you.html", 
            "word_or_phrase_searches.html", 
            "camera_information.html", 
            "locations_of_interest.html", 
            "profile_based_in.html", 
            "account_supervision.html", 
            "instagram_profile_information.html", 
            "note_and_repost_interactions.html", 
            "personal_information.html", 
            "last_known_location.html", "login_activity.html", 
            "profile_activity.html", 
            "signup_details.html", 
            "post_comments_1.html", 
            "liked_comments.html", 
            "liked_posts.html", 
            "profile_photos.html", 
            "stories.html", 
            "chats.html", 
            "secret_conversations.html", 
            "eligibility.html", 
            "surveys.html", 
            "your_information_download_requests.html", 
            "saved_music.html", 
            "saved_posts.html", 
            "checkout_payment_information.html", 
            "recently_viewed_items.html", 
            "polls.html", 
            "stories_viewed.html", 
            "story_likes.html", 
            "start_here.html",
        ],
    ),
]



# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _sort_by_date(out: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Sort *out* by *date_column* using ISO-timestamp ordering.

    Parameters
    ----------
    out:
        DataFrame to sort.
    date_column:
        Name of the column that contains ISO-formatted timestamp strings.
        Rows with empty timestamps are placed last.
    """
    return out.sort_values(by=date_column, key=eh.sort_isotimestamp_empty_timestamp_last)


def _naive_local_datetime(timestamp: str) -> datetime | None:
    """Parse an html-style local timestamp string into a naive ``datetime``, ignoring
    timezone.

    ``link_history.json`` writes its per-visit start/end times in this same
    ``Aug 26, 2026 4:59:34am`` shape the html export uses, but at a different,
    unmeasured offset from UTC (a spot check against the file's own epoch
    ``timestamp`` field put it near UTC-7, not the html export's measured
    UTC-8 — a different field, on a different clock). Rather than guess at a
    second offset, this is used only to take the *difference* between two such
    strings from the same item, which is offset-independent as long as both
    fall on the same local day.

    Returns ``None`` when the string cannot be parsed.
    """
    if not timestamp or not isinstance(timestamp, str):
        return None

    match = _HTML_TIMESTAMP.match(timestamp.strip())
    if not match:
        return None

    month, day, year, hour, minute, second, meridiem = match.groups()
    number = _HTML_MONTHS.get(month[:3].lower())
    if number is None:
        return None

    hour = int(hour)
    if meridiem:
        hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
    try:
        return datetime(int(year), number, int(day), hour, int(minute), int(second or 0))
    except ValueError:
        return None


def _first_present(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Return the first dict value found for the given keys, or empty dict.

    Parameters
    ----------
    data:
        Dictionary to search.
    keys:
        Ordered list of keys to try; the value of the first key whose
        corresponding value is a ``dict`` is returned.
    """
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _extract_owner_details(label_values: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Extract ``(owner_name, owner_username, url)`` from a nested label_values structure.

    This structure is used in newer Instagram export formats.

    Parameters
    ----------
    label_values:
        Nested list/dict structure from the Instagram DDP containing labelled
        metadata fields such as ``"Name"``, ``"Username"``, and ``"URL"``.

    Returns
    -------
    tuple[str, str, str]
        A three-tuple of ``(owner_name, owner_username, url)``.  Any field
        not found in *label_values* is returned as an empty string.
    """
    owner_name = ""
    owner_username = ""
    url = ""

    def visit(node: Any) -> None:
        nonlocal owner_name, owner_username, url

        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if not isinstance(node, dict):
            return

        label = str(node.get("label", ""))
        value = str(node.get("value", ""))
        href = str(node.get("href", ""))

        if label == "URL" and not url:
            url = href or value
        elif label in {"Naam", "Name"} and not owner_name:
            owner_name = eh.fix_latin1_string(value)
        elif label in {"Gebruikersnaam", "Username", "Author"} and not owner_username:
            owner_username = eh.fix_latin1_string(value)

        for child in node.values():
            visit(child)

    visit(label_values)
    return owner_name, owner_username, url


def _extract_owner_from_html(section) -> tuple[str, str]:
    """Extract ``(owner_name, owner_username)`` from an HTML Owner subsection.

    Looks for an ``<h2>Owner</h2>`` inside *section*, then reads the
    innermost ``<table>`` (one without nested tables) to find the
    ``Name`` and ``Username`` rows.

    Returns ``("", "")`` when no Owner block is found.
    """
    owner_h2 = section.xpath('.//h2[text()="Owner"]')
    if not owner_h2:
        return "", ""
    owner_div = owner_h2[0].getparent()
    tables = owner_div.xpath('.//table[not(.//table)]')
    name = ""
    username = ""
    for table in tables:
        for tr in table.xpath('.//tr'):
            tds = tr.xpath('td')
            if len(tds) == 2:
                label = tds[0].text.strip() if tds[0].text else ""
                value = tds[1].text.strip() if tds[1].text else ""
                if label == "Name" and not name:
                    name = value
                elif label == "Username" and not username:
                    username = value
    return name, username


# ---------------------------------------------------------------------------
# Per-table extraction functions
# ---------------------------------------------------------------------------
# Ordered to match the algosoc-2026 extraction list.
# Extractors not in the list are commented out at the end.
# Missing extractors are marked with TODO comments.
# ---------------------------------------------------------------------------

def followers_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "followers_1.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the list of followers into a DataFrame.

    Handles both the newer bare top-level list format and the older format
    where entries are wrapped under a ``"relationships_followers"`` key.

    Json-only: the html export does not carry an equivalent page, so
    *validation* is accepted (for calling-convention parity with the rest of
    the registry, whose extractors all take it) but ignored.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"followers_1.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one account that follows the participant on Instagram, including when they started following.",
          "source_file": "followers_1.json",
          "columns": {
            "Account": "Username or display name of the follower account.",
            "URL": "Direct URL to the follower's Instagram profile.",
            "Date": "ISO 8601 timestamp of when the account started following the participant."
          }
        }

    Table config::

        {
          "id": "instagram_followers",
          "title": {"en": "Your Instagram followers", "nl": "Je Instagram-volgers"},
          "description": {
            "en": "List of accounts that follow you on Instagram.",
            "nl": "Lijst van accounts die jou op Instagram volgen."
          },
          "headers": {
            "Account": {"en": "Account", "nl": "Account"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data.get("relationships_followers", [])
        else:
            items = data  # pyright: ignore

        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "value") or eh.find_item(d, "title")),
                eh.find_item(d, "href"),
                eh.epoch_to_datetime_string(eh.find_item(d, "timestamp"), errors=errors),
            ))
        out = pd.DataFrame(datapoints, columns=["Account", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def following_to_df(reader: ZipArchiveReader, errors: Counter, validation=None) -> pd.DataFrame:
    """Extract the list of followed accounts into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one account that the participant follows on Instagram, including when they started following.",
          "source_file": "following.json / following.html",
          "columns": {
            "Account": "Username or display name of the followed account.",
            "URL": "Direct URL to the followed account's Instagram profile.",
            "Date": "ISO 8601 timestamp of when the participant started following this account."
          }
        }

    Table config::

        {
          "id": "instagram_following",
          "title": {
            "en": "Followed Accounts",
            "nl": "Gevolgde Accounts"
          },
          "description": {
            "en": "In this table, you find the accounts that you follow on Instagram.",
            "nl": "In deze tabel zie je de accounts die je volgt op Instagram."
          },
          "headers": {
            "Account": {"en": "Account", "nl": "Account"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _following_html(reader, errors)

    return _following_json(reader, errors)


def _following_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("following.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["relationships_following"]  # pyright: ignore
        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "title") or eh.find_item(d, "value")),
                eh.find_item(d, "href"),
                eh.epoch_to_datetime_string(eh.find_item(d, "timestamp"), errors=errors),
            ))
        out = pd.DataFrame(datapoints, columns=["Account", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _following_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("following.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            h2 = section.xpath(".//h2")
            account = h2[0].text.strip() if h2 and h2[0].text else ""

            a = section.xpath(".//a[@href]")
            url = a[0].get("href", "") if a else ""

            # Timestamp is the div sibling after the <a> link
            date_divs = section.xpath(".//div[contains(@class, '_a6-p')]//div[not(@class) and not(div) and not(a)]")
            timestamp = ""
            for d in date_divs:
                if d.text and d.text.strip():
                    timestamp = _html_timestamp(d.text.strip(), errors)
                    break

            datapoints.append((account, url, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Account", "URL", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def posts_viewed_to_df(reader: ZipArchiveReader, errors: Counter, validation=None) -> pd.DataFrame:
    """Extract the list of viewed posts into a DataFrame.

    Handles both the older ``string_map_data`` format (dict root keyed by
    ``"impressions_history_posts_seen"``) and the newer ``label_values``
    list-at-root format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Author``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post that appeared in the participant's Instagram feed and was registered as viewed. Captures the author and timing of each impression.",
          "source_file": "posts_viewed.json / posts_viewed.html",
          "columns": {
            "Author": "Username or display name of the account that published the viewed post.",
            "URL": "Direct URL to the viewed post.",
            "Date": "ISO 8601 timestamp of when the post was viewed."
          }
        }

    Table config::

        {
          "id": "instagram_posts_viewed",
          "title": {
            "en": "Posts viewed on Instagram",
            "nl": "Berichten bekeken op Instagram"
          },
          "description": {
            "en": "In this table you find the accounts of posts you viewed on Instagram sorted over time. Below, you find visualizations of different parts of this table. First, you find a timeline showing you the number of posts you viewed over time. Next, you find a histogram indicating how many posts you have viewed per hour of the day.",
            "nl": "In deze tabel zie je de accounts van berichten die je op Instagram hebt bekeken, gesorteerd op tijd. Hieronder vind je visualisaties van verschillende onderdelen van deze tabel. Eerst zie je een tijdlijn met het aantal berichten dat je in de loop van de tijd hebt bekeken. Daarna zie je een histogram dat aangeeft hoeveel berichten je per uur van de dag hebt bekeken."
          },
          "headers": {
            "Author": {"en": "Author", "nl": "Account"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          },
          "visualizations": [
            {
              "title": {
                "en": "The total number of Instagram posts you viewed over time",
                "nl": "Het totale aantal Instagram-berichten dat je in de loop van de tijd hebt bekeken"
              },
              "type": "area",
              "group": {"column": "Date", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"label": {"en": "Number of posts", "nl": "Aantal berichten"}, "aggregate": "count"}]
            },
            {
              "title": {
                "en": "The total number of Instagram posts you have viewed per hour of the day",
                "nl": "Het totale aantal Instagram-berichten dat je per uur van de dag hebt bekeken"
              },
              "type": "bar",
              "group": {"column": "Date", "dateFormat": "hour_cycle", "label": {"en": "Hour of the day", "nl": "Uur van de dag"}},
              "values": [{"label": {"en": "Number of posts", "nl": "Aantal berichten"}}]
            }
          ]
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _posts_viewed_html(reader, errors)

    return _posts_viewed_json(reader, errors)


def _posts_viewed_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("posts_viewed.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["impressions_history_posts_seen"]  # pyright: ignore
            for item in items:
                string_map_data = item.get("string_map_data", {})
                author = _first_present(string_map_data, ["Author", "Auteur"])
                time = _first_present(string_map_data, ["Time", "Tijd"])
                url = _first_present(string_map_data, ["URL"])
                datapoints.append((
                    eh.fix_latin1_string(str(author.get("value", ""))),
                    url.get("href", ""),
                    eh.epoch_to_datetime_string(time.get("timestamp", ""), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    url,
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Author", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _posts_viewed_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("posts_viewed.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            name, username = _extract_owner_from_html(section)
            author = username or name

            url_a = section.xpath(".//td[contains(@class, '_a6_q') and starts-with(text(), 'URL')]//a")
            url = url_a[0].get("href", "") if url_a else ""

            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((author, url, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Author", "URL", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def videos_watched_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract the list of watched videos into a DataFrame.

    Handles both the older ``string_map_data`` format (dict root keyed by
    ``"impressions_history_videos_watched"``) and the newer ``label_values``
    list-at-root format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Author``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one video (including Reels) that the participant watched on Instagram. Captures the creator and timing of each view event.",
          "source_file": "videos_watched.json / videos_watched.html",
          "columns": {
            "Author": "Username or display name of the account that published the watched video.",
            "URL": "Direct URL to the watched video.",
            "Date": "ISO 8601 timestamp of when the video was watched."
          }
        }

    Table config::

        {
          "id": "instagram_videos_watched",
          "title": {
            "en": "Videos watched on Instagram",
            "nl": "Video's bekeken op Instagram"
          },
          "description": {
            "en": "In this table you find the accounts of videos you watched on Instagram sorted over time. Below, you find a timeline showing you the number of videos you watched over time.",
            "nl": "In deze tabel zie je de accounts van video's die je op Instagram hebt bekeken, gesorteerd op tijd. Hieronder zie je een tijdlijn met het aantal video's dat je in de loop van de tijd hebt bekeken."
          },
          "headers": {
            "Author": {"en": "Author", "nl": "Account"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          },
          "visualizations": [
            {
              "title": {
                "en": "The total number of videos watched on Instagram over time",
                "nl": "Het totale aantal video's dat je op Instagram hebt bekeken in de loop van de tijd"
              },
              "type": "area",
              "group": {"column": "Date", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Videos watched", "nl": "Bekeken video's"}}]
            }
          ]
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _videos_watched_html(reader, errors)
    return _videos_watched_json(reader, errors)


def _videos_watched_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("videos_watched.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["impressions_history_videos_watched"]  # pyright: ignore
            for item in items:
                string_map_data = item.get("string_map_data", {})
                author = _first_present(string_map_data, ["Author", "Auteur"])
                time = _first_present(string_map_data, ["Time", "Tijd"])
                url = _first_present(string_map_data, ["URL"])
                datapoints.append((
                    eh.fix_latin1_string(str(author.get("value", ""))),
                    url.get("href", ""),
                    eh.epoch_to_datetime_string(time.get("timestamp", ""), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    url,
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Author", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _videos_watched_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("videos_watched.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            name, username = _extract_owner_from_html(section)
            author = username or name

            url_a = section.xpath(".//td[contains(@class, '_a6_q') and starts-with(text(), 'URL')]//a")
            url = url_a[0].get("href", "") if url_a else ""

            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((author, url, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Author", "URL", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def post_comments_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract all post comments across multiple matching files into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Comment``, ``Media owner``, ``Date``.
        Empty DataFrame when no matching files are found or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one comment the participant posted on an Instagram post. Covers all matching comment files in the archive (e.g. post_comments.json, post_comments_1.json).",
          "source_file": "post_comments*.json / post_comments*.html",
          "columns": {
            "Comment": "The full text of the comment posted by the participant.",
            "Media owner": "Username of the account that owns the post the comment was placed on.",
            "Date": "ISO 8601 timestamp of when the comment was posted."
          }
        }

    Table config::

        {
          "id": "instagram_post_comments",
          "title": {
            "en": "Comments posted on Instagram",
            "nl": "Reacties geplaatst op Instagram"
          },
          "description": {
            "en": "List of comments you posted on Instagram.",
            "nl": "Lijst van reacties die je op Instagram hebt geplaatst."
          },
          "headers": {
            "Comment": {"en": "Comment", "nl": "Reactie"},
            "Media owner": {"en": "Media owner", "nl": "Account"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _post_comments_html(reader, errors)
    return _post_comments_json(reader, errors)


def _post_comments_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    out = pd.DataFrame()
    datapoints = []

    try:
        results = reader.json_all(r"(^|/)post_comments(?:_\d+)?\.json$")

        if not results:
            return pd.DataFrame()

        for result in results:
            data = result.data
            if isinstance(data, list):
                items = data
            elif "string_map_data" in data:
                items = [data]
            else:
                items = data.get("comments_media_comments", [])
            for item in items:  # pyright: ignore[assignment]
                string_map_data = item.get("string_map_data", {})
                comment = _first_present(string_map_data, ["Comment", "Opmerking"])
                owner = _first_present(string_map_data, ["Media Owner", "Media-eigenaar"])
                time = _first_present(string_map_data, ["Time", "Tijd"])
                datapoints.append((
                    eh.fix_latin1_string(str(comment.get("value", ""))),
                    eh.fix_latin1_string(str(owner.get("value", ""))),
                    eh.epoch_to_datetime_string(time.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Comment", "Media owner", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _post_comments_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    results = reader.raw_all(r"(^|/)post_comments(?:_\d+)?\.html$")
    if not results:
        return pd.DataFrame()

    datapoints = []

    try:
        for result in results:
            tree = etree.HTML(result.data.read())

            sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
            for section in sections:
                comment = ""
                media_owner = ""
                timestamp = ""

                tds = section.xpath(".//td[contains(@class, '_a6_q')]")
                for td in tds:
                    label = td.text.strip() if td.text else ""
                    if label == "Comment":
                        val_div = td.xpath(".//div/div")
                        comment = val_div[0].text.strip() if val_div and val_div[0].text else ""
                    elif label == "Media Owner":
                        val_div = td.xpath(".//div/div")
                        media_owner = val_div[0].text.strip() if val_div and val_div[0].text else ""
                    elif label == "Time":
                        sibling = td.getnext()
                        if sibling is not None and sibling.text:
                            timestamp = _html_timestamp(sibling.text.strip(), errors)

                datapoints.append((comment, media_owner, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Comment", "Media owner", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def liked_comments_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract the list of liked comments into a DataFrame.

    Handles both the older ``string_list_data`` format (dict root keyed by
    ``"likes_comment_likes"``) and the newer ``label_values`` list-at-root
    format.  Note that the comment text is not available in the newer format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account name``, ``Value``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one comment the participant liked on Instagram. Comment text may be absent in newer export formats.",
          "source_file": "liked_comments.json / liked_comments.html",
          "columns": {
            "Account name": "Username of the account whose comment was liked.",
            "Value": "Text of the liked comment, if available in the export (empty in newer export formats).",
            "Date": "ISO 8601 timestamp of when the comment was liked."
          }
        }

    Table config::

        {
          "id": "instagram_liked_comments",
          "title": {
            "en": "Instagram liked comments",
            "nl": "Instagram-reacties die je leuk vond"
          },
          "description": {
            "en": "List of comments that you liked on Instagram.",
            "nl": "Lijst van reacties die je leuk vond op Instagram."
          },
          "headers": {
            "Account name": {"en": "Account name", "nl": "Account"},
            "Value": {"en": "Comment", "nl": "Reactie"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _liked_comments_html(reader, errors)
    return _liked_comments_json(reader, errors)


def _liked_comments_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("liked_comments.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["likes_comment_likes"]  # pyright: ignore
            for item in items:
                entry = item.get("string_list_data", [{}])[0]
                datapoints.append((
                    eh.fix_latin1_string(item.get("title", "")),
                    eh.fix_latin1_string(entry.get("value", "")),
                    eh.epoch_to_datetime_string(entry.get("timestamp", ""), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    "",  # comment text not available in label_values format
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Account name", "Value", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _liked_comments_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("liked_comments.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            h2 = section.xpath(".//h2")
            account_name = h2[0].text.strip() if h2 and h2[0].text else ""

            # Value is the link text (e.g. thumbs up emoji)
            a = section.xpath(".//a")
            value = a[0].text.strip() if a and a[0].text else ""

            # Timestamp is the plain div after the <a> link
            date_divs = section.xpath(".//div[contains(@class, '_a6-p')]//div[not(@class) and not(div) and not(a)]")
            timestamp = ""
            for d in date_divs:
                if d.text and d.text.strip():
                    timestamp = _html_timestamp(d.text.strip(), errors)
                    break

            datapoints.append((account_name, value, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Account name", "Value", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def liked_posts_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract the list of liked posts into a DataFrame.

    Handles both the older ``dict_denester`` format (dict root keyed by
    ``"likes_media_likes"``) and the newer ``label_values`` list-at-root
    format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account name``, ``Value``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post the participant liked on Instagram, including the account whose post was liked and when the like was given.",
          "source_file": "liked_posts.json / liked_posts.html",
          "columns": {
            "Account name": "Username of the account whose post was liked.",
            "Value": "Display name or additional label for the liked post, depending on export format.",
            "Date": "ISO 8601 timestamp of when the post was liked."
          }
        }

    Table config::

        {
          "id": "instagram_liked_posts",
          "title": {
            "en": "Instagram liked posts",
            "nl": "Instagram-berichten die je leuk vond"
          },
          "description": {"en": "This table shows posts you liked on Instagram, including the account whose post was liked and when the like was given.", "nl": "In deze tabel ziet u de Instagram-berichten die u leuk vond, met de account die het bericht plaatste."},
          "headers": {
            "Account name": {"en": "Account name", "nl": "Account"},
            "Value": {"en": "Display name", "nl": "Weergavenaam"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          },
          "visualizations": [
            {
              "title": {"en": "Most liked accounts", "nl": "Meest gelikete accounts"},
              "type": "wordcloud",
              "textColumn": "Account name",
              "tokenize": false
            }
          ]
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _liked_posts_html(reader, errors)
    return _liked_posts_json(reader, errors)


def _liked_posts_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("liked_posts.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["likes_media_likes"]  # pyright: ignore
            for item in items:
                d = eh.dict_denester(item)
                datapoints.append((
                    eh.fix_latin1_string(eh.find_item(d, "title")),
                    eh.fix_latin1_string(eh.find_item(d, "value")),
                    eh.epoch_to_datetime_string(eh.find_item(d, "timestamp"), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    owner_name,
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Account name", "Value", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _liked_posts_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("liked_posts.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            name, username = _extract_owner_from_html(section)
            account_name = username or name

            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((account_name, name, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Account name", "Value", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def story_likes_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract the list of liked stories into a DataFrame.

    Handles both the older ``string_list_data`` format (dict root keyed by
    ``"story_activities_story_likes"``) and the newer ``label_values``
    list-at-root format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account name``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one Instagram Story the participant liked, recording the account whose story was liked and when.",
          "source_file": "story_likes.json / story_likes.html",
          "columns": {
            "Account name": "Username of the account whose story was liked.",
            "Date": "ISO 8601 timestamp of when the story was liked."
          }
        }

    Table config::

        {
          "id": "instagram_story_likes",
          "title": {"en": "Liked Stories", "nl": "Gelikete Stories"},
          "description": {
            "en": "List of Instagram stories you liked.",
            "nl": "Lijst van Instagram-stories die je leuk vond."
          },
          "headers": {
            "Account name": {"en": "Account name", "nl": "Account"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _story_likes_html(reader, errors)
    return _story_likes_json(reader, errors)


def _story_likes_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("story_likes.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["story_activities_story_likes"]  # pyright: ignore
            for item in items:
                entry = item.get("string_list_data", [{}])[0]
                datapoints.append((
                    eh.fix_latin1_string(item.get("title", "")),
                    eh.epoch_to_datetime_string(entry.get("timestamp", ""), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, _ = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Account name", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _story_likes_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("story_likes.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            name, username = _extract_owner_from_html(section)
            account_name = username or name

            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((account_name, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Account name", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def saved_posts_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract the list of saved posts into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Caption``, ``URL``, ``Username``, ``Hashtags``, ``Timestamp``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post the participant bookmarked (saved) on Instagram for later viewing.",
          "source_file": "saved_posts.json / saved_posts.html",
          "columns": {
            "Caption": "Caption text of the saved post.",
            "URL": "URL linking to the saved post.",
            "Username": "Username of the account that created the saved post.",
            "Hashtags": "Space-separated hashtags associated with the saved post, or 'Geen hashtags' if none.",
            "Timestamp": "ISO 8601 timestamp of when the post was saved."
          }
        }

    Table config::

        {
          "id": "instagram_saved_posts",
          "title": {
            "en": "Saved posts",
            "nl": "Opgeslagen berichten"
          },
          "description": {
            "en": "List of posts you have saved on Instagram.",
            "nl": "Lijst van berichten die je hebt opgeslagen op Instagram."
          },
          "headers": {
            "Caption": {"en": "Caption", "nl": "Bijschrift"},
            "URL": {"en": "URL", "nl": "URL"},
            "Username": {"en": "Username", "nl": "Account"},
            "Hashtags": {"en": "Hashtags", "nl": "Hashtags"},
            "Timestamp": {"en": "Timestamp", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _saved_posts_html(reader, errors)
    return _saved_posts_json(reader, errors)


def _saved_posts_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("saved_posts.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data if isinstance(data, list) else data.get("saved_saved_media", [])  # pyright: ignore
        for item in items:
            caption = ""
            url = ""
            username = ""
            hashtags = ""
            timestamp_source = item.get("timestamp", "")

            if "label_values" in item:
                # Newer schema: a label_values list, either flat {"label",
                # "value"} pairs or nested {"dict": [...], "title": "..."}
                # groups. Caption/URL/Username/Hashtags all come from here;
                # the item-level "timestamp" set above is correct for this
                # schema.
                for lv in item.get("label_values", []):
                    if "value" in lv:
                        # Flavour 1: {"label": "...", "value": "..."}
                        label = lv.get("label", "")
                        value = eh.fix_latin1_string(lv.get("value", ""))
                        if label == "Caption":
                            caption = value
                        elif label == "URL":
                            url = value
                        elif label == "Username":
                            username = value
                    elif "dict" in lv:
                        # Flavour 2: {"dict": [...], "title": "..."}
                        title = lv.get("title", "")
                        if title == "Hashtags":
                            dict_list = lv.get("dict", [])
                            tags = []
                            for dict_item in dict_list:
                                denested = eh.dict_denester(dict_item)
                                tag = eh.find_item(denested, "value")
                                if tag:
                                    tags.append(eh.fix_latin1_string(tag))
                            hashtags = " ".join(tags) if tags else "Geen hashtags"
                        elif title == "Owner":
                            dict_list = lv.get("dict", [])
                            for dict_item in dict_list:
                                for inner in dict_item.get("dict", []):
                                    if inner.get("label") == "Username":
                                        username = eh.fix_latin1_string(inner.get("value", ""))
            else:
                # Older schema (upstream, pre-algosoc): a bare "title" plus
                # either "string_list_data" (a one-entry list carrying href
                # and timestamp) or "string_map_data" (keyed by a "Saved
                # on"/"Opgeslagen op" entry with the same two fields).
                # Neither older shape carries a username or hashtags, so
                # those stay blank/"Geen hashtags" as they always did for
                # this schema — only Caption, URL and Timestamp are
                # available. Restored from `git show
                # 0c4412a:packages/python/port/platforms/instagram.py`
                # (upstream's saved_posts_to_df) so an older-schema donor
                # doesn't silently lose Caption/URL to a label_values-shaped
                # empty read.
                caption = eh.fix_latin1_string(item.get("title", ""))
                if "string_list_data" in item:
                    string_list = item.get("string_list_data", [{}])
                    entry = string_list[0] if string_list else {}
                else:
                    entry = _first_present(item.get("string_map_data", {}), ["Saved on", "Opgeslagen op"])
                url = entry.get("href", "")
                timestamp_source = entry.get("timestamp", "")

            if not hashtags:
                hashtags = "Geen hashtags"

            datapoints.append((
                caption,
                url,
                username,
                hashtags,
                eh.epoch_to_datetime_string(timestamp_source, errors=errors),
            ))
        out = pd.DataFrame(datapoints, columns=["Caption", "URL", "Username", "Hashtags", "Timestamp"])  # pyright: ignore
        out = _sort_by_date(out, "Timestamp")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _saved_posts_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("saved_posts.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            # URL
            url_a = section.xpath(".//td[contains(@class, '_a6_q') and starts-with(text(), 'URL')]//a")
            url = url_a[0].get("href", "") if url_a else ""

            # Caption
            caption_tds = section.xpath(".//td[contains(@class, '_a6_q') and text()='Caption']")
            caption = ""
            if caption_tds:
                sibling = caption_tds[0].getnext()
                if sibling is not None and sibling.text:
                    caption = sibling.text.strip()

            # Owner username
            _, username = _extract_owner_from_html(section)

            # Hashtags
            hashtags = "Geen hashtags"
            hashtag_h2 = section.xpath('.//h2[text()="Hashtags"]')
            if hashtag_h2:
                hashtag_div = hashtag_h2[0].getparent()
                tag_divs = hashtag_div.xpath('.//div[contains(@class, "_a6-p")]')
                tags = [t.text.strip() for t in tag_divs if t.text and t.text.strip()]
                if tags:
                    hashtags = " ".join(tags)

            # Timestamp
            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((caption, url, username, hashtags, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Caption", "URL", "Username", "Hashtags", "Timestamp"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# RECREATED FROM algosoc-dd-old — NEEDS MANUAL VERIFICATION
# Source: algosoc-dd-old/src/framework/processing/py/port/instagram.py parse_searches()
# ---------------------------------------------------------------------------
def word_or_phrase_searches_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract keyword searches into a DataFrame.

    Reads the older ``string_map_data`` format keyed by
    ``"searches_keyword"``.  Each entry contains a search term and timestamp.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Search term``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one keyword or phrase search the participant performed on Instagram.",
          "source_file": "word_or_phrase_searches.json / word_or_phrase_searches.html",
          "columns": {
            "Search term": "The word or phrase that was searched for.",
            "Date": "ISO 8601 timestamp of when the search was performed."
          }
        }

    Table config::

        {
          "id": "instagram_word_or_phrase_searches",
          "title": {
            "en": "Searches",
            "nl": "Zoekopdrachten"
          },
          "description": {
            "en": "List of words or phrases you have searched for on Instagram.",
            "nl": "Lijst van woorden of zinnen die je op Instagram hebt gezocht."
          },
          "headers": {
            "Search term": {"en": "Search term", "nl": "Zoekterm"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _word_or_phrase_searches_html(reader, errors)
    return _word_or_phrase_searches_json(reader, errors)


def _word_or_phrase_searches_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("word_or_phrase_searches.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data.get("searches_keyword", [])
        else:
            items = data  # pyright: ignore

        for item in items:
            string_map_data = item.get("string_map_data", {})
            # The English, Dutch and German keys come from real DDPs; the Spanish,
            # Arabic, Turkish and Chinese ones are derived from Instagram's own
            # translations and have not been checked against a real export yet.
            search = _first_present(string_map_data, [
                "Search", "Zoekopdracht", "Zoeken", "Suche",
                "Búsqueda", "Buscar",
                "بحث", "البحث",
                "Arama", "Ara",
                "搜索", "搜索内容",
            ])
            time = _first_present(string_map_data, [
                "Time", "Tijd", "Datum/Uhrzeit der Suche", "Uhrzeit",
                "Hora", "Fecha y hora",
                "الوقت", "التاريخ والوقت",
                "Saat", "Zaman",
                "时间", "日期和时间",
            ])
            datapoints.append((
                eh.fix_latin1_string(str(search.get("value", ""))),
                eh.epoch_to_datetime_string(time.get("timestamp", ""), errors=errors),
            ))

        out = pd.DataFrame(datapoints, columns=["Search term", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _word_or_phrase_searches_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("word_or_phrase_searches.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            search_term = ""
            timestamp = ""

            tds = section.xpath(".//td[contains(@class, '_a6_q')]")
            for td in tds:
                label = td.text.strip() if td.text else ""
                if label == "Search":
                    val_div = td.xpath(".//div/div")
                    search_term = val_div[0].text.strip() if val_div and val_div[0].text else ""
                elif label == "Time":
                    sibling = td.getnext()
                    if sibling is not None and sibling.text:
                        timestamp = _html_timestamp(sibling.text.strip(), errors)

            datapoints.append((search_term, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Search term", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def stories_published_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract published stories into a DataFrame.

    Reads the ``"ig_stories"`` key from the JSON.  Each entry contains a
    title and a ``creation_timestamp``.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Text``, ``Media type``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one Instagram Story published by the participant.",
          "source_file": "stories.json / stories.html",
          "columns": {
            "Text": "Caption or text of the story, or 'Story has no text' when empty.",
            "Media type": "File extension of the story media asset (e.g. .jpg, .mp4).",
            "Date": "ISO 8601 timestamp of when the story was created."
          }
        }

    Table config::

        {
          "id": "instagram_stories_published",
          "title": {
            "en": "Published stories",
            "nl": "Geplaatste stories"
          },
          "description": {
            "en": "List of stories you have published on Instagram.",
            "nl": "Lijst van stories die je op Instagram hebt geplaatst."
          },
          "headers": {
            "Text": {"en": "Text", "nl": "Tekst"},
            "Media type": {"en": "File type", "nl": "Bestandstype"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _stories_published_html(reader, errors)
    return _stories_published_json(reader, errors)


def _stories_published_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("stories.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data.get("ig_stories", [])
        else:
            items = data  # pyright: ignore

        for item in items:
            title = eh.fix_latin1_string(item.get("title", ""))
            if not title:
                title = "Story zonder tekst"
            uri = item.get("uri", "")
            ext = os.path.splitext(uri)[1] if uri else ""
            datapoints.append((
                title,
                ext,
                eh.epoch_to_datetime_string(item.get("creation_timestamp", ""), errors=errors),
            ))

        out = pd.DataFrame(datapoints, columns=["Text", "Media type", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _stories_published_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("stories.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            # URI from media link
            a = section.xpath(".//a[@href]")
            uri = a[0].get("href", "") if a else ""
            ext = os.path.splitext(uri)[1] if uri else ""

            # Title
            title_h2 = section.xpath(".//h2[contains(@class, '_a6-h') and contains(@class, '_a6-i')]")
            title = title_h2[0].text.strip() if title_h2 and title_h2[0].text else ""
            if not title:
                title = "Story zonder tekst"

            # Timestamp
            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((title, ext, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Text", "Media type", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# RECREATED FROM algosoc-dd-old — NEEDS MANUAL VERIFICATION
# Source: algosoc-dd-old/src/framework/processing/py/port/instagram.py parse_advertisers_using_activity()
# ---------------------------------------------------------------------------
def advertisers_using_activity_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    validation=None,
) -> pd.DataFrame:
    """Extract advertisers using participant activity into a DataFrame.

    Handles the newer ``label_values`` format where advertisers are grouped
    under category labels, and the older format keyed by
    ``"ig_custom_audiences_all_types"``.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Advertiser``, ``Category``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one advertiser that used the participant's activity or information to target them on Instagram.",
          "source_file": "advertisers_using_your_activity_or_information.json / advertisers_using_your_activity_or_information.html",
          "columns": {
            "Advertiser": "Name of the advertiser.",
            "Category": "Category describing how the advertiser used the participant's data."
          }
        }

    Table config::

        {
          "id": "instagram_advertisers_using_activity",
          "title": {
            "en": "Advertisers using your activity or information",
            "nl": "Adverteerders die je activiteit of informatie gebruiken"
          },
          "description": {
            "en": "List of advertisers that used your activity or information to reach you on Instagram.",
            "nl": "Lijst van adverteerders die je activiteit of informatie hebben gebruikt om je te bereiken op Instagram."
          },
          "headers": {
            "Advertiser": {"en": "Advertiser", "nl": "Adverteerder"},
            "Category": {"en": "How they reached you", "nl": "Hoe zij u bereikten"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _advertisers_using_activity_html(reader, errors)
    return _advertisers_using_activity_json(reader, errors)


def _advertisers_using_activity_json(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.json("advertisers_using_your_activity_or_information.json")
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            # Newer format: label_values at root level
            label_values = data.get("label_values", [])
            if label_values:
                for group in label_values:
                    category = group.get("label", "")
                    for entry in group.get("vec", []):
                        datapoints.append((
                            eh.fix_latin1_string(entry.get("value", "")),
                            category,
                        ))
            else:
                # Older format: ig_custom_audiences_all_types
                items = data.get("ig_custom_audiences_all_types", [])
                for item in items:
                    datapoints.append((
                        eh.fix_latin1_string(item.get("advertiser_name", "")),
                        "",
                    ))

        out = pd.DataFrame(datapoints, columns=["Advertiser", "Category"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _advertisers_using_activity_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("advertisers_using_your_activity_or_information.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        headed_tds = eh.xpath_nodes(tree, "//td[contains(@class, '_a6_q') and @colspan]")
        for td in headed_tds:
            category = td.text.strip() if td.text else ""
            if not category:
                continue

            value_divs = td.xpath(".//div[contains(@class, '_a6-g')]/div[contains(@class, '_a6-p')]")
            for div in value_divs:
                advertiser = div.text.strip() if div.text else ""
                if advertiser:
                    datapoints.append((advertiser, category))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Advertiser", "Category"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


def ads_viewed_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "ads_viewed.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the list of viewed ads into a DataFrame.

    Supports both the list-at-root format and the dict format keyed by
    ``"impressions_history_ads_seen"``.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"ads_viewed.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Account name``, ``Name``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one advertisement impression shown to the participant on Instagram. Includes the advertiser identity and when the ad was displayed.",
          "source_file": "ads_viewed.json / ads_viewed.html",
          "columns": {
            "Account name": "Username of the advertiser's Instagram account.",
            "Name": "Display name of the advertiser.",
            "URL": "URL associated with the advertisement.",
            "Date": "ISO 8601 timestamp of when the ad was shown to the participant."
          }
        }

    Table config::

        {
          "id": "instagram_ads_viewed",
          "title": {
            "en": "Ads viewed on Instagram",
            "nl": "Advertenties bekeken op Instagram"
          },
          "description": {
            "en": "List of ads that you viewed on Instagram.",
            "nl": "Lijst van advertenties die je op Instagram hebt bekeken."
          },
          "headers": {
            "Account name": {"en": "Account name", "nl": "Account"},
            "Name": {"en": "Name", "nl": "Naam"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _ads_viewed_html(reader, errors)

    return _ads_viewed_json(reader, errors, filename=filename)


def _ads_viewed_json(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "ads_viewed.json",
) -> pd.DataFrame:
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("impressions_history_ads_seen", [])  # pyright: ignore
        else:
            items = []

        for item in items:  # pyright: ignore
            owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
            datapoints.append((
                owner_username or owner_name,
                owner_name,
                url,
                eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
            ))

        out = pd.DataFrame(datapoints, columns=["Account name", "Name", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _ads_viewed_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("ads_viewed.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
        for section in sections:
            name, username = _extract_owner_from_html(section)

            url_a = section.xpath(".//td[contains(@class, '_a6_q') and starts-with(text(), 'URL')]//a")
            url = url_a[0].get("href", "") if url_a else ""

            ts = section.xpath(".//div[contains(@class, '_a6-o')]")
            timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

            datapoints.append((username or name, name, url, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Account name", "Name", "URL", "Date"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()



def profile_searches_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "profile_searches.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the list of profile searches into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"profile_searches.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Timestamp``, ``Name``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one profile search performed by the participant on Instagram, recording what was searched and when.",
          "source_file": "profile_searches.json",
          "columns": {
            "Name": "Username or display name that was searched for.",
            "Timestamp": "ISO 8601 timestamp of when the search was performed."
          }
        }

    Table config::

        {
          "id": "instagram_profile_searches",
          "title": {
            "en": "Profile searches",
            "nl": "Profielzoekopdrachten"
          },
          "description": {
            "en": "List of profiles you have searched for on Instagram.",
            "nl": "Lijst van profielen die je op Instagram hebt gezocht."
          },
          "headers": {
            "Name": {"en": "Name", "nl": "Naam"},
            "Timestamp": {"en": "Timestamp", "nl": "Datum en tijd"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["searches_user"]  # pyright: ignore
        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.epoch_to_datetime_string(eh.find_item(d, "timestamp"), errors=errors),
                eh.fix_latin1_string(eh.find_item(d, "title") or eh.find_item(d, "value")),
            ))
        out = pd.DataFrame(datapoints, columns=["Timestamp", "Name"])  # pyright: ignore
        out = _sort_by_date(out, "Timestamp")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def threads_viewed_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "threads_viewed.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the list of viewed Threads posts into a DataFrame.

    Handles both the older ``string_map_data`` format (dict root keyed by
    ``"text_post_app_text_post_app_posts_seen"``) and the newer
    ``label_values`` list-at-root format.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"threads_viewed.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Author``, ``URL``, ``Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post on Threads (Meta's text-based social network linked to Instagram) that the participant viewed, including the author and timing.",
          "source_file": "threads_viewed.json",
          "columns": {
            "Author": "Username or display name of the account that published the viewed Threads post.",
            "URL": "Direct URL to the viewed Threads post.",
            "Date": "ISO 8601 timestamp of when the post was viewed."
          }
        }

    Table config::

        {
          "id": "instagram_threads_viewed",
          "title": {"en": "Threads viewed", "nl": "Threads bekeken"},
          "description": {
            "en": "List of Threads posts you viewed.",
            "nl": "Lijst van Threads-berichten die je hebt bekeken."
          },
          "headers": {
            "Author": {"en": "Author", "nl": "Account"},
            "URL": {"en": "URL", "nl": "URL"},
            "Date": {"en": "Date", "nl": "Datum en tijd"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            items = data["text_post_app_text_post_app_posts_seen"]  # pyright: ignore
            for item in items:
                string_map_data = item.get("string_map_data", {})
                author = _first_present(string_map_data, ["Author", "Auteur"])
                time = _first_present(string_map_data, ["Time", "Tijd"])
                url = _first_present(string_map_data, ["URL"])
                datapoints.append((
                    eh.fix_latin1_string(str(author.get("value", ""))),
                    url.get("href", ""),
                    eh.epoch_to_datetime_string(time.get("timestamp", ""), errors=errors),
                ))
        else:
            for item in data:  # pyright: ignore
                owner_name, owner_username, url = _extract_owner_details(item.get("label_values", []))
                datapoints.append((
                    owner_username or owner_name,
                    url,
                    eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Author", "URL", "Date"])  # pyright: ignore
        out = _sort_by_date(out, "Date")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def ads_clicked_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "ads_clicked.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the list of clicked ads into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"ads_clicked.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Action``, ``Title``, ``URL``, ``Timestamp``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one advertisement the participant clicked on Instagram.",
          "source_file": "ads_clicked.json",
          "columns": {
            "Action": "The action performed on the ad (e.g. Click).",
            "Title": "Title or name of the clicked advertisement.",
            "URL": "URL of the clicked advertisement.",
            "Timestamp": "ISO 8601 timestamp of when the ad was clicked."
          }
        }

    Table config::

        {
          "id": "instagram_ads_clicked",
          "title": {
            "en": "Ads clicked on Instagram",
            "nl": "Advertenties aangeklikt op Instagram"
          },
          "description": {
            "en": "List of ads you clicked on Instagram.",
            "nl": "Lijst van advertenties die je op Instagram hebt aangeklikt."
          },
          "headers": {
            "Action": {"en": "Action", "nl": "Actie"},
            "Title": {"en": "Title", "nl": "Titel"},
            "URL": {"en": "URL", "nl": "URL"},
            "Timestamp": {"en": "Timestamp", "nl": "Datum en tijd"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data if isinstance(data, list) else [data]  # pyright: ignore
        for item in items:
            action = ""
            title = ""
            url = ""

            for lv in item.get("label_values", []):
                if "value" in lv:
                    label = lv.get("label", "")
                    value = eh.fix_latin1_string(lv.get("value", ""))
                    if label == "Action":
                        action = value
                    elif label == "Title":
                        title = value
                    elif label == "URL":
                        url = value

            datapoints.append((
                action,
                title,
                url,
                eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors),
            ))

        out = pd.DataFrame(datapoints, columns=["Action", "Title", "URL", "Timestamp"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def posts_published_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename_pattern: str = r"(^|/)posts(?:_\d+)?\.json$",
    validation=None,
) -> pd.DataFrame:
    """Extract published posts across multiple matching files into a DataFrame.

    Reads files matching ``posts_1.json``, ``posts_2.json``, etc.  Each entry
    contains a title and a ``creation_timestamp``.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename_pattern:
        Regular expression matched against archive member paths.  Defaults to
        a pattern that matches ``posts.json``, ``posts_1.json``, etc.

    Returns
    -------
    pd.DataFrame
        Columns: ``Title``, ``Timestamp``.
        Empty DataFrame when no matching files are found or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post published by the participant on Instagram.",
          "source_file": "posts_*.json / posts_*.html",
          "columns": {
            "Title": "Caption or title text of the post.",
            "Timestamp": "ISO 8601 timestamp of when the post was created."
          }
        }

    Table config::

        {
          "id": "instagram_posts_published",
          "title": {
            "en": "Posts",
            "nl": "Geplaatste berichten"
          },
          "description": {
            "en": "List of posts you have published on Instagram.",
            "nl": "Lijst van publieke berichten die je op Instagram hebt geplaatst."
          },
          "headers": {
            "Title": {"en": "Title", "nl": "Titel"},
            "Timestamp": {"en": "Timestamp", "nl": "Datum en tijd"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _posts_published_html(reader, errors)

    return _posts_published_json(reader, errors, filename_pattern=filename_pattern)


def _posts_published_json(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename_pattern: str = r"(^|/)posts(?:_\d+)?\.json$",
) -> pd.DataFrame:
    out = pd.DataFrame()
    datapoints = []

    try:
        results = reader.json_all(filename_pattern)
        if not results:
            return pd.DataFrame()

        for result in results:
            data = result.data
            # Posts can be a list at root or nested under a key
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = [data]
            else:
                items = []

            for item in items:  # pyright: ignore
                dd = eh.dict_denester(item)
                datapoints.append((
                    eh.fix_latin1_string(eh.find_item(dd, "title")),
                    eh.epoch_to_datetime_string(eh.find_item(dd, "creation_timestamp"), errors=errors),
                ))

        out = pd.DataFrame(datapoints, columns=["Title", "Timestamp"])  # pyright: ignore
        out = _sort_by_date(out, "Timestamp")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _posts_published_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    results = reader.raw_all(r"(^|/)posts(?:_\d+)?\.html$")
    if not results:
        return pd.DataFrame()

    datapoints = []

    try:
        for result in results:
            tree = etree.HTML(result.data.read())

            sections = eh.xpath_nodes(tree, "//main/div[contains(@class, '_a6-g')]")
            for section in sections:
                # The post title (caption) is the section's own heading; media
                # entries nested deeper carry their own headings.
                h2 = section.xpath("h2")
                title = h2[0].text.strip() if h2 and h2[0].text else ""

                ts = section.xpath(".//div[contains(@class, '_a6-o')]")
                timestamp = _html_timestamp(ts[0].text.strip() if ts and ts[0].text else "", errors)

                datapoints.append((title, timestamp))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Title", "Timestamp"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# RECREATED FROM algosoc-dd-old — NEEDS MANUAL VERIFICATION
# Source: algosoc-dd-old/src/framework/processing/py/port/instagram.py parse_subscription_for_no_ads()
# ---------------------------------------------------------------------------
def subscription_for_no_ads_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "subscription_for_no_ads.json",
    validation=None,
) -> pd.DataFrame:
    """Extract ad-free subscription status into a DataFrame.

    Reads the ``label_values`` structure from the subscription file.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"subscription_for_no_ads.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Label``, ``Value``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents a field from the participant's ad-free subscription status on Instagram.",
          "source_file": "subscription_for_no_ads.json / subscription_for_no_ads.html",
          "columns": {
            "Label": "Description label for the subscription field.",
            "Value": "Value of the subscription field."
          }
        }

    Table config::

        {
          "id": "instagram_subscription_for_no_ads",
          "title": {
            "en": "Ad-free subscription status",
            "nl": "Status advertentievrij abonnement"
          },
          "description": {
            "en": "Your ad-free subscription status on Instagram.",
            "nl": "Je status van het advertentievrije abonnement op Instagram."
          },
          "headers": {
            "Label": {"en": "Label", "nl": "Label"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    if validation and validation.current_ddp_category.ddp_filetype == DDPFiletype.HTML:
        return _subscription_for_no_ads_html(reader, errors)

    return _subscription_for_no_ads_json(reader, errors, filename=filename)


def _subscription_for_no_ads_json(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "subscription_for_no_ads.json",
) -> pd.DataFrame:
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        if isinstance(data, dict):
            label_values = data.get("label_values", [])
        elif isinstance(data, list):
            label_values = data
        else:
            label_values = []

        for item in label_values:
            datapoints.append((
                item.get("label", ""),
                item.get("value", ""),
            ))

        out = pd.DataFrame(datapoints, columns=["Label", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def _subscription_for_no_ads_html(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    result = reader.raw("subscription_for_no_ads.html")
    if not result.found:
        return pd.DataFrame()

    datapoints = []

    try:
        tree = etree.HTML(result.data.read())

        rows = eh.xpath_nodes(tree, "//tr[td[contains(@class, '_a6_q')] and td[contains(@class, '_a6_r')]]")
        for row in rows:
            label_td = row.xpath("td[contains(@class, '_a6_q')]")
            value_td = row.xpath("td[contains(@class, '_a6_r')]")
            label = label_td[0].text.strip() if label_td and label_td[0].text else ""
            value = value_td[0].text.strip() if value_td and value_td[0].text else ""
            if label:
                datapoints.append((eh.fix_latin1_string(label), eh.fix_latin1_string(value)))

        if datapoints:
            return pd.DataFrame(datapoints, columns=["Label", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# New extractors (Task 15b, story edu-curation): tables built for the "what
# they know about you" lens and the Digital Trace Data Lab 2 requirement of a
# first, account-identifying table. None of these have an html twin in the
# algosoc-2026 source module (checked against
# ddt-forks/algosoc-2026/packages/python/port/platforms/instagram.py, which
# carries the same 18 extractors this module started with and no more) — every
# one of them is JSON-only. The html export always returns an empty table
# here, which run_extraction drops without incrementing the error counter
# (ADR-0024); validation is accepted on each, for calling-convention parity
# with the rest of the registry, but ignored.
# ---------------------------------------------------------------------------

def account_info_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "personal_information/personal_information.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the participant's core account fields into a DataFrame.

    Reads every ``string_map_data`` field under ``profile_user`` (username,
    name, email address, phone number, and whatever else Instagram bundles
    into this file) as a generic label/value dump — the point of this table,
    the lab's requirement for a first, account-identifying table, is showing
    the account's own fingerprint in one place rather than a curated subset
    of it.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"personal_information/personal_information.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Field``, ``Value``.
        Empty DataFrame when the file is absent, empty, or carries no
        ``profile_user`` entries.

    Table documentation::

        {
          "summary": "One row per account field Instagram stores for the participant's profile — username, name, contact details, and whatever else this file bundles.",
          "source_file": "personal_information/personal_information.json",
          "columns": {
            "Field": "Name of the account field (e.g. Username, Email address).",
            "Value": "Value Instagram has on file for that field."
          }
        }

    Table config::

        {
          "id": "instagram_account_info",
          "title": {
            "en": "Your Instagram account information",
            "nl": "Jouw Instagram-accountgegevens"
          },
          "description": {
            "en": "The core account details Instagram stores for your profile — name, username, contact details, and more — read from your export's personal_information.json file.",
            "nl": "De belangrijkste accountgegevens die Instagram voor je profiel bewaart — naam, gebruikersnaam, contactgegevens en meer — gelezen uit het bestand personal_information.json van je export."
          },
          "headers": {
            "Field": {"en": "Field", "nl": "Veld"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data.get("profile_user", []) if isinstance(data, dict) else []
        for item in items:
            string_map_data = item.get("string_map_data", {}) if isinstance(item, dict) else {}
            for field, entry in string_map_data.items():
                value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
                datapoints.append((field, eh.fix_latin1_string(str(value))))

        out = pd.DataFrame(datapoints, columns=["Field", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def ad_targeting_categories_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the inferred ad-targeting segment labels into a DataFrame.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Category``.
        Empty DataFrame when the file is absent, empty, or carries no labels.

    Table documentation::

        {
          "summary": "Each row is one inferred targeting-segment label Instagram's ad system has assigned to the participant's account.",
          "source_file": "ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json",
          "columns": {
            "Category": "One inferred targeting-segment label."
          }
        }

    Table config::

        {
          "id": "instagram_ad_targeting_categories",
          "title": {
            "en": "Categories advertisers used to target you",
            "nl": "Categorieën die adverteerders gebruikten om jou te bereiken"
          },
          "description": {
            "en": "Targeting-segment labels Instagram's ad system has assigned to your account, read from your export's other_categories_used_to_reach_you.json file.",
            "nl": "Targeting-segmentlabels die het advertentiesysteem van Instagram aan je account heeft toegekend, gelezen uit het bestand other_categories_used_to_reach_you.json van je export."
          },
          "headers": {
            "Category": {"en": "Category", "nl": "Categorie"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Categories advertisers used to target you",
                "nl": "Categorieën die adverteerders gebruikten om jou te bereiken"
              },
              "type": "wordcloud",
              "textColumn": "Category",
              "tokenize": false
            }
          ]
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        label_values = data.get("label_values", []) if isinstance(data, dict) else []
        for group in label_values:
            for entry in group.get("vec", []):
                value = entry.get("value", "")
                if value:
                    datapoints.append((eh.fix_latin1_string(str(value)),))

        out = pd.DataFrame(datapoints, columns=["Category"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def link_history_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "logged_information/link_history/link_history.json",
    validation=None,
) -> pd.DataFrame:
    """Extract off-Instagram links Instagram logged the participant visiting.

    ``Visit end`` comes from the item's own epoch ``timestamp``, which a spot
    check against the fixture confirmed lines up with the end of the visit.
    ``Visit start`` is derived from it by subtracting the duration between the
    file's own local-time ``Website session start/end time`` strings — a
    difference is offset-independent, so this does not need (and does not
    guess at) the strings' own timezone, which is measurably not the html
    export's UTC-8 (see ``_naive_local_datetime``). Falls back to repeating
    ``Visit end`` when either local string cannot be parsed.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"logged_information/link_history/link_history.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Page title``, ``URL``, ``Visit start``, ``Visit end``.
        Empty DataFrame when the file is absent, empty, or carries no items.

    Table documentation::

        {
          "summary": "Each row is one off-Instagram website visit Instagram logged for the participant, with the full URL and page title.",
          "source_file": "logged_information/link_history/link_history.json",
          "columns": {
            "Page title": "Title of the visited web page.",
            "URL": "Full URL of the visited web page, tracking parameters included when present.",
            "Visit start": "ISO 8601 timestamp of when the visit started.",
            "Visit end": "ISO 8601 timestamp of when the visit ended."
          }
        }

    Table config::

        {
          "id": "instagram_link_history",
          "title": {
            "en": "Websites Instagram logged you visiting",
            "nl": "Websites die Instagram registreerde dat je bezocht"
          },
          "description": {
            "en": "Websites you visited outside Instagram, recorded in your export's link_history.json file, including the full URL. These URLs sometimes carry tracking parameters (such as utm or fbclid codes) added by the platform.",
            "nl": "Websites die je buiten Instagram hebt bezocht, vastgelegd in het bestand link_history.json van je export, inclusief de volledige URL. Deze URL's bevatten soms trackingparameters (zoals utm- of fbclid-codes) die door het platform zijn toegevoegd."
          },
          "headers": {
            "Page title": {"en": "Page title", "nl": "Paginatitel"},
            "URL": {"en": "URL", "nl": "URL"},
            "Visit start": {"en": "Visit start", "nl": "Bezoek gestart"},
            "Visit end": {"en": "Visit end", "nl": "Bezoek beëindigd"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Websites Instagram logged you visiting",
                "nl": "Websites die Instagram registreerde dat je bezocht"
              },
              "type": "area",
              "group": {"column": "Visit start", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Site visits logged", "nl": "Geregistreerde websitebezoeken"}}]
            }
          ]
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data if isinstance(data, list) else []
        for item in items:
            label_values = item.get("label_values", []) if isinstance(item, dict) else []
            fields = {lv.get("label", ""): lv.get("value", "") for lv in label_values if "value" in lv}

            title = fields.get("Title of website page that you visited", "")
            url = fields.get("Website link that you visited", "")
            start_text = fields.get("Website session start time", "")
            end_text = fields.get("Website session end time", "")

            end_str = eh.epoch_to_datetime_string(item.get("timestamp", ""), errors=errors)
            start_str = end_str

            end_epoch = item.get("timestamp", "")
            start_dt = _naive_local_datetime(start_text)
            end_dt = _naive_local_datetime(end_text)
            if start_dt is not None and end_dt is not None and end_epoch not in ("", None):
                try:
                    delta_seconds = (end_dt - start_dt).total_seconds()
                    start_str = eh.epoch_to_datetime_string(float(end_epoch) - delta_seconds, errors=errors)
                except (TypeError, ValueError):
                    start_str = end_str

            datapoints.append((
                eh.fix_latin1_string(str(title)),
                str(url),
                start_str,
                end_str,
            ))

        out = pd.DataFrame(datapoints, columns=["Page title", "URL", "Visit start", "Visit end"])  # pyright: ignore
        out = _sort_by_date(out, "Visit start")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def login_activity_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "security_and_login_information/login_and_profile_creation/login_activity.json",
    validation=None,
) -> pd.DataFrame:
    """Extract per-login records into a DataFrame.

    The ``IP address`` column is kept deliberately (per Danielle's 2026-09-08
    ruling) rather than dropped as most of the other new "surprise" tables
    drop it — login activity is the one source file in this fork's Instagram
    curation where showing the address itself is the point. ``Port`` and
    ``Cookie name`` are left out: too technical to read as a fact about the
    participant, and the cookie name is already partially masked in the
    export itself.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"security_and_login_information/login_and_profile_creation/login_activity.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Timestamp``, ``IP address``, ``Language code``.
        Empty DataFrame when the file is absent, empty, or carries no items.

    Table documentation::

        {
          "summary": "Each row is one login Instagram recorded for the participant's account, with the IP address it was made from.",
          "source_file": "security_and_login_information/login_and_profile_creation/login_activity.json",
          "columns": {
            "Timestamp": "ISO 8601 timestamp of the login.",
            "IP address": "IP address the login was made from.",
            "Language code": "Language code the client reported at login time."
          }
        }

    Table config::

        {
          "id": "instagram_login_activity",
          "title": {
            "en": "When and where you logged in",
            "nl": "Wanneer en waar je bent ingelogd"
          },
          "description": {
            "en": "Login events Instagram recorded for your account, including the IP address used, read from your export's login_activity.json file. An IP address is the network identifier a device is assigned when it connects to the internet.",
            "nl": "Login-gebeurtenissen die Instagram voor je account heeft geregistreerd, inclusief het gebruikte IP-adres, gelezen uit het bestand login_activity.json van je export. Een IP-adres is de netwerkidentificatie die een apparaat krijgt toegewezen wanneer het verbinding maakt met internet."
          },
          "headers": {
            "Timestamp": {"en": "Timestamp", "nl": "Datum en tijd"},
            "IP address": {"en": "IP address", "nl": "IP-adres"},
            "Language code": {"en": "Language", "nl": "Taal"}
          },
          "visualizations": [
            {
              "title": {
                "en": "When and where you logged in",
                "nl": "Wanneer en waar je bent ingelogd"
              },
              "type": "area",
              "group": {"column": "Timestamp", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Logins", "nl": "Inlogmomenten"}}]
            }
          ]
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data.get("account_history_login_history", []) if isinstance(data, dict) else []
        for item in items:
            string_map_data = item.get("string_map_data", {}) if isinstance(item, dict) else {}
            ip = string_map_data.get("IP address", {}).get("value", "")
            lang = string_map_data.get("Language code", {}).get("value", "")
            time_field = string_map_data.get("Time", {})
            timestamp = eh.epoch_to_datetime_string(time_field.get("timestamp", ""), errors=errors)
            datapoints.append((timestamp, str(ip), str(lang)))

        out = pd.DataFrame(datapoints, columns=["Timestamp", "IP address", "Language code"])  # pyright: ignore
        out = _sort_by_date(out, "Timestamp")

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def locations_of_interest_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "personal_information/information_about_you/locations_of_interest.json",
    validation=None,
) -> pd.DataFrame:
    """Extract place names Instagram has inferred interest in into a DataFrame.

    Only the ``label_values`` group that carries a ``vec`` (a list of places)
    is read; a sibling group such as "Usage explanation" carries a single
    descriptive ``value`` rather than a place, and is skipped by the same
    ``"vec" in group`` check.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"personal_information/information_about_you/locations_of_interest.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Location``.
        Empty DataFrame when the file is absent, empty, or carries no places.

    Table documentation::

        {
          "summary": "Each row is one place name Instagram has inferred the participant is interested in.",
          "source_file": "personal_information/information_about_you/locations_of_interest.json",
          "columns": {
            "Location": "One inferred place of interest (typically a city/region pair)."
          }
        }

    Table config::

        {
          "id": "instagram_locations_of_interest",
          "title": {
            "en": "Places Instagram thinks you're interested in",
            "nl": "Plaatsen waarvan Instagram denkt dat je erin geïnteresseerd bent"
          },
          "description": {
            "en": "Place names Instagram has inferred you're interested in, read from your export's locations_of_interest.json file.",
            "nl": "Plaatsnamen waarvan Instagram heeft afgeleid dat je erin geïnteresseerd bent, gelezen uit het bestand locations_of_interest.json van je export."
          },
          "headers": {
            "Location": {"en": "Location", "nl": "Locatie"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Places Instagram thinks you're interested in",
                "nl": "Plaatsen waarvan Instagram denkt dat je erin geïnteresseerd bent"
              },
              "type": "wordcloud",
              "textColumn": "Location",
              "tokenize": false
            }
          ]
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        label_values = data.get("label_values", []) if isinstance(data, dict) else []
        for group in label_values:
            if "vec" not in group:
                continue
            for entry in group.get("vec", []):
                value = entry.get("value", "")
                if value:
                    datapoints.append((eh.fix_latin1_string(str(value)),))

        out = pd.DataFrame(datapoints, columns=["Location"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def off_meta_activity_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "apps_and_websites_off_of_instagram/apps_and_websites/your_activity_off_meta_technologies_settings.json",
    validation=None,
) -> pd.DataFrame:
    """Extract off-Meta activity tracking settings and counters into a DataFrame.

    A settings/counters snapshot (whether cross-app account association is
    enabled, how many times the clear-history tools have been used), not an
    itemized event log — this account's export carries only the settings
    layer of this file, not individual off-Meta events.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"apps_and_websites_off_of_instagram/apps_and_websites/your_activity_off_meta_technologies_settings.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Label``, ``Value``.
        Empty DataFrame when the file is absent, empty, or carries no flat
        label/value fields.

    Table documentation::

        {
          "summary": "One row per off-Meta activity tracking setting or counter Instagram keeps for the participant's account.",
          "source_file": "apps_and_websites_off_of_instagram/apps_and_websites/your_activity_off_meta_technologies_settings.json",
          "columns": {
            "Label": "Name of the setting or counter.",
            "Value": "Its current value."
          }
        }

    Table config::

        {
          "id": "instagram_off_meta_activity",
          "title": {
            "en": "Your off-Instagram activity tracking settings",
            "nl": "Je trackinginstellingen voor activiteit buiten Instagram"
          },
          "description": {
            "en": "Settings and counters for whether Instagram links your activity to other Meta apps and websites, read from your export's your_activity_off_meta_technologies_settings.json file.",
            "nl": "Instellingen en tellers die aangeven of Instagram je activiteit koppelt aan andere Meta-apps en -websites, gelezen uit het bestand your_activity_off_meta_technologies_settings.json van je export."
          },
          "headers": {
            "Label": {"en": "Setting", "nl": "Instelling"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        label_values = data.get("label_values", []) if isinstance(data, dict) else []
        for item in label_values:
            label = item.get("label", "")
            if not label:
                continue
            if "value" in item:
                value = str(item.get("value", ""))
            elif "timestamp_value" in item:
                ts = item.get("timestamp_value", 0)
                value = eh.epoch_to_datetime_string(ts, errors=errors) if ts else ""
            else:
                # Nested-dict entries (e.g. "Your latest and upcoming profile
                # association states") carry no flat scalar value on this
                # fixture; skipped rather than guessed at.
                continue
            datapoints.append((label, eh.fix_latin1_string(value)))

        out = pd.DataFrame(datapoints, columns=["Label", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def profile_based_in_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "personal_information/information_about_you/profile_based_in.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the inferred Country/Region/City the account is based in.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"personal_information/information_about_you/profile_based_in.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Field``, ``Value``.
        Empty DataFrame when the file is absent, empty, or carries no fields.

    Table documentation::

        {
          "summary": "The country, region, and city Instagram has inferred as the participant's base.",
          "source_file": "personal_information/information_about_you/profile_based_in.json",
          "columns": {
            "Field": "Name of the inferred field (Country, Region, or City).",
            "Value": "Its inferred value."
          }
        }

    Table config::

        {
          "id": "instagram_profile_based_in",
          "title": {
            "en": "Where Instagram thinks you're based",
            "nl": "Waar Instagram denkt dat je woont"
          },
          "description": {
            "en": "The country, region, and city Instagram has inferred as your base, read from your export's profile_based_in.json file.",
            "nl": "Het land, de regio en de stad die Instagram als jouw thuisbasis heeft afgeleid, gelezen uit het bestand profile_based_in.json van je export."
          },
          "headers": {
            "Field": {"en": "Field", "nl": "Veld"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        label_values = data.get("label_values", []) if isinstance(data, dict) else []
        for group in label_values:
            if "value" in group:
                label = group.get("label", "")
                if label:
                    datapoints.append((label, eh.fix_latin1_string(str(group.get("value", "")))))
            elif "dict" in group:
                for entry in group.get("dict", []):
                    label = entry.get("label", "")
                    if label:
                        datapoints.append((label, eh.fix_latin1_string(str(entry.get("value", "")))))

        out = pd.DataFrame(datapoints, columns=["Field", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


def camera_info_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    filename: str = "personal_information/device_information/camera_information.json",
    validation=None,
) -> pd.DataFrame:
    """Extract the device/camera fingerprint Instagram has recorded.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    filename:
        Path inside the zip archive to read.  Defaults to
        ``"personal_information/device_information/camera_information.json"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Field``, ``Value``.
        Empty DataFrame when the file is absent, empty, or carries no fields.

    Table documentation::

        {
          "summary": "A device and camera fingerprint (device ID, supported camera SDK versions) Instagram has recorded for the participant.",
          "source_file": "personal_information/device_information/camera_information.json",
          "columns": {
            "Field": "Name of the fingerprint field.",
            "Value": "Its recorded value."
          }
        }

    Table config::

        {
          "id": "instagram_camera_info",
          "title": {
            "en": "The camera and device Instagram has detected",
            "nl": "De camera en het apparaat die Instagram heeft gedetecteerd"
          },
          "description": {
            "en": "A device and camera fingerprint Instagram has recorded for your account, read from your export's camera_information.json file.",
            "nl": "Een apparaat- en cameravingerafdruk die Instagram voor je account heeft geregistreerd, gelezen uit het bestand camera_information.json van je export."
          },
          "headers": {
            "Field": {"en": "Field", "nl": "Veld"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    result = reader.json(filename)
    if not result.found:
        return pd.DataFrame()
    data = result.data

    out = pd.DataFrame()
    datapoints = []

    try:
        label_values = data.get("label_values", []) if isinstance(data, dict) else []
        for item in label_values:
            label = item.get("label", "")
            if not label:
                continue
            if "value" in item:
                datapoints.append((label, eh.fix_latin1_string(str(item.get("value", "")))))
            elif "dict" in item:
                for entry in item.get("dict", []):
                    sub_label = entry.get("label", "")
                    if sub_label:
                        datapoints.append((sub_label, eh.fix_latin1_string(str(entry.get("value", "")))))

        out = pd.DataFrame(datapoints, columns=["Field", "Value"])  # pyright: ignore

    except Exception as e:
        logger.error("Exception caught: %s", e)
        errors[type(e).__name__] += 1

    return out


# ---------------------------------------------------------------------------
# Commented out: not in algosoc-2026 extraction list
# ---------------------------------------------------------------------------

# def followers_to_df(
#     reader: ZipArchiveReader,
#     errors: Counter,
#     *,
#     filename: str = "followers_1.json",
# ) -> pd.DataFrame:
#     """Extract the list of followers into a DataFrame.
#
#     Handles both the newer bare top-level list format and the older format
#     where entries are wrapped under a ``"relationships_followers"`` key.
#
#     Parameters
#     ----------
#     reader:
#         Archive reader used to load JSON files from the DDP zip.
#     errors:
#         Mutable counter that accumulates error type counts encountered during
#         extraction.  Updated in-place.
#     filename:
#         Path inside the zip archive to read.  Defaults to
#         ``"followers_1.json"``.
#
#     Returns
#     -------
#     pd.DataFrame
#         Columns: ``Account``, ``URL``, ``Date``.
#         Empty DataFrame when the file is absent or parsing fails.
#
#     Table documentation::
#
#         {
#           "summary": "Each row represents one account that follows the participant on Instagram, including when they started following.",
#           "source_file": "followers_1.json",
#           "columns": {
#             "Account": "Username or display name of the follower account.",
#             "URL": "Direct URL to the follower's Instagram profile.",
#             "Date": "ISO 8601 timestamp of when the account started following the participant."
#           }
#         }
#
#     Table config::
#
#         {
#           "id": "instagram_followers",
#           "title": {"en": "Your Instagram followers", "nl": "Je Instagram-volgers"},
#           "description": {
#             "en": "List of accounts that follow you on Instagram.",
#             "nl": "Lijst van accounts die jou op Instagram volgen."
#           },
#           "headers": {
#             "Account": {"en": "Account", "nl": "Account"},
#             "URL": {"en": "URL", "nl": "URL"},
#             "Date": {"en": "Date", "nl": "Datum en tijd"}
#           }
#         }
#     """
#     result = reader.json(filename)
#     if not result.found:
#         return pd.DataFrame()
#     data = result.data
#
#     out = pd.DataFrame()
#     datapoints = []
#
#     try:
#         if isinstance(data, dict):
#             items = data.get("relationships_followers", [])
#         else:
#             items = data  # pyright: ignore
#
#         for item in items:
#             d = eh.dict_denester(item)
#             datapoints.append((
#                 eh.fix_latin1_string(eh.find_item(d, "value") or eh.find_item(d, "title")),
#                 eh.find_item(d, "href"),
#                 eh.epoch_to_datetime_string(eh.find_item(d, "timestamp"), errors=errors),
#             ))
#         out = pd.DataFrame(datapoints, columns=["Account", "URL", "Date"])  # pyright: ignore
#         out = _sort_by_date(out, "Date")
#
#     except Exception as e:
#         logger.error("Exception caught: %s", e)
#         errors[type(e).__name__] += 1
#
#     return out


# ---------------------------------------------------------------------------
# Extractor registry & platform info
# ---------------------------------------------------------------------------

#: Mapping from the string names used in port_config.json to actual extractor functions.
EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "followers_to_df": followers_to_df,
    "following_to_df": following_to_df,
    "posts_viewed_to_df": posts_viewed_to_df,
    "videos_watched_to_df": videos_watched_to_df,
    "post_comments_to_df": post_comments_to_df,
    "liked_comments_to_df": liked_comments_to_df,
    "liked_posts_to_df": liked_posts_to_df,
    "saved_posts_to_df": saved_posts_to_df,
    "word_or_phrase_searches_to_df": word_or_phrase_searches_to_df,
    "stories_published_to_df": stories_published_to_df,
    "advertisers_using_activity_to_df": advertisers_using_activity_to_df,
    "ads_viewed_to_df": ads_viewed_to_df,
    "profile_searches_to_df": profile_searches_to_df,
    "threads_viewed_to_df": threads_viewed_to_df,
    "ads_clicked_to_df": ads_clicked_to_df,
    "posts_published_to_df": posts_published_to_df,
    # Task 15b (story edu-curation) additions — "what they know about you" +
    # the lab's account-identifying first table. story_likes_to_df and
    # subscription_for_no_ads_to_df are intentionally no longer registered
    # here: both were dropped from instagram_config.json (story_likes per
    # Danielle's 2026-09-08 ruling; subscription_for_no_ads per the
    # proposal's own unchanged rev.-1 verdict — a static account-setting
    # snapshot, not behavioural or inferred data), so keeping either
    # registered here with nothing in the config pointing at it would be
    # registry use of a table this fork no longer surfaces. Both function
    # definitions are left in place above, unused, rather than deleted,
    # matching this file's existing convention for algosoc extractors this
    # fork does not surface.
    "account_info_to_df": account_info_to_df,
    "ad_targeting_categories_to_df": ad_targeting_categories_to_df,
    "link_history_to_df": link_history_to_df,
    "login_activity_to_df": login_activity_to_df,
    "locations_of_interest_to_df": locations_of_interest_to_df,
    "off_meta_activity_to_df": off_meta_activity_to_df,
    "profile_based_in_to_df": profile_based_in_to_df,
    "camera_info_to_df": camera_info_to_df,
}


# ---------------------------------------------------------------------------
# Main extraction & flow
# ---------------------------------------------------------------------------

def _extract_username(reader: ZipArchiveReader) -> str | None:
    """Try to extract the participant's name from personal_information.json."""
    result = reader.json("personal_information/personal_information.json")
    if not result.found:
        return None
    try:
        d = result.data
        denested = eh.dict_denester(d)
        name = eh.find_item(denested, "name-username")
        if not name:
            name = eh.find_item(denested, "username")
        if not name:
            name = eh.find_item(denested, "name")
        if name and isinstance(name, str) and len(name) >= 2:
            return eh.fix_latin1_string(name)
    except Exception as e:
        logger.warning("Could not extract Instagram username: %s", e)
    return None


def extraction(
    instagram_zip: SeekableBinaryReader,
    validation,
) -> ExtractionResult:
    """Extract data from an Instagram DDP zip and return consent-form tables.

    Parameters
    ----------
    instagram_zip:
        Seekable binary reader over the Instagram DDP zip — the upload
        adapter itself, never a path (ADR-0026).
    validation:
        Validation result object whose ``archive_members`` attribute is passed
        to ``ZipArchiveReader``.
    """
    config = load_port_config(EXTRACTOR_REGISTRY, "instagram")
    for table in config:
        table.extractor_kwargs = {'validation': validation}
    errors: Counter = Counter()
    reader = ZipArchiveReader(instagram_zip, validation.archive_members, errors)

    result = run_extraction(reader, errors, config)

    username = _extract_username(reader)
    if username:
        logger.info("Extracted Instagram username for anonymization.")

    TEXT_COLUMNS = ["Comment", "Caption", "Text", "Title"]
    for table in result.tables:
        eh.anonymize_dataframe(table.data_frame, TEXT_COLUMNS, username)

    return result


class InstagramFlow(FlowBuilder):
    """Flow implementation for the Instagram data donation study.

    Parameters
    ----------
    session_id:
        Unique identifier for the current participant session.
    """

    def __init__(self, session_id: str):
        super().__init__(session_id, "Instagram")

    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file_value, validation):
        return extraction(file_value, validation)


def process(session_id):
    flow = InstagramFlow(session_id)
    return flow.start_flow()
