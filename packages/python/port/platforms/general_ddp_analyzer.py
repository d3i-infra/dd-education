"""
General DDP Analyzer — universal ZIP explorer for any data package.

Unlike other platforms, this does not validate against known DDP file lists.
It accepts any ZIP and shows the file structure for educational exploration.
Deliberately skips FlowBuilder's DDP validation and safety checks.
"""

import logging

from collections import Counter

import port.helpers.extraction_helpers as eh
import port.helpers.port_helpers as ph
import port.api.props as props
from port.api.d3i_props import ExtractionResult, PropsUIPromptConsentFormTableViz
from port.helpers.flow_builder import FlowBuilder
from port.helpers import validate

logger = logging.getLogger(__name__)

PLATFORM_NAME = "General DDP Analyzer"

HEADER = props.Translatable({
    "en": PLATFORM_NAME,
    "nl": PLATFORM_NAME,
})


class GeneralDDPAnalyzerFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(session_id, PLATFORM_NAME)

    def validate_file(self, file: str) -> validate.ValidateInput:
        # Not used — start_flow() is overridden
        raise NotImplementedError

    def extract_data(self, file: str, validation=None) -> ExtractionResult:
        """Extract file structure and metadata from any ZIP."""
        errors = Counter()
        tables = []

        file_structures_df = eh.extract_file_structures_from_zip(file, infer_types=False)
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

        file_info_df = eh.extract_zip_file_info(file)
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

    def start_flow(self):
        """Override to skip DDP validation — accepts any ZIP file."""
        yield from ph.emit_log("info", f"[{PLATFORM_NAME}] Starting flow")

        # File prompt
        file_prompt = self.generate_file_prompt()
        file_result = yield ph.render_page(HEADER, file_prompt)

        if file_result.__type__ not in ("PayloadFile", "PayloadString"):
            return

        from port.helpers.uploads import materialize_file
        file_path = materialize_file(file_result)
        yield from ph.emit_log("info", f"[{PLATFORM_NAME}] File materialized")

        # Extract (no validation step)
        yield from ph.emit_log("info", f"[{PLATFORM_NAME}] Extracting data")
        result = self.extract_data(file_path)

        if not result.tables:
            _ = yield ph.render_no_data_page(PLATFORM_NAME)
            return

        yield from ph.emit_log("info", f"[{PLATFORM_NAME}] Extraction complete: {len(result.tables)} tables")

        # Consent form
        consent_prompt = self.generate_review_data_prompt(result.tables)
        consent_result = yield ph.render_page(HEADER, consent_prompt)

        if consent_result.__type__ == "PayloadJSON":
            donate_key = f"{self.session_id}-{PLATFORM_NAME.lower().replace(' ', '_')}"
            yield ph.donate(donate_key, consent_result.value)
