"""
Netflix

This module provides an example flow of a Netflix data donation study.

Assumptions:
It handles DDPs in the English language with filetype CSV.
Netflix DDPs may have files nested under a numeric user ID prefix directory.

Configuration
-------------
The ``extraction`` function is driven by ``port_config.json``.  Generate one with::

    pnpm generate-config netflix

Each extractor function carries its own table config in a ``Table config::``
JSON block inside its docstring.  The generator reads those blocks and
assembles the JSON file.

Platform info::

    {
        "name": "Netflix",
        "filetypes": ["csv"],
        "languages": ["en", "nl"],
        "description": "Handles DDPs in English. Supports multi-profile DDPs; the participant selects their profile at runtime. These data donation flows have not been tested yet, if you find anything wrong with them report to datadonation@uu.nl and they will be fixed!",
        "time_last_tested": "not yet implemented"
    }

Note: Netflix extractors receive the selected profile name via
``extractor_kwargs["selected_user"]``.  The ``extraction()`` function injects
the runtime-selected value into each ``TableConfig`` before calling
``run_extraction``.
"""
import logging
from collections import Counter
from typing import Callable

import pandas as pd

from port.api.props import Translatable
import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
import port.helpers.port_helpers as ph
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
)
from port.api.d3i_props import ExtractionResult
from port.helpers.table_extractor import (
    load_port_config,
    run_extraction,
)

logger = logging.getLogger(__name__)

