"""
dd-education: Digital Footprint Explorer.

Composite platform module. Selected with ``VITE_PLATFORM=education``; upstream's
``script.py`` dispatches here unchanged (ADR-0029). ``process()`` loops a platform
menu and runs the chosen platform's own ``FlowBuilder`` in education mode: no
donation, an instruction page first, and an issue-report form on the consent page.

Platform info::

    {
      "name": "education",
      "filetypes": ["zip"],
      "languages": ["en", "nl"],
      "description": "Interactive menu over the education platforms; no donation.",
      "time_last_tested": "2026-09"
    }
"""
from collections import Counter
from dataclasses import dataclass
from importlib import import_module
import logging

import port.api.props as props
import port.helpers.port_helpers as ph
from port.api.d3i_props import ExtractionResult
from port.helpers.flow_builder import FlowBuilder, TaskIncompleteError
from port.platforms.google import GoogleFlow

logger = logging.getLogger(__name__)

#: No extractors of its own; the validator requires the attribute (ADR-0029).
EXTRACTOR_REGISTRY: dict = {}

#: Table id prefix shared by the four YouTube tables extracted from a Google Takeout.
YOUTUBE_TABLE_PREFIX = "youtube_"


class YouTubeOnlyGoogleFlow(GoogleFlow):
    """The Google Takeout flow, showing only its YouTube tables (education menu entry).

    The YouTube exports on hand for this study are HTML Takeout, which
    ``platforms.youtube`` cannot read (JSON/CSV only). Google's flow reads YouTube
    history from either format, in seven locales, so this entry reuses it wholesale
    and filters the result down to the YouTube tables for a focused menu item.

    Owns its own ``platform_name`` rather than leaving ``GoogleFlow``'s hardcoded
    "Google" in place: ``FlowBuilder`` uses ``self.platform_name`` throughout
    ``start_flow`` (instructions page, no-data page, protocol-error page, issue page,
    every ``emit_log`` call), so a bolted-on header override would have left every one
    of those still reading "Google". Re-running the inherited ``_initialize_ui_text``
    after resetting the name re-derives every UI_TEXT entry from "YouTube" instead of
    duplicating that derivation here.
    """

    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.platform_name = "YouTube"
        self._initialize_ui_text()

    def extract_data(self, archive_set, validation) -> ExtractionResult:
        result = super().extract_data(archive_set, validation)
        kept = [t for t in result.tables if t.id.startswith(YOUTUBE_TABLE_PREFIX)]
        if not kept:
            # No YouTube activity in this Takeout: the no-data page is the right
            # outcome, even if the wider Google extraction hit an unrelated error on
            # some other source — that error is not this entry's concern, and
            # forwarding it would route a YouTube-activity-free participant into the
            # extraction-failure path instead.
            return ExtractionResult(tables=[], errors=Counter())
        return ExtractionResult(tables=kept, errors=result.errors)


@dataclass(frozen=True)
class PlatformEntry:
    module: str
    cls: str
    instruction_image: str | None
    review_description: props.Translatable | None


