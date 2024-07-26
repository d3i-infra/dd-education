"""
DDP extract Netflix module
"""
from pathlib import Path
import logging
import zipfile
import json
from collections import Counter

import pandas as pd

import port.api.props as props
import port.unzipddp as unzipddp
import port.port_helpers as ph
from port.api.commands import CommandUIRender

from port.validate import (
    DDPCategory,
    Language,
    DDPFiletype,
    ValidateInput,
    StatusCode,
)

logger = logging.getLogger(__name__)

DDP_CATEGORIES = [
    DDPCategory(
        id="csv",
        ddp_filetype=DDPFiletype.CSV,
        language=Language.EN,
        known_files= [
            "MyList.csv",
             "ViewingActivity.csv",
             "SearchHistory.csv",
             "IndicatedPreferences.csv",
             "PlaybackRelatedEvents.csv",
             "InteractiveTitles.csv",
             "Ratings.csv",
             "GamePlaySession.txt",
             "IpAddressesLogin.csv",
             "IpAddressesAccountCreation.txt",
             "IpAddressesStreaming.csv",
             "Additional Information.pdf",
             "MessagesSentByNetflix.csv",
             "SocialMediaConnections.txt",
             "AccountDetails.csv",
             "ProductCancellationSurvey.txt",
             "CSContact.csv",
             "ChatTranscripts.csv",
             "Cover sheet.pdf",
             "Devices.csv",
             "ParentalControlsRestrictedTitles.txt",
             "AvatarHistory.csv",
             "Profiles.csv",
             "Clickstream.csv",
             "BillingHistory.csv",
         ]
    )
]

STATUS_CODES = [
    StatusCode(id=0, description="Valid zip", message="Valid zip"),
    StatusCode(id=1, description="Bad zipfile", message="Bad zipfile"),
]


def validate_zip(zfile: Path) -> ValidateInput:
    """
    Validates the input of an Youtube zipfile

    This function sets a validation object generated with ValidateInput
    This validation object can be read later on to infer possible problems with the zipfile
    I dont like this design myself, but I also havent found any alternatives that are better
    """

    validation = ValidateInput(STATUS_CODES, DDP_CATEGORIES)

    try:
        paths = []
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                p = Path(f)
                if p.suffix in (".txt", ".csv", ".pdf"):
                    logger.debug("Found: %s in zip", p.name)
                    paths.append(p.name)

        if validation.infer_ddp_category(paths):
            validation.set_status_code_by_id(0)
        else:
            validation.set_status_code_by_id(1)

    except zipfile.BadZipFile:
        validation.set_status_code_by_id(3)

    return validation


def extract_users_from_df(df: pd.DataFrame) -> list[str]:
    """
    Extracts all users from a netflix csv file 
    This function expects all users to be present in the first column
    of a pd.DataFrame
    """
    out = []
    try:
        out = df[df.columns[0]].unique().tolist()
        out.sort()
    except Exception as e:
        logger.error("Cannot extract users: %s", e)

    return out
    

def extract_users(netflix_zip):
    """
    Reads viewing activity and extracts users from the first column
    returns list[str]
    """
    b = unzipddp.extract_file_from_zip(netflix_zip, "ViewingActivity.csv")
    df = unzipddp.read_csv_from_bytes_to_df(b)
    users = extract_users_from_df(df)
    return users



def keep_user(df: pd.DataFrame, selected_user: str) -> pd.DataFrame:
    """
    Keep only the rows where the first column of df
    is equal to selected_user
    """
    try:
        df =  df.loc[df.iloc[:, 0] == selected_user].reset_index(drop=True)
    except Exception as e:  
        logger.info(e)

    return df

    
def netflix_to_df(netflix_zip: str, file_name: str, selected_user: str) -> pd.DataFrame:
    """
    netflix csv to df
    returns empty df in case of error
    """
    ratings_bytes = unzipddp.extract_file_from_zip(netflix_zip, file_name)
    df = unzipddp.read_csv_from_bytes_to_df(ratings_bytes)
    df = keep_user(df, selected_user)

    return df


