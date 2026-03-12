# Dual-View Extraction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add package-explorer + researcher-view dual consent screens to YouTube, Netflix, and new LinkedIn scripts in dd-education.

**Architecture:** Each platform script shows two sequential consent screens: (1) comprehensive `extraction()` tables first, then (2) aggregate-only `extraction_researcher()` tables. ChatGPT and Instagram already follow this pattern. LinkedIn is ported from dd-vu-2026 and extended with a researcher view. No framework files are touched.

**Tech Stack:** Python 3.10+, pandas, Pyodide (browser runtime). All scripts run in-browser via `py_worker.js`. The UI props API is at `port/api/props.py`. Zip utilities at `port/unzipddp.py`.

---

## Worktree Setup

Before starting, create an isolated branch:

```bash
cd /home/dmm/src/d3i/forks/daniellemccool/dd-education
git checkout -b feat/dual-view-extraction
```

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/framework/processing/py/port/youtube.py` | Modify | Add `extraction_researcher()`, update `script()`, add text constants |
| `src/framework/processing/py/port/netflix.py` | Modify | Fix `validate_zip` bug, add `extraction_researcher()`, update `script()`, add text constants |
| `src/framework/processing/py/port/linkedin.py` | Create | Full LinkedIn platform: validate, extraction, extraction_researcher, script |
| `src/framework/processing/py/port/script.py` | Modify | Fix id=5 collision, add LinkedIn import + menu item + dispatch |

No changes to: `chatgpt.py`, `instagram.py`, `whatsapp.py`, `extraction_helpers.py`, `unzipddp.py`, `port_helpers.py`, or any framework files.

---

## Chunk 1: Baseline + YouTube Researcher View

### Task 1: Verify baseline compiles

**Files:**
- Check: all `.py` files under `src/framework/processing/py/port/`

- [ ] **Step 1: Run py_compile on all existing scripts**

```bash
cd /home/dmm/src/d3i/forks/daniellemccool/dd-education
python -m py_compile \
  src/framework/processing/py/port/script.py \
  src/framework/processing/py/port/chatgpt.py \
  src/framework/processing/py/port/youtube.py \
  src/framework/processing/py/port/netflix.py \
  src/framework/processing/py/port/instagram.py \
  src/framework/processing/py/port/whatsapp.py \
  src/framework/processing/py/port/general_ddp_analyzer.py \
  src/framework/processing/py/port/extraction_helpers.py \
  src/framework/processing/py/port/unzipddp.py \
  src/framework/processing/py/port/validate.py \
  src/framework/processing/py/port/port_helpers.py && echo "ALL OK"
```

Expected: `ALL OK` (no output before it means no syntax errors)

---

### Task 2: Add `extraction_researcher` to `youtube.py`

**Files:**
- Modify: `src/framework/processing/py/port/youtube.py`

The existing `extraction()` function in `youtube.py` takes `(youtube_zip: str, validation: ValidateInput)` and returns a list of `PropsUIPromptConsentFormTable`. The researcher view calls `watch_history_to_df(youtube_zip, validation)` (which already exists in the file) to get a DataFrame with columns including `"Date standard format"` (ISO8601 string) and `"Channel"` (string, may be None).

- [ ] **Step 1: Add two new text constants after `CONSENT_FORM_DESCRIPTION_ALL`**

In `youtube.py`, locate the block of text constants (around line 572–605) and add after `CONSENT_FORM_DESCRIPTION_ALL`:

```python
RESEARCHER_VIEW_HEADER = props.Translatable({
    "en": "Your YouTube data — researcher view",
    "nl": "Uw YouTube gegevens — onderzoekersweergave",
})

