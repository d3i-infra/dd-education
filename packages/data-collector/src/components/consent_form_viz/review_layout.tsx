import { useCallback, useEffect, useMemo, useRef, useState, ReactElement } from "react"
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

interface ReviewLayoutProps {
  tables: TableWithContext[]
  updateTable: (tableId: string, table: TableWithContext) => void
  locale: string
  description: string
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

  const [activeId, setActiveId] = useState<string | undefined>(orderedTables[0]?.id)

  const orderedIds = orderedTables.map((t) => t.id).join(",")

  // Highlights the chip for whichever card is currently under the sticky
  // strip. jsdom (and any environment without IntersectionObserver) simply
  // skips this — chips still render and still scroll on click.
  useEffect(() => {
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
      // view" for chip-highlighting purposes once it's in the top 40%.
      { rootMargin: "-112px 0px -60% 0px", threshold: [0, 0.5, 1] }
    )

    nodes.forEach(([, node]) => observer.observe(node))
    return () => observer.disconnect()
  }, [orderedIds])

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

  return (
    <div className="flex flex-col gap-4 w-full">
      <nav aria-label={text.navLabel} className="sticky top-0 z-[60] bg-white border-b-[0.2rem] border-grey4">
        <div className="flex gap-2 overflow-x-auto scrollbar-hide py-3">
          {orderedTables.map((table) => {
            const isActive = table.id === activeId
            const count = table.body.rows.length.toLocaleString(locale, { useGrouping: true })
            return (
              <button
                key={table.id}
                type="button"
                data-chip-id={table.id}
                aria-current={isActive ? "true" : undefined}
                onClick={() => scrollToCard(table.id)}
                className={`shrink-0 flex items-baseline gap-1.5 rounded-full border-2 px-4 py-2 font-label text-labelsmall md:text-label transition-colors ${
                  isActive ? "bg-primarylight border-primary text-primary" : "bg-white border-grey4 text-grey1"
                }`}
              >
                <span>{table.title}</span>
                <span className={isActive ? "text-primary" : "text-grey2"}>({count})</span>
              </button>
            )
          })}
        </div>
      </nav>

      <p className="text-caption font-body text-grey1">{description}</p>

      <div className="flex flex-col gap-4">
        {orderedTables.map((table) => (
          <div key={table.id} data-card-id={table.id} ref={registerCard(table.id)} className="scroll-mt-24">
            <TableContainer id={table.id} table={table} updateTable={updateTable} locale={locale} variant="review" />
          </div>
        ))}
      </div>
    </div>
  )
}

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
}
