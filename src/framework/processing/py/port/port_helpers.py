import pandas as pd

import port.api.props as props
import port.extraction_helpers as eh
from port.api.commands import (CommandSystemDonate, CommandUIRender)


def render_page(header_text: props.Translatable, body):
    """
    Renders the UI components
    """
    header = props.PropsUIHeader(header_text)
    footer = props.PropsUIFooter()
    page = props.PropsUIPageDonation("does not matter", header, body, footer)
    return CommandUIRender(page)


def generate_retry_prompt(platform: str) -> props.PropsUIPromptConfirm:
    text = props.Translatable({
        "en": f"Unfortunately, we cannot process your {platform} file. Continue, if you are sure that you selected the right file. Try again to select a different file.",
        "nl": f"Helaas, kunnen we uw {platform} bestand niet verwerken. Weet u zeker dat u het juiste bestand heeft gekozen? Ga dan verder. Probeer opnieuw als u een ander bestand wilt kiezen."
    })
    ok = props.Translatable({
        "en": "Try again",
        "nl": "Probeer opnieuw"
    })
    cancel = props.Translatable({
        "en": "Continue",
        "nl": "Verder"
    })
    return props.PropsUIPromptConfirm(text, ok, cancel)


def generate_file_prompt(platform, extensions) -> props.PropsUIPromptFileInput:
    description = props.Translatable({
        "en": f"Select the .zip file you received from the platform and stored on your device, and press \"Continue\".",
        "nl": f"Volg de download instructies van de vorige pagina en kies het bestand dat u opgeslagen heeft op uw apparaat."
    })
    return props.PropsUIPromptFileInput(description, extensions)


def generate_consent_prompt(table_list: list[props.PropsUIPromptConsentFormTable], description: props.Translatable) -> props.PropsUIPromptConsentForm:
    donate_question = props.Translatable({
       "en": "",
       "nl": ""
    })

    donate_button = props.Translatable({
       "en": "Continue",
       "nl": "Doorgaan"
    })

    return props.PropsUIPromptConsentForm(
       table_list, 
       meta_tables=[],
       description=description,
       donate_question=donate_question,
       donate_button=donate_button
    )


def generate_issue_prompt(zfile: str) -> props.PropsUIPromptIssueForm:
    tables_to_render = []

    df = eh.extract_file_structures_from_zip(zfile)
    if not df.empty:
        table_title = props.Translatable({
            "en": "asd",
            "nl": "asd"
        })
        table_description = props.Translatable({
            "en": "asd", 
            "nl": "asd", 
        })
        table = props.PropsUIPromptConsentFormTable("asd", table_title, df, table_description, [])
        tables_to_render.append(table)

    df = eh.extract_zip_file_info(zfile)
    if not df.empty:
        table_title = props.Translatable({
            "en": "qwe",
            "nl": "qwe"
        })
        table_description = props.Translatable({
            "en": "qwe", 
            "nl": "qwe", 
        })
        table = props.PropsUIPromptConsentFormTable("qwe", table_title, df, table_description, [])
        tables_to_render.append(table)


    description = props.Translatable({
       "en": "banaan",
       "nl": "banaan"
    })

    return props.PropsUIPromptIssueForm(
       tables_to_render, 
       description=description,
    )


def retry_confirmation(platform):
    text = props.Translatable(
        {
            "en": f"Unfortunately, we could not process your {platform} file. If you are sure that you selected the correct file, press Continue. To select a different file, press Try again.",
            "nl": f"Helaas, kunnen we uw {platform} bestand niet verwerken. Weet u zeker dat u het juiste bestand heeft gekozen? Ga dan verder. Probeer opnieuw als u een ander bestand wilt kiezen."
        }
    )
    ok = props.Translatable({"en": "Try again", "nl": "Probeer opnieuw"})
    cancel = props.Translatable({"en": "Continue", "nl": "Verder"})
    return props.PropsUIPromptConfirm(text, ok, cancel)


def generate_instructions_prompt(description: props.Translatable, image_url: str) -> props.PropsUIPromptInstructions:
    return props.PropsUIPromptInstructions(
        description=description,
        imageUrl=image_url
    )

