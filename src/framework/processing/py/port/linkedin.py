"""
DDP extract LinkedIn module

Handles LinkedIn data download packages (CSV format, English only).
Ported from dd-vu-2026 linkedin.py with dd-education API adaptations.
"""

import logging
import io
import re
import zipfile
from pathlib import Path

import pandas as pd

import port.api.props as props
import port.unzipddp as unzipddp
import port.extraction_helpers as eh
import port.port_helpers as ph

from port.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
    ValidateInput,
    StatusCode,
)

logger = logging.getLogger(__name__)


DDP_CATEGORIES = [
    DDPCategory(
        id="csv_en",
        ddp_filetype=DDPFiletype.CSV,
        language=Language.EN,
        known_files=[
            "Ads Clicked.csv",
            "Ad_Targeting.csv",
            "Comments.csv",
            "Company Follows.csv",
            "Connections.csv",
            "Reactions.csv",
            "SearchQueries.csv",
            "Shares.csv",
            "Member_Follows.csv",
        ],
    )
]

STATUS_CODES = [
    StatusCode(id=0, description="Valid zip", message="Valid zip"),
    StatusCode(id=1, description="Bad zipfile", message="Bad zipfile"),
]


def strip_notes(b: io.BytesIO) -> io.BytesIO:
    """
    Strip the note LinkedIn prepends to some CSV files before the header row.
    Returns a fresh BytesIO with only the CSV content (header + rows).
    """
    try:
        content = b.read()
        pattern = re.compile(b"(?:^|\n)(\\w[^\n]*,[^\n]*\n(?:[^\n]*\n)*)", re.MULTILINE)
        match = pattern.search(content)
        if match:
            return io.BytesIO(match.group(1))
        return io.BytesIO(content)
    except Exception as e:
        logger.error("strip_notes error: %s", e)
        b.seek(0)
        return b


def validate_zip(zfile: str) -> ValidateInput:
    validation = ValidateInput(STATUS_CODES, DDP_CATEGORIES)
    try:
        paths = []
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                paths.append(Path(f).name)
        if validation.infer_ddp_category(paths):
            validation.set_status_code_by_id(0)
        else:
            validation.set_status_code_by_id(1)
    except zipfile.BadZipFile as e:
        logger.error("BadZipFile: %s", e)
        validation.set_status_code_by_id(1)
    except Exception as e:
        logger.error("Exception in validate_zip: %s", e)
        validation.set_status_code_by_id(1)
    return validation


# --- Data extraction helpers ---

def ads_clicked_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Ads Clicked.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def comments_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Comments.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def company_follows_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Company Follows.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def shares_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Shares.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def reactions_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Reactions.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def connections_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Connections.csv")
    b = strip_notes(b)
    return unzipddp.read_csv_from_bytes_to_df(b)


def member_follows_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Member_Follows.csv")
    b = strip_notes(b)
    return unzipddp.read_csv_from_bytes_to_df(b)


def search_queries_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "SearchQueries.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


# --- Package explorer ---

