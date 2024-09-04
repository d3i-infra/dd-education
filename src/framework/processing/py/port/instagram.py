
"""
DDP Instagram module

This module contains functions to handle *.jons files contained within an instagram ddp
"""

from pathlib import Path
import logging
import zipfile

import pandas as pd

import port.api.props as props
import port.unzipddp as unzipddp
import port.extraction_helpers as eh
import port.port_helpers as ph

from port.validate import (
    DDPCategory,
    StatusCode,
    ValidateInput,
    Language,
    DDPFiletype,
)

logger = logging.getLogger(__name__)

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
            "ads_interests.json",
            "account_searches.json",
            "following.json",
            "posts_viewed.json",
            "recently_unfollowed_accounts.json",
            "post_comments.json",
            "account_information.json",
            "accounts_you're_not_interested_in.json",
            "use_cross-app_messaging.json",
            "profile_changes.json",
            "reels.json",
        ],
    )
]

STATUS_CODES = [
    StatusCode(id=0, description="Valid DDP", message="Valid DDP"),
    StatusCode(id=1, description="Not a valid DDP", message="Not a valid DDP"),
    StatusCode(id=2, description="Bad zipfile", message="Bad zip"),
]


def validate_zip(zfile: Path) -> ValidateInput:
    """
    Validates the input of an Instagram zipfile

    This function should set and return a validation object
    """

    validation = ValidateInput(STATUS_CODES, DDP_CATEGORIES)

    try:
        paths = []
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                p = Path(f)
                if p.suffix in (".html", ".json"):
                    logger.debug("Found: %s in zip", p.name)
                    paths.append(p.name)

        
        if validation.infer_ddp_category(paths):
            validation.set_status_code_by_id(0)
        else:
            validation.set_status_code_by_id(1)

    except zipfile.BadZipFile:
        validation.set_status_code_by_id(2)

    return validation


