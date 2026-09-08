"""UI-content locale coverage checks in ``port_config_validator``.

These guard the *JSON config* path, which never passes through
``Translatable`` — a researcher edits a ``Table config::`` docstring block and
the generator copies it verbatim into ``configs/<platform>_config.json``.  A
plain string where a locale bundle belongs, or a bundle with no English text,
must surface at generation/release time rather than as ``?text?`` in front of
a participant.

All fixtures here are synthetic: table *metadata* only, never participant data.
"""

import json
import re
from pathlib import Path

import pytest

from port.helpers.port_config_validator import (
    ui_content_coverage,
    validate,
    validate_ui_content,
)
from port.helpers.ui_locale import (
    DEFAULT_UI_LOCALE,
    PROVISIONAL_UI_LOCALES,
    SUPPORTED_UI_LOCALES,
)

#: The committed configs, the ones a release actually ships.
CONFIG_DIR = Path(__file__).resolve().parent.parent / "port" / "configs"


def _table(**overrides) -> dict:
    """A minimal, fully-covered table entry; override one field per test."""
    entry = {
        "id": "synthetic_table",
        "extractor": "synthetic_to_df",
        "title": {"en": "Synthetic title", "nl": "Synthetische titel"},
        "description": {"en": "A synthetic table.", "nl": "Een synthetische tabel."},
        "headers": {
            "col_a": {"en": "Column A", "nl": "Kolom A"},
            "col_b": {"en": "Column B", "nl": "Kolom B"},
        },
    }
    entry.update(overrides)
    return entry


# --- seed case 1: missing English -------------------------------------------


def test_bundle_without_english_is_an_error():
    tables = [_table(title={"nl": "Alleen Nederlands"})]

    errors, warnings = validate_ui_content(tables)

    assert warnings == []
    assert len(errors) == 1
    assert "title" in errors[0]
    assert DEFAULT_UI_LOCALE in errors[0]


def test_header_without_english_is_an_error():
    tables = [_table(headers={"col_a": {"nl": "Kolom A"}})]

    errors, _ = validate_ui_content(tables)

    assert len(errors) == 1
    assert "col_a" in errors[0]


# --- seed case 2: plain string where a locale bundle belongs -----------------


def test_plain_string_header_is_an_error():
    tables = [_table(headers={"col_a": "Column A"})]

    errors, _ = validate_ui_content(tables)

    assert len(errors) == 1
    assert "col_a" in errors[0]
    assert "str" in errors[0]


def test_non_string_translation_value_is_an_error():
    tables = [_table(title={"en": "Fine", "nl": 42})]

    errors, _ = validate_ui_content(tables)

    assert len(errors) == 1
    assert "nl" in errors[0]
    assert "int" in errors[0]


def test_visualization_titles_are_checked_too():
    tables = [
        _table(
            visualizations=[
                {"title": "Wordcloud", "type": "wordcloud", "textColumn": "col_a"}
            ]
        )
    ]

    errors, _ = validate_ui_content(tables)

    assert len(errors) == 1
    assert "visualizations" in errors[0]


# --- seed case 3: empty translation is deliberate ----------------------------


def test_empty_translation_is_a_warning_never_an_error():
    tables = [_table(description={"en": "", "nl": ""})]

    errors, warnings = validate_ui_content(tables)

    assert errors == []
    assert len(warnings) == 1
    assert "empty" in warnings[0].lower()


def test_empty_translations_aggregate_into_one_warning():
    tables = [
        _table(id=f"t{i}", description={"en": "", "nl": ""}) for i in range(6)
    ]

    errors, warnings = validate_ui_content(tables)

    assert errors == []
    assert len(warnings) == 1


# --- seed case 4: unknown locale keys aggregate ------------------------------


def test_unknown_locale_keys_produce_a_single_aggregate_warning():
    unknown = "zz"
    assert unknown not in SUPPORTED_UI_LOCALES
    tables = [
        _table(
            id=f"t{i}",
            title={"en": "Title", unknown: "Titel"},
            description={"en": "Description", unknown: "Beschrijving"},
        )
        for i in range(5)
    ]

    errors, warnings = validate_ui_content(tables)

    assert errors == []
    assert len(warnings) == 1, "unknown locale keys must not produce per-row noise"
    assert unknown in warnings[0]


def test_aggregate_warning_names_the_supported_locales_from_ui_locale():
    tables = [_table(title={"en": "Title", "zz": "Titel"})]

    _, warnings = validate_ui_content(tables)

    assert all(locale in warnings[0] for locale in SUPPORTED_UI_LOCALES)


# --- seed case 5: a real-shaped config passes --------------------------------


NETFLIX_SHAPED_TABLES = [
    {
        "id": "netflix_ratings",
        "extractor": "ratings_to_df",
        "title": {"en": "Your ratings", "nl": "Uw beoordelingen"},
        "description": {"en": "Titles you rated.", "nl": "Titels die u beoordeelde."},
        "headers": {
            "Title Name": {"en": "Title", "nl": "Titel"},
            "Thumbs Value": {"en": "Thumbs value", "nl": "Aantal duimpjes"},
            "Event Utc Ts": {"en": "Date", "nl": "Datum en tijd"},
        },
        "visualizations": [
            {
                "title": {"en": "Titles rated", "nl": "Beoordeelde titels"},
                "type": "wordcloud",
                "textColumn": "Title Name",
            }
        ],
        "documentation": {
            "summary": "One row per rated title.",
            "source_file": "Ratings.csv",
            "columns": {"Title Name": "Name of the rated title."},
        },
    },
    {
        "id": "netflix_viewing_activity",
        "extractor": "viewing_activity_to_df",
        "title": {"en": "What you watched", "nl": "Wat u heeft gekeken"},
        "description": {"en": "Titles you watched.", "nl": "Titels die u keek."},
        "headers": {
            "Start Time": {"en": "Start time", "nl": "Starttijd"},
            "Duration": {"en": "Hours watched", "nl": "Aantal uur gekeken"},
        },
        "extractor_kwargs": {"selected_user": ""},
    },
]


