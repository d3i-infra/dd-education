# Visualization plugin

Renders the `visualizations` blocks that Python passes through from a table's
`configs/<platform>_config.json` entry (`TableConfig.visualizations`, see
`packages/python/port/helpers/table_extractor.py`). Each block is a plain JSON
object; `figure.tsx` validates it against the zod schemas in `types.ts` before
rendering, so a malformed block renders nothing (an empty `<div />`) and logs
once to the console instead of crashing the consent form.

Every visualization computes its chart-ready data off the main thread, in a
worker spawned per figure and terminated as soon as it answers
(`visualizationDataFunctions/useVisualizationData.tsx`,
`visualizationDataWorker.ts` -- ADR-0032). Before the table is posted to the
worker, `selectVisualizationColumns.ts` projects it down to only the columns
the visualization actually reads, so a `postMessage` clones a slice of the
table rather than the whole thing. Figures only ever read table data; they
never mutate or shrink it (ADR-0031).

All types below share `title: Translatable` (shown as the figure's heading)
and an optional `height` (pixels; defaults to 250).

## Chart types: `line` | `bar` | `area`

Aggregates one or more columns by a group column, via
`visualizationDataFunctions/prepareChartData.ts`, and renders with Recharts
(`figures/recharts_graph.tsx`).

```json
{
  "title": { "en": "Videos watched per month" },
  "type": "bar",
  "group": { "column": "watched_at", "dateFormat": "month" },
  "values": [{ "column": ".COUNT" }]
}
```

`group.top` (optional): for a **categorical** group (no `dateFormat`), keep
only the `top` N groups with the largest first-series value, sorted
descending. Ignored when `dateFormat` is set, since a time axis's order is
already meaningful. Use it to turn a long tail of categories into a
top-N bars chart:

```json
{
  "title": { "en": "Top 5 creators" },
  "type": "bar",
  "group": { "column": "creator", "top": 5 },
  "values": [{ "column": ".COUNT" }]
}
```

## `wordcloud`

See `visualizationDataFunctions/prepareTextData.ts` / `figures/d3_wordcloud.tsx`.

```json
{
  "title": { "en": "Most common words" },
  "type": "wordcloud",
  "textColumn": "message",
  "tokenize": true
}
```

Optional fields, all off by default -- useful for a chat export, where the
raw message text is full of things that aren't the words a participant
actually wants to see:

| field | type | notes |
|---|---|---|
| `stripMentions` | `boolean` | drops any token beginning with `@` (a WhatsApp-style `@mention`) -- only its first word; the rest of a mentioned name (WhatsApp writes it out in full, e.g. `@John Doe`) needs `excludeColumn` |
| `excludeColumn` | `string` | every distinct value of this column, lowercased and split on whitespace, joins the stopword set -- for a chat table this is the participant-name column, so nobody's own name dominates their own wordcloud |
| `stripPlaceholders` | `boolean` | drops media-placeholder text before tokenizing: any `<...>` tag, plus the bare forms in `PLACEHOLDER_PHRASES` (`prepareTextData.ts`) for both "omitted" (en) and "weggelaten" (nl) exports |

```json
{
  "title": { "en": "Most common words in your chats" },
  "type": "wordcloud",
  "textColumn": "Message",
  "tokenize": true,
  "stripMentions": true,
  "excludeColumn": "Name",
  "stripPlaceholders": true
}
```

## `stats`

A responsive row of stat tiles ("big number, small label"), one per entry in
`tiles`. Data prep: `visualizationDataFunctions/prepareStatsData.ts`.
Rendering: `figures/stat_tiles.tsx`.

```json
{
  "title": { "en": "At a glance" },
  "type": "stats",
  "tiles": [
    { "label": { "en": "Total videos" }, "aggregate": "count" },
    { "label": { "en": "Creators" }, "aggregate": "distinct", "column": "creator" },
    { "label": { "en": "First watched" }, "aggregate": "first_date", "column": "watched_at", "dateFormat": "day" },
    { "label": { "en": "Busiest day" }, "aggregate": "busiest_day", "column": "watched_at" }
  ]
}
```

Each tile:

| field | type | notes |
|---|---|---|
| `label` | `Translatable` | required |
| `aggregate` | `"count" \| "distinct" \| "min" \| "max" \| "sum" \| "mean" \| "first_date" \| "last_date" \| "span_days" \| "busiest_day"` | required |
| `column` | `string` | required for every aggregate except `count` (which counts all rows when `column` is omitted, or non-empty cells in `column` when given) |
| `dateFormat` | one of the chart `group.dateFormat` values (e.g. `"day"`, `"month"`, `"year"`) | only affects `first_date` / `last_date` / `busiest_day` display precision; defaults to `"day"` |

A tile whose column has no valid values for its aggregate (e.g. `mean` on a
column with no numeric cells) renders `"–"` rather than failing the whole
block. A tile that omits a `column` it requires (e.g. `distinct` with no
`column`) is a config error and fails the block, the same way a chart's
missing column does today.

## `heatmap`

Plain SVG, no charting dependency. Cells are colour-scaled (5 steps, light to
dark) by count (or an aggregate of `valueColumn`); the exact value is always
in the cell's tooltip (`<title>`), never carried by colour alone. Data prep:
`visualizationDataFunctions/prepareHeatmapData.ts`. Rendering:
`figures/heatmap.tsx`.

Two modes:

- `"calendar"`: one grid per calendar year present in the data, GitHub-style
  -- rows are weekdays (Monday first), columns are weeks, with month labels
  along the top.
- `"weekday_hour"`: a single 7 (weekday) x 24 (hour) grid.

```json
{
  "title": { "en": "When donations happen" },
  "type": "heatmap",
  "mode": "calendar",
  "dateColumn": "created_at"
}
```

```json
{
  "title": { "en": "Activity by time of day" },
  "type": "heatmap",
  "mode": "weekday_hour",
  "dateColumn": "created_at",
  "valueColumn": "duration_seconds",
  "aggregate": "sum"
}
```

| field | type | notes |
|---|---|---|
| `mode` | `"calendar" \| "weekday_hour"` | required |
| `dateColumn` | `string` | required; parsed the same way chart date columns are (`new Date(cell)`) |
| `valueColumn` | `string` | optional; when omitted each row counts as 1 |
| `aggregate` | `"count" \| "sum" \| "mean"` | optional, defaults to `"count"` (row count) |

A row whose `dateColumn` cell doesn't parse as a date is skipped rather than
failing the block. An empty table, or a table where every date is unparseable,
renders the "no data" fallback.

## `thread`

A paged conversation viewer: a list of threads (left, or above on narrow
screens) and the selected thread's messages as chat bubbles (right, or
below). One viewer serves every "grouped conversation" export -- ChatGPT
conversations today, WhatsApp / Meta message exports later. Data prep:
`visualizationDataFunctions/prepareThreadData.ts`. Rendering:
`figures/thread_view.tsx`.

