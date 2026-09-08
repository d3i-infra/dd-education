import port.api.props as props
from port.helpers import port_helpers as ph


def test_multi_prompt_copy_covers_required_locales():
    prompt = ph.generate_file_prompt("application/zip", multiple=True)
    d = prompt.toDict()
    translations = d["description"]["translations"]
    assert set(translations) >= {"en", "nl", "de", "it", "es"}
    assert "file(s)" in translations["en"] or "files" in translations["en"]


def test_single_prompt_copy_unchanged():
    prompt = ph.generate_file_prompt("application/zip")
    assert prompt.toDict()["__type__"] == "PropsUIPromptFileInput"


def test_multi_prompt_includes_example_covering_required_locales():
    """generate_file_prompt(multiple=True) supplies the Takeout-shaped example
    (ITEM 1): PropsUIPromptFileInputMultiple.toDict() includes an "example"
    key when the field is set, covering all 5 locales."""
    prompt = ph.generate_file_prompt("application/zip", multiple=True)
    d = prompt.toDict()
    assert "example" in d
    translations = d["example"]["translations"]
    assert set(translations) >= {"en", "nl", "de", "it", "es"}


def test_multi_prompt_example_filename_identical_across_locales():
    """Only the leading word ("Example"/"Voorbeeld"/...) is translated; the
    Takeout filename shape itself must not vary by locale."""
    prompt = ph.generate_file_prompt("application/zip", multiple=True)
    translations = prompt.toDict()["example"]["translations"]
    filename_part = "takeout-...-1-001.zip, takeout-...-2-001.zip"
    for locale, text in translations.items():
        assert text.endswith(filename_part), f"locale {locale!r} filename part diverged: {text!r}"


def test_single_prompt_has_no_example_key():
    """The single-file prompt type carries no `example` concept at all —
    only PropsUIPromptFileInputMultiple gained the field."""
    prompt = ph.generate_file_prompt("application/zip")
    assert "example" not in prompt.toDict()


def test_protocol_error_page_covers_required_locales():
    page = ph.render_protocol_error_page("Instagram").toDict()["page"]
    body = page["body"][0]
    assert set(page["header"]["title"]["translations"]) >= {"en", "nl", "de", "it", "es"}
    assert set(body["text"]["translations"]) >= {"en", "nl", "de", "it", "es"}
    assert set(body["ok"]["translations"]) >= {"en", "nl", "de", "it", "es"}


def test_protocol_error_page_has_no_cancel_button():
    """ITEM 3: FlowBuilder discards this Confirm's result and always raises
    TaskIncompleteError("upload_rejected") next regardless of which button is
    pressed — a second identical button would invent a distinction that
    isn't there, so this is a single acknowledging button."""
    body = ph.render_protocol_error_page("Instagram").toDict()["page"]["body"][0]
    assert "cancel" not in body


def test_retry_prompt_single_file_wording_unchanged():
    prompt = ph.generate_retry_prompt("Instagram").toDict()
    assert "select a different file" in prompt["text"]["translations"]["en"]
    assert "ALL" not in prompt["text"]["translations"]["en"]


def test_retry_prompt_multiple_tells_participant_to_reselect_all_files():
    """ITEM 2: a multi-file (Google-Takeout-style) retry must ask the
    participant to select ALL the files, not just "a different file"."""
    prompt = ph.generate_retry_prompt("Google", multiple=True).toDict()
    translations = prompt["text"]["translations"]
    assert set(translations) >= {"en", "nl", "de", "it", "es"}
    assert "ALL" in translations["en"]
    assert "ALLE" in translations["nl"]


def test_retry_prompt_multiple_does_not_double_the_retry_adverb():
    """Copy-review fix: "Try again to select ALL the files again" (and the
    nl/de/it/es equivalents) doubled the retry adverb — say it once."""
    translations = ph.generate_retry_prompt("Google", multiple=True).toDict()["text"]["translations"]
    assert "again to select ALL the files again" not in translations["en"]
    assert "opnieuw om ALLE bestanden opnieuw" not in translations["nl"]
    assert "erneut, um ALLE Dateien erneut" not in translations["de"]
    assert "di nuovo TUTTI" not in translations["it"]
    assert "TODOS los archivos de nuevo" not in translations["es"]


def test_retry_prompt_multiple_ok_cancel_labels_unchanged():
    """Only the body text is multi-aware; the Try again / Continue button
    labels stay the same for both single- and multi-file retries."""
    single = ph.generate_retry_prompt("Instagram").toDict()
    multi = ph.generate_retry_prompt("Google", multiple=True).toDict()
    assert single["ok"]["translations"] == multi["ok"]["translations"]
    assert single["cancel"]["translations"] == multi["cancel"]["translations"]


def test_platform_selection_menu_shape():
    import port.helpers.port_helpers as ph

    menu = ph.generate_platform_selection_menu(["YouTube", "Netflix"])
    d = menu.toDict()
    assert d["__type__"] == "PropsUIPromptPlatformSelection"
    assert [i["value"] for i in d["items"]] == ["YouTube", "Netflix"]
    assert set(menu.intro.translations) >= {"en", "nl"}


def test_render_issue_page_builds_tables_from_reader():
    import io
    import zipfile

    import port.api.d3i_props as d3i_props
    import port.helpers.port_helpers as ph

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x/a.json", '{"k": 1}')
    buf.seek(0)
    cmd = ph.render_issue_page("YouTube", buf)
    body = cmd.page.body
    # Prompt dataclasses carry no __type__ attribute on the live object
    # (only in toDict()) — assert the class instead.
    assert isinstance(body, d3i_props.PropsUIPromptIssueForm)
    assert [t.id for t in body.tables] == ["file_structures", "file_info"]