def test_netflix_shaped_config_passes_clean():
    errors, warnings = validate_ui_content(NETFLIX_SHAPED_TABLES)

    assert errors == []
    assert warnings == []


# --- R1: export languages are never inspected --------------------------------


def test_platform_info_languages_are_never_inspected():
    """``platform_info.languages`` is DDP *export* metadata, not UI locales."""
    raw = {
        "platform_info": {"name": "Synthetic", "languages": ["zz", "qq"]},
        "tables": NETFLIX_SHAPED_TABLES,
    }

    errors, warnings = validate_ui_content(raw["tables"])

    assert errors == []
    assert warnings == []


# --- coverage matrix ---------------------------------------------------------


def test_coverage_counts_present_and_empty_per_locale():
    tables = [
        _table(id="t0"),
        _table(id="t1", description={"en": "", "nl": "Iets"}),
    ]

    coverage = ui_content_coverage(tables)

    # 2 tables x (title + description + 2 headers) = 8 bundles.
    assert coverage["total"] == 8
    assert coverage["present"][DEFAULT_UI_LOCALE] == 7
    assert coverage["empty"][DEFAULT_UI_LOCALE] == 1
    assert coverage["present"]["nl"] == 8
    for locale in PROVISIONAL_UI_LOCALES:
        assert coverage["present"][locale] == 0


def test_coverage_reports_unknown_locale_keys_separately():
    coverage = ui_content_coverage([_table(title={"en": "Title", "zz": "Titel"})])

    assert coverage["unknown"] == {"zz": 1}
    assert "zz" not in coverage["present"]


# --- integration through validate() -----------------------------------------


def test_validate_runs_the_ui_content_checks_on_a_shipped_config():
    errors, warnings = validate("example")

    assert errors == []
    assert warnings == []


def test_validate_reports_ui_content_errors_for_a_broken_config(monkeypatch):
    broken = {
        "platform_info": {"name": "example"},
        "tables": [_table(headers={"col_a": "Column A"})],
    }
    monkeypatch.setattr(
        "port.helpers.port_config_validator.read_config",
        lambda platform: broken,
    )

    errors, _ = validate("example")

    assert any("col_a" in e for e in errors)


@pytest.mark.parametrize("locale", SUPPORTED_UI_LOCALES)
def test_every_supported_locale_appears_in_the_coverage_matrix(locale):
    coverage = ui_content_coverage(NETFLIX_SHAPED_TABLES)

    assert locale in coverage["present"]
    assert locale in coverage["empty"]


class TestTheDutchConfigStringsStayInformal:
    """The committed configs address a participant as ``je``, never ``u``.

    This tool is aimed at students exploring their own data, and the whole flow — the
    menu, the consent page, the framework's own chrome — speaks informally. One table
    description that switches to ``u`` reads as though it were written for someone else,
    and the mixture is more jarring than either register alone.

    Committed configs are what ships (ADR-0030), so they are what is checked; the
    extractor docstrings that seeded them are bootstrap metadata and are not.
    """

    #: A standalone formal pronoun. Bounded on both sides so it never fires inside a
    #: word — ``uit``, ``duur``, ``menu`` are all ordinary Dutch.
    FORMAL_PRONOUN = re.compile(r"(?<![\w'-])[Uu](?:w|zelf)?(?![\w'-])")

    def _nl_strings(self, node, path=""):
        """Every ``nl`` string in a config, with the path that leads to it."""
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "nl" and isinstance(value, str):
                    yield f"{path}/nl", value
                else:
                    yield from self._nl_strings(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from self._nl_strings(value, f"{path}[{index}]")

    @pytest.mark.parametrize("config_path", sorted(CONFIG_DIR.glob("*_config.json")), ids=lambda p: p.name)
    def test_no_config_addresses_the_participant_as_u(self, config_path):
        offenders = [
            f"{config_path.name}{path}: {text}"
            for path, text in self._nl_strings(json.loads(config_path.read_text(encoding="utf-8")))
            if self.FORMAL_PRONOUN.search(text)
        ]
        assert not offenders, "formal address in a Dutch config string:\n" + "\n".join(offenders)

    def test_the_pattern_catches_what_it_is_meant_to(self):
        assert self.FORMAL_PRONOUN.search("Wat u heeft gekeken")
        assert self.FORMAL_PRONOUN.search("Uw Netflix-account")
        assert self.FORMAL_PRONOUN.search("Bekijk het uzelf")

    def test_the_pattern_leaves_ordinary_dutch_alone(self):
        for ordinary in ("uit Ratings.csv", "de duur van je sessie", "het menu", "Jouw uren"):
            assert not self.FORMAL_PRONOUN.search(ordinary), ordinary
