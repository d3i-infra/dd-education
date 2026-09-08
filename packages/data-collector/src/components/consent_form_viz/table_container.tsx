import { useCallback, useMemo, useState, useEffect, useRef, ReactElement } from "react"
import { Title4 } from "@eyra/feldspar"
import TextBundle from "@eyra/feldspar"
import { resolveAll } from "../../locale/text"
import { 
    TableWithContext,
    PropsUITableRow,
} from "./types"
import { TableItems } from "./table_items"
import { Figure } from "./visualization_plugin/figure"
import { Table } from "./table"
import { SearchBar } from "./search_bar"
import { zTable, Table as ValidatedTable } from "./visualization_plugin/types"

// Review cards this small (<=25 rows) have nothing to gain from collapsing —
// hiding a 1-row table hides everything for no benefit — so they start
// expanded instead of behind the "Show N rows" toggle.
const REVIEW_AUTO_EXPAND_THRESHOLD = 25

interface TableContainerProps {
  id: string
  table: TableWithContext
  updateTable: (tableId: string, table: TableWithContext) => void
  locale: string
  // "study" (default) is upstream's stacked title/description/table/figures
  // layout, byte-for-byte unchanged (ADR-0002/0033 — the fork must stay
  // mergeable). "review" is the education-mode card used by review_layout.tsx:
  // figures first, table collapsed by default behind a "Show N rows" control.
  variant?: "study" | "review"
}

