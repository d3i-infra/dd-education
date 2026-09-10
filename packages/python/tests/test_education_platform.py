"""Tests for the composite education platform module."""
from unittest.mock import MagicMock, patch

import pytest

from port.api.commands import CommandUIRender
from port.helpers.flow_builder import FlowBuilder, TaskIncompleteError
import port.platforms.education as education


#: Stands in for the kind of detail a real extractor exception carries — a member path
#: or a value out of the participant's own export. It must reach the local logger and
#: nothing else.
RAISED_DETAIL = "no field 'sender' in messages/inbox/synthetic_contact/message_1.json"


def _payload(type_name, value=None):
    p = MagicMock(); p.__type__ = type_name; p.value = value; return p


class FakeFlow(FlowBuilder):
    """Flow whose start_flow ends the way the test wants."""
    ending = "return"

    def __init__(self, session_id):
        super().__init__(session_id, "Fake")

    def start_flow(self):
        yield CommandUIRender(MagicMock())
        if self.ending == "incomplete":
            raise TaskIncompleteError("abandoned")
        if self.ending == "raises":
            raise ValueError(RAISED_DETAIL)
        return


def _advance(gen, payload=None):
    cmd = gen.send(payload)
    while cmd is None or cmd.__class__.__name__ == "CommandSystemLog":
        cmd = gen.send(None)
    return cmd


@pytest.fixture
def fake_menu(monkeypatch):
    entry = education.PlatformEntry(module="tests.test_education_platform", cls="FakeFlow",
                                    instruction_image="fake.svg", review_description=None)
    monkeypatch.setattr(education, "PLATFORMS", {"Fake": entry})
    return entry


def test_menu_then_flow_then_completion_then_menu(fake_menu):
    gen = education.process("s")
    menu = _advance(gen)
    assert type(menu.page.body).__name__ == "PropsUIPromptPlatformSelection"
    flow_cmd = _advance(gen, _payload("PayloadString", "Fake"))
    assert isinstance(flow_cmd, CommandUIRender)
    done = _advance(gen, _payload("PayloadTrue"))
    assert type(done.page.body).__name__ == "PropsUIPromptConfirm"
    again = _advance(gen, _payload("PayloadTrue"))
    assert type(again.page.body).__name__ == "PropsUIPromptPlatformSelection"


def test_flow_instance_gets_education_attributes(fake_menu):
    with patch.object(FakeFlow, "start_flow", autospec=True) as sf:
        sf.side_effect = lambda self: iter([CommandUIRender(MagicMock())])
        gen = education.process("s")
        _advance(gen); _advance(gen, _payload("PayloadString", "Fake"))
        inst = sf.call_args.args[0]
    assert inst.donate_enabled is False
    assert inst.instruction_image == "fake.svg"


def test_incomplete_flow_returns_to_menu(fake_menu):
    FakeFlow.ending = "incomplete"
    try:
        gen = education.process("s")
        _advance(gen); _advance(gen, _payload("PayloadString", "Fake"))
        back = _advance(gen, _payload("PayloadTrue"))
        assert type(back.page.body).__name__ == "PropsUIPromptPlatformSelection"
    finally:
        FakeFlow.ending = "return"


def test_a_raising_flow_apologises_and_returns_to_menu(fake_menu):
    """One platform's bug is not the end of the session: the menu has no exit, so an
    unhandled exception has to come back as a page rather than as a dead generator."""
    FakeFlow.ending = "raises"
    try:
        gen = education.process("s")
        _advance(gen)
        _advance(gen, _payload("PayloadString", "Fake"))
        apology = _advance(gen, _payload("PayloadTrue"))

        assert type(apology.page.body).__name__ == "PropsUIPromptConfirm"
        text = apology.page.body.text.translations
        assert "Fake" in text["en"] and "Fake" in text["nl"]
        assert set(text) >= {"en", "nl"}

        back = _advance(gen, _payload("PayloadTrue"))
        assert type(back.page.body).__name__ == "PropsUIPromptPlatformSelection"
    finally:
        FakeFlow.ending = "return"


def test_the_traceback_is_logged_locally_and_never_emitted(fake_menu, caplog):
    """ADR-0023: the detail goes to this module's logger for the browser console; the
    host-visible log stream carries none of it."""
    FakeFlow.ending = "raises"
    emitted = []
    try:
        with caplog.at_level("ERROR", logger="port.platforms.education"):
            gen = education.process("s")
            cmd = gen.send(None)
            while True:
                if cmd.__class__.__name__ == "CommandSystemLog":
                    emitted.append(cmd)
                    cmd = gen.send(None)
                    continue
                if type(cmd.page.body).__name__ == "PropsUIPromptConfirm":
                    break
                cmd = gen.send(_payload("PayloadString", "Fake"))
    finally:
        FakeFlow.ending = "return"

    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1 and errors[0].exc_info is not None, "the traceback is logged once, locally"
    assert RAISED_DETAIL in str(errors[0].exc_info[1])
    for log_cmd in emitted:
        assert RAISED_DETAIL not in str(getattr(log_cmd, "message", ""))