DDP_CATEGORIES = [
    DDPCategory(
        id="csv",
        ddp_filetype=DDPFiletype.CSV,
        language=Language.EN,
        known_files=[
            "MyList.csv", "ViewingActivity.csv", "SearchHistory.csv",
            "IndicatedPreferences.csv", "PlaybackRelatedEvents.csv",
            "InteractiveTitles.csv", "Ratings.csv", "GamePlaySession.csv",
            "IpAddressesLogin.csv", "IpAddressesAccountCreation.txt",
            "IpAddressesStreaming.csv", "Additional Information.pdf",
            "MessagesSentByNetflix.csv", "AccountDetails.csv",
            "ProductCancellationSurvey.txt", "CSContact.txt",
            "ChatTranscripts.txt", "Cover Sheet.pdf", "Devices.csv",
            "ParentalControlsRestrictedTitles.txt", "AvatarHistory.csv",
            "Profiles.csv", "Clickstream.csv", "BillingHistory.csv",
            "AccessAndDevices.csv", "ExtraMembers.txt", "SubscriptionHistory.csv",
        ]
    )
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def extract_users(reader: ZipArchiveReader) -> list[str]:
    """Extract all profile names from Profiles.csv (first column).

    Falls back to ViewingActivity.csv if Profiles.csv is not available.
    Uses column position rather than name to handle different DDP languages.
    """
    out: list[str] = []

    result = reader.csv("Profiles.csv")
    df = result.data if result.found else pd.DataFrame()

    if df.empty:
        result = reader.csv("ViewingActivity.csv")
        df = result.data if result.found else pd.DataFrame()

    try:
        if not df.empty:
            if "Profile Name" in df.columns:
                out = df["Profile Name"].unique().tolist()
            else:
                out = df[df.columns[0]].unique().tolist()
            out.sort()
    except Exception as e:
        logger.error("Cannot extract users: %s", e)
        reader.errors[type(e).__name__] += 1
    return out


def keep_user(df: pd.DataFrame, selected_user: str) -> pd.DataFrame:
    """Keep only rows where the profile name column matches selected_user."""
    try:
        if "Profile Name" in df.columns:
            df = df.loc[df["Profile Name"] == selected_user].reset_index(drop=True)
        else:
            for col in df.columns:
                if selected_user in df[col].values:
                    df = df.loc[df[col] == selected_user].reset_index(drop=True)
                    break
    except Exception as e:
        logger.info(e)
    return df


def netflix_to_df(reader: ZipArchiveReader, file_name: str, selected_user: str) -> pd.DataFrame:
    """Load a Netflix CSV, filter to selected user."""
    result = reader.csv(file_name)
    if not result.found:
        return pd.DataFrame()
    return keep_user(result.data, selected_user)


# ---------------------------------------------------------------------------
# Per-table extraction functions
# ---------------------------------------------------------------------------

def ratings_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract Netflix ratings — title, thumbs value, timestamp.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Title Name``, ``Thumbs Value``, ``Event Utc Ts``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one title the participant rated on Netflix, including the rating value and timestamp.",
          "source_file": "Ratings.csv",
          "columns": {
            "Title Name": "Name of the rated Netflix title.",
            "Thumbs Value": "Thumbs up or thumbs down value given by the participant.",
            "Event Utc Ts": "ISO 8601 timestamp of when the rating was given."
          }
        }

    Table config::

        {
          "id": "netflix_ratings",
          "title": {"en": "Your ratings on Netflix", "nl": "Uw beoordelingen op Netflix"},
          "description": {
            "en": "Titles you have rated on Netflix.",
            "nl": "Titels die u op Netflix heeft beoordeeld."
          },
          "headers": {
            "Title Name": {"en": "Title", "nl": "Titel"},
            "Thumbs Value": {"en": "Thumbs value", "nl": "Aantal duimpjes omhoog"},
            "Event Utc Ts": {"en": "Date", "nl": "Datum en tijd"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Titles rated by thumbs value",
                "nl": "Beoordeelde titels op basis van duimpjes"
              },
              "type": "wordcloud",
              "textColumn": "Title Name",
              "valueColumn": "Thumbs Value"
            }
          ]
        }
    """
    columns_to_keep = ["Title Name", "Thumbs Value", "Event Utc Ts"]
    df = netflix_to_df(reader, "Ratings.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def time_string_to_hours(time_str: str) -> float:
    try:
        hours, minutes, seconds = map(int, time_str.split(':'))
        total_hours = (hours * 3600 + minutes * 60 + seconds) / 3600
    except Exception:
        return 0.0
    return round(total_hours, 3)


def viewing_activity_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract Netflix viewing activity — start time, duration, title, type.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Start Time``, ``Duration``, ``Title``, ``Supplemental Video Type``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one viewing session on Netflix, including the title watched, start time, and duration in hours.",
          "source_file": "ViewingActivity.csv",
          "columns": {
            "Start Time": "ISO 8601 timestamp of when the viewing session started.",
            "Duration": "Duration of the viewing session in hours.",
            "Title": "Name of the Netflix title watched.",
            "Supplemental Video Type": "Type of supplemental video (e.g. trailer), if applicable."
          }
        }

    Table config::

        {
          "id": "netflix_viewing_activity",
          "title": {"en": "What you watched", "nl": "Wat u heeft gekeken"},
          "description": {
            "en": "This table shows what titles you watched, when, and for how long.",
            "nl": "Deze tabel toont welke titels u heeft gekeken, wanneer, en hoe lang."
          },
          "headers": {
            "Start Time": {"en": "Start time", "nl": "Starttijd"},
            "Duration": {"en": "Hours watched", "nl": "Aantal uur gekeken"},
            "Title": {"en": "Title", "nl": "Titel"},
            "Supplemental Video Type": {"en": "Type", "nl": "Aanvullende informatie"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Total hours watched per month",
                "nl": "Totaal aantal uren gekeken per maand"
              },
              "type": "area",
              "group": {"column": "Start Time", "dateFormat": "month", "label": "Month"},
              "values": [{"column": "Duration", "aggregate": "sum"}]
            },
            {
              "title": {
                "en": "Total hours watched by hour of the day",
                "nl": "Totaal aantal uur gekeken per uur van de dag"
              },
              "type": "bar",
              "group": {"column": "Start Time", "dateFormat": "hour_cycle"},
              "values": [{"column": "Duration", "aggregate": "sum"}]
            }
          ]
        }
    """
    columns_to_keep = ["Start Time", "Duration", "Title", "Supplemental Video Type"]
    df = netflix_to_df(reader, "ViewingActivity.csv", selected_user)
    remove_values = ["TEASER_TRAILER", "HOOK", "TRAILER", "CINEMAGRAPH"]
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
            mask = out["Supplemental Video Type"].isin(remove_values)
            out = out[~mask].reset_index(drop=True)
            out["Duration"] = out["Duration"].apply(time_string_to_hours)
            out = out.sort_values(by="Start Time", ascending=True).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def search_history_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract Netflix search history — query, displayed result, timestamp.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Query Typed``, ``Displayed Name``, ``Utc Timestamp``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one search the participant performed on Netflix.",
          "source_file": "SearchHistory.csv",
          "columns": {
            "Query Typed": "The search query the participant typed.",
            "Displayed Name": "The result title that was displayed.",
            "Utc Timestamp": "ISO 8601 timestamp of when the search was performed."
          }
        }

    Table config::

        {
          "id": "netflix_search_history",
          "title": {
            "en": "Your search history on Netflix",
            "nl": "Uw zoekgeschiedenis op Netflix"
          },
          "description": {
            "en": "Searches you have performed on Netflix.",
            "nl": "Zoekopdrachten die u op Netflix heeft uitgevoerd."
          },
          "headers": {
            "Query Typed": {"en": "Search query", "nl": "Zoekterm"},
            "Displayed Name": {"en": "Result shown", "nl": "Weergegeven resultaat"},
            "Utc Timestamp": {"en": "Date", "nl": "Datum en tijd"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Most searched terms",
                "nl": "Meest gezochte termen"
              },
              "type": "wordcloud",
              "textColumn": "Query Typed",
              "tokenize": false
            }
          ]
        }
    """
    df = netflix_to_df(reader, "SearchHistory.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            columns_to_keep = [c for c in ["Query Typed", "Displayed Name", "Utc Timestamp"] if c in df.columns]
            out = pd.DataFrame(df[columns_to_keep])
            if "Utc Timestamp" in out.columns:
                out = out.sort_values(by="Utc Timestamp", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def indicated_preferences_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract Netflix's "indicated preferences" — titles Netflix asked
    whether the participant was interested in, sometimes titles already
    watched.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Show``, ``Is Interested``, ``Has Watched``, ``Event Date``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one title Netflix explicitly asked the participant whether they were interested in.",
          "source_file": "IndicatedPreferences.csv",
          "columns": {
            "Show": "Name of the title Netflix asked about.",
            "Is Interested": "Whether the participant indicated interest (true/false).",
            "Has Watched": "Whether the participant had already watched the title (true/false).",
            "Event Date": "Date the preference was recorded."
          }
        }

    Table config::

        {
          "id": "netflix_indicated_preferences",
          "title": {
            "en": "Titles Netflix asked about",
            "nl": "Titels waarover Netflix vroeg"
          },
          "description": {
            "en": "Titles Netflix asked whether you were interested in, from IndicatedPreferences.csv.",
            "nl": "Titels waarvan Netflix vroeg of u interesse had, uit IndicatedPreferences.csv."
          },
          "headers": {
            "Show": {"en": "Title", "nl": "Titel"},
            "Is Interested": {"en": "Interested?", "nl": "Interesse?"},
            "Has Watched": {"en": "Already watched?", "nl": "Al bekeken?"},
            "Event Date": {"en": "Date", "nl": "Datum"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Titles Netflix asked if you're interested in",
                "nl": "Titels waarvan Netflix vroeg of je interesse had"
              },
              "type": "bar",
              "group": {"column": "Is Interested", "label": {"en": "Your answer", "nl": "Je antwoord"}},
              "values": [{"aggregate": "count", "label": {"en": "Titles", "nl": "Titels"}}]
            }
          ]
        }
    """
    columns_to_keep = ["Show", "Is Interested", "Has Watched", "Event Date"]
    df = netflix_to_df(reader, "IndicatedPreferences.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
            if "Event Date" in out.columns:
                out = out.sort_values(by="Event Date", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def ip_addresses_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract every IP address Netflix tied to a login or a streaming
    session, merging the login and streaming files.

    IP addresses are account-wide in Netflix's export (neither source file
    carries a profile column), so ``selected_user`` is accepted for
    consistency with the other extractors but not used to filter rows.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Unused; accepted because ``extraction()`` injects it into every
        extractor's kwargs.

    Returns
    -------
    pd.DataFrame
        Columns: ``Country``, ``Region``, ``Ip``, ``Device Description``,
        ``Ts``, ``Event Type``. ``Region`` normalises the login file's
        ``Region Code`` and the streaming file's ``Region Code Display
        Name`` into one column (blank on whichever side didn't supply it).
        Empty DataFrame when both source files are absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one login or streaming session Netflix tied to an IP address.",
          "source_file": "IpAddressesLogin.csv, IpAddressesStreaming.csv",
          "columns": {
            "Country": "Country Netflix associated with the IP address.",
            "Region": "Region Netflix associated with the session — Region Code for a login row, Region Code Display Name for a streaming row.",
            "Ip": "The raw IP address recorded for the session.",
            "Device Description": "Description of the device used for the session.",
            "Ts": "ISO 8601 timestamp of the login or streaming session.",
            "Event Type": "Whether the row came from a login event or a streaming event."
          }
        }

    Table config::

        {
          "id": "netflix_ip_addresses",
          "title": {
            "en": "IP addresses linked to your Netflix account",
            "nl": "IP-adressen gekoppeld aan uw Netflix-account"
          },
          "description": {
            "en": "Every login and streaming IP address Netflix recorded, from IpAddressesLogin.csv and IpAddressesStreaming.csv. An IP address can indicate a rough location and network operator.",
            "nl": "Elk login- en streaming-IP-adres dat Netflix heeft geregistreerd, uit IpAddressesLogin.csv en IpAddressesStreaming.csv. Een IP-adres kan een globale locatie en netwerkaanbieder aangeven."
          },
          "headers": {
            "Country": {"en": "Country", "nl": "Land"},
            "Region": {"en": "Region", "nl": "Regio"},
            "Ip": {"en": "IP address", "nl": "IP-adres"},
            "Device Description": {"en": "Device", "nl": "Apparaat"},
            "Ts": {"en": "Date and time", "nl": "Datum en tijd"},
            "Event Type": {"en": "Event type", "nl": "Type gebeurtenis"}
          }
        }
    """
    columns_to_keep = ["Country", "Ip", "Device Description", "Ts"]
    column_order = ["Country", "Region", "Ip", "Device Description", "Ts", "Event Type"]
    out = pd.DataFrame()
    try:
        frames = []
        login_result = reader.csv("IpAddressesLogin.csv")
        if login_result.found and not login_result.data.empty:
            login_df = pd.DataFrame(login_result.data[columns_to_keep])
            login_df["Region"] = login_result.data["Region Code"] if "Region Code" in login_result.data.columns else ""
            login_df["Event Type"] = "Login"
            frames.append(login_df)
        streaming_result = reader.csv("IpAddressesStreaming.csv")
        if streaming_result.found and not streaming_result.data.empty:
            streaming_df = pd.DataFrame(streaming_result.data[columns_to_keep])
            streaming_df["Region"] = (
                streaming_result.data["Region Code Display Name"]
                if "Region Code Display Name" in streaming_result.data.columns else ""
            )
            streaming_df["Event Type"] = "Streaming"
            frames.append(streaming_df)
        if frames:
            out = pd.concat(frames, ignore_index=True)
            out = pd.DataFrame(out[column_order])
            out = out.sort_values(by="Ts", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def devices_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract every device Netflix has recorded for the account, merging the
    per-profile device list with the account-wide access-and-devices log.

    ``Devices.csv`` carries a profile column and is filtered to
    ``selected_user``; ``AccessAndDevices.csv`` is account-wide and is not
    filtered.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name used to filter ``Devices.csv``.  Passed via
        ``extractor_kwargs`` from ``port_config.json`` and injected at
        runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Esn``, ``Device Type``, ``First Playback Date``,
        ``Last Playback Date``, ``Access Date``, ``Source``. The playback
        dates are blank for ``AccessAndDevices.csv`` rows (that file has no
        playback date, only an access-event date); ``Access Date`` is blank
        for ``Devices.csv`` rows.
        Empty DataFrame when both source files are absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one device Netflix has recognized on the account, from either the per-profile device list or the account-wide access log.",
          "source_file": "Devices.csv, AccessAndDevices.csv",
          "columns": {
            "Esn": "Device fingerprint (Electronic Serial Number) Netflix assigned to the device.",
            "Device Type": "Type or model of the device.",
            "First Playback Date": "Earliest playback date recorded for the device (Devices.csv rows only).",
            "Last Playback Date": "Most recent playback date recorded for the device (Devices.csv rows only).",
            "Access Date": "Date of the account-wide access event recorded (AccessAndDevices.csv rows only).",
            "Source": "Which export file the row came from."
          }
        }

    Table config::

        {
          "id": "netflix_devices",
          "title": {
            "en": "Devices linked to your Netflix account",
            "nl": "Apparaten gekoppeld aan uw Netflix-account"
          },
          "description": {
            "en": "Every device Netflix has recorded for your account, from Devices.csv and AccessAndDevices.csv.",
            "nl": "Elk apparaat dat Netflix voor uw account heeft geregistreerd, uit Devices.csv en AccessAndDevices.csv."
          },
          "headers": {
            "Esn": {"en": "Device ID", "nl": "Apparaat-ID"},
            "Device Type": {"en": "Device type", "nl": "Apparaattype"},
            "First Playback Date": {"en": "First used", "nl": "Voor het eerst gebruikt"},
            "Last Playback Date": {"en": "Last used", "nl": "Laatst gebruikt"},
            "Access Date": {"en": "Access date", "nl": "Toegangsdatum"},
            "Source": {"en": "Source file", "nl": "Bronbestand"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Every device Netflix has seen",
                "nl": "Elk apparaat dat Netflix heeft gezien"
              },
              "type": "bar",
              "group": {"column": "Device Type", "label": {"en": "Device type", "nl": "Apparaattype"}},
              "values": [{"aggregate": "count", "label": {"en": "Times seen", "nl": "Aantal keer gezien"}}]
            }
          ]
        }
    """
    device_columns = ["Esn", "Device Type", "First Playback Date", "Last Playback Date", "Access Date", "Source"]
    out = pd.DataFrame()
    try:
        frames = []
        devices_df = netflix_to_df(reader, "Devices.csv", selected_user)
        if not devices_df.empty:
            renamed = devices_df.rename(columns={
                "Profile First Playback Date": "First Playback Date",
                "Profile Last Playback Date": "Last Playback Date",
            })
            frame = pd.DataFrame(renamed[["Esn", "Device Type", "First Playback Date", "Last Playback Date"]])
            frame["Access Date"] = ""
            frame["Source"] = "Devices.csv"
            frames.append(frame)

        access_result = reader.csv("AccessAndDevices.csv")
        if access_result.found and not access_result.data.empty:
            access_df = access_result.data
            frame = pd.DataFrame({
                "Esn": access_df["Esn"],
                "Device Type": access_df["Devices"],
                "First Playback Date": "",
                "Last Playback Date": "",
                "Access Date": access_df["Date"],
                "Source": "AccessAndDevices.csv",
            })
            frames.append(frame)

        if frames:
            out = pd.concat(frames, ignore_index=True)
            out = pd.DataFrame(out[device_columns])
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def profile_demographics_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract the demographic fields Netflix stores per profile.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Gender``, ``Date Of Birth``, ``Maturity Level``, ``Primary Lang``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "One row describing the demographic fields Netflix stores for the selected profile.",
          "source_file": "Profiles.csv",
          "columns": {
            "Gender": "Gender recorded for the profile, if any.",
            "Date Of Birth": "Date of birth recorded for the profile, if any.",
            "Maturity Level": "Content maturity level set for the profile.",
            "Primary Lang": "Primary language/locale code set for the profile."
          }
        }

    Table config::

        {
          "id": "netflix_profile_demographics",
          "title": {
            "en": "Your Netflix profile details",
            "nl": "Uw Netflix-profielgegevens"
          },
          "description": {
            "en": "The demographic fields Netflix stores for this profile, from Profiles.csv.",
            "nl": "De demografische gegevens die Netflix voor dit profiel bewaart, uit Profiles.csv."
          },
          "headers": {
            "Gender": {"en": "Gender", "nl": "Geslacht"},
            "Date Of Birth": {"en": "Date of birth", "nl": "Geboortedatum"},
            "Maturity Level": {"en": "Maturity level", "nl": "Volwassenheidsniveau"},
            "Primary Lang": {"en": "Primary language", "nl": "Voorkeurstaal"}
          }
        }
    """
    columns_to_keep = ["Gender", "Date Of Birth", "Maturity Level", "Primary Lang"]
    df = netflix_to_df(reader, "Profiles.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def my_list_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract titles the participant added to Netflix's "My List".

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Country``, ``Utc Title Add Date``, ``Title Name``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one title the participant added to My List on Netflix.",
          "source_file": "MyList.csv",
          "columns": {
            "Country": "Country recorded at the time the title was added.",
            "Utc Title Add Date": "Date the title was added to My List.",
            "Title Name": "Name of the Netflix title added."
          }
        }

    Table config::

        {
          "id": "netflix_my_list",
          "title": {
            "en": "Your Netflix My List",
            "nl": "Uw Netflix Mijn Lijst"
          },
          "description": {
            "en": "Titles you added to My List on Netflix, from MyList.csv.",
            "nl": "Titels die u aan Mijn Lijst op Netflix heeft toegevoegd, uit MyList.csv."
          },
          "headers": {
            "Country": {"en": "Country", "nl": "Land"},
            "Utc Title Add Date": {"en": "Date added", "nl": "Datum toegevoegd"},
            "Title Name": {"en": "Title", "nl": "Titel"}
          }
        }
    """
    columns_to_keep = ["Country", "Utc Title Add Date", "Title Name"]
    df = netflix_to_df(reader, "MyList.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
            if "Utc Title Add Date" in out.columns:
                out = out.sort_values(by="Utc Title Add Date", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def clickstream_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract Netflix's raw page-navigation clickstream for the selected profile.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Profile name to filter rows by.  Passed via ``extractor_kwargs`` from
        ``port_config.json`` and injected at runtime by ``extraction()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``Navigation Level``, ``Webpage Url``, ``Source``,
        ``Click Utc Ts``, ``Referrer Url``. ``Profile Name`` is dropped —
        rows are already filtered to the selected profile.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one page-navigation event Netflix logged for the selected profile.",
          "source_file": "Clickstream.csv",
          "columns": {
            "Navigation Level": "The navigation action or page category recorded.",
            "Webpage Url": "The internal Netflix page URL visited.",
            "Source": "Where the navigation event originated (e.g. www).",
            "Click Utc Ts": "ISO 8601 timestamp of the click.",
            "Referrer Url": "The page that referred the participant to this one."
          }
        }

    Table config::

        {
          "id": "netflix_clickstream",
          "title": {
            "en": "Your Netflix click history",
            "nl": "Uw Netflix-klikgeschiedenis"
          },
          "description": {
            "en": "Every page click Netflix logged for your account, from Clickstream.csv.",
            "nl": "Elke pagina-klik die Netflix voor uw account heeft geregistreerd, uit Clickstream.csv."
          },
          "headers": {
            "Navigation Level": {"en": "Navigation level", "nl": "Navigatieniveau"},
            "Webpage Url": {"en": "Page URL", "nl": "Pagina-URL"},
            "Source": {"en": "Source", "nl": "Bron"},
            "Click Utc Ts": {"en": "Date and time", "nl": "Datum en tijd"},
            "Referrer Url": {"en": "Referring page", "nl": "Verwijzende pagina"}
          },
          "visualizations": [
            {
              "title": {
                "en": "How Netflix tracked your clicks",
                "nl": "Hoe Netflix je klikken volgde"
              },
              "type": "area",
              "group": {"column": "Click Utc Ts", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Clicks logged", "nl": "Geregistreerde klikken"}}]
            }
          ]
        }
    """
    columns_to_keep = ["Navigation Level", "Webpage Url", "Source", "Click Utc Ts", "Referrer Url"]
    df = netflix_to_df(reader, "Clickstream.csv", selected_user)
    out = pd.DataFrame()
    try:
        if not df.empty:
            out = pd.DataFrame(df[columns_to_keep])
            if "Click Utc Ts" in out.columns:
                out = out.sort_values(by="Click Utc Ts", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


#: The ~15 marketing/communication opt-in flags AccountDetails.csv carries,
#: one column per channel x message-type combination. Excludes PII fields
#: (First Name, Last Name, Email Address, Phone Number, Postal Code, Brazil
#: Cpf) and account-admin fields (Has Rejoined, Test Participation, ...) —
#: only the "(Email)"/"(Push Notification)" consent toggles.
MARKETING_CONSENT_COLUMNS = [
    "Membership Offers (Push Notification)",
    "Watch Recommendations And More (Email)",
    "Using The Netflix App (Email)",
    "Using The Netflix App (Push Notification)",
    "Membership Offers (Email)",
    "Netflix Games (Email)",
    "Surveys And Research Invites (Email)",
    "What You Watch (Email)",
    "Netflix Games (Push Notification)",
    "Netflix Shop And Experiences (Push Notification)",
    "Kid's Activity Report (Email)",
    "Surveys And Research Invites (Push Notification)",
    "Watch Recommendations And More (Push Notification)",
    "What You Watch (Push Notification)",
    "Netflix Shop And Experiences (Email)",
]


def _account_field(row: "pd.Series", column: str) -> str:
    """Read *column* off a one-row account-level Series, blank for missing/NaN."""
    value = row.get(column, "")
    return "" if pd.isna(value) else value


def account_and_billing_to_df(
    reader: ZipArchiveReader,
    errors: Counter,
    *,
    selected_user: str = "",
) -> pd.DataFrame:
    """Extract account status, marketing-consent flags, current plan, and
    full payment history — never card details.

    One row per payment transaction (``BillingHistory.csv``), with the
    account-wide membership status, country, marketing-consent flags, and
    current plan (``AccountDetails.csv`` / ``SubscriptionHistory.csv``)
    repeated onto every row. When ``BillingHistory.csv`` is absent or empty
    (a zero-transaction account) but either of the other two sources is
    present, a single row of account/plan fields is still returned, with the
    billing columns left blank — a zero-transaction account should not lose
    the whole table (ADR-0024: an absent file is not an error, and here it
    must not make an otherwise-present table disappear either). All three
    source files are account-wide, so ``selected_user`` is accepted for
    consistency but not used to filter rows.

    The current plan is the ``SubscriptionHistory.csv`` row with the latest
    parseable ``Plan Change Date`` (falling back to the last row in file
    order when that column is missing or unparseable).

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.
    selected_user:
        Unused; accepted because ``extraction()`` injects it into every
        extractor's kwargs.

    Returns
    -------
    pd.DataFrame
        Columns: ``Membership Status``, ``Country Of Registration``, ``Plan``,
        the 15 ``MARKETING_CONSENT_COLUMNS`` entries, ``Transaction Date``,
        ``Gross Sale Amt``, ``Currency``, ``Payment Type``.
        Empty DataFrame only when all three source files are absent/empty or
        parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one Netflix payment transaction, alongside the account's membership status, marketing-consent flags, and current plan.",
          "source_file": "AccountDetails.csv, SubscriptionHistory.csv, BillingHistory.csv",
          "columns": {
            "Membership Status": "Current membership status for the account.",
            "Country Of Registration": "Country the account is registered in.",
            "Plan": "Most recent subscription plan category.",
            "Transaction Date": "Date of the payment transaction.",
            "Gross Sale Amt": "Amount charged for the transaction.",
            "Currency": "Currency of the transaction amount.",
            "Payment Type": "Payment method category used (e.g. direct debit) — never card numbers or other card details."
          }
        }

    Table config::

        {
          "id": "netflix_account_and_billing",
          "title": {
            "en": "Your Netflix account and billing details",
            "nl": "Uw Netflix-account- en factuurgegevens"
          },
          "description": {
            "en": "Your membership status, marketing preferences, and payment history, from AccountDetails.csv, SubscriptionHistory.csv, and BillingHistory.csv.",
            "nl": "Uw lidmaatschapsstatus, marketingvoorkeuren en betalingsgeschiedenis, uit AccountDetails.csv, SubscriptionHistory.csv en BillingHistory.csv."
          },
          "headers": {
            "Membership Status": {"en": "Membership status", "nl": "Lidmaatschapsstatus"},
            "Country Of Registration": {"en": "Country of registration", "nl": "Land van registratie"},
            "Plan": {"en": "Plan", "nl": "Abonnement"},
            "Membership Offers (Push Notification)": {"en": "Membership offers (push)", "nl": "Lidmaatschapsaanbiedingen (push)"},
            "Watch Recommendations And More (Email)": {"en": "Watch recommendations (email)", "nl": "Kijkaanbevelingen (e-mail)"},
            "Using The Netflix App (Email)": {"en": "Using the Netflix app (email)", "nl": "Gebruik van de Netflix-app (e-mail)"},
            "Using The Netflix App (Push Notification)": {"en": "Using the Netflix app (push)", "nl": "Gebruik van de Netflix-app (push)"},
            "Membership Offers (Email)": {"en": "Membership offers (email)", "nl": "Lidmaatschapsaanbiedingen (e-mail)"},
            "Netflix Games (Email)": {"en": "Netflix Games (email)", "nl": "Netflix Games (e-mail)"},
            "Surveys And Research Invites (Email)": {"en": "Survey invitations (email)", "nl": "Uitnodigingen voor onderzoek (e-mail)"},
            "What You Watch (Email)": {"en": "What you watch (email)", "nl": "Wat u kijkt (e-mail)"},
            "Netflix Games (Push Notification)": {"en": "Netflix Games (push)", "nl": "Netflix Games (push)"},
            "Netflix Shop And Experiences (Push Notification)": {"en": "Netflix Shop and experiences (push)", "nl": "Netflix Shop en experiences (push)"},
            "Kid's Activity Report (Email)": {"en": "Kid's activity report (email)", "nl": "Activiteitenrapport kinderen (e-mail)"},
            "Surveys And Research Invites (Push Notification)": {"en": "Survey invitations (push)", "nl": "Uitnodigingen voor onderzoek (push)"},
            "Watch Recommendations And More (Push Notification)": {"en": "Watch recommendations (push)", "nl": "Kijkaanbevelingen (push)"},
            "What You Watch (Push Notification)": {"en": "What you watch (push)", "nl": "Wat u kijkt (push)"},
            "Netflix Shop And Experiences (Email)": {"en": "Netflix Shop and experiences (email)", "nl": "Netflix Shop en experiences (e-mail)"},
            "Transaction Date": {"en": "Transaction date", "nl": "Transactiedatum"},
            "Gross Sale Amt": {"en": "Amount", "nl": "Bedrag"},
            "Currency": {"en": "Currency", "nl": "Valuta"},
            "Payment Type": {"en": "Payment method", "nl": "Betaalmethode"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Your Netflix payments over time",
                "nl": "Je Netflix-betalingen in de loop van de tijd"
              },
              "type": "area",
              "group": {"column": "Transaction Date", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"column": "Gross Sale Amt", "aggregate": "sum", "label": {"en": "Amount", "nl": "Bedrag"}}]
            }
          ]
        }
    """
    billing_columns = ["Transaction Date", "Gross Sale Amt", "Currency", "Payment Type"]
    out = pd.DataFrame()
    try:
        billing_result = reader.csv("BillingHistory.csv")
        account_result = reader.csv("AccountDetails.csv")
        subscription_result = reader.csv("SubscriptionHistory.csv")

        has_billing = billing_result.found and not billing_result.data.empty
        account_row = account_result.data.iloc[0] if account_result.found and not account_result.data.empty else None
        has_subscription = subscription_result.found and not subscription_result.data.empty

        if not has_billing and account_row is None and not has_subscription:
            # ADR-0024: all three sources absent/empty — nothing to show,
            # not an error.
            return out

        if has_billing:
            out = pd.DataFrame(billing_result.data[billing_columns])
        else:
            # A zero-transaction account still has account/plan fields worth
            # showing — one blank-billing row, not a dropped table.
            out = pd.DataFrame([{column: "" for column in billing_columns}])

        out["Membership Status"] = _account_field(account_row, "Membership Status") if account_row is not None else ""
        out["Country Of Registration"] = _account_field(account_row, "Country Of Registration") if account_row is not None else ""
        for column in MARKETING_CONSENT_COLUMNS:
            out[column] = _account_field(account_row, column) if account_row is not None else ""

        plan = ""
        if has_subscription:
            subscription_df = subscription_result.data.reset_index(drop=True)
            position = len(subscription_df) - 1
            if "Plan Change Date" in subscription_df.columns:
                parsed_dates = pd.to_datetime(subscription_df["Plan Change Date"], errors="coerce")
                if parsed_dates.notna().any():
                    position = int(parsed_dates.argmax())
            plan_row = subscription_df.iloc[position]
            plan = _account_field(plan_row, "Plan Change New Category")
            if plan == "":
                plan = _account_field(plan_row, "Signup Plan Category")
        out["Plan"] = plan

        column_order = ["Membership Status", "Country Of Registration", "Plan"] + MARKETING_CONSENT_COLUMNS + billing_columns
        out = pd.DataFrame(out[column_order])
        if has_billing:
            out = out.sort_values(by="Transaction Date", ascending=False).reset_index(drop=True)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


# ---------------------------------------------------------------------------
# Extractor registry & platform info
# ---------------------------------------------------------------------------

#: Mapping from the string names used in port_config.json to actual extractor functions.
EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "ratings_to_df": ratings_to_df,
    "viewing_activity_to_df": viewing_activity_to_df,
    "search_history_to_df": search_history_to_df,
    "indicated_preferences_to_df": indicated_preferences_to_df,
    "ip_addresses_to_df": ip_addresses_to_df,
    "devices_to_df": devices_to_df,
    "profile_demographics_to_df": profile_demographics_to_df,
    "my_list_to_df": my_list_to_df,
    "clickstream_to_df": clickstream_to_df,
    "account_and_billing_to_df": account_and_billing_to_df,
}


# ---------------------------------------------------------------------------
# Main extraction & flow
# ---------------------------------------------------------------------------

def extraction(reader: ZipArchiveReader, selected_user: str) -> ExtractionResult:
    """Extract data from a Netflix DDP zip and return consent-form tables.

    Loads ``port_config.json``, injects the runtime-selected ``selected_user``
    into each table's ``extractor_kwargs``, then delegates to
    ``run_extraction``.

    Parameters
    ----------
    reader:
        Initialised archive reader for the Netflix DDP zip.
    selected_user:
        Profile name chosen by the participant during the flow.
    """
    config = load_port_config(EXTRACTOR_REGISTRY, "netflix")
    for table_cfg in config:
        table_cfg.extractor_kwargs["selected_user"] = selected_user
    return run_extraction(reader, reader.errors, config)


class NetflixFlow(FlowBuilder):
    """Flow implementation for the Netflix data donation study."""

    def __init__(self, session_id: str):
        super().__init__(session_id, "Netflix")

    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file, validation):
        errors: Counter = Counter()
        reader = ZipArchiveReader(file, validation.archive_members, errors)
        selected_user = ""
        users = extract_users(reader)

        if len(users) == 1:
            selected_user = users[0]
            return extraction(reader, selected_user)
        elif len(users) > 1:
            title = Translatable({
                "en": "Select your Netflix profile name",
                "nl": "Kies jouw Netflix profielnaam",
            })
            empty_text = Translatable({"en": "", "nl": ""})
            radio_prompt = ph.generate_radio_prompt(title, empty_text, users)
            selection = yield ph.render_page(empty_text, radio_prompt)
            selected_user = selection.value
            return extraction(reader, selected_user)


def process(session_id):
    flow = NetflixFlow(session_id)
    return flow.start_flow()
