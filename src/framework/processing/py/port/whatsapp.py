"""
DDP extract Netflix module
"""

import pandas as pd
from dateutil import parser
import logging
import re
from typing import Tuple, TypedDict
from collections import Counter
import unicodedata
import logging
import zipfile


import port.api.props as props
import port.port_helpers as ph
from port.helpers.emoji_pattern import EMOJI_PATTERN

logger = logging.getLogger(__name__)


SIMPLIFIED_REGEXES = [
    r"^%d/%m/%y, %H:%M - %name: %chat_message$",
    r"^\[%d/%m/%y, %H:%M:%S\] %name: %chat_message$",
    r"^%d-%m-%y %H:%M - %name: %chat_message$",
    r"^\[%d-%m-%y %H:%M:%S\] %name: %chat_message$",
    r"^%d/%m/%y, %H:%M – %name: %chat_message$",
    r"^%d/%m/%y, %H:%M - %name: %chat_message$",
    r"^%d.%m.%y, %H:%M – %name: %chat_message$",
    r"^%d.%m.%y, %H:%M - %name: %chat_message$",
    r"^\[%d/%m/%y, %H:%M:%S %P\] %name: %chat_message$",
    r"^\[%m/%d/%y, %H:%M:%S %P\] %name: %chat_message$",
    r"^\[%m/%d/%y, %H:%M:%S\] %name: %chat_message$",
    r"^\[%d.%m.%y, %H:%M:%S\] %name: %chat_message$",
    r"^\[%m/%d/%y %H:%M:%S\] %name: %chat_message$",
    r"^\[%m-%d-%y, %H:%M:%S\] %name: %chat_message$",
    r"^\[%m-%d-%y %H:%M:%S\] %name: %chat_message$",
    r"^%m.%d.%y, %H:%M - %name: %chat_message$",
    r"^%m.%d.%y %H:%M - %name: %chat_message$",
    r"^%m-%d-%y %H:%M - %name: %chat_message$",
    r"^%m-%d-%y, %H:%M - %name: %chat_message$",
    r"^%m-%d-%y, %H:%M , %name: %chat_message$",
    r"^%m/%d/%y, %H:%M , %name: %chat_message$",
    r"^%d-%m-%y, %H:%M , %name: %chat_message$",
    r"^%d/%m/%y, %H:%M , %name: %chat_message$",
    r"^%d.%m.%y %H:%M – %name: %chat_message$",
    r"^%m.%d.%y, %H:%M – %name: %chat_message$",
    r"^%m.%d.%y %H:%M – %name: %chat_message$",
    r"^\[%d.%m.%y %H:%M:%S\] %name: %chat_message$",
    r"^\[%m.%d.%y, %H:%M:%S\] %name: %chat_message$",
    r"^\[%m.%d.%y %H:%M:%S\] %name: %chat_message$",
    r"^%m/%d/%y, %H:%M - %name: %chat_message$",
    r"^(?P<year>.*?)(?:\] | - )%name: %chat_message$"  # Fallback catch all regex
]


REGEX_CODES = {
    "%Y": r"(?P<year>\d{2,4})",
    "%y": r"(?P<year>\d{2,4})",
    "%m": r"(?P<month>\d{1,2})",
    "%d": r"(?P<day>\d{1,2})",
    "%H": r"(?P<hour>\d{1,2})",
    "%I": r"(?P<hour>\d{1,2})",
    "%M": r"(?P<minutes>\d{2})",
    "%S": r"(?P<seconds>\d{2})",
    "%P": r"(?P<ampm>[AaPp].? ?[Mm].?)",
    "%p": r"(?P<ampm>[AaPp].? ?[Mm].?)",
    "%name": r"(?P<name>[^:]*)",
    "%chat_message": r"(?P<chat_message>.*)"
}


def generate_regexes(simplified_regexes):
    """
    Create the complete regular expression by substituting
    REGEX_CODES into SIMPLIFIED_REGEXES

    """
    final_regexes = []

    for simplified_regex in simplified_regexes:

        codes = re.findall(r"\%\w*", simplified_regex)
        for code in codes:
            try:
                simplified_regex = simplified_regex.replace(code, REGEX_CODES[code])
            except KeyError:
                logger.error(f"Could not find regular expression for: {code}")

        final_regexes.append(simplified_regex)

    return final_regexes


REGEXES =  generate_regexes(SIMPLIFIED_REGEXES)