def ratings_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract ratings from netflix zip to df
    Only keep the selected user
    """

    columns_to_keep = ["Title Name", "Thumbs Value", "Device Model", "Event Utc Ts"]
    columns_to_rename =  {
        "Title Name": "Titel",
        "Event Utc Ts": "Datum en tijd",
        "Device Model": "Gebruikte apparaat",
        "Thumbs Value": "Aantal duimpjes omhoog"
    }

    df = netflix_to_df(netflix_zip, "Ratings.csv", selected_user)

    # Extraction logic here
    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def time_string_to_hours(time_str):
    try:
        # Split the time string into hours, minutes, and seconds
        hours, minutes, seconds = map(int, time_str.split(':'))

        # Convert each component to hours
        hours_in_seconds = hours * 3600
        minutes_in_seconds = minutes * 60

        # Sum up the converted values
        total_hours = (hours_in_seconds + minutes_in_seconds + seconds) / 3600
    except:
        return 0

    return round(total_hours, 3)


def viewing_activity_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract ViewingActivity from netflix zip to df
    Only keep the selected user
    """

    columns_to_keep = ["Start Time","Duration","Title","Device Type"]
    columns_to_rename =  {
        "Start Time": "Start tijd",
        "Title": "Titel",
        "Device Type": "Apparaat",
        "Duration": "Aantal uur gekeken"
    }

    df = netflix_to_df(netflix_zip, "ViewingActivity.csv", selected_user)

    # Extraction logic here
    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)

        df['Aantal uur gekeken'] = df['Aantal uur gekeken'].apply(time_string_to_hours)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def clickstream_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract Clickstream from netflix zip to df
    """

    columns_to_keep = ["Source","Navigation Level","Click Utc Ts"]
    columns_to_rename =  {
        "Click Utc Ts": "Datum en tijd",
        "Source": "Bron"
    }

    df = netflix_to_df(netflix_zip, "Clickstream.csv", selected_user)

    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def my_list_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract MyList.csv from netflix zip to df
    """

    columns_to_keep = ["Title Name", "Utc Title Add Date"]
    columns_to_rename =  {
        "Utc Title Add Date": "Datum",
        "Title Name": "Titel"
    }

    df = netflix_to_df(netflix_zip, "MyList.csv", selected_user)

    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
            print("renamed")
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def indicated_preferences_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract MyList.csv from netflix zip to df
    """

    columns_to_keep = ["Show", "Has Watched", "Is Interested", "Event Date"]
    columns_to_rename =  {
        "Event Date": "Datum en tijd",
        "Has Watched": "Heeft u bekeken?",
        "Is Interested": "Toegevoegd",
        "Show": "Title"
    }

    df = netflix_to_df(netflix_zip, "IndicatedPreferences.csv", selected_user)

    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def playtraces_counts_to_df(df):
    """
    creates a df with counts for playback
    """
    out = []
    for item in df["Playtraces"]:
        events = json.loads(item)
        out.append(Counter([event.get("eventType") for event in events]))

    return pd.DataFrame(out).fillna(0)


def playback_related_events_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract PlaybackRelatedEvents.csv from netflix zip to df
    """

    columns_to_keep = ["Title Description", "Device", "Playback Start Utc Ts"]
    columns_to_rename =  {
        "Title Description": "Titel",
        "Playback Start Utc Ts": "Datum en tijd",
        "Device": "Apparaat"
    }

    df = netflix_to_df(netflix_zip, "PlaybackRelatedEvents.csv", selected_user)

    try:
        if not df.empty:
            playtraces_df = playtraces_counts_to_df(df)
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
            df = df.join(playtraces_df)

    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def search_history_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract SearchHistory.csv from netflix zip to df
    """

    columns_to_keep = ["Device", "Is Kids", "Query Typed", "Displayed Name", "Action", "Section", "Utc Timestamp"]
    columns_to_rename =  {
        "Utc Timestamp": "Datum",
        "Device": "Apparaat",
        "Query Typed": "zoekopdracht",
        "Displayed Name": "Titel",
        "Action": "Actie",
        "Section": "Sectie",
        "Device": "Apparaat",
    }

    df = netflix_to_df(netflix_zip, "SearchHistory.csv", selected_user)

    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df


def messages_sent_by_netflix_to_df(netflix_zip: str, selected_user: str)  -> pd.DataFrame:
    """
    Extract MessagesSentByNetflix.csv from netflix zip to df
    """

    columns_to_keep = ["Sent Utc Ts", "Message Name", "Channel", "Title Name", "Click Cnt"]
    columns_to_rename =  {
        "Sent Utc Ts": "Datum en tijd",
        "Click Cnt": "Aantal keer op geklikt",
        "Title Name": "Titel",
        "Message Name": "Type bericht",
        "Channel": "Type melding",
    }

    df = netflix_to_df(netflix_zip, "MessagesSentByNetflix.csv", selected_user)

    try:
        if not df.empty:
            df = df[columns_to_keep]
            df = df.rename(columns=columns_to_rename)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return df



# EXTRACTION LOGIC

def extraction(netflix_zip: str, selected_user: str) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []
    
    df = ratings_to_df(netflix_zip, selected_user)
    if not df.empty:
        wordcloud = {
            "title": {"en": "Titles rated by thumbs value", "nl": "Gekeken titles, grootte is gebasseerd op het aantal duimpjes omhoog"},
            "type": "wordcloud",
            "textColumn": "Titel",
            "valueColumn": "Aantal duimpjes omhoog",
        }
        table_title = props.Translatable({"en": "Your ratings on Netflix", "nl": "Uw beoordelingen op Netflix"})
        table_description = props.Translatable({
            "en": "Click 'Show Table' to view these ratings per row.", 
            "nl": "Klik op ‘Tabel tonen’ om deze beoordelingen per rij te bekijken."
        })
        table = props.PropsUIPromptConsentFormTable("netflix_rating", table_title, df, table_description, [wordcloud])
        tables_to_render.append(table)


    df = viewing_activity_to_df(netflix_zip, selected_user)
    if not df.empty:

        hours_logged_in = {
            "title": {"en": "Total hours watched per month of the year", "nl": "Totaal aantal uren gekeken per maand van het jaar"},
            "type": "area",
            "group": {
                "column": "Start tijd",
                "dateFormat": "month"
            },
            "values": [{
                "column": "Aantal uur gekeken",
                "aggregate": "sum",
            }]
        }

        at_what_time = {
            "title": {"en": "Total hours watch by hour of the day", "nl": "Totaal aantal uur gekeken op uur van de dag"},
            "type": "bar",
            "group": {
                "column": "Start tijd",
                "dateFormat": "hour_cycle"
            },
            "values": [{
                "column": "Aantal uur gekeken",
                "aggregate": "sum",
            }]
        }

        table_title = props.Translatable({"en": "What you watched", "nl": "Wanneer kijkt u Netflix"})
        table_description = props.Translatable({
            "en": "This table shows what titles you watched when, for how long, and on what device.", 
            "nl": "Klik op ‘Tabel tonen’ om voor elke keer dat u iets op Netflix heeft gekeken te zien welke serie of film dit was, wanneer u dit heeft gekeken, hoe lang u het heeft gekeken en op welk apparaat u het heeft gekeken."
        })
        table = props.PropsUIPromptConsentFormTable("netflix_viewings", table_title, df, table_description, [hours_logged_in, at_what_time])
        tables_to_render.append(table)

        df = clickstream_to_df(netflix_zip, selected_user)
        if not df.empty:
            table_description = props.Translatable({
                "en": "This table shows how you used the Netflix interface for finding content and learning more about titles. It includes the device you used and the specific times you clicked on a button in the Netflix interface (e.g., movie details, search bar)", 
                "nl": "Klik op ‘Tabel tonen’ om te zien welke opties in Netflix u heeft gebruikt om series en films te vinden, wanneer u deze opties heeft gebruikt en met welk apparaat. Het gaat om opties zoals de zoekfunctie of door middel van advertenties die Netflix aan u heeft laten zien."
            })
            table_title = props.Translatable({"en": "Which Netflixs functions you used", "nl": "Welke Netflix functies u heeft gebruikt"})
            table = props.PropsUIPromptConsentFormTable("netflix_clickstream", table_title, df, table_description, [])
            tables_to_render.append(table)

        # Extract my list
        df = my_list_to_df(netflix_zip, selected_user)
        if not df.empty:
            table_description = props.Translatable({
                "en": "This table shows which titles you added to your watch list and on what dates",
                "nl": "Klik op ‘Tabel tonen’ om te zien welke titels u heeft toegevoegd aan ‘Mijn lijst’ en wanneer u dit heeft gedaan. In ‘Mijn lijst’ heeft u bijvoorbeeld series en films opgeslagen die u graag nog wilt zien."
            })
            table_title = props.Translatable({"en": "What you added to your watch list", "nl": "Wat u aan uw watch list heeft toegevoegd"})
            table = props.PropsUIPromptConsentFormTable("netflix_my_list", table_title, df, table_description, []) 
            tables_to_render.append(table)

        # Extract Indicated preferences
        df = indicated_preferences_to_df(netflix_zip, selected_user)
        if not df.empty:
            table_description = props.Translatable({
                "en": "This table shows what titles you watched and whether you listed them as preferences (i.e, liked, added to your list)",
                "nl": "Deze tabel toont welke titels u hebt bekeken en of u ze hebt aangemerkt als voorkeuren (d.w.z. leuk gevonden, toegevoegd aan uw lijst)"
            })
            table_title = props.Translatable({"en": "What you watched and listed as a preference", "nl": "Wat u heeft bekeken en als voorkeur heeft opgegeven"})
            table = props.PropsUIPromptConsentFormTable("netflix_indicated_preferences", table_title, df, table_description, [])
            tables_to_render.append(table)

        # Extract playback related events
        df = playback_related_events_to_df(netflix_zip, selected_user)
        if not df.empty:
            table_description = props.Translatable({
                "nl": "Klik op ‘Tabel tonen’ om per serie of film te zien hoevaak u pauze heeft genomen, of heeft teruggespoeld.",
                "en": "This table shows what titles you watched from which devices at what time and date. It also includes how often you started, stopped, pressed play, and pressed pause per title"
            })
            table_title = props.Translatable({"en": "How you watched netflix content", "nl": "Hoevaak neemt u pauze tijdens het kijken naar series en films op Netflix?"})
            table = props.PropsUIPromptConsentFormTable("netflix_playback", table_title, df, table_description, []) 
            tables_to_render.append(table)

        # Extract search history
        df = search_history_to_df(netflix_zip, selected_user)
        if not df.empty:
            table_description = props.Translatable({
                "nl": "Klik op ‘Tabel tonen’ om  te zien naar welke series en films u heeft gezocht en welke zoektermen u heeft gebruikt om dit te vinden. U ziet ook of u de gevonden serie of film vervolgens heeft gekeken of aan ‘Mijn lijst’ heeft toegevoegd.",
                "en": "This table shows which titles you have searched for. It includes the device you used for searching, whether the title was searched in the kid-friendly account, the search terms you used, the result that was shown to you, and how you proceeded with that result (did you add it to your watch list or play it immediately?). It also shows in which section of Netflix you found the title and when you did the search query"
            })
            table_title = props.Translatable({"en": "Your search history", "nl": "Uw zoekgeschiedenis"})
            table = props.PropsUIPromptConsentFormTable("netflix_search", table_title, df, table_description, []) 
            tables_to_render.append(table)

        # Extract messages sent by netflix
        df = messages_sent_by_netflix_to_df(netflix_zip, selected_user)
        if not df.empty:

            table_description = props.Translatable({
                "nl": "Klik op ‘Tabel tonen’ om te zien welke reclame berichten u van Netflix heeft ontvangen, bijvoorbeeld over nieuwe series of films. U ziet ook of u de getoonde serie of film vervolgens heeft gekeken.",
                "en": "This table shows what promotional messages you received from Netflix about new titles. It includes the time you received the message, the type of notification, the channel through which it was sent, which specific title was promoted in the message, and whether you clicked on the message, along with the frequency of such clicks"
            })
            table_title = props.Translatable({"en": "Messages that you received from Netflix", "nl": "Berichten van Netflix"})
            table = props.PropsUIPromptConsentFormTable("netflix_messages", table_title, df, table_description, [])
            tables_to_render.append(table)

    return tables_to_render



# TEXTS and script
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your Netflix file", 
    "nl": "Select your Netflix file", 
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your Netflix data", 
    "nl": "Uw Netflix gegevens",
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw",
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a currated selection of your Netflix data. Most of the data in your package is displayed here. Try searching sensitive data in your package.", 
   "nl": "Below you will find a currated selection of your Netflix data. Most of the data in your takeout package is displayed here. Try searching sensitive data in your package."
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
    "nl": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
})

INSTRUCTION_HEADER = props.Translatable({
   "en": "Instructions to request your Netflix data",
   "nl": "Instructions to request your Netflix data",
})


def prompt_radio_menu_select_username(users):
    """
    Prompt selection menu to select which user you are
    """

    title = props.Translatable({ "en": "Select your Netflix profile name", "nl": "Kies jouw Netflix profielnaam" })
    description = props.Translatable({ "en": "", "nl": "" })
    header = props.PropsUIHeader(props.Translatable({"en": "", "nl": ""}))

    radio_items = [{"id": i, "value": username} for i, username in enumerate(users)]
    body = props.PropsUIPromptRadioInput(title, description, radio_items)
    footer = props.PropsUIFooter()

    page = props.PropsUIPageDonation("Netflix", header, body, footer)

    return CommandUIRender(page)



def script():
    platform_name = "Netflix"
    table_list = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "netflix_instructions.svg")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            validation = validate_zip(file_result.value)

            # Happy flow: Valid DDP
            if validation.status_code.id == 0:

                # Extract the user
                users = extract_users(file_result.value)

                if len(users) == 1:
                    selected_user = users[0]
                    extraction_result = extraction(file_result.value, selected_user)
                    table_list = extraction_result
                elif len(users) > 1:
                    selection = yield prompt_radio_menu_select_username(users)
                    if selection.__type__ == "PayloadString":
                        selected_user = selection.value
                        extraction_result = extraction(file_result.value, selected_user)
                        table_list = extraction_result
                    else:
                        pass
                else:
                    pass

                break

            # Enter retry flow, reason: if DDP was not a Netflix DDP
            if validation.status_code.id != 0:
                retry_result = yield ph.render_page(RETRY_HEADER, ph.retry_confirmation(platform_name))

                if retry_result.__type__ == "PayloadTrue":
                    continue
                else:
                    logger.info("Skipped during retry flow")
                    break

        else:
            logger.info("Skipped at file selection ending flow")
            break

    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)

    return

