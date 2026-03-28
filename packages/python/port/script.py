"""
dd-education: Digital Footprint Explorer

Interactive platform selection menu. Users pick a platform from a radio
menu, explore their data, and return to the menu to try another platform.
"""

from importlib import import_module

import port.api.props as props
import port.helpers.port_helpers as ph

# Map display name -> (module_path, class_name)
# Platforms are enabled incrementally — add entries as each platform is validated.
PLATFORM_MAP: dict[str, tuple[str, str]] = {
    "YouTube": ("port.platforms.youtube", "YouTubeFlow"),
    "Netflix": ("port.platforms.netflix", "NetflixFlow"),
    "Instagram": ("port.platforms.instagram", "InstagramFlow"),
    "LinkedIn": ("port.platforms.linkedin", "LinkedInFlow"),
    "WhatsApp": ("port.platforms.whatsapp", "WhatsAppFlow"),
    "ChatGPT": ("port.platforms.chatgpt", "ChatGPTFlow"),
    "General DDP Analyzer": ("port.platforms.general_ddp_analyzer", "GeneralDDPAnalyzerFlow"),
}

HEADER = props.Translatable({
    "en": "Digital Footprint Explorer",
    "nl": "Digitale Voetafdruk Verkenner",
})


def process(session_id: str, platform: str | None = None):
    """Main entry point. Yields an interactive platform menu in a loop."""
    while True:
        platform_names = list(PLATFORM_MAP.keys())
        menu = ph.generate_platform_selection_menu(platform_names)

        selection = yield ph.render_page(HEADER, menu)

        if selection.__type__ == "PayloadString" and selection.value in PLATFORM_MAP:
            module_path, class_name = PLATFORM_MAP[selection.value]
            mod = import_module(module_path)
            FlowClass = getattr(mod, class_name)
            flow = FlowClass(session_id)
            yield from flow.start_flow()

            # Show completion page before returning to platform menu
            _ = yield ph.render_page(
                props.Translatable({
                    "en": "Exploration Complete",
                    "nl": "Verkenning Voltooid",
                }),
                props.PropsUIPromptConfirm(
                    text=props.Translatable({
                        "en": "We hope you enjoyed exploring your digital footprint!",
                        "nl": "We hopen dat je hebt genoten van het verkennen van je digitale voetafdruk!",
                    }),
                    ok=props.Translatable({
                        "en": "Explore another platform",
                        "nl": "Verken een ander platform",
                    }),
                    cancel=props.Translatable({
                        "en": "Explore another platform",
                        "nl": "Verken een ander platform",
                    }),
                ),
            )