def remove_unwanted_characters(s: str) -> str:
    """
    Cleans string from bytes using magic

    Keeps empjis intact
    """
    s = "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")
    s = unicodedata.normalize("NFKD", s)
    return s


def convert_to_iso8601(timestamp):
    try:
        dt = parser.parse(timestamp)
        return dt.isoformat()
    except (ValueError, TypeError) as e:
        return timestamp


class Datapoint(TypedDict):
    date: str
    name: str
    chat_message: str


def create_data_point_from_chat(chat: str, regex) -> Datapoint:
    """
    Construct data point from chat messages
    """
    result = re.match(regex, chat)
    if result:
        result = result.groupdict()
    else:
        return Datapoint(date="", name="", chat_message="")

    # Construct data
    date = convert_to_iso8601(
        f"{result.get('year', '')}-{result.get('month', '')}-{result.get('day', '')} {result.get('hour', '')}:{result.get('minutes', '')}"
    )
    name = result.get("name", "")
    chat_message = result.get("chat_message", "")

    return Datapoint(date=date, name=name, chat_message=chat_message)


def remove_empty_chats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes all rows from the chat dataframe where no regex matched
    """
    df = df.drop(df[df.chat_message == ""].index)
    df = df.reset_index(drop=True)
    return df


def filter_username(df: pd.DataFrame, username: str) -> pd.DataFrame:
    """
    Extracts unique usersnames from chat dataframe
    """
    df = df.drop(df[df.name != username].index)
    df = df.reset_index(drop=True)

    return df


def split_dataframe(df: pd.DataFrame, row_count: int) -> list[pd.DataFrame]:
    """
    Split a pandas DataFrame into multiple based on a preset row_count.
    """
    print('split_dataframe test')
    # Calculate the number of splits needed.
    num_splits = int(len(df) / row_count) + (len(df) % row_count > 0)

    # Split the DataFrame into chunks of size row_count.
    df_splits = [df[i*row_count:(i+1)*row_count].reset_index(drop=True) for i in range(num_splits)]

    return df_splits


def extract_users(df: pd.DataFrame) -> list[str]:
    """
    Extracts unique usersnames from chat dataframe
    """
    return list(set(df["name"]))


def reverse_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts unique usersnames from chat dataframe
    """
    df = df.sort_values('date',ascending=False)
    return df


