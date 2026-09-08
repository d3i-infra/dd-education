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