export const TableContainer = ({ id, table, updateTable, locale, variant = "study" }: TableContainerProps): ReactElement => {
  const isReview = variant === "review"
  const tableVisualizations = table.visualizations != null ? table.visualizations : []
  const [searchFilterIds, setSearchFilterIds] = useState<Set<string>>()
  const [search, setSearch] = useState<string>("")
  const lastSearch = useRef<string>("")
  const text = useMemo(() => getTranslations(locale), [locale])
  const unfilteredRows = table.body.rows.length
  const nLabel = unfilteredRows.toLocaleString(locale, { useGrouping: true })
  // Review cards default to collapsed regardless of the researcher's `folded`
  // setting — the card's figures are the point, the table is supporting
  // detail — except small tables (see REVIEW_AUTO_EXPAND_THRESHOLD above),
  // which start expanded.
  const [show, setShow] = useState<boolean>(isReview ? unfilteredRows <= REVIEW_AUTO_EXPAND_THRESHOLD : !table.folded)

  useEffect(() => {
    const timer = setTimeout(() => {
      const ids = searchRows(table.originalBody.rows, search)
      setSearchFilterIds(ids)
      if (search !== "" && lastSearch.current === "") {
        setTimeout(() => setShow(true), 10)
      }
      lastSearch.current = search
    }, 300)
    return () => clearTimeout(timer)
  }, [search, lastSearch, table.originalBody.rows])

  const searchedTable = useMemo(() => {
    if (searchFilterIds === undefined) return table
    const filteredRows = table.body.rows.filter((row) => searchFilterIds.has(row.id))
    return { ...table, body: { ...table.body, rows: filteredRows } }
  }, [table, searchFilterIds])

  // Validate once per table update and share across figures — previously every
  // Figure deep-cloned the full table via zod (issue #122). Skipped entirely
  // for tables without visualizations.
  const validatedTable: ValidatedTable | null = useMemo(() => {
    if (tableVisualizations.length === 0) return null
    const result = zTable.safeParse(searchedTable)
    if (!result.success) console.error(result.error)
    return result.success ? result.data : null
  }, [searchedTable, tableVisualizations.length])

  const handleDelete = useCallback(
    (rowIds?: string[]) => {
      if (rowIds == null) {
        if (searchedTable !== null) {
          // if no rowIds specified, delete all rows that meet search condition
          rowIds = searchedTable.body.rows.map((row) => row.id)
        } else {
          return
        }
      }
      if (rowIds.length > 0) {
        if (rowIds.length === searchedTable?.body?.rows?.length) {
          setSearch("")
          setSearchFilterIds(undefined)
        }
        const deletedRows = [...table.deletedRows, rowIds]
        const newTable = deleteTableRows(table, deletedRows)
        updateTable(id, newTable)
      }
    },
    [id, table, searchedTable, updateTable]
  )

  const handleUndo = useCallback(() => {
    const deletedRows = table.deletedRows.slice(0, -1)
    const newTable = deleteTableRows(table, deletedRows)
    updateTable(id, newTable)
  }, [id, table, updateTable])

  if (isReview) {
    if (unfilteredRows === 0) {
      // Born empty (the export never had rows here) reads differently from
      // emptied by the participant's own deletions — the latter must keep
      // TableItems' deleted-count + Undo control reachable (study mode never
      // loses it either), so it renders inside the compact card rather than
      // the plain "no entries" line.
      const emptiedByDeletion = table.deletedRowCount > 0
      return (
        <div
          key={table.id}
          className="p-4 md:p-5 flex flex-col gap-2 w-full overflow-hidden border-[0.2rem] border-grey4 rounded-lg bg-grey6"
        >
          <div className="flex items-center justify-between gap-4">
            <Title4 text={table.title} margin="" />
            {!emptiedByDeletion ? (
              <div className="text-caption font-body text-grey2 whitespace-nowrap">{text.noEntries}</div>
            ) : null}
          </div>
          {emptiedByDeletion ? (
            <TableItems table={table} searchedTable={searchedTable} handleUndo={handleUndo} locale={locale} />
          ) : null}
        </div>
      )
    }

    return (
      <div
        key={table.id}
        className="p-3 md:p-4 lg:p-6 flex flex-col gap-4 w-full overflow-hidden border-[0.2rem] border-grey4 rounded-lg bg-white"
      >
        <div className="flex flex-col gap-1">
          <Title4 text={table.title} margin="" />
          {table.description !== "" ? (
            <p className="text-caption font-body text-grey2 max-w-2xl">{table.description}</p>
          ) : null}
        </div>

        {tableVisualizations.length > 0 && validatedTable != null ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tableVisualizations.map((vs: any, i: number) => (
              <div key={table.id + "_" + String(i)} className={visualizationSpan(vs)}>
                <Figure
                  tableInput={validatedTable}
                  visualizationInput={vs}
                  locale={locale}
                  handleDelete={handleDelete}
                  handleUndo={handleUndo}
                />
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <TableItems table={table} searchedTable={searchedTable} handleUndo={handleUndo} locale={locale} />
              {/* Grey outline "secondary" treatment (border-grey3/text-grey1,
                  echoing SearchBar's own border-grey3 rounded-lg) so this sits
                  beside the row count as a clearly-a-button control without
                  competing with the page's green Continue button. Label is
                  always visible — a narrow-width icon-only button read as an
                  unlabelled second search button (Danielle: "I don't
                  actually see any tables"), so unlike study mode's
                  show/hideTable control below, nothing here is `hidden`. */}
              <button
                type="button"
                aria-expanded={show}
                className="flex items-center gap-2 shrink-0 h-44px rounded-lg border-2 border-grey3 text-grey1 px-3 font-button text-buttonsmall hover:bg-grey5 active:shadow-top2px"
                onClick={() => setShow(!show)}
              >
                <span className="text-grey1">{show ? zoomOutIcon : zoomInIcon}</span>
                <span className="whitespace-nowrap">
                  {show ? text.hideRows : text.showRowsTemplate.replace("{n}", nLabel)}
                </span>
              </button>
            </div>
            <SearchBar placeholder={text.searchPlaceholder} search={search} onSearch={setSearch} />
          </div>
          <Table
            show={show}
            table={searchedTable}
            search={search}
            unfilteredRows={unfilteredRows}
            handleDelete={handleDelete}
            handleUndo={handleUndo}
            locale={locale}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      key={table.id}
      className="p-3 md:p-4 lg:p-6 flex flex-col gap-4 w-full overflow-hidden border-[0.2rem] border-grey4 rounded-lg"
    >
      <div className="flex flex-wrap ">
        <div key="Title" className="flex sm:flex-row justify-between w-full gap-1 mb-2">
          <Title4 text={table.title} margin="" />

          {unfilteredRows > 0 ? (
            <SearchBar placeholder={text.searchPlaceholder} search={search} onSearch={setSearch} />
          ) : null}
        </div>
        <div key="Description" className="flex flex-col w-full mb-2 text-base md:text-lg font-body max-w-2xl">
          <p>{table.description}</p>
        </div>
        <div key="TableSummary" className="flex items-center justify-between w-full mt-1 pt-1 rounded ">
          <TableItems table={table} searchedTable={searchedTable} handleUndo={handleUndo} locale={locale} />

          <button
            key={show ? "animate" : ""}
            className={`flex end gap-3 animate-fadeIn ${unfilteredRows === 0 ? "hidden" : ""}`}
            onClick={() => setShow(!show)}
          >
            <div key="zoomIcon" className="text-primary">
              {show ? zoomOutIcon : zoomInIcon}
            </div>
            <div key="zoomText" className="text-right hidden md:block">
              {show ? text.hideTable : text.showTable}
            </div>
          </button>
        </div>
        <div key="Table" className="w-full">
          <div className="">
            <Table
              show={show}
              table={searchedTable}
              search={search}
              unfilteredRows={unfilteredRows}
              handleDelete={handleDelete}
              handleUndo={handleUndo}
              locale={locale}
            />
          </div>
        </div>
        <div
          key="Visualizations"
          className={`pt-2 grid w-full gap-4 transition-all ${
            tableVisualizations.length > 0 && unfilteredRows > 0 && validatedTable != null ? "" : "hidden"
          }`}
        >
          {validatedTable != null &&
            tableVisualizations.map((vs: any, i: number) => {
              return (
                <Figure
                  key={table.id + "_" + String(i)}
                  tableInput={validatedTable}
                  visualizationInput={vs}
                  locale={locale}
                  handleDelete={handleDelete}
                  handleUndo={handleUndo}
                />
              )
            })}
        </div>
      </div>
    </div>
  )
}

function deleteTableRows(table: TableWithContext, deletedRows: string[][]): TableWithContext {
  const deleteIds = new Set<string>()
  for (const deletedSet of deletedRows) {
    for (const id of deletedSet) {
      deleteIds.add(id)
    }
  }

  const rows = table.originalBody.rows.filter((row) => !deleteIds.has(row.id))
  const deletedRowCount = table.originalBody.rows.length - rows.length
  return {
    ...table,
    body: { ...table.body, rows },
    deletedRowCount,
    deletedRows,
  }
}

// Review-mode figure grid: `stats` tiles and `heatmap` grids read poorly at
// half width (a tile row wants to breathe; a calendar heatmap's weeks are
// wide), so both span both columns from `md`. Every other chart type
// (line/bar/area/wordcloud) sits at one column so two can sit side by side.
function visualizationSpan(vs: any): string {
  const type = vs != null && typeof vs === "object" ? vs.type : undefined
  return type === "stats" || type === "heatmap" ? "md:col-span-2" : ""
}

function searchRows(rows: PropsUITableRow[], search: string): Set<string> | undefined {
  if (search.trim() === "") return undefined

  // Not sure whether it's better to look for one of the words or exact string.
  // Now going for exact string. Note that if you change this, you should also change
  // the highlighting behavior in table.tsx (<Highlighter searchWords.../>)
  // const query = search.trim().split(/\s+/)
  const query = [search.trim()]

  const regexes: RegExp[] = []
  for (const q of query) {
    regexes.push(new RegExp(q.replace(/[-/\\^$*+?.()|[\]{}]/, "\\$&"), "i"))
  }

  const ids = new Set<string>()
  for (const row of rows) {
    for (const regex of regexes) {
      let anyCellMatches = false
      for (const cell of row.cells) {
        if (regex.test(cell)) {
          anyCellMatches = true
          break
        }
      }
      if (anyCellMatches) ids.add(row.id)
    }
  }

  return ids
}

const zoomInIcon = (
  <svg
    className="h-6 w-6"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6"
    />
  </svg>
)

const zoomOutIcon = (
  <svg
    className="h-6 w-6"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM13.5 10.5h-6"
    />
  </svg>
)

function getTranslations(locale: string): Record<string, string> {
  return resolveAll(translations, locale)
}

const translations = {
  searchPlaceholder: new TextBundle()
    .add("en", "Search")
    .add("nl", "Zoeken")
    .add("de", "Suchen")
    .add("it", "Cerca")
    .add("es", "Buscar"),
  showTable: new TextBundle()
    .add("en", "Show table")
    .add("nl", "Tabel tonen")
    .add("de", "Tabelle anzeigen")
    .add("it", "Mostra tabella")
    .add("es", "Mostrar tabla"),
  hideTable: new TextBundle()
    .add("en", "Hide table")
    .add("nl", "Tabel verbergen")
    .add("de", "Tabelle ausblenden")
    .add("it", "Nascondi tabella")
    .add("es", "Ocultar tabla"),
  // Review variant only — templated ("{n}" replaced with the localized row
  // count) since word order around a count differs by language.
  showRowsTemplate: new TextBundle()
    .add("en", "Show {n} rows")
    .add("nl", "Toon {n} rijen")
    .add("de", "{n} Zeilen anzeigen")
    .add("it", "Mostra {n} righe")
    .add("es", "Mostrar {n} filas"),
  hideRows: new TextBundle()
    .add("en", "Hide rows")
    .add("nl", "Verberg rijen")
    .add("de", "Zeilen ausblenden")
    .add("it", "Nascondi righe")
    .add("es", "Ocultar filas"),
  noEntries: new TextBundle()
    .add("en", "No entries in this export")
    .add("nl", "Geen items in dit exportbestand")
    .add("de", "Keine Einträge in diesem Export")
    .add("it", "Nessuna voce in questa esportazione")
    .add("es", "Sin entradas en esta exportación"),
}
