# `tests/ddp/` — real DDP fixtures (git-ignored)

Per ADR-0014, real participant data export ("DDP") zips never enter version
control. `tests/ddp/*` is git-ignored (see `.gitignore`), except this file
and `.gitkeep`, so the directory itself is tracked while its contents are
not.

Integration canaries (`tests/test_extractor_integration_*.py`) look for
fixtures here via `extractor_integration_helpers.find_fixture(platform)`,
which returns the first `<platform>_*.zip` match, sorted by name, or `None`
if the directory is empty — every canary skips cleanly when its fixture is
absent, so a checkout with no `tests/ddp/` contents (e.g. CI) runs clean.

## Naming convention

```
<platform>_<anything>.zip
```

`find_fixture("instagram")` returns the first match by sorted filename, so
when more than one fixture for a platform is present, name the one you want
picked up first so it sorts first (see the Instagram entry below).

## Fixtures used by this repo's canaries (symlinks to real exports)

These are personal, real exports living outside the repo; the files in this
directory are symlinks to them, never copies:

| Fixture (symlink)                       | Target                                                             |
|------------------------------------------|--------------------------------------------------------------------|
| `chatgpt_2026-08.zip`                     | `~/data/d3i/self/chatgpt/*.zip`                                    |
| `netflix_2026-03.zip`                     | `~/Downloads/Telegram Desktop/netflix_test.zip`                    |
| `linkedin_basic_2026-09.zip`              | `~/data/d3i/data_collection/linkedin/Basic_LinkedInDataExport_09-07-2026.zip` |
| `whatsapp_nl_android_2026-09.zip`         | `~/data/d3i/data_collection/whatsapp/WhatsApp-chat met Family McCool.zip` |
| `instagram_a_json_2026-08.zip`            | `~/data/d3i/data_collection/instagram/instagram-maria8200143-2026-08-29-ZQvZXHLb.zip` |
| `instagram_html_2026-08.zip`              | `~/data/d3i/data_collection/instagram/instagram-maria8200143-2026-08-29-m6ADNs3V.zip` |
| `youtube_html_2026-08.zip`                | `~/data/d3i/data_collection/youtube/Takeout-2.zip`                 |

The Instagram JSON fixture is named `instagram_a_json_2026-08.zip` (not
`instagram_json_2026-08.zip`) so that, sorted alongside
`instagram_html_2026-08.zip`, the JSON export is the one `find_fixture`
returns (`a_json` < `html` lexicographically) — the JSON canary
(`test_extractor_integration_instagram.py`) is written against the JSON
shape, and the HTML export is for a future canary (Task 10) to pick up
separately.

Re-create the symlinks after a fresh checkout with:

```bash
D=~/data/d3i/data_collection; T=packages/python/tests/ddp
ln -s "$HOME/Downloads/Telegram Desktop/netflix_test.zip"          "$T/netflix_2026-03.zip"
ln -s "$D/linkedin/Basic_LinkedInDataExport_09-07-2026.zip"         "$T/linkedin_basic_2026-09.zip"
ln -s "$D/whatsapp/WhatsApp-chat met Family McCool.zip"             "$T/whatsapp_nl_android_2026-09.zip"
ln -s "$D/instagram/instagram-maria8200143-2026-08-29-ZQvZXHLb.zip" "$T/instagram_a_json_2026-08.zip"
ln -s "$D/instagram/instagram-maria8200143-2026-08-29-m6ADNs3V.zip" "$T/instagram_html_2026-08.zip"
ln -s "$D/youtube/Takeout-2.zip"                                    "$T/youtube_html_2026-08.zip"
ln -s ~/data/d3i/self/chatgpt/*.zip                                 "$T/chatgpt_2026-08.zip"
```
