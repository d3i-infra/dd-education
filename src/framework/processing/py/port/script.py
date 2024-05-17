import logging

import port.api.props as props
from port.api.commands import (CommandUIRender, CommandSystemExit)

import port.port_helpers as ph
import port.chatgpt as chatgpt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s --- %(name)s --- %(levelname)s --- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

HEADER_TEXT = props.Translatable({
    "en": "Data donation for educational purposes",
    "nl": "Data donation for educational purposes",
})


def process(_):
    # Start of the data donation flow
    selection_prompt = generate_platform_selection_menu()
    selection_result = yield ph.render_page(HEADER_TEXT, selection_prompt)

    # If the participant submitted a file: continue
    if selection_result.__type__ == 'PayloadString':
        if selection_result.value == "ChatGPT":
            yield from chatgpt.script()


    yield exit_port(0, "Success")
    yield render_end_page()



def generate_platform_selection_menu():
    """
    Generate a menu that person can change from to interact with their data from chosen platform
    """
    title = props.Translatable({
        "en": "Select your platform",
        "nl": "Select the platform",
    })

    description = props.Translatable({
        "en": "Welcome to the data donation task, a website dedicated to visualizing individuals' data packages obtained from major platforms for educational purposes.\nThis platform offers concise and straightforward visual representations of the data collected, allowing users to gain insights into their digital footprint. Explore your online activities with the data donation task and enhance your understanding of data privacy and digital literacy.\nNote: At no point in the process, data leave your own device. Everything you see on screen happens in your browser.",
        "nl": "Welcome to the data donation task, a website dedicated to visualizing individuals' data packages obtained from major platforms for educational purposes.\nThis platform offers concise and straightforward visual representations of the data collected, allowing users to gain insights into their digital footprint. Explore your online activities with the data donation task and enhance your understanding of data privacy and digital literacy.\nNote: At no point in the process, data leave your own device. Everything you see on screen happens in your browser.",
    })

    items = [
        props.RadioItem(id = 1, value = "Facebook"),
        props.RadioItem(id = 2, value = "YouTube"),
        props.RadioItem(id = 3, value = "ChatGPT"),
        props.RadioItem(id = 4, value = "Whatever"),
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


