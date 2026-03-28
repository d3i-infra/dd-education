"""Props specific to dd-education that are not in the standard d3i_props."""

from dataclasses import dataclass, field

import port.api.props as props
import port.api.d3i_props as d3i_props


@dataclass
class PropsUIPromptIssueForm:
    """Issue report form with file structure tables and upload capability."""

    description: props.Translatable
    tables: list[d3i_props.PropsUIPromptConsentFormTableViz]
    platform: str
    __type__: str = field(default="PropsUIPromptIssueForm", init=False)

    def toDict(self):
        return {
            "__type__": self.__type__,
            "description": self.description.toDict(),
            "tables": [t.toDict() for t in self.tables],
            "platform": self.platform,
        }