def _archive_set_part(name: str, entries: list[tuple[str, bytes]]):
    """Build one in-memory ArchiveSet part (mirrors tests/test_archive_set.py::_part)."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in entries:
            zf.writestr(path, content)
    buf.seek(0)
    buf.name = name
    buf.size = len(buf.getvalue())
    return buf


def test_render_issue_page_builds_tables_from_archive_set():
    """A multi-file (PayloadFiles) flow, e.g. Google, hands render_issue_page
    an ArchiveSet rather than a single SeekableBinaryReader."""
    import port.api.d3i_props as d3i_props
    import port.helpers.port_helpers as ph
    from port.helpers.archive_set import ArchiveSet

    part = _archive_set_part("takeout-1-001.zip", [("Takeout/data.json", b'{"k": 1}')])
    archive_set = ArchiveSet([part])
    cmd = ph.render_issue_page("Google", archive_set)
    body = cmd.page.body
    assert isinstance(body, d3i_props.PropsUIPromptIssueForm)
    assert [t.id for t in body.tables] == ["file_structures", "file_info"]


def test_completion_prompt_buttons_are_labelled_for_what_they_do():
    """Both buttons return to the menu (ADR-0041: the loop has no exit), so they are
    labelled for the two reasons a participant is here, not as two outcomes."""
    prompt = ph.generate_platform_completion_prompt()
    assert prompt.ok.translations["en"] == "Explore another platform"
    assert prompt.ok.translations["nl"] == "Verken nog een platform"
    assert prompt.cancel.translations["en"] == "Back to the menu"
    assert prompt.cancel.translations["nl"] == "Terug naar het menu"
    assert prompt.ok.translations != prompt.cancel.translations


def test_platform_error_page_names_the_platform_and_offers_one_way_on():
    page = ph.render_platform_error_page("Netflix").toDict()["page"]
    body = page["body"][0]
    assert set(body["text"]["translations"]) >= {"en", "nl"}
    assert "Netflix" in body["text"]["translations"]["en"]
    assert "Netflix" in body["text"]["translations"]["nl"]
    assert "cancel" not in body, "there is one way on from here: back to the menu"
    assert body["ok"]["translations"]["en"] == "Continue"


class TestTheIssueReportNamesNobody:
    """The issue report is uploaded, so the member paths in it must carry the archive's
    shape and nothing else — an export names folders and files after the people the
    participant talked to."""

    def _synthetic_export(self):
        """A synthetic archive shaped like a real export: contact names as folder and
        file names, at several depths."""
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("messages/inbox/name_123/message_1.json", '{"sender": "name"}')
            zf.writestr("messages/inbox/other_person_99/message_1.json", '{"sender": "other"}')
            zf.writestr("ads_information/advertisers.json", '{"a": 1}')
            zf.writestr("archive_browser.html", b"<html></html>")
        buf.seek(0)
        return buf

    def _rows(self, table, column):
        return list(table.data_frame[column])

    def test_no_leaf_or_intermediate_name_survives_in_the_file_info_table(self):
        import port.helpers.port_helpers as ph

        body = ph.render_issue_page("Instagram", self._synthetic_export()).page.body
        file_info = next(t for t in body.tables if t.id == "file_info")
        paths = self._rows(file_info, "file_path")

        assert sorted(paths) == sorted([
            "messages/<dir>/<dir>/<file>.json",
            "messages/<dir>/<dir>/<file>.json",
            "ads_information/<file>.json",
            "<file>.html",
        ])
        joined = " ".join(paths)
        for name in ("name_123", "other_person_99", "message_1", "advertisers", "archive_browser"):
            assert name not in joined

    def test_the_structure_table_is_redacted_too(self):
        """Both tables are serialized into the same upload, so both are redacted."""
        import port.helpers.port_helpers as ph

        body = ph.render_issue_page("Instagram", self._synthetic_export()).page.body
        structures = next(t for t in body.tables if t.id == "file_structures")
        paths = set(self._rows(structures, "filepath"))

        assert paths == {"messages/<dir>/<dir>/<file>.json", "ads_information/<file>.json"}

    def test_the_top_level_section_and_the_depth_are_what_is_kept(self):
        """What a bug report needs from a path: which section, how deep, what kind."""
        import port.helpers.port_helpers as ph

        body = ph.render_issue_page("Instagram", self._synthetic_export()).page.body
        file_info = next(t for t in body.tables if t.id == "file_info")
        paths = self._rows(file_info, "file_path")

        assert "messages/<dir>/<dir>/<file>.json" in paths, "depth and section preserved"
        assert all(p.endswith((".json", ".html")) for p in paths), "extension preserved"


def test_review_data_prompt_default_is_not_review_only():
    import port.helpers.port_helpers as ph
    prompt = ph.generate_review_data_prompt(props.Translatable({"en": "d", "nl": "d"}), [])
    assert prompt.toDict()["reviewOnly"] is False


def test_review_data_prompt_review_only_uses_continue_copy():
    import port.helpers.port_helpers as ph
    prompt = ph.generate_review_data_prompt(props.Translatable({"en": "d", "nl": "d"}), [], review_only=True)
    d = prompt.toDict()
    assert d["reviewOnly"] is True
    assert prompt.donate_button.translations["en"] == "Continue"
    assert prompt.donate_question.translations["en"] == ""
