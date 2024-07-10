"""
DDP extract Youtube
"""
from pathlib import Path
import logging
import zipfile
import re
import io

import pandas as pd
from bs4 import BeautifulSoup
from lxml import etree

import port.api.props as props
import port.unzipddp as unzipddp
import port.extraction_helpers as eh
import port.port_helpers as ph

from port.validate import (
    DDPCategory,
    Language,
    DDPFiletype,
    ValidateInput,
    StatusCode,
)

logger = logging.getLogger(__name__)


VIDEO_REGEX = r"(?P<video_url>^http[s]?://www\.youtube\.com/watch\?v=[a-z,A-Z,0-9,\-,_]+)(?P<rest>$|&.*)"
CHANNEL_REGEX = r"(?P<channel_url>^http[s]?://www\.youtube\.com/channel/[a-z,A-Z,0-9,\-,_]+$)"

DDP_CATEGORIES = [
    DDPCategory(
        id="html_en",
        ddp_filetype=DDPFiletype.HTML,
        language=Language.EN,
        known_files=[
            "archive_browser.html",
            "watch-history.html",
            "my-comments.html",
            "my-live-chat-messages.html",
            "subscriptions.csv",
            "comments.csv",
        ],
    ),
    DDPCategory(
        id="html_nl",
        ddp_filetype=DDPFiletype.HTML,
        language=Language.NL,
        known_files=[
            "archive_browser.html",
            "kijkgeschiedenis.html",
            "zoekgeschiedenis.html",
            "mijn-reacties.html",
            "abonnementen.csv",
            "reacties.csv",
        ],
    ),
]


