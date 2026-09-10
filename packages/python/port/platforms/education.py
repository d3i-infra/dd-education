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
    instruction_image: str | list[str] | None
    review_description: props.Translatable | None
    request_url: str | None = None
    request_note: props.Translatable | None = None


def _instruction_steps(platform_slug: str, step_count: int) -> list[str]:
    """Ordered step-image URLs for a platform's instruction deck.

    Matches the files rendered from doc/instructions/source/<platform>-request-steps.pdf
    into public/instructions/<platform_slug>/step-NN.webp (see
    tests/test_education_platform.py for the glob that checks these resolve
    to real files).
    """
    return [f"instructions/{platform_slug}/step-{i:02d}.webp" for i in range(1, step_count + 1)]


PLATFORMS: dict[str, PlatformEntry] = {
    "YouTube": PlatformEntry("port.platforms.education", "YouTubeOnlyGoogleFlow", _instruction_steps("youtube", 10),
        props.Translatable({"en": "Below you will find your YouTube watch history, search history, subscriptions, and comments, from your Google Takeout export.",
                            "nl": "Hieronder vind je je YouTube-kijkgeschiedenis, zoekgeschiedenis, abonnementen en reacties, uit je Google Takeout-export."}),
        request_url="https://takeout.google.com/"),
    "Google": PlatformEntry("port.platforms.google", "GoogleFlow", None,
        props.Translatable({"en": "Below you will find the tables Google's Takeout export contains about your account: your ads, Discover, and Chrome history, your YouTube activity, your Google search history, and your News activity.",
                            "nl": "Hieronder vind je de tabellen die de Takeout-export van Google over je account bevat: je advertentie-, Discover- en Chrome-geschiedenis, je YouTube-activiteit, je Google-zoekgeschiedenis en je Nieuws-activiteit."}),
        request_url="https://takeout.google.com/"),
    "Netflix": PlatformEntry("port.platforms.netflix", "NetflixFlow", "instructions/netflix/step-01.webp",
        props.Translatable({"en": "Below you will find a curated selection of your Netflix data, including your account, devices, viewing activity, ratings, and search history.",
                            "nl": "Hieronder vind je een samengestelde selectie van je Netflix-gegevens, waaronder je account, apparaten, kijkactiviteit, beoordelingen en zoekgeschiedenis."}),
        # The account page, not /account/getmyinfo: the export page rejects the
        # redirect after a fresh login ("something went wrong", Danielle's check).
        request_url="https://www.netflix.com/account",
        request_note=props.Translatable({
            "en": "This opens your account page. Under your profile's security settings, "
                  "choose the option to download your personal information.",
            "nl": "Dit opent je accountpagina. Ga naar de beveiligingsinstellingen van je "
                  "profiel en kies daar de optie om je persoonlijke gegevens te downloaden."})),
    "Instagram": PlatformEntry("port.platforms.instagram", "InstagramFlow", _instruction_steps("instagram", 12),
        props.Translatable({"en": "Below you will find the tables Instagram's export contains about your account: your account information, inferred ad-targeting categories, your off-platform link and login history, the locations and device details Instagram has inferred or stored, and the posts, videos, ads, comments, and likes recorded from your activity on Instagram.",
                            "nl": "Hieronder vind je de tabellen die de export van Instagram over je account bevat: je accountgegevens, afgeleide advertentietargetingcategorieën, je link- en logingeschiedenis buiten het platform, de locatie- en apparaatgegevens die Instagram heeft afgeleid of opgeslagen, en de berichten, video's, advertenties, reacties en likes die zijn geregistreerd van je activiteit op Instagram."}),
        request_url="https://accountscenter.instagram.com/info_and_permissions/dyi/"),
    "Facebook": PlatformEntry("port.platforms.facebook", "FacebookFlow", None,
        props.Translatable({"en": "Below you will find the tables Facebook's export contains about your account: the contact lists and friend suggestions Facebook has kept on file, your search history, the ad topics and advertisers linked to you, your activity off Facebook, your posts, comments, and reactions, and the groups, pages, and profiles you follow.",
                            "nl": "Hieronder vind je de tabellen die de export van Facebook over je account bevat: de contactenlijsten en vriendschapssuggesties die Facebook heeft bewaard, je zoekgeschiedenis, de advertentieonderwerpen en adverteerders die aan jou zijn gekoppeld, je activiteit buiten Facebook, je berichten, opmerkingen en reacties, en de groepen, pagina's en profielen die je volgt."}),
        request_url="https://accountscenter.facebook.com/info_and_permissions/dyi/"),
    "LinkedIn": PlatformEntry("port.platforms.linkedin", "LinkedInFlow", "instructions/linkedin/step-01.webp",
        props.Translatable({"en": "Below you will find the attributes LinkedIn has inferred about you for ad targeting, your contact and registration details on file, and the tables LinkedIn's export contains about your connections, reactions, search queries, and other activity.",
                            "nl": "Hieronder vind je de kenmerken die LinkedIn over jou heeft afgeleid voor advertentiedoeleinden, je contact- en registratiegegevens, en de tabellen die de export van LinkedIn bevat over je connecties, reacties, zoekopdrachten en overige activiteit."}),
        request_url="https://www.linkedin.com/mypreferences/d/download-my-data"),
    "WhatsApp": PlatformEntry("port.platforms.whatsapp", "WhatsAppFlow", "instructions/whatsapp/step-01.webp",
        props.Translatable({"en": "Below you will find your group chat's messages, emoji usage, and per-participant statistics.",
                            "nl": "Hieronder vind je de berichten van je groepschat, het emoji-gebruik en statistieken per deelnemer."}),
        request_url=None),
    "ChatGPT": PlatformEntry("port.platforms.chatgpt", "ChatGPTFlow", _instruction_steps("chatgpt", 10),
        props.Translatable({"en": "Below you will find the account details OpenAI has on file and your conversations with ChatGPT.",
                            "nl": "Hieronder vind je de accountgegevens die OpenAI heeft vastgelegd en je gesprekken met ChatGPT."}),
        request_url="https://chatgpt.com/#settings/DataControls",
        request_note=props.Translatable({
            "en": "If ChatGPT asks you to log in first, it won't bring you back to the export "
                  "page afterwards. Open Settings, then Data controls, then Export data.",
            "nl": "Als ChatGPT je eerst vraagt om in te loggen, kom je daarna niet vanzelf op de "
                  "exportpagina terecht. Open dan Instellingen, daarna Gegevensbeheer en dan "
                  "Gegevens exporteren."})),
    "General DDP Analyzer": PlatformEntry("port.platforms.general_ddp_analyzer", "GeneralDDPAnalyzerFlow", None, None),
}

HEADER = props.Translatable({"en": "Digital Footprint Explorer", "nl": "Digitale Voetafdruk Verkenner"})


def _build_flow(session_id: str, entry: PlatformEntry) -> FlowBuilder:
    flow_cls = getattr(import_module(entry.module), entry.cls)
    flow: FlowBuilder = flow_cls(session_id)
    flow.donate_enabled = False
    flow.instruction_image = entry.instruction_image
    flow.instruction_url = entry.request_url
    flow.instruction_note = entry.request_note
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
        except Exception:
            # One platform's bug must not end the session: this menu has no host to hand
            # a failure to and no exit to take (ADR-0041), so an unhandled exception is
            # apologised for and the menu comes back. The traceback stays on this module's
            # logger — local diagnostics only, never emit_log (ADR-0023).
            logger.exception("Flow for %s raised; back to menu", selection.value)
            _ = yield ph.render_platform_error_page(selection.value)
            continue
        _ = yield ph.render_page(
            props.Translatable({"en": "Exploration Complete", "nl": "Verkenning Voltooid"}),
            ph.generate_platform_completion_prompt())