def render_issue_page(platform_name: str, zfile: str):
    """
    Renders the issue report page for data extraction problems
    """
    header_text = props.Translatable({
        "en": "Submit Issue Report",
        "nl": "Probleem Melden"
    })
    
    description = props.Translatable({
        "en": (
            "Thank you for your interest in submitting an issue report!\n\n"
            "Data download packages from platforms can change their file structure over time. "
            "When our extraction process doesn't work as expected, it's usually because the platform "
            "has updated how they organize their files.\n\n"
            "Receiving examples of these new file structures is extremely helpful for us to fix the extraction. "
            "The data below shows the file structure we detected in your download package.\n\n"
            "Please review the information below and only submit if you're comfortable sharing this data. "
            "The report will be securely stored in a SurfDrive folder in the Netherlands, only used for improving this application"
            "and will only be used to improve our data extraction process, and then deleted. "
            "For any questions or remarks email DataDonation@uu.nl"
        ),
        "nl": (
            "Bedankt voor uw interesse in het indienen van een probleemrapport!\n\n"
            "Gegevenspakketten van platforms kunnen hun bestandsstructuur in de loop van de tijd wijzigen. "
            "Wanneer ons extractieproces niet werkt zoals verwacht, komt dit meestal doordat het platform "
            "heeft bijgewerkt hoe ze hun bestanden organiseren.\n\n"
            "Het ontvangen van voorbeelden van deze nieuwe bestandsstructuren is zeer nuttig voor ons om de extractie te verbeteren. "
            "De onderstaande gegevens tonen de bestandsstructuur die we in uw downloadpakket hebben gedetecteerd.\n\n"
            "Bekijk de onderstaande informatie en verstuur alleen als u het goed vindt om deze gegevens te delen. "
            "De bestandsstructuurinformatie wordt veilig opgeslagen in een SurfDrive-map in Nederland "
            "en wordt alleen gebruikt om ons data-extractieproces te verbeteren."
        )
    })
    
    tables_to_render = []
    
    # Extract file structures
    df = eh.extract_file_structures_from_zip(zfile)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Detailed File Structure",
            "nl": "Gedetailleerde Bestandsstructuur"
        })
        table_description = props.Translatable({
            "en": (
                "This table shows the detailed file structure of JSON and CSV files found in your download package. "
                "It displays all key-value pairs that are present. The actual values have been anonymized and "
                "replaced with their data types (e.g., 'string', 'number', 'boolean') to protect your privacy."
            ), 
            "nl": (
                "Deze tabel toont de gedetailleerde bestandsstructuur van JSON- en CSV-bestanden in uw downloadpakket. "
                "Het toont alle sleutel-waardeparen die aanwezig zijn. De werkelijke waarden zijn geanonimiseerd en "
                "vervangen door hun gegevenstypen (bijv. 'string', 'number', 'boolean') om uw privacy te beschermen."
            )
        })
        table = props.PropsUIPromptConsentFormTable(
            "file_structures", 
            table_title, 
            df, 
            table_description, 
            []
        )
        tables_to_render.append(table)
    
    # Extract file info
    df = eh.extract_zip_file_info(zfile)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Folder Structure Overview",
            "nl": "Mapstructuur Overzicht"
        })
        table_description = props.Translatable({
            "en": (
                "This table shows the folder structure of the ZIP file, including the file paths, "
                "modification timestamps, and total file sizes. This helps us understand how the platform "
                "organizes files in their data downloads."
            ), 
            "nl": (
                "Deze tabel toont de mapstructuur van het ZIP-bestand, inclusief de bestandspaden, "
                "wijzigingstijden en totale bestandsgroottes. Dit helpt ons begrijpen hoe het platform "
                "bestanden organiseert in hun gegevensdownloads."
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
    
    body = props.PropsUIPromptIssueForm(
        platform=platform_name,
        tables=tables_to_render, 
        description=description
    )
    
    header = props.PropsUIHeader(header_text)
    footer = props.PropsUIFooter()
    page = props.PropsUIPageDonation("issue_report", header, body, footer)
    
    return CommandUIRender(page)
