"""Canary over real Instagram exports at tests/ddp/instagram_*.zip (skips if
absent): the json export and the html export of the same account. Each
registry extractor runs against both, so a table that only reads one format
is only asserted non-empty on that format's run.

The fixtures are named ``instagram_a_json_2026-08.zip`` and
``instagram_html_2026-08.zip`` rather than the plain ``instagram_<kind>_*.zip``
shape ``find_fixture`` assumes, so discovery here matches on a "json"/"html"
substring instead.

EXPECTED_EMPTY_JSON / EXPECTED_EMPTY_HTML list registry entries that
legitimately return an empty DataFrame for the 2026-08-29 test-account export
in that format, rather than weakening the non-empty assertion for the rest.
"""
from collections import Counter
from pathlib import Path

import pytest

import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms import instagram as I

DDP_DIR = Path(__file__).parent / "ddp"

# 2026-08-29 test-account export, json format (tests/ddp/instagram_a_json_2026-08.zip):
#   - profile_searches_to_df, threads_viewed_to_df: the corresponding source
#     files (profile_searches.json, threads_viewed.json) are absent from the
#     archive — this participant never used profile search or Threads.
#   - word_or_phrase_searches_to_df, ads_clicked_to_df: same source-file
#     absence (word_or_phrase_searches.json, ads_clicked.json) — this
#     participant has no recorded searches or ad clicks. Absent from the html
#     export too (see EXPECTED_EMPTY_HTML): this is the account's real
#     activity, not a format difference.
EXPECTED_EMPTY_JSON = {
    "profile_searches_to_df",
    "threads_viewed_to_df",
    "word_or_phrase_searches_to_df",
    "ads_clicked_to_df",
}

# Same export, html format (tests/ddp/instagram_html_2026-08.zip):
#   - followers_to_df: json-only extractor (no html page carries the follower
#     list) — always empty when run against an html reader.
#   - profile_searches_to_df, threads_viewed_to_df: json-only extractors (no
#     html variant implemented) — always empty when run against an html
#     reader, regardless of what the export contains.
#   - word_or_phrase_searches_to_df, ads_clicked_to_df: source page absent for
#     this participant, same as the json export (see EXPECTED_EMPTY_JSON).
#   - the eight Task 15b additions (account_info_to_df and onward): all
#     JSON-only (see the module note above account_info_to_df in
#     instagram.py) — always empty when run against an html reader, since
#     none of their source files have an html counterpart the algosoc-2026
#     module ever read.
EXPECTED_EMPTY_HTML = {
    "followers_to_df",
    "profile_searches_to_df",
    "threads_viewed_to_df",
    "word_or_phrase_searches_to_df",
    "ads_clicked_to_df",
    "account_info_to_df",
    "ad_targeting_categories_to_df",
    "link_history_to_df",
    "login_activity_to_df",
    "locations_of_interest_to_df",
    "off_meta_activity_to_df",
    "profile_based_in_to_df",
    "camera_info_to_df",
}

SPECS = list(I.EXTRACTOR_REGISTRY.items())


def _find_export(kind: str) -> Path | None:
    """First tests/ddp/instagram_*.zip whose name contains *kind* ("json" or
    "html")."""
    if not DDP_DIR.is_dir():
        return None
    matches = sorted(p for p in DDP_DIR.glob("instagram_*.zip") if kind in p.name)
    return matches[0] if matches else None


def _reader_and_validation(fixture: Path) -> tuple[ZipArchiveReader, validate.ValidateInput]:
    """Build a reader together with the validation result that names its DDP
    category. The html_en extractors dispatch on
    ``validation.current_ddp_category.ddp_filetype`` exactly as the real
    ``extraction()`` does, so passing that through here (rather than the bare
    reader ``make_reader`` builds) is what routes an html fixture to the
    html-reading branch of each extractor instead of silently falling through
    to the json branch and reading nothing."""
    errors: Counter = Counter()
    validation = validate.validate_zip(I.DDP_CATEGORIES, str(fixture))
    reader = ZipArchiveReader(str(fixture), validation.archive_members, errors)
    return reader, validation


@pytest.fixture(scope="module", params=["json", "html"])
def export_kind(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def reader_and_validation(export_kind):
    fixture = _find_export(export_kind)
    if fixture is None:
        pytest.skip(f"No instagram_*{export_kind}*.zip fixture in tests/ddp/")
    return _reader_and_validation(fixture)


@pytest.mark.parametrize("name,extractor", SPECS, ids=[n for n, _ in SPECS])
def test_extractor_not_empty(name, extractor, export_kind, reader_and_validation):
    expected_empty = EXPECTED_EMPTY_JSON if export_kind == "json" else EXPECTED_EMPTY_HTML
    if name in expected_empty:
        pytest.skip(f"{name} is expected empty for the {export_kind} export — see EXPECTED_EMPTY_{export_kind.upper()}")

    reader, validation = reader_and_validation
    errors: Counter = Counter()
    df = extractor(reader, errors, validation=validation)
    assert not df.empty
