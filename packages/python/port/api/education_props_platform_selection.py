from dataclasses import dataclass
from port.api.props import Translatable, RadioItem


@dataclass
class PropsUIPromptPlatformSelection:
    """Platform selection menu with structured educational content.

    Renders as: intro paragraph, instruction list, footer paragraph,
    then a fieldset with radio buttons for platform selection.

    Attributes:
        title: legend text for the radio group fieldset
        intro: introductory paragraph
        instructions: unordered list items (rendered as <ul>)
        footer: closing paragraph (privacy assurance + call to action)
        items: radio items for platform selection
        continue_label: label for the Continue/submit button
    """

    title: Translatable
    intro: Translatable
    instructions: list[Translatable]
    footer: Translatable
    items: list[RadioItem]
    continue_label: Translatable

    def toDict(self):
        dict = {}
        dict["__type__"] = "PropsUIPromptPlatformSelection"
        dict["title"] = self.title.toDict()
        dict["intro"] = self.intro.toDict()
        dict["instructions"] = [item.toDict() for item in self.instructions]
        dict["footer"] = self.footer.toDict()
        # RadioItem is a TypedDict (plain dict) — no .toDict() needed
        dict["items"] = self.items
        dict["continueLabel"] = self.continue_label.toDict()
        return dict