def test_unknown_selection_re_renders_menu(fake_menu):
    gen = education.process("s")
    _advance(gen)
    back = _advance(gen, _payload("PayloadString", "Nope"))
    assert type(back.page.body).__name__ == "PropsUIPromptPlatformSelection"


def test_every_menu_entry_imports():
    from importlib import import_module
    for name, entry in education.PLATFORMS.items():
        cls = getattr(import_module(entry.module), entry.cls)
        assert issubclass(cls, FlowBuilder), name


def test_instruction_image_entries_resolve_to_files_that_exist():
    """Every URL a PlatformEntry.instruction_image names (single image or a
    step-by-step deck's list) must resolve to a real file under
    data-collector/public — and, for a deck, to exactly its files (no step
    missing, none left over)."""
    from pathlib import Path

    public_dir = Path(__file__).resolve().parents[3] / "packages" / "data-collector" / "public"

    for name, entry in education.PLATFORMS.items():
        if entry.instruction_image is None:
            continue
        images = entry.instruction_image if isinstance(entry.instruction_image, list) else [entry.instruction_image]
        for image in images:
            assert (public_dir / image).is_file(), f"{name}: missing {image}"

        # A deck (list) is checked exhaustively against its directory's glob:
        # every step file on disk is named in PLATFORMS, and vice versa.
        if isinstance(entry.instruction_image, list) and entry.instruction_image:
            deck_dir = (public_dir / entry.instruction_image[0]).parent
            on_disk = {f"instructions/{deck_dir.name}/{p.name}" for p in deck_dir.glob("step-*.webp")}
            assert on_disk == set(entry.instruction_image), name


def test_every_web_platform_has_a_request_url():
    for name, entry in education.PLATFORMS.items():
        if name in ("WhatsApp", "General DDP Analyzer"):
            assert entry.request_url is None
        else:
            assert entry.request_url is not None and entry.request_url.startswith("https://")


def test_build_flow_sets_the_instruction_url():
    entry = education.PLATFORMS["Netflix"]
    flow = education._build_flow("s1", entry)
    assert flow.instruction_url == entry.request_url


def test_only_chatgpt_and_netflix_have_a_request_note():
    for name, entry in education.PLATFORMS.items():
        if name in ("ChatGPT", "Netflix"):
            assert entry.request_note is not None, name
            assert set(entry.request_note.translations) >= {"en", "nl"}
        else:
            assert entry.request_note is None, name


def test_build_flow_sets_the_instruction_note():
    entry = education.PLATFORMS["ChatGPT"]
    flow = education._build_flow("s1", entry)
    assert flow.instruction_note == entry.request_note


def test_config_validates():
    from port.helpers.port_config_validator import validate_or_raise
    validate_or_raise("education")


def test_youtube_and_google_entries():
    yt = education.PLATFORMS["YouTube"]
    assert (yt.module, yt.cls) == ("port.platforms.education", "YouTubeOnlyGoogleFlow")
    g = education.PLATFORMS["Google"]
    assert (g.module, g.cls) == ("port.platforms.google", "GoogleFlow")
    flow = education._build_flow("s", yt)
    assert flow.platform_name == "YouTube"
    assert "YouTube" in flow.UI_TEXT["submit_file_header"].translations["en"]
    assert "Google" not in flow.UI_TEXT["submit_file_header"].translations["en"]
    gen = flow.start_flow()
    cmd = _advance(gen)
    assert type(cmd.page.body).__name__ == "PropsUIPromptInstructions"
    assert "YouTube" in cmd.page.header.title.translations["en"]


def test_youtube_only_flow_filters_tables():
    from collections import Counter
    from unittest.mock import MagicMock, patch
    from port.api.d3i_props import ExtractionResult
    tables = [MagicMock(id=i) for i in ("youtube_watch_history", "search_history", "youtube_comments")]
    with patch("port.platforms.google.GoogleFlow.extract_data",
               return_value=ExtractionResult(tables=tables, errors=Counter())):
        out = education.YouTubeOnlyGoogleFlow("s").extract_data(MagicMock(), MagicMock())
    assert [t.id for t in out.tables] == ["youtube_watch_history", "youtube_comments"]


def test_youtube_only_flow_empty_result_drops_unrelated_errors():
    from collections import Counter
    from unittest.mock import MagicMock, patch
    from port.api.d3i_props import ExtractionResult
    tables = [MagicMock(id=i) for i in ("search_history", "chrome_history")]
    with patch("port.platforms.google.GoogleFlow.extract_data",
               return_value=ExtractionResult(tables=tables, errors=Counter({"SomeError": 1}))):
        out = education.YouTubeOnlyGoogleFlow("s").extract_data(MagicMock(), MagicMock())
    assert out.tables == []
    assert out.errors == Counter()
