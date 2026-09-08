"""Canary over real Facebook exports at tests/ddp/facebook_*.zip (skips if
absent): the json export and the html export of the same account. Each of
the 21 registry extractors runs against both, so a table that only reads one
format is only asserted non-empty on that format's run.

The fixtures are named ``facebook_a_json_2026-08.zip`` and
``facebook_html_2026-08.zip`` — the ``a_`` infix on the json one is needed
because "html" sorts before "json" and ``find_fixture`` (a plain
``facebook_*.zip`` glob) would otherwise pick the html export for both —
rather than the plain ``facebook_<kind>_*.zip`` shape ``find_fixture``
assumes, so discovery here matches on a "json"/"html" substring instead,
mirroring ``test_extractor_integration_instagram.py``.

EXPECTED_EMPTY_JSON / EXPECTED_EMPTY_HTML list registry entries that
legitimately return an empty DataFrame for the 2026-08-29 test-account export
in that format, rather than weakening the non-empty assertion for the rest.
"""
from collections import Counter
from pathlib import Path

import pytest

import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms import facebook as F

DDP_DIR = Path(__file__).parent / "ddp"

# 2026-08-29 test-account export, json format (tests/ddp/facebook_a_json_2026-08.zip):
#   - your_events_to_df, your_contributions_to_df: the account has no events
#     and no group contributions recorded in this export.
#   - advertisers_youve_interacted_with_to_df, your_activity_off_meta_to_df:
#     source files absent from this export's categories — present in the html
#     export of the same account (see EXPECTED_EMPTY_HTML), so this is a
#     format/category difference, not an extractor defect.
EXPECTED_EMPTY_JSON = {
    "your_events_to_df",
    "your_contributions_to_df",
    "advertisers_youve_interacted_with_to_df",
    "your_activity_off_meta_to_df",
}

# Same export, html format (tests/ddp/facebook_html_2026-08.zip):
#   - your_events_to_df, your_contributions_to_df: same real absence as the
#     json export (see EXPECTED_EMPTY_JSON) — this account has none, in
#     either format.
EXPECTED_EMPTY_HTML = {
    "your_events_to_df",
    "your_contributions_to_df",
}

SPECS = list(F.EXTRACTOR_REGISTRY.items())


def _find_export(kind: str) -> Path | None:
    """First tests/ddp/facebook_*.zip whose name contains *kind* ("json" or
    "html")."""
    if not DDP_DIR.is_dir():
        return None
    matches = sorted(p for p in DDP_DIR.glob("facebook_*.zip") if kind in p.name)
    return matches[0] if matches else None


def _reader_and_validation(fixture: Path) -> tuple[ZipArchiveReader, validate.ValidateInput]:
    """Build a reader together with the validation result that names its DDP
    category, exactly as the real ``extraction()`` does — the html
    extractors dispatch on ``validation.current_ddp_category.ddp_filetype``."""
    errors: Counter = Counter()
    validation = validate.validate_zip(F.DDP_CATEGORIES, str(fixture))
    reader = ZipArchiveReader(str(fixture), validation.archive_members, errors)
    return reader, validation


@pytest.fixture(scope="module", params=["json", "html"])
def export_kind(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def reader_and_validation(export_kind):
    fixture = _find_export(export_kind)
    if fixture is None:
        pytest.skip(f"No facebook_*{export_kind}*.zip fixture in tests/ddp/")
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
