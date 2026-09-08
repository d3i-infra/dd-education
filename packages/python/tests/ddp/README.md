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
directory are symlinks to them, never copies. Real filenames and which
account or participant each export belongs to are recorded in
`~/data/d3i/data_collection/README.md` (untracked, lives only on Danielle's
machine) — not reproduced here, per ADR-0014:

| Fixture (symlink)                 | Platform / format                          | Export date |
|------------------------------------|---------------------------------------------|-------------|
| `chatgpt_2026-08.zip`               | ChatGPT export                               | 2026-08-25 |
| `netflix_2026-03.zip`               | Netflix export (test account)                | 2026-03 |
| `linkedin_basic_2026-09.zip`        | LinkedIn "basic" export                      | 2026-09-07 |
| `whatsapp_nl_android_2026-09.zip`   | WhatsApp group-chat export, Dutch-locale Android | 2026-09 |
| `instagram_a_json_2026-08.zip`      | Instagram export, JSON format (test-account)  | 2026-08-29 |
| `instagram_html_2026-08.zip`        | Instagram export, HTML format (same test-account export) | 2026-08-29 |
| `facebook_a_json_2026-08.zip`       | Facebook export, JSON format (test-account)   | 2026-08-29 |
| `facebook_html_2026-08.zip`         | Facebook export, HTML format (same test-account export) | 2026-08-29 |
| `facebook_self_json_alltime.zip`    | Facebook export, JSON format, Danielle's own all-time account (contacts and friend-suggestion files) | 2026-09-02 |
| `facebook_self_html_alltime.zip`    | Facebook export, HTML format (same all-time account export) | 2026-09-02 |
| `youtube_html_2026-08.zip`          | YouTube Takeout export, HTML format           | 2026-08 |

The Instagram JSON fixture is named `instagram_a_json_2026-08.zip` (not
`instagram_json_2026-08.zip`) so that, sorted alongside
`instagram_html_2026-08.zip`, the JSON export is the one `find_fixture`
returns (`a_json` < `html` lexicographically) — the JSON canary
(`test_extractor_integration_instagram.py`) is written against the JSON
shape, and the HTML export is for a future canary (Task 10) to pick up
separately.

The Facebook JSON fixture is named `facebook_a_json_2026-08.zip` for the
same reason: `html` sorts before `json`, so without the `a_` infix
`find_fixture("facebook")` would return the HTML export instead.
`test_extractor_integration_facebook.py` matches on exact filenames per
account pair rather than relying on `find_fixture`, so both formats of both
accounts are exercised.

`facebook_self_{json,html}_alltime.zip` is Danielle's own all-time export
(Task 15d, story edu-curation) — the small test-account export above never
uploaded a phone contact list or received friend suggestions, so it carries
none of the contact/friend-suggestion source files that task's tables read
(`contacts_uploaded_before_2021`, `your_imported_contacts`,
`contacts_uploaded_from_your_phone`, `suggested_friends`,
`friends_you_see_less`, `your_friends`); the all-time export does.

## Re-creating the symlinks

Source paths below use glob patterns rather than literal filenames, since
some real filenames embed the account handle or a family member's name
(ADR-0014); check `~/data/d3i/data_collection/README.md` if a glob needs
tightening because a new file collides with it. `$D` is the source
directory to adjust if your export layout differs:

```bash
D=~/data/d3i/data_collection; T=packages/python/tests/ddp
ln -s "$HOME/Downloads/Telegram Desktop/netflix_test.zip"  "$T/netflix_2026-03.zip"
ln -s "$D"/linkedin/Basic_LinkedInDataExport_*.zip          "$T/linkedin_basic_2026-09.zip"
ln -s "$D"/whatsapp/*.zip                                   "$T/whatsapp_nl_android_2026-09.zip"
ln -s "$D"/instagram/*-ZQvZXHLb.zip                         "$T/instagram_a_json_2026-08.zip"
ln -s "$D"/instagram/*-m6ADNs3V.zip                         "$T/instagram_html_2026-08.zip"
ln -s "$D"/facebook/*-CvOb8P1q.zip                          "$T/facebook_a_json_2026-08.zip"
ln -s "$D"/facebook/*-ixwaNMDM.zip                          "$T/facebook_html_2026-08.zip"
ln -s "$D/youtube/Takeout-2.zip"                            "$T/youtube_html_2026-08.zip"
ln -s ~/data/d3i/self/chatgpt/*.zip                         "$T/chatgpt_2026-08.zip"
ln -s ~/data/d3i/self/facebook/*-6zxl8WMW.zip               "$T/facebook_self_json_alltime.zip"
ln -s ~/data/d3i/self/facebook/*-gpgIKVJQ.zip               "$T/facebook_self_html_alltime.zip"
```
