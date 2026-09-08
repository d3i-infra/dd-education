"""
LinkedIn

This module contains an example flow of a LinkedIn data donation study

Assumptions:
It handles DDPs in the english language with filetype CSV.

Configuration
-------------
The ``extraction`` function is driven by ``port_config.json``.  Generate one with::

    pnpm generate-config linkedin

Each extractor function carries its own table config in a ``Table config::``
JSON block inside its docstring.  The generator reads those blocks and
assembles the JSON file.

Platform info::

    {
        "name": "LinkedIn",
        "filetypes": ["csv"],
        "languages": ["en", "nl"],
        "description": "Handles DDPs in English. These data donation flows have not been tested yet, if you find anything wrong with them report to datadonation@uu.nl and they will be fixed!",
        "time_last_tested": "not yet implemented"
    }
"""

import csv
import logging
from collections import Counter
import io
import re
from typing import Callable

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

DDP_CATEGORIES = [
    DDPCategory(
        id="csv_en",
        ddp_filetype=DDPFiletype.CSV,
        language=Language.EN,
        known_files=[
            "Ad_Targeting.csv",
            "Endorsement_Given_Info.csv",
            "Member_Follows.csv",
            "Recommendations_Given.csv",
            "Company Follows.csv",
            "Endorsement_Received_Info.csv",
            "messages.csv",
            "Registration.csv",
            "Connections.csv",
            "Inferences_about_you.csv",
            "PhoneNumbers.csv",
            "Rich Media.csv",
            "Contacts.csv",
            "Invitations.csv",
            "Positions.csv",
            "Skills.csv",
            "Education.csv",
            "Profile.csv",
            "Votes.csv",
            "Email Addresses.csv",
            "Learning.csv",
            "Reactions.csv",
            "LAN Ads Engagement.csv",
            "Whatsapp Phone Numbers.csv",
        ]
    ),
]

#: ``Ad_Targeting.csv`` column (``Category``) to the kind of attribute it
#: holds, for ``ad_targeting_to_df``. LinkedIn mixes attributes the
#: participant declared on their profile, attributes derived from their
#: network, and segments LinkedIn itself infers — this says which is which.
#: A column not listed here maps to "unclassified" rather than a guess.
AD_TARGETING_CATEGORY_KIND: dict[str, str] = {
    # profile: declared by the participant on their LinkedIn profile.
    "Company Names": "profile",
    "Degrees": "profile",
    "degreeClass": "profile",
    "Member Schools": "profile",
    "Fields of Study": "profile",
    "Graduation Year": "profile",
    "Member Groups": "profile",
    "Job Titles": "profile",
    "Profile Locations": "profile",
    "Interface Locales": "profile",
    "interfaceLocale": "profile",
    # network: derived from the participant's LinkedIn connections/follows.
    "Company Connections": "network",
    "Company Follower of": "network",
    # derived: inferred or built by LinkedIn, not declared or connection-based.
    # Member Skills includes skills LinkedIn infers, not only the ones listed
    # on the profile.
    "Member Age": "derived",
    "Member Gender": "derived",
    "Buyer Groups": "derived",
    "Company Category": "derived",
    "Company Size": "derived",
    "Company Growth Rate": "derived",
    "Company Industries": "derived",
    "Company Revenue": "derived",
    "Devices": "derived",
    "Function By Size": "derived",
    "Job Functions": "derived",
    "Job Seniorities": "derived",
    "Years of Experience": "derived",
    "Member Interests": "derived",
    "Member Traits": "derived",
    "High Value Audience Segments": "derived",
    "Standard Audience Segments": "derived",
    "Member Skills": "derived",
}


def strip_notes(b: io.BytesIO) -> io.BytesIO:
    """
    Strip notes LinkedIn puts at the start of CSV files
    """

    try:
        pattern = re.compile(rb'^(.*?)\n\n', re.DOTALL)
        out = io.BytesIO(pattern.sub(b'', b.read()))
    except Exception:
        out = b

    return out