def extraction(linkedin_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Package explorer: 7 curated tables showing the breadth of LinkedIn data.
    Column renames to Dutch match dd-vu-2026 source.
    """
    tables_to_render = []

    df = ads_clicked_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "Ad clicked Date": "Advertentiedatum",
            "Ad Title/Id": "Advertentietitel/id",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_ads_clicked",
            props.Translatable({"en": "Ads you clicked on", "nl": "Ads clicked"}),
            df,
            props.Translatable({
                "en": "Record of advertisements you have clicked on while using LinkedIn.",
                "nl": "Overzicht van advertenties waarop je hebt geklikt tijdens het gebruik van LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = comments_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Date": "Datum", "Message": "Bericht"})
        wordcloud = {
            "title": {"en": "Words in your comments", "nl": "Woorden in je reacties"},
            "type": "wordcloud",
            "textColumn": "Bericht",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_comments",
            props.Translatable({"en": "Your comments on LinkedIn", "nl": "Comments"}),
            df,
            props.Translatable({
                "en": "Comments you've posted on LinkedIn content.",
                "nl": "Reacties die je hebt geplaatst op LinkedIn-content.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    df = company_follows_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Organization": "Organisatie", "Followed On": "Gevolgd op"})
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_company_follows",
            props.Translatable({"en": "Companies you follow", "nl": "Company follows"}),
            df,
            props.Translatable({
                "en": "List of companies you are following on LinkedIn.",
                "nl": "Lijst van bedrijven die je volgt op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = shares_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "Date": "Datum",
            "ShareLink": "Gedeelde link",
            "ShareCommentary": "Gedeelde tekst",
            "SharedUrl": "Gedeelde URL",
            "MediaUrl": "Media-URL",
            "Visibility": "Zichtbaarheid",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_shares",
            props.Translatable({"en": "Posts you shared on LinkedIn", "nl": "Shares"}),
            df,
            props.Translatable({
                "en": "Content you've shared with your network on LinkedIn.",
                "nl": "Content die je hebt gedeeld met je netwerk op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = reactions_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Date": "Datum"})
        # "Type" column is intentionally not renamed — used as-is for wordcloud
        wordcloud = {
            "title": {"en": "Your reaction types", "nl": "Jouw reactietypes"},
            "type": "wordcloud",
            "textColumn": "Type",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_reactions",
            props.Translatable({"en": "Your reactions on LinkedIn", "nl": "Reactions"}),
            df,
            props.Translatable({
                "en": "Record of your reactions to posts and content on LinkedIn.",
                "nl": "Overzicht van je reacties op berichten en content op LinkedIn.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    df = connections_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "First Name": "Voornaam",
            "Last Name": "Achternaam",
            "Email Address": "E-mailadres",
            "Company": "Bedrijf",
            "Position": "Functie",
            "Connected On": "Verbonden op",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_connections",
            props.Translatable({"en": "Your LinkedIn connections", "nl": "Je LinkedIn-connecties"}),
            df,
            props.Translatable({
                "en": "List of people you are connected with on LinkedIn.",
                "nl": "Lijst van mensen met wie je verbonden bent op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = search_queries_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Time": "Tijd", "Search Query": "Zoekterm"})
        wordcloud = {
            "title": {"en": "What you searched for", "nl": "Wat je zocht"},
            "type": "wordcloud",
            "textColumn": "Zoekterm",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_search_queries",
            props.Translatable({"en": "Your search queries on LinkedIn", "nl": "Search queries"}),
            df,
            props.Translatable({
                "en": "Terms and phrases you've searched for on LinkedIn.",
                "nl": "Termen en zinnen waarnaar je hebt gezocht op LinkedIn.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    return tables_to_render


# --- Researcher view ---

def extraction_researcher(linkedin_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Researcher view: aggregate-only tables.
    No individual names, messages, or raw queries — only counts per time
    bucket, reaction type distribution, and search term frequency.
    """
    tables_to_render = []

    # Table 1: new connections over time
    try:
        df = connections_to_df(linkedin_zip)
        # connections_to_df() returns raw column "Connected On" (rename is in extraction() only)
        if not df.empty and "Connected On" in df.columns:
            df["Connected On"] = df["Connected On"].apply(eh.try_to_convert_any_timestamp_to_iso8601)
            df_month = (
                df[df["Connected On"].str.len() >= 7]
                .assign(Month=lambda x: x["Connected On"].str[:7])
                .groupby("Month")
                .size()
                .reset_index(name="Count")
            )
            if not df_month.empty:
                chart = {
                    "title": {"en": "New connections over time", "nl": "Nieuwe connecties over tijd"},
                    "type": "area",
                    "group": {"column": "Month"},
                    "values": [{"column": "Count", "label": {"en": "Connections", "nl": "Connecties"}}],
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_connections",
                    props.Translatable({"en": "New connections over time", "nl": "Nieuwe connecties over tijd"}),
                    df_month,
                    props.Translatable({
                        "en": "Number of new LinkedIn connections made each month.",
                        "nl": "Aantal nieuwe LinkedIn-connecties per maand.",
                    }),
                    [chart],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher connections error: %s", e)

    # Table 2: reaction type counts
    try:
        df = reactions_to_df(linkedin_zip)
        if not df.empty and "Type" in df.columns:
            df_types = (
                df.groupby("Type")
                .size()
                .reset_index(name="Count")
            )
            if not df_types.empty:
                chart = {
                    "title": {"en": "Reaction types", "nl": "Reactietypes"},
                    "type": "bar",
                    "group": {"column": "Type"},
                    "values": [{"column": "Count", "label": {"en": "Count", "nl": "Aantal"}}],
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_reactions",
                    props.Translatable({"en": "Reaction types", "nl": "Reactietypes"}),
                    df_types,
                    props.Translatable({
                        "en": "Distribution of reaction types you used on LinkedIn.",
                        "nl": "Verdeling van reactietypes die je hebt gebruikt op LinkedIn.",
                    }),
                    [chart],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher reactions error: %s", e)

    # Table 3: most searched terms (wordcloud from raw text column)
    try:
        df = search_queries_to_df(linkedin_zip)
        # search_queries_to_df() returns raw column "Search Query" (rename is in extraction() only)
        if not df.empty and "Search Query" in df.columns:
            df_queries = df[["Search Query"]].dropna()
            if not df_queries.empty:
                wordcloud = {
                    "title": {"en": "Most searched terms", "nl": "Meest gezochte termen"},
                    "type": "wordcloud",
                    "textColumn": "Search Query",
                    "tokenize": True,
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_searches",
                    props.Translatable({"en": "Most searched terms", "nl": "Meest gezochte termen"}),
                    df_queries,
                    props.Translatable({
                        "en": "Frequency of terms searched on LinkedIn.",
                        "nl": "Hoe vaak termen zijn gezocht op LinkedIn.",
                    }),
                    [wordcloud],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher searches error: %s", e)

    return tables_to_render


# --- Text constants ---

SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your LinkedIn file",
    "nl": "Selecteer uw LinkedIn bestand",
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your LinkedIn data",
    "nl": "Uw LinkedIn gegevens",
})

RETRY_HEADER = props.Translatable({
    "en": "Try again",
    "nl": "Probeer opnieuw",
})

CONSENT_FORM_DESCRIPTION = props.Translatable({
    "en": "Below you will find a curated selection of your LinkedIn data showing the breadth of what LinkedIn collects about you.",
    "nl": "Hieronder vindt u een samengestelde selectie van uw LinkedIn-gegevens die de breedte laat zien van wat LinkedIn over u verzamelt.",
})

RESEARCHER_VIEW_HEADER = props.Translatable({
    "en": "Your LinkedIn data — researcher view",
    "nl": "Uw LinkedIn gegevens — onderzoekersweergave",
})

RESEARCHER_DESCRIPTION = props.Translatable({
    "en": "This view shows only aggregate statistics — the kind of data a researcher would collect in a real data donation study. No individual names, messages, or raw queries are shown.",
    "nl": "Deze weergave toont alleen geaggregeerde statistieken — het soort gegevens dat een onderzoeker zou verzamelen in een echte datadoneringsstudie.",
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "Please follow the instructions below carefully!\nClick on the button \u201cContinue\u201d at the bottom of this page when you are ready to go to the next step.",
    "nl": "Volg de onderstaande instructies zorgvuldig!\nKlik op de knop \u201cDoorgaan\u201d onderaan deze pagina wanneer u klaar bent voor de volgende stap.",
})

INSTRUCTION_HEADER = props.Translatable({
    "en": "Instructions to request your LinkedIn data",
    "nl": "Instructies om uw LinkedIn-gegevens op te vragen",
})


# --- Script ---

def script():
    platform_name = "LinkedIn"
    table_list = None
    table_list_researcher = None

    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "instructions.svg")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            validation = validate_zip(file_result.value)

            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                table_list = extraction(file_result.value)
                table_list_researcher = extraction_researcher(file_result.value)
                break

            if validation.status_code.id != 0:
                logger.info("Not a valid %s zip; prompt retry_confirmation", platform_name)
                retry_result = yield ph.render_page(RETRY_HEADER, ph.retry_confirmation(platform_name))
                if retry_result.__type__ == "PayloadTrue":
                    continue
                elif retry_result.value == "show issue form":
                    yield ph.render_issue_page(platform_name, file_result.value)
                    return
                else:
                    logger.info("Skipped during retry flow")
                    break

        else:
            logger.info("Skipped at file selection ending flow")
            break

    if table_list:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    if table_list_researcher:
        logger.info("Prompt researcher consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list_researcher, RESEARCHER_DESCRIPTION)
        result = yield ph.render_page(RESEARCHER_VIEW_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