STATUS_CODES = [
    StatusCode(id=0, description="Valid DDP", message=""),
    StatusCode(id=1, description="Valid DDP unhandled format", message=""),
    StatusCode(id=2, description="Not a valid DDP", message=""),
    StatusCode(id=3, description="Bad zipfile", message=""),
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
                if p.suffix in (".json", ".csv", ".html"):
                    logger.debug("Found: %s in zip", p.name)
                    paths.append(p.name)

        if validation.infer_ddp_category(paths):
            validation.set_status_code_by_id(0)
        else:
            validation.set_status_code_by_id(1)

    except zipfile.BadZipFile:
        validation.set_status_code_by_id(3)

    return validation


# Extract my-comments.html
def bytes_to_soup(buf: io.BytesIO) -> BeautifulSoup:
    """
    Remove undecodable bytes from utf-8 string
    BeautifulSoup will hang otherwise
    """

    utf_8_str = buf.getvalue().decode("utf-8", errors="ignore")
    utf_8_str = re.sub(r'[^\x00-\x7F]+', ' ', utf_8_str)
    soup = BeautifulSoup(utf_8_str, "lxml")
    return soup


def my_comments_to_df(youtube_zip: str, validation: ValidateInput) -> pd.DataFrame:
    """
    Parses my-comments.html or mijn-reacties.html from Youtube DDP

    input string to zipfile output df 
    with the comment, type of comment, and a video url
    """

    data_set = []
    video_pattern = re.compile(VIDEO_REGEX)
    df = pd.DataFrame()

   # Determine the language of the file name
    file_name = "my-comments.html"
    if validation.ddp_category.language == Language.NL:
        file_name = "mijn-reacties.html"

    comments = unzipddp.extract_file_from_zip(youtube_zip, file_name)
       
    try:
        soup = bytes_to_soup(comments)
        items = soup.find_all("li")
        for item in items:
            data_point = {}

           # Extract comments
            content = item.get_text(separator="<SEP>").split("<SEP>")
            message = content.pop()
            action = "".join(content)
            data_point["Comment"] = message
            data_point["Type of comment"] = action

           # Search through all references
           # if a video can be found:
           # 1. extract video url
           # 2. add data point
            for ref in item.find_all("a"):
                regex_result = video_pattern.match(ref.get("href"))
                if regex_result:
                    data_point["Video url"] = regex_result.group("video_url")
                    data_set.append(data_point)
                    break

        df = pd.DataFrame(data_set)

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return df


# Extract Watch later.csv
def watch_later_to_df(youtube_zip: str) -> pd.DataFrame:
    """
    Parses 'Watch later.csv' from Youtube DDP
    Filename is the same for Dutch and English Language settings

    Note: 'Watch later.csv' is NOT a proper csv it 2 csv's in one
    """

    ratings_bytes = unzipddp.extract_file_from_zip(youtube_zip, "Watch later.csv")
    df = pd.DataFrame()

    try:
        # remove the first 3 lines from the .csv
        #ratings_bytes = io.BytesIO(re.sub(b'^(.*)\n(.*)\n\n', b'', ratings_bytes.read()))
        ratings_bytes = io.BytesIO(re.sub(b'^((?s).)*?\n\n', b'', ratings_bytes.read()))

        df = unzipddp.read_csv_from_bytes_to_df(ratings_bytes)
        df['Video-ID'] = 'https://www.youtube.com/watch?v=' + df['Video-ID']
    except Exception as e:
        logger.debug("Exception was caught:  %s", e)

    return df



# Extract subscriptions.csv
def subscriptions_to_df(youtube_zip: str, validation: ValidateInput) -> pd.DataFrame:
    """
    Parses 'subscriptions.csv' or 'abonnementen.csv' from Youtube DDP
    """

    # Determine the language of the file name
    file_name = "subscriptions.csv"
    if validation.ddp_category.language == Language.NL:
        file_name = "abonnementen.csv"

    ratings_bytes = unzipddp.extract_file_from_zip(youtube_zip, file_name)
    df = unzipddp.read_csv_from_bytes_to_df(ratings_bytes)
    return df



# Extract watch history
def watch_history_extract_html(bytes: io.BytesIO) -> pd.DataFrame:
    """
    watch-history.html bytes buffer to pandas dataframe
    """

    out = pd.DataFrame()
    datapoints = []

    try:
        tree = etree.HTML(bytes.read())
        outer_container_class = "outer-cell mdl-cell mdl-cell--12-col mdl-shadow--2dp"
        watch_history_container_class = "content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1"
        ads_container_class = "content-cell mdl-cell mdl-cell--12-col mdl-typography--caption"
        r = tree.xpath(f"//div[@class='{outer_container_class}']")

        for e in r:
            is_ad = False
            ads_container = e.xpath(f"./div/div[@class='{ads_container_class}']")[0]
            ad_text = "".join(ads_container.xpath("text()"))
            if ads_container is not None and ("Google Ads" in ad_text or "Google Adverteren" in ad_text):
                is_ad = True
            
            if is_ad: 
                ad = "Yes"
            else: 
                ad = "No"
            v = e.xpath(f"./div/div[@class='{watch_history_container_class}']")[0]
            
            child_all_text_list = v.xpath("text()")

            datetime = child_all_text_list.pop()
            datetime = eh.fix_ascii_string(datetime)
            atags = v.xpath("a")

            try:
                title = atags[0].text
                video_url = atags[0].get("href")
            except:
                if len(child_all_text_list) != 0:
                    title = child_all_text_list[0]
                else:
                    title = None
                video_url = None
                logger.debug("Could not find a title")
            try:
                channel_name = atags[1].text
            except:
                channel_name = None
                logger.debug("Could not find the channel name")

            datapoints.append(
                (title, video_url, ad, channel_name, datetime)
            )
        out = pd.DataFrame(datapoints, columns=["Title", "Url", "Advertisement", "Channel", "Date"])

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out


# Extract watch history
def search_history_extract_html(bytes: io.BytesIO) -> pd.DataFrame:
    """
    watch-history.html bytes buffer to pandas dataframe
    """

    out = pd.DataFrame()
    datapoints = []

    try:
        tree = etree.HTML(bytes.read())
        outer_container_class = "outer-cell mdl-cell mdl-cell--12-col mdl-shadow--2dp"
        search_history_container_class = "content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1"
        ads_container_class = "content-cell mdl-cell mdl-cell--12-col mdl-typography--caption"
        r = tree.xpath(f"//div[@class='{outer_container_class}']")

        for e in r:
            is_ad = False
            ads_container = e.xpath(f"./div/div[@class='{ads_container_class}']")[0]
            ad_text = "".join(ads_container.xpath("text()"))
            if ads_container is not None and ("Google Ads" in ad_text or "Google Adverteren" in ad_text):
                is_ad = True
            
            if is_ad: 
                continue

            s = e.xpath(f"./div/div[@class='{search_history_container_class}']")[0]

            child_all_text_list = s.xpath("text()")

            datetime = child_all_text_list.pop()
            datetime = eh.fix_ascii_string(datetime)
            atags = s.xpath("a")

            try:
                title = atags[0].text
                video_url = atags[0].get("href")
            except:
                if len(child_all_text_list) != 0:
                    title = child_all_text_list[0]
                else:
                    title = None
                video_url = None
                logger.debug("Could not find a title")
            try:
                channel_name = atags[1].text
            except:
                channel_name = None
                logger.debug("Could not find the channel name")

            datapoints.append(
                (title, video_url, datetime)
            )
        out = pd.DataFrame(datapoints, columns=["Search Terms", "Url", "Date"])

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out



def watch_history_to_df(youtube_zip: str, validation: ValidateInput) -> pd.DataFrame:
    """
    Works for watch-history.html and kijkgeschiedenis.html
    """
    out = pd.DataFrame()

    try:
        if validation.ddp_category.ddp_filetype == DDPFiletype.HTML:
            # Determine the language of the file name
            file_name = "watch-history.html"
            if validation.ddp_category.language == Language.NL:
                file_name = "kijkgeschiedenis.html"

            html_bytes_buf = unzipddp.extract_file_from_zip(youtube_zip, file_name)
            out = watch_history_extract_html(html_bytes_buf)
            out["Date standard format"] = out["Date"].apply(eh.try_to_convert_any_timestamp_to_iso8601)

        else:
            out = pd.DataFrame([("Er zit wel data in jouw data package, maar we hebben het er niet uitgehaald")], columns=["Extraction not implemented"])

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out



def search_history_to_df(youtube_zip: str, validation: ValidateInput) -> pd.DataFrame:
    """
    Works for search-history.html and zoekgeschiedenis.html
    """
    out = pd.DataFrame()

    try:
        if validation.ddp_category.ddp_filetype == DDPFiletype.HTML:
            # Determine the language of the file name
            file_name = "search-history.html"
            if validation.ddp_category.language == Language.NL:
                file_name = "zoekgeschiedenis.html"

            html_bytes_buf = unzipddp.extract_file_from_zip(youtube_zip, file_name)
            out = search_history_extract_html(html_bytes_buf)
            out["Date standard format"] = out["Date"].apply(eh.try_to_convert_any_timestamp_to_iso8601)

        else:
            out = pd.DataFrame([("Er zit wel data in jouw data package, maar we hebben het er niet uitgehaald")], columns=["Extraction not implemented"])
    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out



# Extract my-live-chat-messages.html
def my_live_chat_messages_to_df(youtube_zip: str, validation: ValidateInput) -> pd.DataFrame:
    """
    my-live-chat-messages.html to df
    mijn-live-chat-berichten.html
    """
    file_name = "my-live-chat-messages.html"
    if validation.ddp_category.language == Language.NL:
        file_name = "mijn-live-chat-berichten.html"

    live_chats_buf = unzipddp.extract_file_from_zip(youtube_zip, file_name)

    out = pd.DataFrame()
    datapoints = []
    pattern = r"^(.*?\.)(.*)"

    try: 
        tree = etree.HTML(live_chats_buf.read())
        r = tree.xpath(f"//li")
        for e in r:
            # get description and chat message
            full_text = ''.join(e.itertext())
            matches = re.match(pattern, full_text)
            try:
                description = matches.group(1)
                message = matches.group(2)
            except:
                description = message = None

            # extract video url
            message = e.xpath("text()").pop()
            atags = e.xpath("a")
            if atags:
                url = atags[0].get("href")
            else:
                url = None
            
            datapoints.append((description, message, url))
        out = pd.DataFrame(datapoints, columns=["Beschrijving", "Bericht", "Url"])

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out




#  extraction
def extraction(chatgpt_zip: str, validation: ValidateInput) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []
    
    df = watch_history_to_df(chatgpt_zip, validation)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your YouTube watch history",
            "nl": "Your YouTube watch history",
        })
        table_description = props.Translatable({
            "en": "In this table you find the videos you watched on YouTube sorted over time. Below, you find visualizations of different parts of this table. First, you find a timeline showing you the number of videos you watched per month. Second, you find a wordcloud of the YouTube channels you viewed, where the size of the words represents how frequently viewed YouTube channels. Third, you find a histogram indicating how many videos you have watched per hour of the day.", 
            "nl": "In this table you find the videos you watched on YouTube sorted over time. Below, you find visualizations of different parts of this table. First, you find a timeline showing you the number of videos you watched per month. Second, you find a wordcloud of the YouTube channels you viewed, where the size of the words represents how frequently viewed YouTube channels. Third, you find a histogram indicating how many videos you have watched per hour of the day.", 
        })
        wordcloud = {
            "title": {
                "en": "The most frequently watched YouTube channels", 
                "nl": "The most frequently watched YouTube channels", 
            },
            "type": "wordcloud",
            "textColumn": "Channel",
            "tokenize": False,
        }

        total_watched = {
            "title": {
                "en": "The total number of YouTube videos you have watched per month", 
                "nl": "The total number of YouTube videos you have watched per month", 
            },
            "type": "area",
            "group": {
                "column": "Date standard format",
                "dateFormat": "month"
            },
            "values": [{
                "aggregate": "count", 
                "label": {
                    "en": "number of views", 
                    "nl": "aantal keer gekeken"
                }
            }]
        }

        hour_of_the_day = {
            "title": {
                "en": "The total number of YouTube videos you have watched per hour of the day", 
                "nl": "The total number of YouTube videos you have watched per hour of the day", 
            },
            "type": "bar",
            "group": {
                "column": "Date standard format",
                "dateFormat": "hour_cycle"
            },
            "values": [{}]
        }

        table = props.PropsUIPromptConsentFormTable("8917y23", table_title, df, table_description, [total_watched, wordcloud, hour_of_the_day])
        tables_to_render.append(table)

    df = search_history_to_df(chatgpt_zip, validation)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your YouTube search history",
            "nl": "Your YouTube search history",
        })
        table_description = props.Translatable({
            "en": "In this table you find the search terms you have used on YouTube sorted over time. Below, you find a wordcloud of the search terms you used, where the size of the words represents how frequently you used a search term.", 
            "nl": "In this table you find the search terms you have used on YouTube sorted over time. Below, you find a wordcloud of the search terms you used, where the size of the words represents how frequently you used a search term.", 
        })
        wordcloud = {
            "title": {
                "en": "Words you most searched for", 
                "nl": "Words you most searched for", 
            },
            "type": "wordcloud",
            "textColumn": "Search Terms",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable("kjwekj132387dh", table_title, df, table_description, [wordcloud])
        tables_to_render.append(table)

    df = my_comments_to_df(chatgpt_zip, validation)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Comments you posted on YouTube",
            "nl": "Comments you posted on YouTube",
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table = props.PropsUIPromptConsentFormTable("kjhasdh12", table_title, df, table_description, [])
        tables_to_render.append(table)

    df = watch_later_to_df(chatgpt_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your items in watch later",
            "nl": "Your items in watch later",
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table = props.PropsUIPromptConsentFormTable("edaksjd", table_title, df, table_description, [])
        tables_to_render.append(table)

    df = subscriptions_to_df(chatgpt_zip, validation)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your YouTube channel subscriptions",
            "nl": "Your YouTube channel subscriptions",
        })
        table_description = props.Translatable({
            "en": "In this table, you find the YouTube channels you are subscribed to.", 
            "nl": "In this table, you find the YouTube channels you are subscribed to.", 
        })
        table = props.PropsUIPromptConsentFormTable("idasjdhj1", table_title, df, table_description, [])
        tables_to_render.append(table)


    df = my_live_chat_messages_to_df(chatgpt_zip, validation)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your live chat messages",
            "nl": "Your live chat messages",
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table = props.PropsUIPromptConsentFormTable("ksjdk21jw34e", table_title, df, table_description, [])
        tables_to_render.append(table)

    return tables_to_render