PLATFORMS: dict[str, PlatformEntry] = {
    "YouTube": PlatformEntry("port.platforms.education", "YouTubeOnlyGoogleFlow", "youtube_instructions.svg",
        props.Translatable({"en": "Below you will find a curated selection of your YouTube data.",
                            "nl": "Hieronder vindt u een samengestelde selectie van uw YouTube-gegevens."})),
    "Google": PlatformEntry("port.platforms.google", "GoogleFlow", None,
        props.Translatable({"en": "Below you will find a selection of what Google keeps about you: your YouTube history, searches, Chrome history, ads and more.",
                            "nl": "Hieronder vindt u een selectie van wat Google over u bewaart: uw YouTube-geschiedenis, zoekopdrachten, Chrome-geschiedenis, advertenties en meer."})),
    "Netflix": PlatformEntry("port.platforms.netflix", "NetflixFlow", "netflix_instructions.svg",
        props.Translatable({"en": "Below you will find a curated selection of your Netflix data. This includes your viewing history, ratings, and search activity. Try searching through the tables to explore what Netflix knows about your watching habits.",
                            "nl": "Hieronder vindt u een samengestelde selectie van uw Netflix-gegevens. Dit omvat uw kijkgeschiedenis, beoordelingen en zoekactiviteit. Probeer door de tabellen te zoeken om te ontdekken wat Netflix weet over uw kijkgedrag."})),
    "Instagram": PlatformEntry("port.platforms.instagram", "InstagramFlow", "instagram_instructions.svg",
        props.Translatable({"en": "Below you will find a curated selection of your Instagram data. This includes the posts and videos you viewed, your comments, the accounts you follow, and the ads shown to you. Explore the tables to discover the traces you leave behind on Instagram.",
                            "nl": "Hieronder vindt u een samengestelde selectie van uw Instagram-gegevens. Dit omvat de berichten en video's die u heeft bekeken, uw reacties, de accounts die u volgt en de advertenties die aan u zijn getoond. Verken de tabellen om te ontdekken welke sporen u achterlaat op Instagram."})),
    "LinkedIn": PlatformEntry("port.platforms.linkedin", "LinkedInFlow", "linkedin_instructions.png",
        props.Translatable({"en": "Below you will find a curated selection of your LinkedIn data, showing the breadth of what LinkedIn collects about you. This includes your connections, reactions, search queries, and the ads you clicked on.",
                            "nl": "Hieronder vindt u een samengestelde selectie van uw LinkedIn-gegevens, die laat zien hoeveel LinkedIn over u verzamelt. Dit omvat uw connecties, reacties, zoekopdrachten en de advertenties waarop u heeft geklikt."})),
    "WhatsApp": PlatformEntry("port.platforms.whatsapp", "WhatsAppFlow", "whatsapp_instructions.png",
        props.Translatable({"en": "Below you will find the contents of your group chat and some fun statistics about your group! Try searching through the messages to see what your group has been talking about.",
                            "nl": "Hieronder vindt u de inhoud van uw groepschat en enkele leuke statistieken over uw groep! Probeer door de berichten te zoeken om te zien waar uw groep het over heeft gehad."})),
    "ChatGPT": PlatformEntry("port.platforms.chatgpt", "ChatGPTFlow", "chatgpt_instructions.svg",
        props.Translatable({"en": "Below you will find your conversations with ChatGPT. You can read back what you discussed and see how your usage developed over time.",
                            "nl": "Hieronder vindt u uw gesprekken met ChatGPT. U kunt teruglezen wat u heeft besproken en zien hoe uw gebruik zich in de loop van de tijd heeft ontwikkeld."})),
    "General DDP Analyzer": PlatformEntry("port.platforms.general_ddp_analyzer", "GeneralDDPAnalyzerFlow", None, None),
}

HEADER = props.Translatable({"en": "Digital Footprint Explorer", "nl": "Digitale Voetafdruk Verkenner"})


def _build_flow(session_id: str, entry: PlatformEntry) -> FlowBuilder:
    flow_cls = getattr(import_module(entry.module), entry.cls)
    flow: FlowBuilder = flow_cls(session_id)
    flow.donate_enabled = False
    flow.instruction_image = entry.instruction_image
    if entry.review_description is not None:
        flow.UI_TEXT["review_data_description"] = entry.review_description
    return flow


def process(session_id: str):
    """Menu loop. Never exhausts: the participant closes the page (no host, ADR-0025 exception)."""
    while True:
        menu = ph.generate_platform_selection_menu(list(PLATFORMS))
        selection = yield ph.render_page(HEADER, menu)
        if getattr(selection, "__type__", None) != "PayloadString" or selection.value not in PLATFORMS:
            continue
        entry = PLATFORMS[selection.value]
        yield from ph.emit_log("info", f"[education] Platform selected: {selection.value}")
        try:
            yield from _build_flow(session_id, entry).start_flow()
        except TaskIncompleteError as e:
            logger.info("Flow ended without completion (%s); back to menu", e.reason)
            continue
        _ = yield ph.render_page(
            props.Translatable({"en": "Exploration Complete", "nl": "Verkenning Voltooid"}),
            ph.generate_platform_completion_prompt())
