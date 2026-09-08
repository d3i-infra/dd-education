"""Tests for the composite education platform module."""
from unittest.mock import MagicMock, patch

import pytest

from port.api.commands import CommandUIRender
from port.helpers.flow_builder import FlowBuilder, TaskIncompleteError
import port.platforms.education as education


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


def test_config_validates():
    from port.helpers.port_config_validator import validate_or_raise
    validate_or_raise("education")


def test_youtube_and_google_entries():
    yt = education.PLATFORMS["YouTube"]
    assert (yt.module, yt.cls) == ("port.platforms.education", "YouTubeOnlyGoogleFlow")
    g = education.PLATFORMS["Google"]
    assert (g.module, g.cls) == ("port.platforms.google", "GoogleFlow")
    flow = education._build_flow("s", yt)
    assert "YouTube" in flow.UI_TEXT["submit_file_header"].translations["en"]
    assert "Google" not in flow.UI_TEXT["submit_file_header"].translations["en"]


def test_youtube_only_flow_filters_tables():
    from collections import Counter
    from unittest.mock import MagicMock, patch
    from port.api.d3i_props import ExtractionResult
    tables = [MagicMock(id=i) for i in ("youtube_watch_history", "search_history", "youtube_comments")]
    with patch("port.platforms.google.GoogleFlow.extract_data",
               return_value=ExtractionResult(tables=tables, errors=Counter())):
        out = education.YouTubeOnlyGoogleFlow("s").extract_data(MagicMock(), MagicMock())
    assert [t.id for t in out.tables] == ["youtube_watch_history", "youtube_comments"]
