"""Canary over real Facebook exports at tests/ddp/facebook_*.zip (skips a
pair if absent): two account pairs, each a json export and an html export of
the same account. Every registry extractor runs against all four fixtures,
so a table that only reads one format is only asserted non-empty on that
format's run, and a table whose source files are absent from one account is
only asserted non-empty on the account that has them.

Fixture pairs (both symlinks under tests/ddp/, real exports — ADR-0014, never
edited to add names/numbers/e-mails; this file lists only ids and counts):

- "2026-08": the assistant's small test-account export,
  ``facebook_a_json_2026-08.zip`` / ``facebook_html_2026-08.zip`` — the
  ``a_`` infix on the json one is needed because "html" sorts before "json"
  and a plain substring match would otherwise be ambiguous between the two
  fixtures of this pair.
- "alltime": Danielle's own all-time export,
  ``facebook_self_json_alltime.zip`` / ``facebook_self_html_alltime.zip`` —
  built for Task 15d (story edu-curation) specifically because it is the one
  export of the two that carries the contact and friend-suggestion files
  (``contacts_uploaded_before_2021``, ``your_imported_contacts``,
  ``contacts_uploaded_from_your_phone``, ``suggested_friends``,
  ``friends_you_see_less``, ``your_friends``) — real, populated, and about
  800MB each, so members are read streaming through ``ZipArchiveReader``,
  never the whole archive.

EXPECTED_EMPTY[(account, kind)] lists registry entries that legitimately
return an empty DataFrame for that account/format combination, rather than
weakening the non-empty assertion for the rest.
"""
from collections import Counter
from pathlib import Path

import pytest

import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms import facebook as F

DDP_DIR = Path(__file__).parent / "ddp"

# Fixture filenames per account pair, exact (not globbed) so a fixture never
# accidentally resolves to the other account's file.
FIXTURES: dict[str, dict[str, str]] = {
    "2026-08": {
        "json": "facebook_a_json_2026-08.zip",
        "html": "facebook_html_2026-08.zip",
    },
    "alltime": {
        "json": "facebook_self_json_alltime.zip",
        "html": "facebook_self_html_alltime.zip",
    },
}

# 2026-08 test-account export, json format:
#   - your_events_to_df, your_contributions_to_df: the account has no events
#     and no group contributions recorded in this export.
#   - advertisers_youve_interacted_with_to_df, your_activity_off_meta_to_df:
#     source files absent from this export's categories — present in the html
#     export of the same account (see ("2026-08", "html")), so this is a
#     format/category difference, not an extractor defect.
#   - facebook_uploaded_contacts_to_df, suggested_friends_to_df,
#     friends_you_see_less_to_df, your_friends_to_df: this account's export
#     carries none of the six contact/friend-suggestion source files these
#     read (only people_you_may_know.json is present) — a real absence on
#     this small test account, not a defect (see ("alltime", *), where the
#     same tables are populated).
_EMPTY_2026_08_COMMON = {
    "your_events_to_df",
    "your_contributions_to_df",
    "facebook_uploaded_contacts_to_df",
    "suggested_friends_to_df",
    "friends_you_see_less_to_df",
    "your_friends_to_df",
}

# alltime export (Danielle's own account), both formats:
#   - advertisers_youve_interacted_with_to_df: source file absent from both
#     categories of this export — this account has no recorded ad
#     interactions in either format (unlike the 2026-08 account, where it is
#     present on html only).
_EMPTY_ALLTIME_COMMON = {
    "advertisers_youve_interacted_with_to_df",
}

EXPECTED_EMPTY: dict[tuple[str, str], set[str]] = {
    ("2026-08", "json"): _EMPTY_2026_08_COMMON | {
        "advertisers_youve_interacted_with_to_df",
        "your_activity_off_meta_to_df",
    },
    ("2026-08", "html"): _EMPTY_2026_08_COMMON,
    ("alltime", "json"): _EMPTY_ALLTIME_COMMON,
    # your_friends_to_df is json-only (no html page for it exists at all —
    # ADR-0024); always empty against an html reader, on either account.
    ("alltime", "html"): _EMPTY_ALLTIME_COMMON | {"your_friends_to_df"},
}

SPECS = list(F.EXTRACTOR_REGISTRY.items())
ACCOUNTS = list(FIXTURES)
KINDS = ["json", "html"]


def _fixture_path(account: str, kind: str) -> Path:
    return DDP_DIR / FIXTURES[account][kind]


def _reader_and_validation(fixture: Path) -> tuple[ZipArchiveReader, validate.ValidateInput]:
    """Build a reader together with the validation result that names its DDP
    category, exactly as the real ``extraction()`` does — the html
    extractors dispatch on ``validation.current_ddp_category.ddp_filetype``."""
    errors: Counter = Counter()
    validation = validate.validate_zip(F.DDP_CATEGORIES, str(fixture))
    reader = ZipArchiveReader(str(fixture), validation.archive_members, errors)
    return reader, validation


@pytest.fixture(scope="module", params=ACCOUNTS)
def account(request) -> str:
    return request.param


@pytest.fixture(scope="module", params=KINDS)
def export_kind(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def reader_and_validation(account, export_kind):
    fixture = _fixture_path(account, export_kind)
    if not fixture.is_file():
        pytest.skip(f"No {fixture.name} fixture in tests/ddp/")
    return _reader_and_validation(fixture)


@pytest.mark.parametrize("name,extractor", SPECS, ids=[n for n, _ in SPECS])
def test_extractor_not_empty(name, extractor, account, export_kind, reader_and_validation):
    expected_empty = EXPECTED_EMPTY[(account, export_kind)]
    if name in expected_empty:
        pytest.skip(f"{name} is expected empty for the {account}/{export_kind} export — see EXPECTED_EMPTY")

    reader, validation = reader_and_validation
    errors: Counter = Counter()
    df = extractor(reader, errors, validation=validation)
    assert not df.empty
    assert sum(errors.values()) == 0