def ad_targeting_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract what LinkedIn uses to target the participant with ads.

    ``Ad_Targeting.csv`` is a single wide row of roughly 35 columns, each a
    semicolon-separated list (inferred age bracket, employers, schools, job
    titles, skills, audience segments, and more). This reshapes that one row
    into a long ``Category``/``Kind``/``Value`` table — one row per non-empty
    semicolon-separated entry — so it can be read as a table and fed a
    wordcloud or bar chart at all. ``Kind`` classifies each ``Category`` via
    ``AD_TARGETING_CATEGORY_KIND`` as "profile" (declared by the participant),
    "network" (derived from connections/follows), or "derived" (inferred or
    built by LinkedIn); a column not in that mapping gets "unclassified"
    rather than a guess.

    Read via ``reader.raw`` and a positional ``csv.reader`` rather than
    ``reader.csv`` (which uses ``csv.DictReader``): the real export repeats
    some column names verbatim (e.g. "Job Titles" three times) with
    identical content, and ``DictReader`` collapses same-named columns,
    silently dropping all but the last. A positional read keeps every
    column, and an exact ``(header, value)`` dedup below then removes the
    genuine content-duplicates the export itself repeats — so a repeated
    column contributes its values once, not once per repeat.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Category``, ``Kind``, ``Value``. One row per non-empty
        semicolon-separated entry across every source column.
        Empty DataFrame when the file is absent, holds no data row, or
        parsing fails.

    Table documentation::

        {
          "summary": "Each row is one attribute value from LinkedIn's ad-targeting profile of the participant, reshaped from a single wide row into one row per value, with the kind of attribute it is.",
          "source_file": "Ad_Targeting.csv",
          "columns": {
            "Category": "The source column this value came from (e.g. Job Titles, Member Interests).",
            "Kind": "Whether the attribute came from the participant's profile, from their network, or was derived by LinkedIn.",
            "Value": "One value LinkedIn has attached to the participant under that category."
          }
        }

    Table config::

        {
          "id": "linkedin_ad_targeting",
          "title": {
            "en": "What LinkedIn uses to target you with ads",
            "nl": "Waarmee LinkedIn je advertenties richt"
          },
          "description": {
            "en": "The attributes LinkedIn uses to target you with ads, from Ad_Targeting.csv: some are from your profile, some from your network, and some LinkedIn derived itself.",
            "nl": "De kenmerken die LinkedIn gebruikt om je advertenties te richten, uit Ad_Targeting.csv: sommige komen van je profiel, sommige van je netwerk, en sommige heeft LinkedIn zelf afgeleid."
          },
          "headers": {
            "Category": {"en": "Category", "nl": "Categorie"},
            "Kind": {"en": "Kind", "nl": "Soort"},
            "Value": {"en": "Value", "nl": "Waarde"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Everything LinkedIn has inferred about you",
                "nl": "Alles wat LinkedIn over jou heeft afgeleid"
              },
              "type": "wordcloud",
              "textColumn": "Value",
              "tokenize": false
            },
            {
              "title": {
                "en": "Which kind of profile LinkedIn built the most",
                "nl": "Op welk soort profiel LinkedIn het meest heeft ingezet"
              },
              "type": "bar",
              "group": {"column": "Category", "label": {"en": "Category", "nl": "Categorie"}},
              "values": [{"aggregate": "count", "label": {"en": "Number of inferred values", "nl": "Aantal afgeleide waarden"}}]
            },
            {
              "title": {
                "en": "Where these attributes come from",
                "nl": "Waar deze kenmerken vandaan komen"
              },
              "type": "bar",
              "group": {"column": "Kind", "label": {"en": "Kind", "nl": "Soort"}},
              "values": [{"aggregate": "count", "label": {"en": "Number of values", "nl": "Aantal waarden"}}]
            }
          ]
        }
    """
    result = reader.raw("Ad_Targeting.csv")
    out = pd.DataFrame()
    if not result.found:
        return out
    try:
        raw = result.data.read()
        if not raw:
            return out
        text = raw.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) < 2:
            return out
        header = rows[0]

        seen: set[tuple[str, str]] = set()
        records = []
        for data_row in rows[1:]:
            for column, value in zip(header, data_row):
                value = (value or "").strip()
                if not value:
                    continue
                key = (column, value)
                if key in seen:
                    continue
                seen.add(key)
                kind = AD_TARGETING_CATEGORY_KIND.get(column, "unclassified")
                for token in value.split(";"):
                    token = token.strip()
                    if token:
                        records.append({"Category": column, "Kind": kind, "Value": token})
        out = pd.DataFrame(records)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def contact_info_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the phone numbers, email addresses, and registration details
    LinkedIn has on file, merging four small source files into one
    Field/Value table.

    Each source file is independently optional: an absent file simply
    contributes no rows for that field, never an error (ADR-0024).

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Field``, ``Value``. Up to five rows: phone number(s),
        WhatsApp number(s), email address(es), registration date,
        registration IP address.
        Empty DataFrame when all four source files are absent, empty, or
        parsing fails.

    Table documentation::

        {
          "summary": "One row per contact or registration field LinkedIn has on file, merged from four source files.",
          "source_file": "PhoneNumbers.csv, Whatsapp Phone Numbers.csv, Email Addresses.csv, Registration.csv",
          "columns": {
            "Field": "Name of the contact or registration field.",
            "Value": "Value(s) LinkedIn has on file for that field, joined with '; ' when there is more than one."
          }
        }

    Table config::

        {
          "id": "linkedin_contact_info",
          "title": {
            "en": "Your contact and registration details on file",
            "nl": "Uw contact- en registratiegegevens"
          },
          "description": {
            "en": "The phone numbers, email addresses, and registration details LinkedIn has on file, from PhoneNumbers.csv, Whatsapp Phone Numbers.csv, Email Addresses.csv and Registration.csv.",
            "nl": "De telefoonnummers, e-mailadressen en registratiegegevens die LinkedIn heeft geregistreerd, uit PhoneNumbers.csv, Whatsapp Phone Numbers.csv, Email Addresses.csv en Registration.csv."
          },
          "headers": {
            "Field": {"en": "Field", "nl": "Veld"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    out = pd.DataFrame()
    rows = []
    try:
        phones = reader.csv("PhoneNumbers.csv")
        if phones.found and not phones.data.empty and "Number" in phones.data.columns:
            values = [str(v).strip() for v in phones.data["Number"] if str(v).strip()]
            if values:
                rows.append({"Field": "Phone number(s)", "Value": "; ".join(values)})

        whatsapp = reader.csv("Whatsapp Phone Numbers.csv")
        if whatsapp.found and not whatsapp.data.empty and "Number" in whatsapp.data.columns:
            values = [str(v).strip() for v in whatsapp.data["Number"] if str(v).strip()]
            if values:
                rows.append({"Field": "WhatsApp number(s)", "Value": "; ".join(values)})

        emails = reader.csv("Email Addresses.csv")
        if emails.found and not emails.data.empty and "Email Address" in emails.data.columns:
            values = [str(v).strip() for v in emails.data["Email Address"] if str(v).strip()]
            if values:
                rows.append({"Field": "Email address(es)", "Value": "; ".join(values)})

        registration = reader.csv("Registration.csv")
        if registration.found and not registration.data.empty:
            reg_row = registration.data.iloc[0]
            registered_at = str(reg_row.get("Registered At", "") or "").strip()
            if registered_at:
                rows.append({"Field": "Registration date", "Value": registered_at})
            registration_ip = str(reg_row.get("Registration Ip", "") or "").strip()
            if registration_ip:
                rows.append({"Field": "Registration IP address", "Value": registration_ip})

        if rows:
            out = pd.DataFrame(rows)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


def company_follows_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the companies the participant follows on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Company Follows.csv``: typically
        ``Organization``, ``Followed On``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one company the participant follows on LinkedIn.",
          "source_file": "Company Follows.csv",
          "columns": {
            "Organization": "Name of the followed company.",
            "Followed On": "Date on which the participant started following the company."
          }
        }

    Table config::

        {
          "id": "linked_in_company_follows",
          "title": {"en": "Companies you follow", "nl": "Bedrijven die je volgt"},
          "description": {
            "en": "The companies you follow on LinkedIn, from Company Follows.csv.",
            "nl": "De bedrijven die u op LinkedIn volgt, uit Company Follows.csv."
          },
          "headers": {
            "Organization": {"en": "Organization", "nl": "Organisatie"},
            "Followed On": {"en": "Followed On", "nl": "Gevolgd op"}
          },
          "visualizations": [
            {
              "title": {"en": "When you started following companies", "nl": "Wanneer je bedrijven begon te volgen"},
              "type": "area",
              "group": {"column": "Followed On", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Companies followed", "nl": "Gevolgde bedrijven"}}]
            }
          ]
        }
    """
    result = reader.csv("Company Follows.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def member_follows_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the LinkedIn members the participant follows.

    Strips the introductory notes block LinkedIn prepends to the CSV.

    Parameters
    ----------
    reader:
        Archive reader used to load files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Member_Follows.csv`` after stripping notes.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one LinkedIn member the participant follows.",
          "source_file": "Member_Follows.csv",
          "columns": {
            "To": "Name or identifier of the followed member.",
            "To Name": "Display name of the followed member."
          }
        }

    Table config::

        {
          "id": "linkedin_member_follows",
          "title": {"en": "Members you follow", "nl": "Leden die je volgt"},
          "description": {
            "en": "The LinkedIn members you follow, from Member_Follows.csv.",
            "nl": "De LinkedIn-leden die u volgt, uit Member_Follows.csv."
          },
          "headers": {
            "To": {"en": "To", "nl": "Aan"},
            "To Name": {"en": "To Name", "nl": "Naam"}
          }
        }
    """
    result = reader.raw("Member_Follows.csv")
    if not result.found:
        return pd.DataFrame()
    b = strip_notes(result.data)
    df = eh.read_csv_from_bytes_to_df(b)
    return df


def connections_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the participant's LinkedIn connections.

    Strips the introductory notes block LinkedIn prepends to the CSV.

    Parameters
    ----------
    reader:
        Archive reader used to load files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``First Name``, ``Last Name``, ``Email Address``, ``Company``,
        ``Position``, ``Connected On``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one first-degree LinkedIn connection of the participant.",
          "source_file": "Connections.csv",
          "columns": {
            "First Name": "First name of the connection.",
            "Last Name": "Last name of the connection.",
            "Email Address": "Email address of the connection, if shared.",
            "Company": "Current employer of the connection.",
            "Position": "Current job title of the connection.",
            "Connected On": "Date on which the connection was established."
          }
        }

    Table config::

        {
          "id": "linkedin_connections",
          "title": {"en": "Your LinkedIn connections", "nl": "Je LinkedIn-connecties"},
          "description": {
            "en": "Your first-degree LinkedIn connections, from Connections.csv.",
            "nl": "Uw eerstegraads LinkedIn-connecties, uit Connections.csv."
          },
          "headers": {
            "First Name": {"en": "First Name", "nl": "Voornaam"},
            "Last Name": {"en": "Last Name", "nl": "Achternaam"},
            "Email Address": {"en": "Email Address", "nl": "E-mailadres"},
            "Company": {"en": "Company", "nl": "Bedrijf"},
            "Position": {"en": "Position", "nl": "Functie"},
            "Connected On": {"en": "Connected On", "nl": "Verbonden op"}
          },
          "visualizations": [
            {
              "title": {"en": "When you connected with people", "nl": "Wanneer je met mensen verbonden raakte"},
              "type": "area",
              "group": {"column": "Connected On", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "New connections", "nl": "Nieuwe connecties"}}]
            },
            {
              "title": {"en": "Companies your connections work at", "nl": "Bedrijven waar je connecties werken"},
              "type": "wordcloud",
              "textColumn": "Company",
              "tokenize": false
            },
            {
              "title": {"en": "Job titles among your connections", "nl": "Functietitels onder je connecties"},
              "type": "wordcloud",
              "textColumn": "Position",
              "tokenize": true
            }
          ]
        }
    """
    result = reader.raw("Connections.csv")
    if not result.found:
        return pd.DataFrame()
    b = strip_notes(result.data)
    df = eh.read_csv_from_bytes_to_df(b)
    return df


