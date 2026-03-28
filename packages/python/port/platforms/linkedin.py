"""
LinkedIn

This module contains an example flow of a LinkedIn data donation study

Assumptions:
It handles DDPs in the english language with filetype CSV.
"""

import logging
from collections import Counter
import io
import re

import pandas as pd

import port.api.props as props
import port.api.d3i_props as d3i_props
from port.api.d3i_props import ExtractionResult
import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
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
        ]
    ),
]

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


def company_follows_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Company Follows.csv'
    """
    result = reader.csv("Company Follows.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def member_follows_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Member_Follows.csv'
    """
    result = reader.raw("Member_Follows.csv")
    if not result.found:
        return pd.DataFrame()
    b = strip_notes(result.data)
    df = eh.read_csv_from_bytes_to_df(b)
    return df


def connections_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Connections.csv'
    """
    result = reader.raw("Connections.csv")
    if not result.found:
        return pd.DataFrame()
    b = strip_notes(result.data)
    df = eh.read_csv_from_bytes_to_df(b)
    return df


def reactions_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Reactions.csv'
    """
    result = reader.csv("Reactions.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def ads_clicked_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Ads Clicked.csv'
    """
    result = reader.csv("Ads Clicked.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def search_queries_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'SearchQueries.csv'
    """
    result = reader.csv("SearchQueries.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def shares_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Shares.csv'
    """
    result = reader.csv("Shares.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def comments_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """
    'Comments.csv'
    """
    result = reader.csv("Comments.csv")
    if not result.found:
        return pd.DataFrame()
    return result.data


def extraction(linkedin_zip: str, validation: validate.ValidateInput) -> ExtractionResult:
    errors = Counter()
    reader = ZipArchiveReader(linkedin_zip, validation.archive_members, errors)
    tables = [
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_ads_clicked",
            data_frame=ads_clicked_to_df(reader, errors),
            title=props.Translatable({
                "en": "Ads you clicked on",
                "nl": "Ads clicked"
            }),
            description=props.Translatable({
                "en": "Advertisements you clicked on while using LinkedIn. These show what professional opportunities and products caught your eye.",
                "nl": "Advertenties waarop u heeft geklikt tijdens het gebruik van LinkedIn. Deze laten zien welke professionele kansen en producten uw aandacht trokken.",
            }),
            headers={
                "Ad clicked Date": props.Translatable({"en": "Ad clicked Date", "nl": "Advertentiedatum"}),
                "Ad Title/Id": props.Translatable({"en": "Ad Title/Id", "nl": "Advertentietitel/id"}),
            }
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_comments",
            data_frame=comments_to_df(reader, errors),
            title=props.Translatable({
                "en": "Your comments on LinkedIn",
                "nl": "Comments"
            }),
            description=props.Translatable({
                "en": "Comments you posted on LinkedIn. These reflect how you engage in professional discussions.",
                "nl": "Reacties die u op LinkedIn heeft geplaatst. Deze weerspiegelen hoe u deelneemt aan professionele discussies.",
            }),
            headers={
                "Date": props.Translatable({"en": "Date", "nl": "Datum"}),
                "Message": props.Translatable({"en": "Message", "nl": "Bericht"}),
            },
            visualizations=[
                {
                    "title": {
                        "en": "Words in your comments",
                        "nl": "Words in your comments"
                    },
                    "type": "wordcloud",
                    "textColumn": "Message",
                    "tokenize": True
                }
            ]
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linked_in_company_follows",
            data_frame=company_follows_to_df(reader, errors),
            title=props.Translatable({
                "en": "Companies you follow",
                "nl": "Company follows"
            }),
            description=props.Translatable({
                "en": "Companies you follow on LinkedIn. This reflects the industries and organizations you're interested in.",
                "nl": "Bedrijven die u volgt op LinkedIn. Dit weerspiegelt de sectoren en organisaties waarin u geïnteresseerd bent.",
            }),
            headers={
                "Organization": props.Translatable({"en": "Organization", "nl": "Organisatie"}),
                "Followed On": props.Translatable({"en": "Followed On", "nl": "Gevolgd op"}),
            }
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_shares",
            data_frame=shares_to_df(reader, errors),
            title=props.Translatable({
                "en": "Posts you shared on LinkedIn",
                "nl": "Shares"
            }),
            description=props.Translatable({
                "en": "Content you shared with your professional network on LinkedIn.",
                "nl": "Content die u heeft gedeeld met uw professionele netwerk op LinkedIn.",
            }),
            headers={
                "Date": props.Translatable({"en": "Date", "nl": "Datum"}),
                "ShareLink": props.Translatable({"en": "ShareLink", "nl": "Gedeelde link"}),
                "ShareCommentary": props.Translatable({"en": "ShareCommentary", "nl": "Gedeelde tekst"}),
                "SharedUrl": props.Translatable({"en": "SharedUrl", "nl": "Gedeelde URL"}),
                "MediaUrl": props.Translatable({"en": "MediaUrl", "nl": "Media-URL"}),
                "Visibility": props.Translatable({"en": "Visibility", "nl": "Zichtbaarheid"}),
            }
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_reactions",
            data_frame=reactions_to_df(reader, errors),
            title=props.Translatable({
                "en": "Your reactions on LinkedIn",
                "nl": "Reactions"
            }),
            description=props.Translatable({
                "en": "Your reactions to posts and content on LinkedIn. This reveals what professional content resonates with you.",
                "nl": "Uw reacties op berichten en content op LinkedIn. Dit onthult welke professionele content bij u aanslaat.",
            }),
            headers={
                "Date": props.Translatable({"en": "Date", "nl": "Datum"}),
                "Type": props.Translatable({"en": "Type", "nl": "Type"}),
            },
            visualizations=[
                {
                    "title": {
                        "en": "The type of reactions you put under posts on Linkedin",
                        "nl": "The type of reactions you put under posts on Linkedin"
                    },
                    "type": "wordcloud",
                    "textColumn": "Type",
                    "tokenize": True
                }
            ]
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_connections",
            data_frame=connections_to_df(reader, errors),
            title=props.Translatable({
                "en": "Your LinkedIn connections",
                "nl": "Je LinkedIn-connecties"
            }),
            description=props.Translatable({
                "en": "Your professional connections on LinkedIn. This network represents your professional relationships over time.",
                "nl": "Uw professionele connecties op LinkedIn. Dit netwerk vertegenwoordigt uw professionele relaties in de loop van de tijd.",
            }),
            headers={
                "First Name": props.Translatable({"en": "First Name", "nl": "Voornaam"}),
                "Last Name": props.Translatable({"en": "Last Name", "nl": "Achternaam"}),
                "Email Address": props.Translatable({"en": "Email Address", "nl": "E-mailadres"}),
                "Company": props.Translatable({"en": "Company", "nl": "Bedrijf"}),
                "Position": props.Translatable({"en": "Position", "nl": "Functie"}),
                "Connected On": props.Translatable({"en": "Connected On", "nl": "Verbonden op"}),
            }
        ),
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="linkedin_search_queries",
            data_frame=search_queries_to_df(reader, errors),
            title=props.Translatable({
                "en": "Your search queries on LinkedIn",
                "nl": "Search queries"
            }),
            description=props.Translatable({
                "en": "What you searched for on LinkedIn. This reveals your professional interests, job searches, and networking patterns.",
                "nl": "Wat u op LinkedIn heeft gezocht. Dit onthult uw professionele interesses, zoekgedrag naar banen en netwerkpatronen.",
            }),
            headers={
                "Time": props.Translatable({"en": "Time", "nl": "Tijd"}),
                "Search Query": props.Translatable({"en": "Search Query", "nl": "Zoekterm"}),
            },
            visualizations=[
                {
                    "title": {
                        "en": "What you searched for on Linkedin",
                        "nl": "What you searched for on Linkedin"
                    },
                    "type": "wordcloud",
                    "textColumn": "Search Query",
                    "tokenize": True
                }
            ]
        )
    ]

    return ExtractionResult(
        tables=[table for table in tables if not table.data_frame.empty],
        errors=errors,
    )


class LinkedInFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(session_id, "LinkedIn")
        self.UI_TEXT["review_data_description"] = props.Translatable({
            "en": "Below you will find a curated selection of your LinkedIn data, showing the breadth of what LinkedIn collects about you. This includes your connections, reactions, search queries, and the ads you clicked on.",
            "nl": "Hieronder vindt u een samengestelde selectie van uw LinkedIn-gegevens, die laat zien hoeveel LinkedIn over u verzamelt. Dit omvat uw connecties, reacties, zoekopdrachten en de advertenties waarop u heeft geklikt.",
        })

    def get_instruction_image(self) -> str | None:
        return "linkedin_instructions.png"

    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file_value, validation):
        return extraction(file_value, validation)


def process(session_id):
    flow = LinkedInFlow(session_id)
    return flow.start_flow()
