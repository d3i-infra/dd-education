# dd-education: Dual-View Extraction Design

**Date:** 2026-03-12
**Repo:** `dd-education` (`/home/dmm/src/d3i/forks/daniellemccool/dd-education`)

---

## Overview

Every platform script shows two sequential consent screens:

1. **Package explorer** (shown first) — the comprehensive extraction showing as much of the raw data package as possible so students understand what platforms collect.
2. **Researcher view** (shown second) — privacy-first, showing only what a researcher would collect in a real data donation study: aggregate charts backed by pre-aggregated or minimal-column DataFrames containing no individual identifying rows.

This is consistent with ChatGPT and Instagram, where `extraction_all()` (package explorer) is shown first and `extraction()` (researcher view) is shown second.

For YouTube, Netflix, and LinkedIn the mapping is:
- `extraction()` → package explorer (shown first) — existing comprehensive extraction
- `extraction_researcher()` → researcher view (shown second) — new aggregate-only extraction

---

## Aggregation strategy for researcher view tables

Two patterns are used depending on table type:

**Pattern A — pre-aggregated DataFrame (for area/bar charts):**
Use pandas to group and aggregate before building the table. The resulting DataFrame has only (bucket, count/sum) columns, so even the visible table rows are non-identifying.

Example: `df.groupby(df["Date standard format"].str[:7]).size().reset_index(name="Count")` → `(Month, Count)`.

Chart config: use the pre-aggregated column directly, e.g. `"values": [{"column": "Count"}]` (no `"aggregate"` needed since data is already summed).

**Pattern B — single text-column DataFrame (for wordclouds):**
Pass only the relevant text column (no URLs, timestamps, or other identifying fields). The wordcloud component handles frequency internally via `tokenize: True/False`. Use the column name as it exists after any renaming in the underlying `*_to_df()` function.

---

## Platform-by-Platform Design

### ChatGPT ✅ (no changes needed)
- **Package explorer (1st):** `extraction_all()` — raw JSON key-value dump.
- **Researcher view (2nd):** `extraction()` — curated conversations + wordcloud.

### Instagram ✅ (no changes needed)
- **Package explorer (1st):** `extraction_all()` — raw JSON key-value dump.
- **Researcher view (2nd):** `extraction()` — curated tables + charts.

### WhatsApp ✅ (no changes needed)
- Single view. The existing `extraction(df)` is comprehensive and serves as a combined view.

---

### YouTube

Existing `extraction()` signature: `extraction(youtube_zip: str, validation: ValidateInput) -> list`

**Package explorer (1st):** call `extraction(youtube_zip, validation)` — full watch history, search history, comments, watch later, subscriptions, and live-chat-messages tables + charts.

**Researcher view (2nd):** new `extraction_researcher(youtube_zip: str, validation: ValidateInput) -> list`

Calls `watch_history_to_df(youtube_zip, validation)` internally to get the watch history DataFrame (columns include `"Date standard format"`, `"Channel"`, `"Title"`, `"Url"`, etc.).

Three tables:

1. **Videos per month** (Pattern A):
   - Aggregate: group `"Date standard format"` by year-month prefix (`str[:7]`), count rows → `(Month, Count)` DataFrame
   - Table title: "Videos watched per month"
   - Chart: `{"type": "area", "group": {"column": "Month"}, "values": [{"column": "Count"}]}`

2. **Channels wordcloud** (Pattern B):
   - Pass only the `"Channel"` column (drop NaN rows)
   - Table title: "Most watched channels"
   - Chart: `{"type": "wordcloud", "textColumn": "Channel", "tokenize": False}`

3. **Videos by hour** (Pattern A):
   - Derive hour: `df["Date standard format"].apply(lambda x: x[11:13] if len(x) >= 13 else "")` → group and count → `(Hour, Count)` DataFrame
   - Table title: "Videos watched by hour of day"
   - Chart: `{"type": "bar", "group": {"column": "Hour"}, "values": [{"column": "Count"}]}`

Each table uses `if not df.empty` guard. `script()` update: call `extraction()` and `extraction_researcher()` after successful validation, render package explorer first.

New text constants: `RESEARCHER_VIEW_HEADER`, `RESEARCHER_DESCRIPTION`.
Both consent render calls include `"show issue form"` check (capture result in `result`, consistent with rest of script).

