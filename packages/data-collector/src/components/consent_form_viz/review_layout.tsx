import { useCallback, useEffect, useMemo, useRef, useState, ReactElement, KeyboardEvent } from "react"
import TextBundle from "@eyra/feldspar"
import { resolveAll } from "../../locale/text"
import { TableWithContext } from "./types"
import { TableContainer } from "./table_container"

// Design pass (frontend-design skill, Task 19 — review-only education mode):
// - Type scale: card titles keep study mode's Title4 (28px, via
//   table_container's "review" variant) so a card reads at the same weight
//   as its upstream counterpart; the description drops to caption (14px) so
//   neither it nor the platform header competes with the figures above them —
//   the header is a plain wrapping paragraph, no line clamp; chips use
//   label/labelsmall — small enough that a dozen still fit across a phone
//   width.
// - Card treatment: white surface with the same grey4 hairline border and
//   radius table_container's study card already uses, so review mode reads
//   as a continuation of the fork's visual language rather than a new one.
//   An empty table gets a flatter grey6 strip instead of a full card — there
//   is nothing to look at, so it shouldn't claim card-sized weight.
// - Chip style: rounded pill toggles — primarylight fill + primary text/
//   border for the section currently in view, grey4 border otherwise. No
//   drop shadow, no new hue: just the two states a "where am I" strip needs.
//
// Design pass (frontend-design skill, Task 21 fix round 2, variant A —
// approved mockup): the pill chip strip is gone. One sticky navigation row
// now carries Previous, the page names as text tabs (`font-bold`, a
// `border-secondary` underline on the current one — coral marks "you are
// here", the same role it plays below), the "{i} of {n}" count, and Next.
// Below it, overview-only, a plain-text "Jump to" line does what the old
// grouped-chip pills did — no borders, no pills, just underline-on-hover
// links with the in-view entry picked out in `text-primary`, the same blue
// as the chevrons. Coral (`secondary`) is reserved for the current page tab,
// so the two levels of "where am I" — which page, which card — read as two
// different colours (Danielle's acceptance of the mockup hinged on that).

interface ReviewLayoutProps {
  tables: TableWithContext[]
  updateTable: (tableId: string, table: TableWithContext) => void
  locale: string
  description: string
}

// A table dense enough to want its own page: a thread figure's two-pane
// list+transcript needs room the overview grid can't give it, and four or
// more figures of any kind crowd a shared scroll just as much.
export function isFeaturedTable(table: TableWithContext): boolean {
  const vis = table.visualizations ?? []
  return vis.some((v: any) => v?.type === "thread") || vis.length >= 4
}