```json
{
  "title": { "en": "Your conversations", "nl": "Je gesprekken" },
  "type": "thread",
  "groupColumn": "Conversation id",
  "titleColumn": "Conversation title",
  "roleColumn": "Role",
  "textColumn": "Message",
  "timeColumn": "Time",
  "badgeColumn": "Model",
  "selfRole": "user",
  "pageSize": { "threads": 20, "turns": 50 }
}
```

| field | type | notes |
|---|---|---|
| `groupColumn` | `string` | the grouping key: two rows with the same value are the same thread. Use a stable id column, not a display title -- two distinct threads can share a title (a renamed or never-renamed chat), and grouping by title alone would silently merge them. Required unless `singleThreadTitle` is given instead |
| `titleColumn` | `string` | optional; the column supplying each thread's displayed title. Defaults to `groupColumn` itself, for a table whose grouping key is already display-worthy |
| `singleThreadTitle` | `Label` | renders every row as one thread titled with this text, for a table with no natural group column (e.g. a flat WhatsApp chat export); required unless `groupColumn` is given instead -- exactly one of the two is required |
| `roleColumn` | `string` | required; the speaker of each turn (e.g. `"user"` / `"assistant"`, or a WhatsApp display name) |
| `textColumn` | `string` | required; the message text |
| `timeColumn` | `string` | optional; when given, turns within a thread are sorted by parsed time (a row whose cell doesn't parse sorts after every parseable row, keeping its own relative order) and the thread's list entry shows a date range. Omitted entirely: turns keep table row order, no time is shown |
| `badgeColumn` | `string` | optional; shown next to a turn's time (e.g. the AI model that produced a reply) |
| `selfRole` | `string` | optional; turns whose `roleColumn` value equals this are right-aligned on the primary tint. Every other turn (including all of them, when `selfRole` is omitted) is left-aligned on grey with the role as its label |
| `pageSize` | `{ threads?: number, turns?: number }` | optional; threads per list page (default 20) and turns per transcript page (default 50) |

Grouping preserves each thread's first-appearance order in the table (not
sorted by time or count). Threads are capped at 5000; beyond that the tail is
dropped silently (the underlying data is never altered, ADR-0031 -- only what
this one figure renders) and the list shows a "Showing the first 5000 of N
conversations" notice. The list has a search box that filters by thread
title and by message text; list items are real `<button>` elements, so Enter
selects one for free, and the arrow key matching each pane's Previous/Next
direction pages it from anywhere focus lands inside that pane.

The review-mode figure grid (`table_container.tsx`'s `visualizationSpan`)
gives `thread` the same `md:col-span-2` full-width treatment as `stats` and
`heatmap` -- its two-pane list+transcript layout needs the width, or the
transcript pane has nowhere to grow.

WhatsApp reuse (a flat chat table with no conversation column): set
`roleColumn` to the sender-name column and `singleThreadTitle` instead of
`groupColumn`; leave `selfRole` unset so every message renders left-aligned
with the sender's name as its label, chat-log style rather than a two-sided
conversation.