---

### Netflix

Existing `extraction()` signature: `extraction(netflix_zip: str, selected_user: str) -> list`

**Package explorer (1st):** call `extraction(netflix_zip, selected_user)` — full viewing activity, ratings, search history etc. tables + charts.

**Researcher view (2nd):** new `extraction_researcher(netflix_zip: str, selected_user: str) -> list`

Calls `viewing_activity_to_df(netflix_zip, selected_user)` internally. After `viewing_activity_to_df()`, column names are: `"Start tijd"` (datetime string), `"Titel"` (show title), `"Apparaat"` (device), `"Aantal uur gekeken"` (float, hours).

Three tables:

1. **Hours watched per month** (Pattern A):
   - Aggregate: group `"Start tijd"` by year-month prefix (`str[:7]`), sum `"Aantal uur gekeken"` → `(Month, Hours watched)` DataFrame
   - Table title: "Hours watched per month"
   - Chart: `{"type": "area", "group": {"column": "Month"}, "values": [{"column": "Hours watched"}]}`

2. **Viewing by hour of day** (Pattern A):
   - Derive hour from `"Start tijd"` → group by hour, count → `(Hour, Count)` DataFrame
   - Table title: "Viewing by hour of day"
   - Chart: `{"type": "bar", "group": {"column": "Hour"}, "values": [{"column": "Count"}]}`

3. **Most watched titles** (Pattern B):
   - Pass only the `"Titel"` column
   - Table title: "Most watched titles"
   - Chart: `{"type": "wordcloud", "textColumn": "Titel", "tokenize": False}`

`script()` update: `selected_user` is resolved before both extraction calls (unchanged user-selection sub-flow). In the `else: pass` branch, both `table_list` and `table_list_researcher` remain `None` — nothing is rendered. Both consent render calls include `"show issue form"` check.

**Bug fix (while touching `script()`):** The existing `STATUS_CODES` in `netflix.py` defines only ids 0 and 1, but `validate_zip()` calls `set_status_code_by_id(3)` on `BadZipFile` — a latent crash. Fix this while updating `script()`: change the `BadZipFile` branch in `validate_zip()` to use `set_status_code_by_id(1)` instead of `3`.

New text constants: `RESEARCHER_VIEW_HEADER`, `RESEARCHER_DESCRIPTION`.

---

### LinkedIn (new file: `port/linkedin.py`)

**Source:** `~/src/d3i/forks/daniellemccool/dd-vu-2026/packages/python/port/platforms/linkedin.py`

**Adapter changes:**
- `d3i_props.PropsUIPromptConsentFormTableViz(id=..., data_frame=..., title=..., description=..., visualizations=[...])` → `props.PropsUIPromptConsentFormTable(id, title, df, description, visualizations)`
- `FlowBuilder` / `process()` → generator `script()` following Netflix/YouTube pattern
- `port.helpers.extraction_helpers.extract_file_from_zip` → `port.unzipddp.extract_file_from_zip`
- `port.helpers.extraction_helpers.read_csv_from_bytes_to_df` → `port.unzipddp.read_csv_from_bytes_to_df`
- `port.helpers.validate.*` → `port.validate.*`

**`strip_notes()` helper:** retained as-is. Used in `connections_to_df()` and `member_follows_to_df()`, exactly as in source.

**`STATUS_CODES`** (mirror ChatGPT pattern exactly):
```python
STATUS_CODES = [
    StatusCode(id=0, description="Valid zip", message="Valid zip"),
    StatusCode(id=1, description="Bad zipfile", message="Bad zipfile"),
]
```
`validate_zip()`: id=0 on success, id=1 on `BadZipFile` or failed `infer_ddp_category`.

**`DDP_CATEGORIES`:** port from source and add the four missing filenames that extraction functions read but source omits from `known_files`: `"Ads Clicked.csv"`, `"SearchQueries.csv"`, `"Comments.csv"`, `"Shares.csv"`.

**Column renames:** retain all Dutch renames from source (e.g. `"Message"` → `"Bericht"`, `"Search Query"` → `"Zoekterm"`, `"Date"` → `"Datum"`, etc.). Wordcloud `textColumn` references must use the post-rename Dutch column names.