def accounts_not_interested_in_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "accounts_you're_not_interested_in.json")
    d = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = d["impressions_history_recs_hidden_authors"]
        for item in items:
            data = item.get("string_map_data", {})
            account_name = data.get("Username", {}).get("value", None),
            if "Time" in data:
                timestamp = data.get("Time", {}).get("timestamp", "")
            else:
                timestamp = data.get("Tijd", {}).get("timestamp", "")

            datapoints.append((
                account_name,
                eh.epoch_to_iso(timestamp)
            ))
        out = pd.DataFrame(datapoints, columns=["Account name", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out


def ads_viewed_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "ads_viewed.json")
    d = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = d["impressions_history_ads_seen"]
        for item in items:
            data = item.get("string_map_data", {})
            account_name = data.get("Author", {}).get("value", None)
            if "Time" in data:
                timestamp = data.get("Time", {}).get("timestamp", "")
            else:
                timestamp = data.get("Tijd", {}).get("timestamp", "")

            datapoints.append((
                account_name,
                eh.epoch_to_iso(timestamp)
            ))
        out = pd.DataFrame(datapoints, columns=["Author of ad", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out


def posts_viewed_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "posts_viewed.json")
    d = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = d["impressions_history_posts_seen"]
        for item in items:
            data = item.get("string_map_data", {})
            account_name = data.get("Author", {}).get("value", None)
            if "Time" in data:
                timestamp = data.get("Time", {}).get("timestamp", "")
            else:
                timestamp = data.get("Tijd", {}).get("timestamp", "")

            datapoints.append((
                account_name,
                eh.epoch_to_iso(timestamp)
            ))
        out = pd.DataFrame(datapoints, columns=["Author", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out



def posts_not_interested_in_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "posts_you're_not_interested_in.json")
    data = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["impressions_history_posts_not_interested"]
        for item in items:
            d = eh.dict_denester(item.get("string_list_data"))
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "value")),
                eh.find_item(d, "href"),
                eh.epoch_to_iso(eh.find_item(d, "timestamp"))
            ))
        out = pd.DataFrame(datapoints, columns=["Post", "Link", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out



def videos_watched_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "videos_watched.json")
    d = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = d["impressions_history_videos_watched"]
        for item in items:
            data = item.get("string_map_data", {})
            account_name = data.get("Author", {}).get("value", None)
            if "Time" in data:
                timestamp = data.get("Time", {}).get("timestamp", "")
            else:
                timestamp = data.get("Tijd", {}).get("timestamp", "")

            datapoints.append((
                account_name,
                eh.epoch_to_iso(timestamp)
            ))
        out = pd.DataFrame(datapoints, columns=["Author", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out


def post_comments_to_df(instagram_zip: str) -> pd.DataFrame:
    """
    You can have 1 to n files of post_comments_<x>.json
    """

    out = pd.DataFrame()
    datapoints = []
    i = 1

    while True:
        b = unzipddp.extract_file_from_zip(instagram_zip, f"post_comments_{i}.json")
        d = unzipddp.read_json_from_bytes(b)

        if not d:
            break

        try:
            for item in d:
                data = item.get("string_map_data", {})
                media_owner = data.get("Media Owner", {}).get("value", "")
                comment = data.get("Comment", {}).get("value", "")
                if "Time" in data:
                    timestamp = data.get("Time", {}).get("timestamp", "")
                else:
                    timestamp = data.get("Tijd", {}).get("timestamp", "")

                datapoints.append((
                    media_owner,
                    eh.fix_latin1_string(comment),
                    eh.epoch_to_iso(timestamp)
                ))
            i += 1

        except Exception as e:
            logger.error("Exception caught: %s", e)
            return pd.DataFrame()

    out = pd.DataFrame(datapoints, columns=["Media Owner", "Comment", "Date"])

    return out



def following_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "following.json")
    data = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["relationships_following"] # pyright: ignore
        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "value")),
                eh.find_item(d, "href"),
                eh.epoch_to_iso(eh.find_item(d, "timestamp"))
            ))
        out = pd.DataFrame(datapoints, columns=["Account", "Link", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out



def liked_comments_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "liked_comments.json")
    data = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["likes_comment_likes"] #pyright: ignore
        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "title")),
                eh.fix_latin1_string(eh.find_item(d, "value")),
                eh.find_items(d, "href"),
                eh.epoch_to_iso(eh.find_item(d, "timestamp"))
            ))
        out = pd.DataFrame(datapoints, columns=["Account name", "Value", "Link", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out


def liked_posts_to_df(instagram_zip: str) -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(instagram_zip, "liked_posts.json")
    data = unzipddp.read_json_from_bytes(b)

    out = pd.DataFrame()
    datapoints = []

    try:
        items = data["likes_media_likes"] #pyright: ignore
        for item in items:
            d = eh.dict_denester(item)
            datapoints.append((
                eh.fix_latin1_string(eh.find_item(d, "title")),
                eh.fix_latin1_string(eh.find_item(d, "value")),
                eh.find_items(d, "href"),
                eh.epoch_to_iso(eh.find_item(d, "timestamp"))
            ))
        out = pd.DataFrame(datapoints, columns=["Account name", "Value", "Link", "Date"])
        out = out.sort_values(by="Date", key=eh.sort_isotimestamp_empty_timestamp_last)

    except Exception as e:
        logger.error("Exception caught: %s", e)

    return out



def extraction(instagram_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []

    df = posts_viewed_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Posts viewed on Instagram",
            "nl": "Posts viewed on Instagram"
        })
        table_description = props.Translatable({
            "en": "In this table you find the accounts of posts you viewed on Instagram sorted over time. Below, you find visualizations of different parts of this table. First, you find a timeline showing you the number of posts you viewed over time. Next, you find a histogram indicating how many posts you have viewed per hour of the day.", 
            "nl": "In this table you find the accounts of posts you viewed on Instagram sorted over time. Below, you find visualizations of different parts of this table. First, you find a timeline showing you the number of posts you viewed over time. Next, you find a histogram indicating how many posts you have viewed per hour of the day.", 
        })
        total_watched = {
            "title": {
                "en": "The total number of Instagram posts you viewed over time", 
                "nl": "The total number of Instagram posts you viewed over time", 
            },
            "type": "area",
            "group": {
                "column": "Date",
                "dateFormat": "auto",
            },
            "values": [{
                "label": "Count",
                "aggregate": "count",
            }]
        }

        hour_of_the_day = {
            "title": {
                "en": "The total number of Instagram posts you have viewed per hour of the day", 
                "nl": "The total number of Instagram posts you have viewed per hour of the day", 
            },
            "type": "bar",
            "group": {
                "column": "Date",
                "dateFormat": "hour_cycle",
                "label": "Hour of the day",
            },
            "values": [{
                "label": "Count"
            }]
        }

        table =  props.PropsUIPromptConsentFormTable("instagram_posts_viewed", table_title, df, table_description, [total_watched, hour_of_the_day]) 
        tables_to_render.append(table)

    df = videos_watched_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Videos watched on Instagram",
            "nl": "Videos watched on Instagram"
        })
        table_description = props.Translatable({
            "en": "In this table you find the accounts of videos you watched on Instagram sorted over time. Below, you find a timeline showing you the number of videos you watched over time.", 
            "nl": "In this table you find the accounts of videos you watched on Instagram sorted over time. Below, you find a timeline showing you the number of videos you watched over time. ", 
        })

        total_watched = {
            "title": {
                "en": "The total number of videos watched on Instagram over time", 
                "nl": "The total number of videos watched on Instagram over time", 
            },
            "type": "area",
            "group": {
                "column": "Date",
                "dateFormat": "auto"
            },
            "values": [{
                "aggregate": "count",
                "label": "Count"
            }]
        }

        table =  props.PropsUIPromptConsentFormTable("instagram_videos_watched", table_title, df, table_description, [total_watched]) 
        tables_to_render.append(table)


    df = post_comments_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Comments on Instagram posts",
            "nl": "Comments on Instagram posts",
        })
        table_description = props.Translatable({
            "en": "In this table, you find the comments that you left behind on Instagram posts sorted over time. Below, you find a wordcloud, where the size of the word indicates how frequently that word has been used in these comments.", 
            "nl": "In this table, you find the comments that you left behind on Instagram posts sorted over time. Below, you find a wordcloud, where the size of the word indicates how frequently that word has been used in these comments.", 
        })
        wordcloud = {
            "title": {
                "en": "Most common words in comments on posts", 
                "nl": "Most common words in comments on posts", 
              },
            "type": "wordcloud",
            "textColumn": "Comment",
            "tokenize": True,
        }
        table =  props.PropsUIPromptConsentFormTable("instagram_post_comments", table_title, df, table_description, [wordcloud]) 
        tables_to_render.append(table)

    df = accounts_not_interested_in_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Instagram accounts not interested in",
            "nl": "Instagram accounts not interested in"
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_accounts_not_interested_in", table_title, df, table_description) 
        tables_to_render.append(table)

    df = ads_viewed_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Ads you viewed on Instagram",
            "nl": "Ads you viewed on Instagram"
        })
        table_description = props.Translatable({
            "en": "In this table, you find the ads that you viewed on Instagram sorted over time.", 
            "nl": "In this table, you find the ads that you viewed on Instagram sorted over time.", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_ads_viewed", table_title, df, table_description) 
        tables_to_render.append(table)

    df = posts_not_interested_in_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Instagram posts not interested in",
            "nl": "Instagram posts not interested in"
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_posts_not_interested_in", table_title, df, table_description) 
        tables_to_render.append(table)


    df = following_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Accounts that you follow on Instagram",
            "nl": "Accounts that you follow on Instagram"
        })
        table_description = props.Translatable({
            "en": "In this table, you find the accounts that you follow on Instagram.", 
            "nl": "In this table, you find the accounts that you follow on Instagram.", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_following", table_title, df, table_description) 
        tables_to_render.append(table)

    df = liked_comments_to_df(instagram_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Instagram liked comments",
            "nl": "Instagram liked comments",
        })
        wordcloud = {
            "title": {
                "en": "Accounts who's comments you liked most", 
                "nl": "Accounts who's comments you liked most", 
              },
            "type": "wordcloud",
            "textColumn": "Account name",
            "tokenize": False,
        }
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_liked_comments", table_title, df, table_description, [wordcloud]) 
        tables_to_render.append(table)

    df = liked_posts_to_df(instagram_zip)
    if not df.empty:
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        wordcloud = {
            "title": {
                "en": "Most liked accounts", 
                "nl": "Most liked accounts", 
              },
            "type": "wordcloud",
            "textColumn": "Account name",
            "tokenize": False,
        }
        table_title = props.Translatable({
            "en": "Instagram liked posts",
            "nl": "Instagram liked posts",
        })
        table_description = props.Translatable({
            "en": "", 
            "nl": "", 
        })
        table =  props.PropsUIPromptConsentFormTable("instagram_liked_posts", table_title, df, table_description, [wordcloud]) 
        tables_to_render.append(table)

    return tables_to_render





def extraction_all(zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    This extracts all key value pairs from all json files in a zip
    """

    tables_to_render = []

    df = eh.json_dumper(zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your Instagram data",
            "nl": "Your Instagram data",
        })
        table_description = props.Translatable({
            "en": "Your Instagram .zip file consists of a number of .json files and files containing the .jpeg and .mp4 files of photos and videos you posted on Instagram. These .json files consists of key-value pairs. In this table, you can find all key–value pairs from all .json files present in your .zip file.", 
            "nl": "Your Instagram .zip file consists of a number of .json files and files containing the .jpeg and .mp4 files of photos and videos you posted on Instagram. These .json files consists of key-value pairs. In this table, you can find all key–value pairs from all .json files present in your .zip file.", 
        })
        table = props.PropsUIPromptConsentFormTable("all", table_title, df, table_description)
        tables_to_render.append(table)

    return tables_to_render



# TEXTS
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your Instagram file", 
    "nl": "Selecteer uw Instagram bestand"
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your Instagram data", 
    "nl": "Uw Instagram gegevens"
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw"
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a curated selection of Instagram data. In this case only the conversations you had with Instagram are show on screen. The data represented in this way are much more insightful because you can actually read back the conversations you had with Instagram.",
   "nl": "Below you will find a curated selection of Instagram data. In this case only the conversations you had with Instagram are show on screen. The data represented in this way are much more insightful because you can actually read back the conversations you had with Instagram.",
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
   "en": "Instructions to request your Instagram data",
   "nl": "Instructions to request your Instagram data",
})


def script():
    platform_name = "Instagram"
    table_list = None
    table_list_all = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "instagram_instructions.svg")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            validation = validate_zip(file_result.value)

            # Happy flow: Valid DDP
            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                extraction_result = extraction(file_result.value)
                extraction_result_all = extraction_all(file_result.value)
                table_list = extraction_result
                table_list_all = extraction_result_all
                break

            # Enter retry flow, reason: if DDP was not a Instagram DDP
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

    if table_list_all is not None:
        consent_prompt = ph.generate_consent_prompt(table_list_all, CONSENT_FORM_DESCRIPTION_ALL)
        yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)

    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)

    return