def reactions_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the participant's reactions on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Reactions.csv``: typically ``Date``, ``Type``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one reaction the participant gave to a post or content on LinkedIn.",
          "source_file": "Reactions.csv",
          "columns": {
            "Date": "Date of the reaction.",
            "Type": "Type of reaction (e.g. Like, Celebrate, Support)."
          }
        }

    Table config::

        {
          "id": "linkedin_reactions",
          "title": {"en": "Your reactions on LinkedIn", "nl": "Je reacties op LinkedIn"},
          "description": {
            "en": "Your reactions to posts on LinkedIn, from Reactions.csv.",
            "nl": "Uw reacties op berichten op LinkedIn, uit Reactions.csv."
          },
          "headers": {
            "Date": {"en": "Date", "nl": "Datum"},
            "Type": {"en": "Type", "nl": "Type"}
          },
          "visualizations": [
            {
              "title": {
                "en": "The type of reactions you give most",
                "nl": "Het soort reacties dat je het meest geeft"
              },
              "type": "bar",
              "group": {"column": "Type", "label": {"en": "Reaction type", "nl": "Type reactie"}},
              "values": [{"aggregate": "count", "label": {"en": "Times given", "nl": "Aantal keer gegeven"}}]
            }
          ]
        }
    """
    result = reader.csv("Reactions.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def ads_clicked_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the advertisements the participant clicked on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Ads Clicked.csv``: typically
        ``Ad clicked Date``, ``Ad Title/Id``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one advertisement the participant clicked on LinkedIn.",
          "source_file": "Ads Clicked.csv",
          "columns": {
            "Ad clicked Date": "Date on which the ad was clicked.",
            "Ad Title/Id": "Title or numeric ID of the clicked advertisement."
          }
        }

    Table config::

        {
          "id": "linkedin_ads_clicked",
          "title": {"en": "Ads you clicked on", "nl": "Advertenties waarop je hebt geklikt"},
          "description": {
            "en": "The ads you clicked on LinkedIn, from Ads Clicked.csv. Note: LinkedIn only provides numeric ad IDs, not ad titles or descriptions.",
            "nl": "De advertenties waarop u op LinkedIn heeft geklikt, uit Ads Clicked.csv. Let op: LinkedIn geeft alleen numerieke advertentie-ID's, geen titels of beschrijvingen."
          },
          "headers": {
            "Ad clicked Date": {"en": "Ad clicked Date", "nl": "Advertentiedatum"},
            "Ad Title/Id": {"en": "Ad Title/Id", "nl": "Advertentietitel/id"}
          },
          "visualizations": [
            {
              "title": {"en": "Ads you clicked on", "nl": "Advertenties waarop je hebt geklikt"},
              "type": "wordcloud",
              "textColumn": "Ad Title/Id",
              "tokenize": false
            }
          ]
        }
    """
    result = reader.csv("Ads Clicked.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def search_queries_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the participant's search queries on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``SearchQueries.csv``: typically
        ``Time``, ``Search Query``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one search query the participant performed on LinkedIn.",
          "source_file": "SearchQueries.csv",
          "columns": {
            "Time": "Timestamp of when the search was performed.",
            "Search Query": "The search term entered by the participant."
          }
        }

    Table config::

        {
          "id": "linkedin_search_queries",
          "title": {"en": "Your search queries on LinkedIn", "nl": "Je zoekopdrachten op LinkedIn"},
          "description": {
            "en": "Your search queries on LinkedIn, from SearchQueries.csv.",
            "nl": "Uw zoekopdrachten op LinkedIn, uit SearchQueries.csv."
          },
          "headers": {
            "Time": {"en": "Time", "nl": "Tijd"},
            "Search Query": {"en": "Search Query", "nl": "Zoekterm"}
          },
          "visualizations": [
            {
              "title": {
                "en": "What you searched for on LinkedIn",
                "nl": "Waar je naar hebt gezocht op LinkedIn"
              },
              "type": "wordcloud",
              "textColumn": "Search Query",
              "tokenize": true
            },
            {
              "title": {"en": "Your LinkedIn searches over time", "nl": "Je LinkedIn-zoekopdrachten in de loop van de tijd"},
              "type": "area",
              "group": {"column": "Time", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Searches", "nl": "Zoekopdrachten"}}]
            }
          ]
        }
    """
    result = reader.csv("SearchQueries.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def shares_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the posts the participant shared on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Shares.csv``: typically ``Date``,
        ``ShareLink``, ``ShareCommentary``, ``SharedUrl``, ``MediaUrl``,
        ``Visibility``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one post the participant shared on LinkedIn.",
          "source_file": "Shares.csv",
          "columns": {
            "Date": "Date of the share.",
            "ShareLink": "Link to the share.",
            "ShareCommentary": "Text commentary added when sharing.",
            "SharedUrl": "URL of the content that was shared.",
            "MediaUrl": "URL of any media attached to the share.",
            "Visibility": "Visibility setting of the share (e.g. PUBLIC, CONNECTIONS)."
          }
        }

    Table config::

        {
          "id": "linkedin_shares",
          "title": {"en": "Posts you shared on LinkedIn", "nl": "Berichten die je hebt gedeeld op LinkedIn"},
          "description": {
            "en": "The posts you shared on LinkedIn, from Shares.csv.",
            "nl": "De berichten die u op LinkedIn heeft gedeeld, uit Shares.csv."
          },
          "headers": {
            "Date": {"en": "Date", "nl": "Datum"},
            "ShareLink": {"en": "ShareLink", "nl": "Gedeelde link"},
            "ShareCommentary": {"en": "ShareCommentary", "nl": "Gedeelde tekst"},
            "SharedUrl": {"en": "SharedUrl", "nl": "Gedeelde URL"},
            "MediaUrl": {"en": "MediaUrl", "nl": "Media-URL"},
            "Visibility": {"en": "Visibility", "nl": "Zichtbaarheid"}
          },
          "visualizations": [
            {
              "title": {"en": "Words in what you shared", "nl": "Woorden in wat je hebt gedeeld"},
              "type": "wordcloud",
              "textColumn": "ShareCommentary",
              "tokenize": true
            }
          ]
        }
    """
    result = reader.csv("Shares.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def comments_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the participant's comments on LinkedIn.

    Parameters
    ----------
    reader:
        Archive reader used to load CSV files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns as returned by ``Comments.csv``: typically ``Date``,
        ``Message``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one comment the participant posted on LinkedIn content.",
          "source_file": "Comments.csv",
          "columns": {
            "Date": "Date of the comment.",
            "Message": "Text of the comment."
          }
        }

    Table config::

        {
          "id": "linkedin_comments",
          "title": {"en": "Your comments on LinkedIn", "nl": "Je reacties op LinkedIn"},
          "description": {
            "en": "The comments you posted on LinkedIn content, from Comments.csv.",
            "nl": "De reacties die u op LinkedIn-content heeft geplaatst, uit Comments.csv."
          },
          "headers": {
            "Date": {"en": "Date", "nl": "Datum"},
            "Message": {"en": "Message", "nl": "Bericht"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Words in your comments",
                "nl": "Woorden in je reacties"
              },
              "type": "wordcloud",
              "textColumn": "Message",
              "tokenize": true
            },
            {
              "title": {"en": "When you commented on LinkedIn", "nl": "Wanneer je op LinkedIn hebt gereageerd"},
              "type": "area",
              "group": {"column": "Date", "dateFormat": "auto", "label": {"en": "Date", "nl": "Datum"}},
              "values": [{"aggregate": "count", "label": {"en": "Comments", "nl": "Reacties"}}]
            }
          ]
        }
    """
    result = reader.csv("Comments.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


# ---------------------------------------------------------------------------
# Extractor registry & platform info
# ---------------------------------------------------------------------------

#: Mapping from the string names used in port_config.json to actual extractor functions.
EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "ad_targeting_to_df": ad_targeting_to_df,
    "contact_info_to_df": contact_info_to_df,
    "ads_clicked_to_df": ads_clicked_to_df,
    "comments_to_df": comments_to_df,
    "company_follows_to_df": company_follows_to_df,
    "shares_to_df": shares_to_df,
    "reactions_to_df": reactions_to_df,
    "connections_to_df": connections_to_df,
    "search_queries_to_df": search_queries_to_df,
    "member_follows_to_df": member_follows_to_df,
}


# ---------------------------------------------------------------------------
# Main extraction & flow
# ---------------------------------------------------------------------------

def extraction(linkedin_zip: SeekableBinaryReader, validation: validate.ValidateInput) -> ExtractionResult:
    """Extract data from a LinkedIn DDP zip and return consent-form tables.

    Parameters
    ----------
    linkedin_zip:
        Seekable binary reader over the LinkedIn DDP zip — the upload
        adapter itself, never a path (ADR-0026).
    validation:
        Validation result object whose ``archive_members`` attribute is passed
        to ``ZipArchiveReader``.
    """
    config = load_port_config(EXTRACTOR_REGISTRY, "linkedin")
    errors: Counter = Counter()
    reader = ZipArchiveReader(linkedin_zip, validation.archive_members, errors)
    return run_extraction(reader, errors, config)


class LinkedInFlow(FlowBuilder):
    """Flow implementation for the LinkedIn data donation study."""

    def __init__(self, session_id: str):
        super().__init__(session_id, "LinkedIn")

    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file_value, validation):
        return extraction(file_value, validation)


def process(session_id):
    flow = LinkedInFlow(session_id)
    return flow.start_flow()