**Table IDs:** use consistently prefixed IDs with no typos. Note: the source has a typo (`"linked_in_company_follows"`) — correct it to `"linkedin_company_follows"`:
- `"linkedin_ads_clicked"`, `"linkedin_comments"`, `"linkedin_company_follows"`, `"linkedin_shares"`, `"linkedin_reactions"`, `"linkedin_connections"`, `"linkedin_search_queries"`

**Package explorer (1st):** `extraction(linkedin_zip: str) -> list` — 7 tables:
- Ads clicked (`Ads Clicked.csv`) — no visualizations
- Comments + wordcloud: `{"type": "wordcloud", "textColumn": "Bericht", "tokenize": True}` (`Comments.csv`)
- Company follows (`Company Follows.csv`) — no visualizations
- Shares (`Shares.csv`) — no visualizations
- Reactions + wordcloud: `{"type": "wordcloud", "textColumn": "Type", "tokenize": True}` (`Reactions.csv`) — `"Type"` is the raw unrenamed column name for reaction type
- Connections (`Connections.csv`) — no visualizations
- Search queries + wordcloud: `{"type": "wordcloud", "textColumn": "Zoekterm", "tokenize": True}` (`SearchQueries.csv`)

**Researcher view (2nd):** `extraction_researcher(linkedin_zip: str) -> list` — three tables:

1. **New connections over time** (Pattern A):
   - Call `connections_to_df(linkedin_zip)` → returns raw column names from CSV; the rename to `"Verbonden op"` happens only inside `extraction()`, so here the column is `"Connected On"`.
   - Apply `try_to_convert_any_timestamp_to_iso8601` to `"Connected On"` to normalise dates
   - Group by year-month prefix, count → `(Month, Count)` DataFrame
   - Table title: "New connections over time"
   - Chart: `{"type": "area", "group": {"column": "Month"}, "values": [{"column": "Count"}]}`

2. **Reaction types** (Pattern A):
   - Call `reactions_to_df(linkedin_zip)` → `"Type"` column contains reaction type strings
   - Group by `"Type"`, count → `(Type, Count)` DataFrame
   - Table title: "Reaction types"
   - Chart: `{"type": "bar", "group": {"column": "Type"}, "values": [{"column": "Count"}]}`

3. **Most searched terms** (Pattern B):
   - Call `search_queries_to_df(linkedin_zip)` → columns include `"Zoekterm"` (after rename from `"Search Query"`)
   - Pass only `"Zoekterm"` column
   - Table title: "Most searched terms"
   - Chart: `{"type": "wordcloud", "textColumn": "Zoekterm", "tokenize": True}`

Each table uses `if not df.empty` guard.

`script()`: dual-flow. Both consent render calls include `"show issue form"` check.

New text constants: `SUBMIT_FILE_HEADER`, `REVIEW_DATA_HEADER`, `RETRY_HEADER`, `CONSENT_FORM_DESCRIPTION`, `RESEARCHER_VIEW_HEADER`, `RESEARCHER_DESCRIPTION`, `INSTRUCTION_DESCRIPTION`, `INSTRUCTION_HEADER`.

Instruction image: `"instructions.svg"` (existing generic placeholder).

---

## `script.py` Changes

Fix duplicate `id=5` in `generate_platform_selection_menu()`. Assign:
- ChatGPT=1, YouTube=2, Instagram=3, Netflix=4, Whatsapp group chat=5, General DDP Analyzer=6, LinkedIn=7

Add to dispatch in `process()`:
```python
import port.linkedin as linkedin
# ...
if selection_result.value == "LinkedIn":
    yield from linkedin.script()
```

---

## Verification

After all changes, run `python -m py_compile` on every `.py` file under `src/framework/processing/py/port/` to confirm no syntax errors.

---

## Files Changed

| File | Change |
|---|---|
| `port/youtube.py` | Add `extraction_researcher()`, update `script()`, add text constants |
| `port/netflix.py` | Add `extraction_researcher()`, update `script()`, add text constants; fix `validate_zip()` status code 3 bug |
| `port/linkedin.py` | New file |
| `port/script.py` | Fix id collision, add LinkedIn import + menu item + dispatch |

No changes to: `chatgpt.py`, `instagram.py`, `whatsapp.py`, framework files.