# TEXTS and script
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your YouTube file", 
    "nl": "Select your YouTube file", 
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your YouTube data", 
    "nl": "Uw YouTube gegevens",
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw",
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a currated selection of your YouTube data. Most of the data in your takeout package is displayed here. Try searching sensitive data in your package. The tables showing your watch, search and comment history are well suited for this. You can use the search function to search through the tables.",
   "nl": "Below you will find a currated selection of your YouTube data. Most of the data in your takeout package is displayed here. Try searching sensitive data in your package. The tables showing your watch, search and comment history are well suited for this. You can use the search function to search through the tables.",
})

CONSENT_FORM_DESCRIPTION_ALL = props.Translatable({
   "en": "",
   "nl": ""
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
    "nl": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
})

INSTRUCTION_HEADER = props.Translatable({
   "en": "Instructions to request your YouTube data",
   "nl": "Instructions to request your YouTube data",
})


def script():
    platform_name = "YouTube"
    table_list = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "youtube_instructions.svg")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            validation = validate_zip(file_result.value)

            # Happy flow: Valid DDP
            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                extraction_result = extraction(file_result.value, validation)
                table_list = extraction_result
                break

            # Enter retry flow, reason: if DDP was not a YouTube DDP
            if validation.status_code.id != 0:
                logger.info("Not a valid %s zip; No payload; prompt retry_confirmation", platform_name)
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

