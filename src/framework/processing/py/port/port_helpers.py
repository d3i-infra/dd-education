import pandas as pd

import port.api.props as props
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
        "en": f"Please follow the download instructions from the previous page and choose the file that you stored on your device.",
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

