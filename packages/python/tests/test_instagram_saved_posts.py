"""Regression test: `saved_posts_to_df` must not silently drop Caption/URL for
an older-schema donor.

The ported (algosoc) `_saved_posts_json` only read the newer `label_values`
schema. Upstream also handled an older schema — a bare `item["title"]` plus
either `string_list_data` (a one-entry list carrying `href`/`timestamp`) or
`string_map_data` (keyed by a "Saved on"/"Opgeslagen op" entry) — see `git
show 0c4412a:packages/python/port/platforms/instagram.py`. Without that
fallback, an older-schema item still produced a row (no exception), but with
blank Caption/URL/Username and the literal "Geen hashtags" placeholder: rows
present, data silently gone.

Builds a `ZipArchiveReader` directly over an in-memory zip the way
`test_zip_archive_reader.py` does (rather than routing through
`extractor_integration_helpers.make_reader`, which additionally needs a full
`DDPCategory` validation pass this test has no reason to exercise) — same
reader class, same error-counting behaviour, `saved_posts.json` placed at the
nested path a real export uses so `resolve_member`'s suffix match is what
finds it, not an exact top-level match.
"""
import io
import json
import zipfile
from collections import Counter

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms.instagram import saved_posts_to_df

SAVED_POSTS_PATH = "instagram-testaccount-2026-01-01/your_instagram_activity/saved/saved_posts.json"


def _reader_for(saved_posts: list[dict]) -> ZipArchiveReader:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(SAVED_POSTS_PATH, json.dumps(saved_posts))
    buf.seek(0)
    return ZipArchiveReader(buf, [SAVED_POSTS_PATH], Counter())


class TestBothSchemasYieldACaptionAndUrl:
    def test_newer_label_values_schema(self):
        """The schema algosoc's port already handled."""
        item = {
            "timestamp": 1700000000,
            "label_values": [
                {"label": "URL", "value": "https://example.com/p/newschema/"},
                {"label": "Caption", "value": "a caption from the newer schema"},
                {"label": "Title", "value": ""},
            ],
        }

        out = saved_posts_to_df(_reader_for([item]), Counter())

        assert len(out) == 1
        row = out.iloc[0]
        assert row["Caption"] == "a caption from the newer schema"
        assert row["URL"] == "https://example.com/p/newschema/"

    def test_older_string_list_data_schema(self):
        """The schema this fix restores: title + string_list_data."""
        item = {
            "title": "a caption from the older schema",
            "string_list_data": [
                {"href": "https://example.com/p/oldschema/", "timestamp": 1690000000},
            ],
        }

        out = saved_posts_to_df(_reader_for([item]), Counter())

        assert len(out) == 1
        row = out.iloc[0]
        assert row["Caption"] == "a caption from the older schema"
        assert row["URL"] == "https://example.com/p/oldschema/"

    def test_older_string_map_data_schema(self):
        """The other older-schema shape: title + string_map_data keyed by
        "Saved on" (the Dutch export uses "Opgeslagen op" instead)."""
        item = {
            "title": "a caption from the older map-data schema",
            "string_map_data": {
                "Saved on": {"href": "https://example.com/p/oldmapschema/", "timestamp": 1680000000},
            },
        }

        out = saved_posts_to_df(_reader_for([item]), Counter())

        assert len(out) == 1
        row = out.iloc[0]
        assert row["Caption"] == "a caption from the older map-data schema"
        assert row["URL"] == "https://example.com/p/oldmapschema/"

    def test_mixed_schemas_in_one_export_both_yield_captions_and_urls(self):
        """A per-item schema check, not a per-file one: a real donor's export
        will not usually mix vintages, but the detection must be per item
        rather than assumed from the first entry."""
        newer = {
            "timestamp": 1700000000,
            "label_values": [
                {"label": "URL", "value": "https://example.com/p/mixed-new/"},
                {"label": "Caption", "value": "mixed export, newer item"},
            ],
        }
        older = {
            "title": "mixed export, older item",
            "string_list_data": [
                {"href": "https://example.com/p/mixed-old/", "timestamp": 1690000000},
            ],
        }

        out = saved_posts_to_df(_reader_for([newer, older]), Counter())

        assert len(out) == 2
        captions = set(out["Caption"])
        urls = set(out["URL"])
        assert captions == {"mixed export, newer item", "mixed export, older item"}
        assert urls == {"https://example.com/p/mixed-new/", "https://example.com/p/mixed-old/"}
        # The older schema carries no username or hashtags — confirming those
        # stay blank/placeholder rather than being invented.
        older_row = out[out["Caption"] == "mixed export, older item"].iloc[0]
        assert older_row["Username"] == ""
        assert older_row["Hashtags"] == "Geen hashtags"
