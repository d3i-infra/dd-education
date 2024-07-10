"""
DDP extract ChatGPT module
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
    Language,
    DDPFiletype,
    ValidateInput,
    StatusCode,
)

logger = logging.getLogger(__name__)

DDP_CATEGORIES = [
    DDPCategory(
        id="json",
        ddp_filetype=DDPFiletype.JSON,
        language=Language.EN,
        known_files=["chat.html", "conversations.json", "message_feedback.json", "model_comparisons.json", "user.json"]
    )
]

STATUS_CODES = [
    StatusCode(id=0, description="Valid zip", message="Valid zip"),
    StatusCode(id=1, description="Bad zipfile", message="Bad zipfile"),
]


def validate_zip(zfile: Path) -> ValidateInput:
    """
    Make sure you always set a status code
    """

    validate = ValidateInput(STATUS_CODES, DDP_CATEGORIES)

    try:
        paths = []
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                p = Path(f)
                if p.suffix in (".html", ".json"):
                    logger.debug("Found: %s in zip", p.name)
                    paths.append(p.name)

        if validate.infer_ddp_category(paths):
            validate.set_status_code_by_id(0)
        else:
            validate.set_status_code_by_id(1)
    except zipfile.BadZipFile:
        validate.set_status_code_by_id(1)

    return validate


def conversations_to_df(chatgpt_zip: str)  -> pd.DataFrame:

    b = unzipddp.extract_file_from_zip(chatgpt_zip, "conversations.json")
    conversations = unzipddp.read_json_from_bytes(b)

    datapoints = []
    out = pd.DataFrame()

    try:
        for conversation in conversations:
            title = conversation["title"]
            for _, turn in conversation["mapping"].items():

                denested_d = eh.dict_denester(turn)
                is_hidden = eh.find_item(denested_d, "is_visually_hidden_from_conversation")
                if is_hidden != "True":
                    role = eh.find_item(denested_d, "role")
                    message = "".join(eh.find_items(denested_d, "part"))
                    model = eh.find_item(denested_d, "-model_slug")
                    time = eh.convert_unix_timestamp(eh.find_item(denested_d, "create_time"))

                    datapoint = {
                        "conversation title": title,
                        "role": role,
                        "message": message,
                        "model": model,
                        "time": time,
                    }
                    if role != "":
                        datapoints.append(datapoint)

        out = pd.DataFrame(datapoints)

    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return out



def extraction(chatgpt_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []
    
    df = conversations_to_df(chatgpt_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Your conversations with ChatGPT",
            "nl": "Uw gesprekken met ChatGPT"
        })
        table_description = props.Translatable({
            "en": "In this table you find your conversations with ChatGPT sorted over time. Below, you find a wordcloud, where the size of the words represents how frequent these words have been used in the conversations.", 
            "nl": "In this table you find your conversations with ChatGPT sorted over time. Below, you find a wordcloud, where the size of the words represents how frequent these words have been used in the conversations.", 
        })
        wordcloud = {
            "title": {"en": "", "nl": ""},
            "type": "wordcloud",
            "textColumn": "message",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable("chatgpt_conversations", table_title, df, table_description, [wordcloud])
        tables_to_render.append(table)


    return tables_to_render


def extraction_all(chatgpt_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    This extracts all key value pairs from all json files in a zip
    """

    tables_to_render = []

    df = eh.json_dumper(chatgpt_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Data extracted from all .json files in your ChatGPT .zip file",
            "nl": "Data extracted from all .json files in your ChatGPT .zip file",
        })
        table_description = props.Translatable({
            "en": "Your ChatGPT .zip file consists of a number of .json files. These .json files consists of key-value pairs. In this table, you can find all key–value pairs from all .json files present in your .zip file.", 
            "nl": "Your ChatGPT .zip file consists of a number of .json files. These .json files consists of key-value pairs. In this table, you can find all key–value pairs from all .json files present in your .zip file.", 
        })
        table = props.PropsUIPromptConsentFormTable("all", table_title, df, table_description)
        tables_to_render.append(table)

    return tables_to_render


# TEXTS
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your ChatGPT file", 
    "nl": "Selecteer uw ChatGPT bestand"
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your ChatGPT data", 
    "nl": "Uw ChatGPT gegevens"
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw"
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a currated selection of ChatGPT data. In this case only the conversations you had with ChatGPT are show on screen. The data represented in this way are much more insightfull because you can actually read back the conversations you had with ChatGPT",
   "nl": "Below you will find a currated selection of ChatGPT data. In this case only the conversations you had with ChatGPT are show on screen. The data represented in this way are much more insightfull because you can actually read back the conversations you had with ChatGPT",
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
   "en": "Instructions to request your ChatGPT data",
   "nl": "Instructions to request your ChatGPT data",
})


def script():
    platform_name = "ChatGPT"
    table_list = None
    table_list_all = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "chatgpt_instructions.svg")
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

            # Enter retry flow, reason: if DDP was not a ChatGPT DDP
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

