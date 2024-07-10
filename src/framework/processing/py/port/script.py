import logging

import port.api.props as props
from port.api.commands import (CommandUIRender, CommandSystemExit)

import port.port_helpers as ph
import port.chatgpt as chatgpt
import port.youtube as youtube
import port.instagram as instagram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s --- %(name)s --- %(levelname)s --- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

HEADER_TEXT = props.Translatable({
    "en": "Digital Footprint Explorer",
    "nl": "Digital Footprint Explorer",
})


def process(_):

    selection_prompt = generate_platform_selection_menu()
    selection_result = yield ph.render_page(HEADER_TEXT, selection_prompt)

    # If the participant submitted a file: continue
    if selection_result.__type__ == 'PayloadString':
        if selection_result.value == "ChatGPT":
            yield from chatgpt.script()

        if selection_result.value == "YouTube":
            yield from youtube.script()

        if selection_result.value == "Instagram":
            yield from instagram.script()

    yield exit_port(0, "Success")
    yield render_end_page()


def generate_platform_selection_menu():
    """
    Generate a menu that person can change from to interact with their data from chosen platform
    """
    title = props.Translatable({
        "en": "Select the platform",
        "nl": "Select the platform",
    })

    description = props.Translatable({
"en": """
Welcome! The Digital Footprint Explorer visualizes the digital traces that you leave behind on the platforms that you use. With this tool you can gain a better understanding of your own digital footprint.

It works as follows:

* You request a digital copy of your personal data at a platform.
* You store this data at your own personal device.
* Next, you open the data using this tool and start exploring!
* When you are done, you simply close the page.

The tool works locally in the browser of your computer. Never, at any moment, will the data leave your computer! 

Click on one of the platforms below and start exploring!
""",
"nl": """
Welcome! The Digital Footprint Explorer visualizes the digital traces that you leave behind on the platforms that you use. With this tool you can gain a better understanding of your own digital footprint.

It works as follows:

* You request a digital copy of your personal data at a platform.
* You store this data at your own personal device.
* Next, you open the data using this tool and start exploring!
* When you are done, you simply close the page.

The tool works locally in the browser of your computer. Never, at any moment, will the data leave your computer! 

Click on one of the platforms below and start exploring!
""",
    })

    items = [
        props.RadioItem(id = 1, value = "ChatGPT"),
        props.RadioItem(id = 2, value = "YouTube"),
        props.RadioItem(id = 3, value = "Instagram"),
    ]
    
    return props.PropsUIPromptRadioInput(title = title, description = description, items = items)



def render_end_page():
    """
    Renders a thank you page
    """
    page = props.PropsUIPageEnd()
    return CommandUIRender(page)


def exit_port(code, info):
    return CommandSystemExit(code, info)


