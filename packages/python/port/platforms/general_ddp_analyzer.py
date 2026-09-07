"""
General DDP Analyzer — universal ZIP explorer for any data package.

Unlike other platforms, this does not validate against known DDP file lists.
It accepts any ZIP and shows the file structure for educational exploration.
Uses the standard FlowBuilder flow (with safety checks and donate_enabled guard)
but always passes validation.

Not config-driven: it has no extractor functions, so there is nothing for
``EXTRACTOR_REGISTRY``/``load_port_config`` to describe. Its two tables are
built inline from ``PropsUIPromptConsentFormTableViz`` literals rather than
docstring-driven config (ADR-0028 exception) because their shape (whatever
files happen to be in the uploaded ZIP) isn't known ahead of time.
"""

import logging

from collections import Counter

import port.helpers.extraction_helpers as eh
import port.api.props as props
from port.api.d3i_props import ExtractionResult, PropsUIPromptConsentFormTableViz
from port.api.file_utils import SeekableBinaryReader
from port.helpers.flow_builder import FlowBuilder
from port.helpers import validate

logger = logging.getLogger(__name__)

PLATFORM_NAME = "General DDP Analyzer"

#: No extractor functions of its own; the validator requires the attribute (ADR-0029).
EXTRACTOR_REGISTRY: dict = {}


class GeneralDDPAnalyzerFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(session_id, PLATFORM_NAME)
        self.UI_TEXT["review_data_description"] = props.Translatable({
            "en": "Below you will find the structure of the files in your data package. This shows what types of data the platform stores about you, organized by file and folder.",
            "nl": "Hieronder vindt u de structuur van de bestanden in uw datapakket. Dit laat zien welke soorten gegevens het platform over u opslaat, georganiseerd per bestand en map.",
        })

    def validate_file(self, archive: SeekableBinaryReader) -> validate.ValidateInput:
        """Always returns valid — accepts any ZIP file."""
        status_codes = [validate.StatusCode(id=0, description="Valid")]
        v = validate.ValidateInput(
            all_status_codes=status_codes,
            all_ddp_categories=[],
        )
        v.current_status_code = status_codes[0]
        return v

    def extract_data(self, archive: SeekableBinaryReader, validation=None) -> ExtractionResult:
        """Extract file structure and metadata from any ZIP."""
        errors: Counter[str] = Counter()
        tables = []

        file_structures_df = eh.extract_file_structures_from_zip(archive, infer_types=False)
        if not file_structures_df.empty:
            tables.append(
                PropsUIPromptConsentFormTableViz(
                    id="file_structures",
                    title=props.Translatable({"en": "File Structure", "nl": "Bestandsstructuur"}),
                    data_frame=file_structures_df,
                    description=props.Translatable({
                        "en": "Field names and values found in JSON and CSV files in the data package.",
                        "nl": "Veldnamen en waarden gevonden in JSON- en CSV-bestanden in het datapakket.",
                    }),
                )
            )

        file_info_df = eh.extract_zip_file_info(archive)
        if not file_info_df.empty:
            tables.append(
                PropsUIPromptConsentFormTableViz(
                    id="file_info",
                    title=props.Translatable({"en": "Folder Structure", "nl": "Mapstructuur"}),
                    data_frame=file_info_df,
                    description=props.Translatable({
                        "en": "Overview of all files in the data package with sizes and types.",
                        "nl": "Overzicht van alle bestanden in het datapakket met groottes en typen.",
                    }),
                )
            )

        return ExtractionResult(tables=tables, errors=errors)


def process(session_id: str):
    return GeneralDDPAnalyzerFlow(session_id).start_flow()