RESEARCHER_DESCRIPTION = props.Translatable({
    "en": "This view shows only aggregate statistics — the kind of data a researcher would collect in a real data donation study. No individual videos, URLs, or search queries are shown.",
    "nl": "Deze weergave toont alleen geaggregeerde statistieken — het soort gegevens dat een onderzoeker zou verzamelen in een echte datadoneringsstudie. Er worden geen individuele video's, URL's of zoektermen getoond.",
})
```

- [ ] **Step 2: Add `extraction_researcher` function**

Add the following function to `youtube.py` immediately after the existing `extraction()` function (around line 569):

```python
def extraction_researcher(youtube_zip: str, validation: ValidateInput) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Researcher view: aggregate-only tables derived from watch history.
    No individual video titles, URLs, or search terms — only counts per
    time bucket and channel frequency, suitable for a real donation study.
    """
    tables_to_render = []

    df = watch_history_to_df(youtube_zip, validation)
    if df.empty:
        return tables_to_render

    # Table 1: videos watched per month
    try:
        df_month = (
            df[df["Date standard format"].str.len() >= 7]
            .assign(Month=df["Date standard format"].str[:7])
            .groupby("Month")
            .size()
            .reset_index(name="Count")
        )
        if not df_month.empty:
            table_title = props.Translatable({
                "en": "Videos watched per month",
                "nl": "Video's bekeken per maand",
            })
            table_description = props.Translatable({
                "en": "Number of YouTube videos watched each month.",
                "nl": "Aantal YouTube-video's bekeken per maand.",
            })
            chart = {
                "title": {"en": "Videos watched per month", "nl": "Video's bekeken per maand"},
                "type": "area",
                "group": {"column": "Month"},
                "values": [{"column": "Count", "label": {"en": "Videos", "nl": "Video's"}}],
            }
            table = props.PropsUIPromptConsentFormTable(
                "youtube_researcher_monthly", table_title, df_month, table_description, [chart]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher monthly error: %s", e)

    # Table 2: most-watched channels (wordcloud)
    try:
        df_channels = df[["Channel"]].dropna()
        if not df_channels.empty:
            table_title = props.Translatable({
                "en": "Most watched channels",
                "nl": "Meest bekeken kanalen",
            })
            table_description = props.Translatable({
                "en": "Frequency of YouTube channels watched.",
                "nl": "Hoe vaak YouTube-kanalen zijn bekeken.",
            })
            wordcloud = {
                "title": {"en": "Most watched channels", "nl": "Meest bekeken kanalen"},
                "type": "wordcloud",
                "textColumn": "Channel",
                "tokenize": False,
            }
            table = props.PropsUIPromptConsentFormTable(
                "youtube_researcher_channels", table_title, df_channels, table_description, [wordcloud]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher channels error: %s", e)

    # Table 3: videos watched by hour of day
    try:
        df_hour = (
            df[df["Date standard format"].str.len() >= 13]
            .assign(Hour=df["Date standard format"].str[11:13])
            .groupby("Hour")
            .size()
            .reset_index(name="Count")
        )
        if not df_hour.empty:
            table_title = props.Translatable({
                "en": "Videos watched by hour of day",
                "nl": "Video's bekeken per uur van de dag",
            })
            table_description = props.Translatable({
                "en": "Number of YouTube videos watched at each hour of the day.",
                "nl": "Aantal YouTube-video's bekeken per uur van de dag.",
            })
            chart = {
                "title": {"en": "Videos by hour of day", "nl": "Video's per uur van de dag"},
                "type": "bar",
                "group": {"column": "Hour"},
                "values": [{"column": "Count", "label": {"en": "Videos", "nl": "Video's"}}],
            }
            table = props.PropsUIPromptConsentFormTable(
                "youtube_researcher_hourly", table_title, df_hour, table_description, [chart]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher hourly error: %s", e)

    return tables_to_render
```

- [ ] **Step 3: Update `script()` in `youtube.py` to dual-flow**

Locate the `script()` function in `youtube.py`. Currently it has:

```python
def script():
    platform_name = "YouTube"
    table_list = None
    while True:
```

Replace the function body so that after successful validation it computes both table lists, and renders them sequentially. The retry/skip logic is unchanged. Find the block:

```python
            # Happy flow: Valid DDP
            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                extraction_result = extraction(file_result.value, validation)
                table_list = extraction_result
                break
```

Replace with:

```python
            # Happy flow: Valid DDP
            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                table_list = extraction(file_result.value, validation)
                table_list_researcher = extraction_researcher(file_result.value, validation)
                break
```

Also add `table_list_researcher = None` at the top of `script()` alongside `table_list = None`:

```python
    table_list = None
    table_list_researcher = None
```

Then find the rendering block at the bottom of `script()`:

```python
    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
```

Replace with:

```python
    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    if table_list_researcher is not None:
        logger.info("Prompt researcher consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list_researcher, RESEARCHER_DESCRIPTION)
        result = yield ph.render_page(RESEARCHER_VIEW_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
```

- [ ] **Step 4: Verify youtube.py compiles**

```bash
python -m py_compile src/framework/processing/py/port/youtube.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/framework/processing/py/port/youtube.py
git commit -m "feat: add YouTube researcher view (aggregate-only charts)"
```

---

## Chunk 2: Netflix Researcher View + Bug Fix

### Task 3: Fix `validate_zip` bug and add `extraction_researcher` to `netflix.py`

**Files:**
- Modify: `src/framework/processing/py/port/netflix.py`

Netflix has a latent bug: `STATUS_CODES` defines ids 0 and 1, but `validate_zip()` calls `set_status_code_by_id(3)` on `BadZipFile`, which raises at runtime. Fix this while touching the file.

- [ ] **Step 1: Fix the `validate_zip` bug**

In `netflix.py`, locate `validate_zip()`. Find:

```python
    except zipfile.BadZipFile:
        validation.set_status_code_by_id(3)
```

Replace with:

```python
    except zipfile.BadZipFile:
        validation.set_status_code_by_id(1)
```

- [ ] **Step 2: Verify the fix compiles**

```bash
python -m py_compile src/framework/processing/py/port/netflix.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Add two new text constants to `netflix.py`**

Locate the text constants block (around `CONSENT_FORM_DESCRIPTION`). Add after it:

```python
RESEARCHER_VIEW_HEADER = props.Translatable({
    "en": "Your Netflix data — researcher view",
    "nl": "Uw Netflix gegevens — onderzoekersweergave",
})

RESEARCHER_DESCRIPTION = props.Translatable({
    "en": "This view shows only aggregate statistics — the kind of data a researcher would collect in a real data donation study. No individual titles, devices, or search queries are shown.",
    "nl": "Deze weergave toont alleen geaggregeerde statistieken — het soort gegevens dat een onderzoeker zou verzamelen in een echte datadoneringsstudie.",
})
```

- [ ] **Step 4: Add `extraction_researcher` function to `netflix.py`**

Add the following function immediately after the existing `extraction()` function:

```python
def extraction_researcher(netflix_zip: str, selected_user: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Researcher view: aggregate-only tables derived from viewing activity.
    No individual titles or devices — only hours per month, viewing by hour,
    and title frequency wordcloud.
    """
    tables_to_render = []

    df = viewing_activity_to_df(netflix_zip, selected_user)
    # After viewing_activity_to_df(), columns are:
    #   "Start tijd" (datetime string), "Titel" (str),
    #   "Apparaat" (str), "Aantal uur gekeken" (float)
    if df.empty:
        return tables_to_render

    # Table 1: hours watched per month
    try:
        df_month = (
            df[df["Start tijd"].str.len() >= 7]
            .assign(Month=df["Start tijd"].str[:7])
            .groupby("Month")["Aantal uur gekeken"]
            .sum()
            .reset_index()
            .rename(columns={"Aantal uur gekeken": "Hours watched"})
        )
        if not df_month.empty:
            table_title = props.Translatable({
                "en": "Hours watched per month",
                "nl": "Uren gekeken per maand",
            })
            table_description = props.Translatable({
                "en": "Total hours of Netflix content watched each month.",
                "nl": "Totaal aantal uren Netflix-content bekeken per maand.",
            })
            chart = {
                "title": {"en": "Hours watched per month", "nl": "Uren gekeken per maand"},
                "type": "area",
                "group": {"column": "Month"},
                "values": [{"column": "Hours watched", "label": {"en": "Hours", "nl": "Uren"}}],
            }
            table = props.PropsUIPromptConsentFormTable(
                "netflix_researcher_monthly", table_title, df_month, table_description, [chart]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher monthly error: %s", e)

    # Table 2: viewing by hour of day
    try:
        df_hour = (
            df[df["Start tijd"].str.len() >= 13]
            .assign(Hour=df["Start tijd"].str[11:13])
            .groupby("Hour")
            .size()
            .reset_index(name="Count")
        )
        if not df_hour.empty:
            table_title = props.Translatable({
                "en": "Viewing by hour of day",
                "nl": "Kijken per uur van de dag",
            })
            table_description = props.Translatable({
                "en": "Number of Netflix viewing sessions started at each hour of the day.",
                "nl": "Aantal Netflix-kijksessies gestart per uur van de dag.",
            })
            chart = {
                "title": {"en": "Viewing by hour of day", "nl": "Kijken per uur van de dag"},
                "type": "bar",
                "group": {"column": "Hour"},
                "values": [{"column": "Count", "label": {"en": "Sessions", "nl": "Sessies"}}],
            }
            table = props.PropsUIPromptConsentFormTable(
                "netflix_researcher_hourly", table_title, df_hour, table_description, [chart]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher hourly error: %s", e)

    # Table 3: most watched titles (wordcloud)
    try:
        df_titles = df[["Titel"]].dropna()
        if not df_titles.empty:
            table_title = props.Translatable({
                "en": "Most watched titles",
                "nl": "Meest bekeken titels",
            })
            table_description = props.Translatable({
                "en": "Frequency of Netflix titles watched.",
                "nl": "Hoe vaak Netflix-titels zijn bekeken.",
            })
            wordcloud = {
                "title": {"en": "Most watched titles", "nl": "Meest bekeken titels"},
                "type": "wordcloud",
                "textColumn": "Titel",
                "tokenize": False,
            }
            table = props.PropsUIPromptConsentFormTable(
                "netflix_researcher_titles", table_title, df_titles, table_description, [wordcloud]
            )
            tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher titles error: %s", e)

    return tables_to_render
```

- [ ] **Step 5: Update `script()` in `netflix.py` to dual-flow**

In `netflix.py`, locate `script()`. Add `table_list_researcher = None` alongside `table_list = None` at the top of the function:

```python
    table_list = None
    table_list_researcher = None
```

Find and replace the two extraction call sites individually (they have different indentation depths — do them one at a time).

**Site A** — inside `if len(users) == 1:` (20-space indentation). Replace:

```python
                    selected_user = users[0]
                    extraction_result = extraction(file_result.value, selected_user)
                    table_list = extraction_result
```

With:

```python
                    selected_user = users[0]
                    table_list = extraction(file_result.value, selected_user)
                    table_list_researcher = extraction_researcher(file_result.value, selected_user)
```

**Site B** — inside `elif len(users) > 1: ... if selection.__type__ == "PayloadString":` (24-space indentation). Replace:

```python
                        selected_user = selection.value
                        extraction_result = extraction(file_result.value, selected_user)
                        table_list = extraction_result
```

With:

```python
                        selected_user = selection.value
                        table_list = extraction(file_result.value, selected_user)
                        table_list_researcher = extraction_researcher(file_result.value, selected_user)
```

(The `else: pass` branches leave both as `None` — intentional, nothing is rendered.)

Then find the rendering block at the bottom of `script()`:

```python
    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
```

Replace with:

```python
    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    if table_list_researcher is not None:
        logger.info("Prompt researcher consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list_researcher, RESEARCHER_DESCRIPTION)
        result = yield ph.render_page(RESEARCHER_VIEW_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
```

- [ ] **Step 6: Verify netflix.py compiles**

```bash
python -m py_compile src/framework/processing/py/port/netflix.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add src/framework/processing/py/port/netflix.py
git commit -m "feat: add Netflix researcher view; fix validate_zip status code bug"
```

---

## Chunk 3: LinkedIn New Script

### Task 4: Create `linkedin.py`

**Files:**
- Create: `src/framework/processing/py/port/linkedin.py`

Ported from `~/src/d3i/forks/daniellemccool/dd-vu-2026/packages/python/port/platforms/linkedin.py` with adapter changes (see spec). Key notes:
- `connections_to_df()` returns `"Connected On"` (not renamed — the Dutch rename lives only in `extraction()`).
- `strip_notes()` is used in `connections_to_df()` and `member_follows_to_df()`.
- Table IDs: `"linkedin_company_follows"` (source had typo `"linked_in_company_follows"`).
- `STATUS_CODES`: ids 0 and 1 only (mirror ChatGPT pattern).
- `DDP_CATEGORIES` includes 4 filenames missing from source: `"Ads Clicked.csv"`, `"SearchQueries.csv"`, `"Comments.csv"`, `"Shares.csv"`.

- [ ] **Step 1: Create the file**

Create `src/framework/processing/py/port/linkedin.py` with the full content:

```python
"""
DDP extract LinkedIn module

Handles LinkedIn data download packages (CSV format, English only).
Ported from dd-vu-2026 linkedin.py with dd-education API adaptations.
"""

import logging
import io
import re
from pathlib import Path
import zipfile

import pandas as pd

import port.api.props as props
import port.unzipddp as unzipddp
import port.extraction_helpers as eh
import port.port_helpers as ph

from port.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
    ValidateInput,
    StatusCode,
)

logger = logging.getLogger(__name__)


DDP_CATEGORIES = [
    DDPCategory(
        id="csv_en",
        ddp_filetype=DDPFiletype.CSV,
        language=Language.EN,
        known_files=[
            "Ad_Targeting.csv",
            "Endorsement_Given_Info.csv",
            "Member_Follows.csv",
            "Recommendations_Given.csv",
            "Company Follows.csv",
            "Endorsement_Received_Info.csv",
            "messages.csv",
            "Registration.csv",
            "Connections.csv",
            "Inferences_about_you.csv",
            "PhoneNumbers.csv",
            "Rich Media.csv",
            "Contacts.csv",
            "Invitations.csv",
            "Positions.csv",
            "Skills.csv",
            "Education.csv",
            "Profile.csv",
            "Votes.csv",
            "Email Addresses.csv",
            "Learning.csv",
            "Reactions.csv",
            # Files used by extraction() that were absent from upstream source:
            "Ads Clicked.csv",
            "SearchQueries.csv",
            "Comments.csv",
            "Shares.csv",
        ],
    ),
]

STATUS_CODES = [
    StatusCode(id=0, description="Valid zip", message="Valid zip"),
    StatusCode(id=1, description="Bad zipfile", message="Bad zipfile"),
]


def validate_zip(zfile: str) -> ValidateInput:
    validation = ValidateInput(STATUS_CODES, DDP_CATEGORIES)
    try:
        paths = []
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                p = Path(f)
                if p.suffix == ".csv":
                    logger.debug("Found: %s in zip", p.name)
                    paths.append(p.name)
        if validation.infer_ddp_category(paths):
            validation.set_status_code_by_id(0)
        else:
            validation.set_status_code_by_id(1)
    except zipfile.BadZipFile:
        validation.set_status_code_by_id(1)
    return validation


def strip_notes(b: io.BytesIO) -> io.BytesIO:
    """Strip notes LinkedIn prepends to CSV files."""
    try:
        pattern = re.compile(rb'^(.*?)\n\n', re.DOTALL)
        out = io.BytesIO(pattern.sub(b'', b.read()))
    except Exception:
        out = b
    return out


# --- Per-file extraction helpers ---

def ads_clicked_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Ads Clicked.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def comments_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Comments.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def company_follows_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Company Follows.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def shares_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Shares.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def reactions_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Reactions.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


def connections_to_df(linkedin_zip: str) -> pd.DataFrame:
    """Returns raw column names including 'Connected On' (not renamed here)."""
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Connections.csv")
    b = strip_notes(b)
    return unzipddp.read_csv_from_bytes_to_df(b)


def member_follows_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "Member_Follows.csv")
    b = strip_notes(b)
    return unzipddp.read_csv_from_bytes_to_df(b)


def search_queries_to_df(linkedin_zip: str) -> pd.DataFrame:
    b = unzipddp.extract_file_from_zip(linkedin_zip, "SearchQueries.csv")
    return unzipddp.read_csv_from_bytes_to_df(b)


# --- Package explorer ---

def extraction(linkedin_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Package explorer: 7 curated tables showing the breadth of LinkedIn data.
    Column renames to Dutch match dd-vu-2026 source.
    """
    tables_to_render = []

    df = ads_clicked_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "Ad clicked Date": "Advertentiedatum",
            "Ad Title/Id": "Advertentietitel/id",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_ads_clicked",
            props.Translatable({"en": "Ads you clicked on", "nl": "Ads clicked"}),
            df,
            props.Translatable({
                "en": "Record of advertisements you have clicked on while using LinkedIn.",
                "nl": "Overzicht van advertenties waarop je hebt geklikt tijdens het gebruik van LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = comments_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Date": "Datum", "Message": "Bericht"})
        wordcloud = {
            "title": {"en": "Words in your comments", "nl": "Woorden in je reacties"},
            "type": "wordcloud",
            "textColumn": "Bericht",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_comments",
            props.Translatable({"en": "Your comments on LinkedIn", "nl": "Comments"}),
            df,
            props.Translatable({
                "en": "Comments you've posted on LinkedIn content.",
                "nl": "Reacties die je hebt geplaatst op LinkedIn-content.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    df = company_follows_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Organization": "Organisatie", "Followed On": "Gevolgd op"})
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_company_follows",
            props.Translatable({"en": "Companies you follow", "nl": "Company follows"}),
            df,
            props.Translatable({
                "en": "List of companies you are following on LinkedIn.",
                "nl": "Lijst van bedrijven die je volgt op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = shares_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "Date": "Datum",
            "ShareLink": "Gedeelde link",
            "ShareCommentary": "Gedeelde tekst",
            "SharedUrl": "Gedeelde URL",
            "MediaUrl": "Media-URL",
            "Visibility": "Zichtbaarheid",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_shares",
            props.Translatable({"en": "Posts you shared on LinkedIn", "nl": "Shares"}),
            df,
            props.Translatable({
                "en": "Content you've shared with your network on LinkedIn.",
                "nl": "Content die je hebt gedeeld met je netwerk op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = reactions_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Date": "Datum"})
        # "Type" column is intentionally not renamed — used as-is for wordcloud
        wordcloud = {
            "title": {"en": "Your reaction types", "nl": "Jouw reactietypes"},
            "type": "wordcloud",
            "textColumn": "Type",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_reactions",
            props.Translatable({"en": "Your reactions on LinkedIn", "nl": "Reactions"}),
            df,
            props.Translatable({
                "en": "Record of your reactions to posts and content on LinkedIn.",
                "nl": "Overzicht van je reacties op berichten en content op LinkedIn.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    df = connections_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={
            "First Name": "Voornaam",
            "Last Name": "Achternaam",
            "Email Address": "E-mailadres",
            "Company": "Bedrijf",
            "Position": "Functie",
            "Connected On": "Verbonden op",
        })
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_connections",
            props.Translatable({"en": "Your LinkedIn connections", "nl": "Je LinkedIn-connecties"}),
            df,
            props.Translatable({
                "en": "List of people you are connected with on LinkedIn.",
                "nl": "Lijst van mensen met wie je verbonden bent op LinkedIn.",
            }),
        )
        tables_to_render.append(table)

    df = search_queries_to_df(linkedin_zip)
    if not df.empty:
        df = df.rename(columns={"Time": "Tijd", "Search Query": "Zoekterm"})
        wordcloud = {
            "title": {"en": "What you searched for", "nl": "Wat je zocht"},
            "type": "wordcloud",
            "textColumn": "Zoekterm",
            "tokenize": True,
        }
        table = props.PropsUIPromptConsentFormTable(
            "linkedin_search_queries",
            props.Translatable({"en": "Your search queries on LinkedIn", "nl": "Search queries"}),
            df,
            props.Translatable({
                "en": "Terms and phrases you've searched for on LinkedIn.",
                "nl": "Termen en zinnen waarnaar je hebt gezocht op LinkedIn.",
            }),
            [wordcloud],
        )
        tables_to_render.append(table)

    return tables_to_render


# --- Researcher view ---

def extraction_researcher(linkedin_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Researcher view: aggregate-only tables.
    No individual names, messages, or raw queries — only counts per time
    bucket, reaction type distribution, and search term frequency.
    """
    tables_to_render = []

    # Table 1: new connections over time
    try:
        df = connections_to_df(linkedin_zip)
        # connections_to_df() returns raw column "Connected On" (rename is in extraction() only)
        if not df.empty and "Connected On" in df.columns:
            df["Connected On"] = df["Connected On"].apply(eh.try_to_convert_any_timestamp_to_iso8601)
            df_month = (
                df[df["Connected On"].str.len() >= 7]
                .assign(Month=lambda x: x["Connected On"].str[:7])
                .groupby("Month")
                .size()
                .reset_index(name="Count")
            )
            if not df_month.empty:
                chart = {
                    "title": {"en": "New connections over time", "nl": "Nieuwe connecties over tijd"},
                    "type": "area",
                    "group": {"column": "Month"},
                    "values": [{"column": "Count", "label": {"en": "Connections", "nl": "Connecties"}}],
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_connections",
                    props.Translatable({"en": "New connections over time", "nl": "Nieuwe connecties over tijd"}),
                    df_month,
                    props.Translatable({
                        "en": "Number of new LinkedIn connections made each month.",
                        "nl": "Aantal nieuwe LinkedIn-connecties per maand.",
                    }),
                    [chart],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher connections error: %s", e)

    # Table 2: reaction type counts
    try:
        df = reactions_to_df(linkedin_zip)
        if not df.empty and "Type" in df.columns:
            df_types = (
                df.groupby("Type")
                .size()
                .reset_index(name="Count")
            )
            if not df_types.empty:
                chart = {
                    "title": {"en": "Reaction types", "nl": "Reactietypes"},
                    "type": "bar",
                    "group": {"column": "Type"},
                    "values": [{"column": "Count", "label": {"en": "Count", "nl": "Aantal"}}],
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_reactions",
                    props.Translatable({"en": "Reaction types", "nl": "Reactietypes"}),
                    df_types,
                    props.Translatable({
                        "en": "Distribution of reaction types you used on LinkedIn.",
                        "nl": "Verdeling van reactietypes die je hebt gebruikt op LinkedIn.",
                    }),
                    [chart],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher reactions error: %s", e)

    # Table 3: most searched terms (wordcloud from raw text column)
    try:
        df = search_queries_to_df(linkedin_zip)
        # search_queries_to_df() returns raw column "Search Query" (rename is in extraction() only)
        if not df.empty and "Search Query" in df.columns:
            df_queries = df[["Search Query"]].dropna()
            if not df_queries.empty:
                wordcloud = {
                    "title": {"en": "Most searched terms", "nl": "Meest gezochte termen"},
                    "type": "wordcloud",
                    "textColumn": "Search Query",
                    "tokenize": True,
                }
                table = props.PropsUIPromptConsentFormTable(
                    "linkedin_researcher_searches",
                    props.Translatable({"en": "Most searched terms", "nl": "Meest gezochte termen"}),
                    df_queries,
                    props.Translatable({
                        "en": "Frequency of terms searched on LinkedIn.",
                        "nl": "Hoe vaak termen zijn gezocht op LinkedIn.",
                    }),
                    [wordcloud],
                )
                tables_to_render.append(table)
    except Exception as e:
        logger.error("extraction_researcher searches error: %s", e)

    return tables_to_render


# --- Text constants ---

SUBMIT_FILE_HEADER = props.Translatable({
    "en": "Select your LinkedIn file",
    "nl": "Selecteer uw LinkedIn bestand",
})

REVIEW_DATA_HEADER = props.Translatable({
    "en": "Your LinkedIn data",
    "nl": "Uw LinkedIn gegevens",
})

RETRY_HEADER = props.Translatable({
    "en": "Try again",
    "nl": "Probeer opnieuw",
})

CONSENT_FORM_DESCRIPTION = props.Translatable({
    "en": "Below you will find a curated selection of your LinkedIn data showing the breadth of what LinkedIn collects about you.",
    "nl": "Hieronder vindt u een samengestelde selectie van uw LinkedIn-gegevens die de breedte laat zien van wat LinkedIn over u verzamelt.",
})

RESEARCHER_VIEW_HEADER = props.Translatable({
    "en": "Your LinkedIn data — researcher view",
    "nl": "Uw LinkedIn gegevens — onderzoekersweergave",
})

RESEARCHER_DESCRIPTION = props.Translatable({
    "en": "This view shows only aggregate statistics — the kind of data a researcher would collect in a real data donation study. No individual names, messages, or raw queries are shown.",
    "nl": "Deze weergave toont alleen geaggregeerde statistieken — het soort gegevens dat een onderzoeker zou verzamelen in een echte datadoneringsstudie.",
})

INSTRUCTION_DESCRIPTION = props.Translatable({
    "en": "Please follow the instructions below carefully!\nClick on the button \u201cContinue\u201d at the bottom of this page when you are ready to go to the next step.",
    "nl": "Volg de onderstaande instructies zorgvuldig!\nKlik op de knop \u201cDoorgaan\u201d onderaan deze pagina wanneer u klaar bent voor de volgende stap.",
})

INSTRUCTION_HEADER = props.Translatable({
    "en": "Instructions to request your LinkedIn data",
    "nl": "Instructies om uw LinkedIn-gegevens op te vragen",
})


# --- Script ---

def script():
    platform_name = "LinkedIn"
    table_list = None
    table_list_researcher = None

    while True:
        logger.info("Prompt for file for %s", platform_name)

        instructions_prompt = ph.generate_instructions_prompt(INSTRUCTION_DESCRIPTION, "instructions.svg")
        file_result = yield ph.render_page(INSTRUCTION_HEADER, instructions_prompt)

        file_prompt = ph.generate_file_prompt(platform_name, "application/zip")
        file_result = yield ph.render_page(SUBMIT_FILE_HEADER, file_prompt)

        if file_result.__type__ == "PayloadString":
            validation = validate_zip(file_result.value)

            if validation.status_code.id == 0:
                logger.info("Payload for %s", platform_name)
                table_list = extraction(file_result.value)
                table_list_researcher = extraction_researcher(file_result.value)
                break

            if validation.status_code.id != 0:
                logger.info("Not a valid %s zip; prompt retry_confirmation", platform_name)
                retry_result = yield ph.render_page(RETRY_HEADER, ph.retry_confirmation(platform_name))
                if retry_result.__type__ == "PayloadTrue":
                    continue
                elif retry_result.value == "show issue form":
                    yield ph.render_issue_page(platform_name, file_result.value)
                    return
                else:
                    logger.info("Skipped during retry flow")
                    break

        else:
            logger.info("Skipped at file selection ending flow")
            break

    if table_list is not None:
        logger.info("Prompt consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list, CONSENT_FORM_DESCRIPTION)
        result = yield ph.render_page(REVIEW_DATA_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    if table_list_researcher is not None:
        logger.info("Prompt researcher consent; %s", platform_name)
        consent_prompt = ph.generate_consent_prompt(table_list_researcher, RESEARCHER_DESCRIPTION)
        result = yield ph.render_page(RESEARCHER_VIEW_HEADER, consent_prompt)
        if result.value == "show issue form":
            yield ph.render_issue_page(platform_name, file_result.value)
            return

    return
```

- [ ] **Step 2: Verify linkedin.py compiles**

```bash
python -m py_compile src/framework/processing/py/port/linkedin.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/framework/processing/py/port/linkedin.py
git commit -m "feat: add LinkedIn extraction script (ported from dd-vu-2026, dual-view)"
```

---

## Chunk 4: script.py Updates + Final Verification

### Task 5: Update `script.py`

**Files:**
- Modify: `src/framework/processing/py/port/script.py`

Two changes: (1) fix the duplicate `id=5` in the radio menu, (2) add LinkedIn.

- [ ] **Step 1: Add LinkedIn import**

At the top of `script.py`, after the existing platform imports, add:

```python
import port.linkedin as linkedin
```

- [ ] **Step 2: Fix radio menu IDs and add LinkedIn**

Locate `generate_platform_selection_menu()`. The current `items` list has a duplicate `id=5`. Replace the entire `items` list with:

```python
    items = [
        props.RadioItem(id=1, value="ChatGPT"),
        props.RadioItem(id=2, value="YouTube"),
        props.RadioItem(id=3, value="Instagram"),
        props.RadioItem(id=4, value="Netflix"),
        props.RadioItem(id=5, value="Whatsapp group chat"),
        props.RadioItem(id=6, value="General DDP Analyzer"),
        props.RadioItem(id=7, value="LinkedIn"),
    ]
```

- [ ] **Step 3: Add LinkedIn dispatch in `process()`**

Locate the `process()` function. After the last `if selection_result.value == ...` block (before `yield render_end_page()`), add:

```python
            if selection_result.value == "LinkedIn":
                yield from linkedin.script()
```

- [ ] **Step 4: Verify script.py compiles**

```bash
python -m py_compile src/framework/processing/py/port/script.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/framework/processing/py/port/script.py
git commit -m "feat: register LinkedIn in platform menu; fix duplicate radio id"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run py_compile on all port files**

```bash
python -m py_compile \
  src/framework/processing/py/port/script.py \
  src/framework/processing/py/port/chatgpt.py \
  src/framework/processing/py/port/youtube.py \
  src/framework/processing/py/port/netflix.py \
  src/framework/processing/py/port/instagram.py \
  src/framework/processing/py/port/whatsapp.py \
  src/framework/processing/py/port/linkedin.py \
  src/framework/processing/py/port/general_ddp_analyzer.py \
  src/framework/processing/py/port/extraction_helpers.py \
  src/framework/processing/py/port/unzipddp.py \
  src/framework/processing/py/port/validate.py \
  src/framework/processing/py/port/port_helpers.py && echo "ALL OK"
```

Expected: `ALL OK`

- [ ] **Step 2: Confirm expected structure in script.py**

```bash
grep -n "yield from\|RadioItem" src/framework/processing/py/port/script.py
```

Expected output should show 7 `RadioItem` entries (ids 1–7) and 7 `yield from` dispatch lines (ChatGPT, YouTube, Instagram, Netflix, Whatsapp, General DDP Analyzer, LinkedIn).

- [ ] **Step 3: Confirm extraction_researcher exists in YouTube, Netflix, and LinkedIn**

```bash
grep -n "def extraction_researcher" \
  src/framework/processing/py/port/youtube.py \
  src/framework/processing/py/port/netflix.py \
  src/framework/processing/py/port/linkedin.py
```

Expected: one match per file (3 total).

- [ ] **Step 4: Confirm 7 dispatch lines in process()**

```bash
grep -n "yield from" src/framework/processing/py/port/script.py
```

Expected: 7 lines (ChatGPT, YouTube, Instagram, Netflix, Whatsapp group chat, General DDP Analyzer, LinkedIn).

- [ ] **Step 5: Open a PR**

```bash
git push -u origin feat/dual-view-extraction
```

**Before pushing, confirm:** remote is `git@github.com:d3i-infra/dd-education.git` and branch is `feat/dual-view-extraction`.

Then open PR via `gh pr create` or GitHub UI.