def remove_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removing the date column from the chat dataframe
    """
    df = df.drop(columns=["date"])
    return df


def determine_regex_from_chat(lines: list[str]) -> str:
    """
    Read lines of chat return the first regex that matches
    That regex is used to process the chatfile
    """

    length_lines = len(lines)
    for index, line in enumerate(lines):
        for regex in REGEXES:
            if re.match(regex, line):
                logger.info(f"Matched regex: {regex}")
                return regex

        if index > length_lines:
            break

    logger.error(f"No matching regex found:")
    raise Exception(f"No matching regex found")


def construct_message(current_line: str, next_line: str, regex: str) -> Tuple[bool, str]:
    """
    Helper function: determines whether the next line in the chat matches the regex
    in case of no match it means that the line belongs to the message on the current line
    """

    match_next_line = re.match(regex, next_line)
    if match_next_line:
        return True, current_line
    else:
        current_line = current_line + " " + next_line
        current_line = current_line.replace("\n", " ")
        return False, current_line


def read_chat_file(path_to_chat_file: str) -> list[str]:
    out = []
    #try:
    if zipfile.is_zipfile(path_to_chat_file):

      with zipfile.ZipFile(path_to_chat_file) as z:
        file_list = z.namelist()
        print(f"{file_list}")
        with z.open(file_list[0]) as f:
            lines = f.readlines()
            lines = [line.decode("utf-8") for line in lines]

    else:
        with open(path_to_chat_file, encoding="utf-8") as f:
            lines = f.readlines()

    out = [remove_unwanted_characters(line) for line in lines]

    #except Exception as e:
    #    raise e

    return out


def parse_chat(path_to_chat: str) -> pd.DataFrame:
    """
    Read chat from file, parse, return df

    In case of error returns empty df
    """
    out = []

    try:
        lines = read_chat_file(path_to_chat)
        regex = determine_regex_from_chat(lines)

        current_line = lines.pop(0)
        next_line = lines.pop(0)

        while True:
            try:
                match_next_line, chat = construct_message(current_line, next_line, regex)

                while not match_next_line:
                    next_line = lines.pop(0)
                    match_next_line, chat = construct_message(chat, next_line, regex)

                data_point = create_data_point_from_chat(chat, regex)
                out.append(data_point)

                current_line = next_line
                next_line = lines.pop(0)

            # IndexError occurs when pop fails
            # Meaning we processed all chat messages
            except IndexError:
                data_point = create_data_point_from_chat(current_line, regex)
                out.append(data_point)
                break

    except Exception as e:
        logger.error(e)

    finally:
        return pd.DataFrame(out)


def find_emojis(df):
    out = pd.DataFrame()
    try:

        emojis = []
        for text in df['Message']:
            chars = EMOJI_PATTERN.findall(text)
            emojis.extend(chars)

        emoji_counter = Counter(emojis)
        print(emoji_counter)
        most_common_emojis = emoji_counter.most_common(100)
        out = pd.DataFrame(most_common_emojis, columns=['Emoji', 'Count'])

    except Exception as e:
        logger.error(e)

    return out



# EXTRACTION LOGIC

def extraction(df: pd.DataFrame) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []
    
    # column names of df are:
    # * date 
    # * name
    # * chat_message
    df = df.rename(columns={
        "date": "Timestamp",
        "name": "Name",
        "chat_message": "Message",
    })
	
    wordcloud = {
        "title": {
            "en": "Most common words in your chats", 
            "nl": "Most common words in your chats", 
          },
        "type": "wordcloud",
        "textColumn": "Message",
        "tokenize": True,
    }

    which_month = {
    "title": {
        "en": "Total chats per month of the year",
        "nl": "Total chats per month of the year",
    },
    "type": "area",
    "group": {
        "column": "Timestamp",
        "dateFormat": "month"
    },
    "values": [{}]
    }

    at_what_time = {
        "title": {
            "en": "Total chats per hour of the day",
            "nl": "Total chats per hour of the day"
        },
        "type": "bar",
        "group": {
            "column": "Timestamp",
            "dateFormat": "hour_cycle"
        },
        "values": [{}]
    }

    table_title = props.Translatable({"en": "Your group chat", "nl": "Your group chat"})
    table_description = props.Translatable({
        "en": "The contents of your group chat. Try searching for stuff in your group chat, the figures should change accordingly! Timestamps (and therefore some tables) can be incorrect as it assumes the European format.",
        "nl": "The contents of your group chat. Try searching for stuff in your group chat, the figures should change accordingly! Timestamps (and therefore some tables) can be incorrect as it assumes the European format.",
    })
    table = props.PropsUIPromptConsentFormTable("whatsapp", table_title, df, table_description, [wordcloud, which_month, at_what_time])
    tables_to_render.append(table)

    df = find_emojis(df)
    if not df.empty:
        table_title = props.Translatable(
            {
                "en": "The 100 most used emojis in the group",
                "nl": "The 100 most emojis used in the group"
            }
        )
        table_description = props.Translatable({
            "en": "",
            "nl": "",
        })
        table = props.PropsUIPromptConsentFormTable("whaasdtsapp", table_title, df, table_description, [])
        tables_to_render.append(table)

    return tables_to_render



# TEXTS and script
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your Whatsapp group chat file", 
    "nl": "Select your Whatsapp group chat file", 
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your Whatsapp group chat data", 
    "nl": "Uw Whatsapp group chat gegevens",
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw",
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a the contents of your group chat", 
   "nl": "Below you will find a the contents of your group chat", 
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
    "nl": "Please follow the instructions below carefully! \nClick on the button “Continue” at the bottom of this page when you are ready to go to the next step.",
})

INSTRUCTION_HEADER = props.Translatable({
   "en": "Instructions to request your Whatsapp group chat data",
   "nl": "Instructions to request your Whatsapp group chat data",
})



def script():
    platform_name = "Whatsapp group chat"
    table_list = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":

            df = parse_chat(file_result.value)
            if not df.empty:
                df = remove_empty_chats(df)
                table_list = extraction(df)

            if df.empty:
                logger.info("Not a valid %s zip; No payload; prompt retry_confirmation", platform_name)
                retry_result = yield ph.render_page(RETRY_HEADER, ph.retry_confirmation(platform_name))

                if retry_result.__type__ == "PayloadTrue":
                    continue
                else:
                    logger.info("Skipped during retry flow")
                    break

            break

        else:
            logger.info("Skipped at file selection ending flow")
            break

    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)

    return

