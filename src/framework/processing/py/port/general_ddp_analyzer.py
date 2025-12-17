"""
General DDP Analyzer
"""

from pathlib import Path
import logging
import zipfile

import pandas as pd

import port.api.props as props
import port.extraction_helpers as eh
import port.port_helpers as ph

logger = logging.getLogger(__name__)


def extraction(zfile: str) -> list[props.PropsUIPromptConsentFormTable]:
    tables_to_render = []
    
    df = eh.extract_file_structures_from_zip(zfile, infer_types=False)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Structure of files in your ZIP archive",
            "nl": "Structuur van bestanden in uw ZIP-archief",
        })

        table_description = props.Translatable({
            "en": (
                "This table describes the structure of the files found in your ZIP archive. "
                "For JSON files, nested objects are flattened and each field is listed separately. "
                "For CSV files, each data point is extracted. "
                "For each field or column, the table shows where it appears in the archive and "
                "the inferred data type (if available)."
            ),
            "nl": (
                "Deze tabel beschrijft de structuur van de bestanden in uw ZIP-archief. "
                "Voor JSON-bestanden worden geneste objecten uitgepakt en worden alle velden afzonderlijk weergegeven. "
                "Voor CSV-bestanden worden de kolomnamen geëxtraheerd. "
                "Per veld of kolom ziet u waar deze voorkomt in het archief en "
                "het afgeleide datatype (indien beschikbaar)."
            ),
        })

        table = props.PropsUIPromptConsentFormTable("ddp file structure", table_title, df, table_description, [])
        tables_to_render.append(table)

    df = eh.extract_zip_file_info(zfile, python_magic=True)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Folder Structure Overview",
            "nl": "Mapstructuur Overzicht"
        })
        table_description = props.Translatable({
            "en": (
                "This table shows the folder structure of the ZIP file, including the file paths, "
                "modification timestamps, and total file sizes. "
                "The mime_type column shows, a guess of what the file might be, this is done by analyzing the first couple of bytes of the file, using python-magic, from these bytes you can infer what type of file it might be."
            ), 
            "nl": (
                ""
            )
        })
        table = props.PropsUIPromptConsentFormTable(
            "file_info", 
            table_title, 
            df, 
            table_description, 
            []
        )
        tables_to_render.append(table)


    return tables_to_render



# TEXTS
SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your zip file", 
    "nl": "Selecteer uw zip bestand"
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your zip data", 
    "nl": "Uw zip gegevens"
})

RETRY_HEADER = props.Translatable({
    "en": "Try again", 
    "nl": "Probeer opnieuw"
})


CONSENT_FORM_DESCRIPTION = props.Translatable({
   "en": "Below you will find a currated selection of zip data. In this case only the conversations you had with zip are show on screen. The data represented in this way are much more insightfull because you can actually read back the conversations you had with zip",
   "nl": "Below you will find a currated selection of zip data. In this case only the conversations you had with zip are show on screen. The data represented in this way are much more insightfull because you can actually read back the conversations you had with zip",
})

CONSENT_FORM_DESCRIPTION_ALL = props.Translatable({
   "en": "",
   "nl": ""
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "This module allows you to analyze Data Download Packages (or any zip file for that matter) from various platforms.""Simply submit your DDP zip file, and the tool will extract and organize the data into a searchable table. This is particularly useful for DDPs containing JSON and CSV files, as it makes it easy to search for specific information, including sensitive data. Please note that all data processing happens locally on your device, your data never leaves your computer. Important: If your DDP contains an extremely large amount of data points, the application may crash due to memory limitations. If this happens, simply refresh the page and try again with a smaller DDP that is of interest to you, or try it on a more powerful device.",
    "nl": "Met deze module kun je Data Download Packages (DDPs) van verschillende platforms analyseren. Selecteer simpelweg je DDP zip-bestand en de tool zal de data extraheren en organiseren in een doorzoekbare tabel. Dit is met name nuttig voor DDPs met JSON en CSV bestanden, omdat het gemakkelijk wordt om naar specifieke informatie te zoeken, inclusief gevoelige data. Let op: alle dataverwerking gebeurt lokaal op jouw apparaat - je data verlaat nooit je computer. Belangrijk: Als je DDP extreem veel datapunten bevat, kan de applicatie crashen door geheugenbeperkingen. Mocht dit gebeuren, ververs dan simpelweg de pagina en probeer het opnieuw met een kleinere dataset.",
})

INSTRUCTION_HEADER = props.Translatable({
   "en": "Instructions to the general DDP Analyzer",
   "nl": "Instructions to the general DDP Analyzer",
})


def script():
    platform_name = "zip"
    table_list = None
    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            table_list = extraction(file_result.value)
            break

        else:
            logger.info("Skipped at file selection ending flow")
            break

    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return