export const ReviewLayout = ({ tables, updateTable, locale, description }: ReviewLayoutProps): ReactElement => {
  const text = useMemo(() => getTranslations(locale), [locale])
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  // Tables with zero rows sink to the end; everything else keeps the order
  // Python sent it in. Recomputed on every table update, so a table emptied
  // by the participant's own deletions sinks too, not just ones born empty.
  const orderedTables = useMemo(() => {
    const withRows = tables.filter((t) => t.body.rows.length > 0)
    const empty = tables.filter((t) => t.body.rows.length === 0)
    return [...withRows, ...empty]
  }, [tables])

  const featured = useMemo(() => orderedTables.filter(isFeaturedTable), [orderedTables])
  const grouped = useMemo(() => orderedTables.filter((t) => !isFeaturedTable(t)), [orderedTables])

  // The review as a sequence of equal pages: page 1 is the overview, pages
  // 2..n are the featured tables, in the same order as their tabs.
  const pageIds = useMemo(() => ["overview", ...featured.map((t) => t.id)], [featured])

  // "overview" or a featured table's id — which page is showing. A featured
  // table's own page mounts only that table (keyed on its id below), so its
  // figures — and any Worker a thread figure spins up — unmount cleanly when
  // the viewer moves on rather than re-rendering in place.
  const [requestedView, setView] = useState<string>("overview")
  // Derived, not reconciled in an effect: when the host replaces the tables
  // (a new upload) while a featured page is open, the id the participant was
  // looking at may be gone or no longer featured. Falling back to the
  // overview during render keeps the page from going blank until a chip is
  // clicked (Task 7 review).
  const view = requestedView === "overview" || featured.some((t) => t.id === requestedView) ? requestedView : "overview"
  const [activeId, setActiveId] = useState<string | undefined>(grouped[0]?.id)

  const groupedIds = grouped.map((t) => t.id).join(",")

  // Highlights the "Jump to" entry for whichever grouped card is currently
  // under the sticky strip. Only meaningful on the overview — the featured
  // pages have no scroll position to track, and their cards aren't in
  // cardRefs anyway (they're never registered there). jsdom (and any
  // environment without IntersectionObserver) simply skips this — the jump
  // line still renders and still scrolls on click.
  useEffect(() => {
    if (view !== "overview") return
    if (typeof IntersectionObserver === "undefined") return
    const nodes = Array.from(cardRefs.current.entries())
    if (nodes.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const topmost = visible.reduce((a, b) => (a.boundingClientRect.top <= b.boundingClientRect.top ? a : b))
        const id = (topmost.target as HTMLElement).dataset.cardId
        if (id !== undefined) setActiveId(id)
      },
      // Excludes the sticky strip itself (~top) and treats a card as "in
      // view" for jump-line-highlighting purposes once it's in the top 40%.
      { rootMargin: "-112px 0px -60% 0px", threshold: [0, 0.5, 1] }
    )

    nodes.forEach(([, node]) => observer.observe(node))
    return () => observer.disconnect()
  }, [groupedIds, view])

  const registerCard = useCallback(
    (id: string) =>
      (el: HTMLDivElement | null): void => {
        if (el != null) cardRefs.current.set(id, el)
        else cardRefs.current.delete(id)
      },
    []
  )

  function scrollToCard(id: string): void {
    cardRefs.current.get(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" })
  }

  const pageIndex = Math.max(0, pageIds.indexOf(view))
  const countText = text.page.replace("{i}", String(pageIndex + 1)).replace("{n}", String(pageIds.length))

  function goToPage(delta: number): void {
    const target = pageIds[pageIndex + delta]
    if (target !== undefined) setView(target)
  }

  function handlePagerKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "ArrowLeft") {
      event.preventDefault()
      goToPage(-1)
    } else if (event.key === "ArrowRight") {
      event.preventDefault()
      goToPage(1)
    }
  }

  const currentFeaturedTable = view === "overview" ? undefined : featured.find((t) => t.id === view)

  return (
    <div className="flex flex-col gap-4 w-full">
      <nav aria-label={text.navLabel} className="sticky top-0 z-[60] bg-white border-b-[0.2rem] border-grey4 py-3">
        {/* Previous / page tabs / count / Next — one row, identical on every page. */}
        <div data-pager className="flex items-center gap-3" onKeyDown={handlePagerKeyDown}>
          <button
            type="button"
            aria-label={text.previous}
            disabled={pageIndex === 0}
            onClick={() => goToPage(-1)}
            className="h-[40px] w-[40px] shrink-0 flex items-center justify-center rounded-lg border-2 border-grey3 text-primary hover:border-primary disabled:opacity-40 disabled:cursor-default"
          >
            {chevronLeftIcon}
          </button>

          <div className="flex-1 min-w-0 flex flex-wrap items-baseline gap-x-5 gap-y-1">
            <button
              type="button"
              data-overview-chip
              aria-current={view === "overview" ? "page" : undefined}
              onClick={() => setView("overview")}
              className={tabClasses(view === "overview")}
            >
              {text.overview}
            </button>
            {featured.map((table) => {
              const isActive = table.id === view
              const count = table.body.rows.length.toLocaleString(locale, { useGrouping: true })
              return (
                <button
                  key={table.id}
                  type="button"
                  data-page-chip={table.id}
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => setView(table.id)}
                  className={tabClasses(isActive)}
                >
                  {table.title}
                  <span className="text-grey2 font-normal ml-1">({count})</span>
                </button>
              )
            })}
          </div>

          <span className="text-captionsmall text-grey2 whitespace-nowrap tabular-nums">{countText}</span>

          <button
            type="button"
            aria-label={text.next}
            disabled={pageIndex === pageIds.length - 1}
            onClick={() => goToPage(1)}
            className="h-[40px] w-[40px] shrink-0 flex items-center justify-center rounded-lg border-2 border-grey3 text-primary hover:border-primary disabled:opacity-40 disabled:cursor-default"
          >
            {chevronRightIcon}
          </button>
        </div>

        {/* "Jump to" line — overview only, the grouped tables' in-page index. */}
        {view === "overview" ? (
          <div data-jump className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 mt-2.5 text-sm">
            <span className="text-grey2">{text.jumpTo}</span>
            {grouped.map((table, index) => {
              const isActive = table.id === activeId
              const count = table.body.rows.length.toLocaleString(locale, { useGrouping: true })
              return (
                <span key={table.id} className="contents">
                  {index > 0 ? (
                    <span aria-hidden="true" className="text-grey3">
                      ·
                    </span>
                  ) : null}
                  <button
                    type="button"
                    data-chip-id={table.id}
                    onClick={() => scrollToCard(table.id)}
                    className={`font-medium hover:underline ${isActive ? "text-primary" : "text-grey1"}`}
                  >
                    {table.title}
                    <span className="text-grey2 font-normal ml-0.5">({count})</span>
                  </button>
                </span>
              )
            })}
          </div>
        ) : null}
      </nav>

      {view === "overview" ? (
        <>
          <p className="text-caption font-body text-grey1 mt-4">{description}</p>
          <div className="flex flex-col gap-4">
            {grouped.map((table) => (
              <div key={table.id} data-card-id={table.id} ref={registerCard(table.id)} className="scroll-mt-24">
                <TableContainer id={table.id} table={table} updateTable={updateTable} locale={locale} variant="review" />
              </div>
            ))}
          </div>
        </>
      ) : currentFeaturedTable !== undefined ? (
        <div key={currentFeaturedTable.id} data-card-id={currentFeaturedTable.id} className="scroll-mt-24">
          <TableContainer
            id={currentFeaturedTable.id}
            table={currentFeaturedTable}
            updateTable={updateTable}
            locale={locale}
            variant="review"
          />
        </div>
      ) : null}
    </div>
  )
}

function tabClasses(isActive: boolean): string {
  return `font-body font-bold text-base py-1.5 border-b-[3px] transition-colors ${
    isActive ? "text-grey1 border-secondary" : "border-transparent text-grey2 hover:text-grey1"
  }`
}

const chevronLeftIcon = (
  <svg
    className="h-5 w-5"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
  </svg>
)

const chevronRightIcon = (
  <svg
    className="h-5 w-5"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
)

function getTranslations(locale: string): Record<string, string> {
  return resolveAll(translations, locale)
}

const translations = {
  navLabel: new TextBundle()
    .add("en", "Tables in this export")
    .add("nl", "Tabellen in dit exportbestand")
    .add("de", "Tabellen in diesem Export")
    .add("it", "Tabelle in questa esportazione")
    .add("es", "Tablas en esta exportación"),
  overview: new TextBundle().add("en", "Overview").add("nl", "Overzicht"),
  previous: new TextBundle().add("en", "Previous").add("nl", "Vorige"),
  next: new TextBundle().add("en", "Next").add("nl", "Volgende"),
  page: new TextBundle().add("en", "{i} of {n}").add("nl", "{i} van {n}"),
  jumpTo: new TextBundle().add("en", "Jump to").add("nl", "Ga naar"),
}
