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
        props.Translatable({"en": "Below you will find your YouTube watch history, search history, subscriptions, and comments, from your Google Takeout export.",
                            "nl": "Hieronder vindt u uw YouTube-kijkgeschiedenis, zoekgeschiedenis, abonnementen en reacties, uit uw Google Takeout-export."})),
    "Google": PlatformEntry("port.platforms.google", "GoogleFlow", None,
        props.Translatable({"en": "Below you will find the tables Google's Takeout export contains about your account: your ads, Discover, and Chrome history, your YouTube activity, your Google search history, and your News activity.",
                            "nl": "Hieronder vindt u de tabellen die de Takeout-export van Google over uw account bevat: uw advertentie-, Discover- en Chrome-geschiedenis, uw YouTube-activiteit, uw Google-zoekgeschiedenis en uw Nieuws-activiteit."})),
    "Netflix": PlatformEntry("port.platforms.netflix", "NetflixFlow", "netflix_instructions.svg",
        props.Translatable({"en": "Below you will find a curated selection of your Netflix data, including your account, devices, viewing activity, ratings, and search history.",
                            "nl": "Hieronder vindt u een samengestelde selectie van uw Netflix-gegevens, waaronder uw account, apparaten, kijkactiviteit, beoordelingen en zoekgeschiedenis."})),
    "Instagram": PlatformEntry("port.platforms.instagram", "InstagramFlow", "instagram_instructions.svg",
        props.Translatable({"en": "Below you will find the tables Instagram's export contains about your account: your account information, inferred ad-targeting categories, your off-platform link and login history, the locations and device details Instagram has inferred or stored, and the posts, videos, ads, comments, and likes recorded from your activity on Instagram.",
                            "nl": "Hieronder vindt u de tabellen die de export van Instagram over uw account bevat: uw accountgegevens, afgeleide advertentietargetingcategorieën, uw link- en logingeschiedenis buiten het platform, de locatie- en apparaatgegevens die Instagram heeft afgeleid of opgeslagen, en de berichten, video's, advertenties, reacties en likes die zijn geregistreerd van uw activiteit op Instagram."})),
    "Facebook": PlatformEntry("port.platforms.facebook", "FacebookFlow", None,
        props.Translatable({"en": "Below you will find the tables Facebook's export contains about your account: the contact lists and friend suggestions Facebook has kept on file, your search history, the ad topics and advertisers linked to you, your activity off Facebook, your posts, comments, and reactions, and the groups, pages, and profiles you follow.",
                            "nl": "Hieronder vindt u de tabellen die de export van Facebook over uw account bevat: de contactenlijsten en vriendschapssuggesties die Facebook heeft bewaard, uw zoekgeschiedenis, de advertentieonderwerpen en adverteerders die aan u zijn gekoppeld, uw activiteit buiten Facebook, uw berichten, opmerkingen en reacties, en de groepen, pagina's en profielen die u volgt."})),
    "LinkedIn": PlatformEntry("port.platforms.linkedin", "LinkedInFlow", "linkedin_instructions.png",
        props.Translatable({"en": "Below you will find the attributes LinkedIn has inferred about you for ad targeting, your contact and registration details on file, and the tables LinkedIn's export contains about your connections, reactions, search queries, and other activity.",
                            "nl": "Hieronder vindt u de kenmerken die LinkedIn over u heeft afgeleid voor advertentiedoeleinden, uw contact- en registratiegegevens, en de tabellen die de export van LinkedIn bevat over uw connecties, reacties, zoekopdrachten en overige activiteit."})),
    "WhatsApp": PlatformEntry("port.platforms.whatsapp", "WhatsAppFlow", "whatsapp_instructions.png",
        props.Translatable({"en": "Below you will find your group chat's messages, emoji usage, and per-participant statistics.",
                            "nl": "Hieronder vindt u de berichten van uw groepschat, het emoji-gebruik en statistieken per deelnemer."})),
    "ChatGPT": PlatformEntry("port.platforms.chatgpt", "ChatGPTFlow", "chatgpt_instructions.svg",
        props.Translatable({"en": "Below you will find the account details OpenAI has on file and your conversations with ChatGPT.",
                            "nl": "Hieronder vindt u de accountgegevens die OpenAI heeft vastgelegd en uw gesprekken met ChatGPT."})),
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
