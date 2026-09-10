import { KeyboardEvent, ReactElement, useMemo, useState } from 'react'
import { resolveFlatText } from '../../../../locale/text'
import { Thread, ThreadTurn, ThreadVisualizationData } from '../types'

interface Props {
  visualizationData: ThreadVisualizationData
  locale: string
}

// Two panes from md up (list left, transcript right); below md they stack,
// list first. Both panes page their own list independently (threads /
// turns), each with its own Previous/Next and an arrow-key shortcut for the
// same action -- see handlePageKey.
//
// The mobile-only classes are written as `max-md:` variants on purpose.
// index.tsx imports @eyra/feldspar's compiled stylesheet after this
// package's own, and both are Tailwind 4 with the same `utilities` layer, so
// a bare utility feldspar also emits (`flex-col`, for one) lands later in
// the cascade than our `md:` override of it and wins at every width -- the
// panes stacked on desktop in Danielle's live run. `max-md:` variants only
// ever apply below md, so there is nothing for a later plain rule to undo.
export default function ThreadView ({ visualizationData, locale }: Props): ReactElement | null {
  const { threads, truncated, totalThreads, pageSize, selfRole } = visualizationData
  const text = useMemo(() => prepareTexts(locale), [locale])

  const [search, setSearch] = useState('')
  const [listPage, setListPage] = useState(0)
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  const [turnPage, setTurnPage] = useState(0)

  const filtered = useMemo(() => filterThreads(threads, search, locale), [threads, search, locale])

  // Defensive only: figure.tsx already renders its own "no data" fallback
  // for an empty threads list (see RenderVisualization), the same
  // belt-and-suspenders split heatmap.tsx uses.
  if (threads.length === 0) return null

  const listPageCount = Math.max(1, Math.ceil(filtered.length / pageSize.threads))
  const clampedListPage = Math.min(listPage, listPageCount - 1)
  const listStart = clampedListPage * pageSize.threads
  const pageThreads = filtered.slice(listStart, listStart + pageSize.threads)

  const selected = filtered.find((thread) => thread.id === selectedId)
  const turnPageCount = selected !== undefined ? Math.max(1, Math.ceil(selected.turns.length / pageSize.turns)) : 1
  const clampedTurnPage = Math.min(turnPage, turnPageCount - 1)
  const turnStart = clampedTurnPage * pageSize.turns
  const pageTurns = selected !== undefined ? selected.turns.slice(turnStart, turnStart + pageSize.turns) : []

  function handleSearch (value: string): void {
    setSearch(value)
    setListPage(0)
  }

  function selectThread (thread: Thread): void {
    setSelectedId(thread.id)
    setTurnPage(0)
  }

  function pageList (delta: number): void {
    setListPage((page) => clamp(page + delta, 0, listPageCount - 1))
  }

  function pageTurnsBy (delta: number): void {
    setTurnPage((page) => clamp(page + delta, 0, turnPageCount - 1))
  }

  // min-w-0: as a grid item the root's automatic minimum is its min-content
  // width, and one long unbreakable token in a message would then widen the
  // figure row past the card (Danielle, live run).
  return (
    // Task 8 polish: gap-3 to match the "gap-3 inside" card rhythm — this
    // layout lives one level inside a card's figure wrapper, so it follows
    // the same interior scale as everything else in there.
    <div className='w-full min-w-0 flex max-md:flex-col gap-3 p-2'>
      <div
        data-pane='list'
        className='flex flex-col gap-2 md:w-1/3 min-w-0 min-h-[32rem]'
        onKeyDown={(e) => handlePageKey(e, pageList)}
      >
        {truncated && (
          <div data-truncated-notice className='text-captionsmall text-grey2 bg-grey5 rounded-md px-3 py-1.5'>
            {truncationMessage(text, threads.length, totalThreads)}
          </div>
        )}
        <input
          type='search'
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={text.searchPlaceholder}
          aria-label={text.searchPlaceholder}
          className='text-grey1 font-body px-3 w-full border-2 border-solid border-grey3 focus:outline-none focus:border-primary rounded-lg h-9'
        />
        {/* No fixed/flex-1 height here: a page (<=20 items) lays out at its
            natural height, so the page control -- not an inner scrollbar --
            is what "sees more" of the list. max-h/overflow only guards
            against a pathologically tall page (very long titles wrapping). */}
        <div className='flex flex-col gap-1 max-h-[70vh] overflow-y-auto' role='list'>
          {pageThreads.length === 0 && <div className='text-captionsmall text-grey2 p-2'>{text.noResults}</div>}
          {pageThreads.map((thread) => (
            <button
              key={thread.id}
              type='button'
              data-thread-id={thread.id}
              onClick={() => selectThread(thread)}
              aria-pressed={thread.id === selectedId}
              className={`text-left rounded-md px-3 py-2 border-[0.15rem] ${
                thread.id === selectedId ? 'border-primary bg-primary/10' : 'border-grey4 hover:border-grey3'
              }`}
            >
              <div className='font-bodybold text-sm truncate'>{resolveFlatText(thread.title, locale)}</div>
              <div className='text-captionsmall text-grey2'>
                {dateRange(thread, locale)}
                {dateRange(thread, locale) !== '' ? ' · ' : ''}
                {turnCountLabel(thread.count, text)}
              </div>
            </button>
          ))}
        </div>
        <PageControls
          page={clampedListPage}
          pageCount={listPageCount}
          start={filtered.length === 0 ? 0 : listStart + 1}
          end={Math.min(listStart + pageSize.threads, filtered.length)}
          total={filtered.length}
          text={text}
          onPrevious={() => pageList(-1)}
          onNext={() => pageList(1)}
        />
      </div>

      <div
        data-pane='transcript'
        className='flex flex-col flex-1 min-w-0 min-h-[32rem] gap-2 max-md:border-t md:border-l border-grey4 max-md:pt-3 md:pl-3'
        onKeyDown={(e) => handlePageKey(e, pageTurnsBy)}
      >
        {selected === undefined
          ? <div className='flex-1 flex items-center justify-center text-grey2 text-sm'>{text.selectPrompt}</div>
          : (
            <>
              <div className='flex flex-col gap-2 p-1 max-h-[70vh] overflow-y-auto'>
                {pageTurns.map((turn, i) => (
                  <Bubble key={turnStart + i} turn={turn} isSelf={selfRole !== undefined && turn.role === selfRole} locale={locale} />
                ))}
              </div>
              <div className='flex items-center justify-between gap-2'>
                <PageControls
                  page={clampedTurnPage}
                  pageCount={turnPageCount}
                  start={selected.turns.length === 0 ? 0 : turnStart + 1}
                  end={Math.min(turnStart + pageSize.turns, selected.turns.length)}
                  total={selected.turns.length}
                  text={text}
                  onPrevious={() => pageTurnsBy(-1)}
                  onNext={() => pageTurnsBy(1)}
                />
                <button
                  type='button'
                  onClick={() => setTurnPage(turnPageCount - 1)}
                  disabled={clampedTurnPage >= turnPageCount - 1}
                  className={clampedTurnPage >= turnPageCount - 1 ? 'text-grey3' : 'text-primary'}
                >
                  {text.jumpToLatest}
                </button>
              </div>
            </>
            )}
      </div>
    </div>
  )
}

function Bubble ({ turn, isSelf, locale }: { turn: ThreadTurn, isSelf: boolean, locale: string }): ReactElement {
  return (
    <div className={`flex ${isSelf ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] md:max-w-[70%] rounded-lg px-3 py-2 whitespace-pre-wrap wrap-anywhere text-sm ${
          isSelf ? 'bg-primary text-white' : 'bg-grey5 text-grey1'
        }`}
      >
        <div>{turn.text}</div>
        {(turn.time !== undefined || turn.badge !== undefined) && (
          <div className={`mt-1 flex gap-2 text-captionsmall ${isSelf ? 'text-white/80' : 'text-grey2'}`}>
            {turn.time !== undefined && <span>{formatTime(turn.time, locale)}</span>}
            {turn.badge !== undefined && <span>{turn.badge}</span>}
          </div>
        )}
      </div>
    </div>
  )
}

function PageControls ({
  page,
  pageCount,
  start,
  end,
  total,
  text,
  onPrevious,
  onNext
}: {
  page: number
  pageCount: number
  start: number
  end: number
  total: number
  text: Record<string, string>
  onPrevious: () => void
  onNext: () => void
}): ReactElement {
  return (
    <div className={`flex items-center justify-between gap-2 text-captionsmall ${pageCount <= 1 ? 'invisible' : ''}`}>
      <button type='button' onClick={onPrevious} disabled={page <= 0} className={page <= 0 ? 'text-grey3' : 'text-primary'}>
        {text.previous}
      </button>
      <div className='text-grey2'>{`${start}–${end} ${text.of} ${total}`}</div>
      <button
        type='button'
        onClick={onNext}
        disabled={page >= pageCount - 1}
        className={page >= pageCount - 1 ? 'text-grey3' : 'text-primary'}
      >
        {text.next}
      </button>
    </div>
  )
}

// Enter already selects a thread for free -- list items are real <button>
// elements, so the browser fires onClick on Enter/Space with no extra code.
// This only needs to handle the paging shortcut: the arrow key that matches
// each pane's Previous/Next direction, from anywhere focus lands inside it.
function handlePageKey (e: KeyboardEvent<HTMLDivElement>, page: (delta: number) => void): void {
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    page(-1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    page(1)
  }
}

function clamp (value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max))
}

function filterThreads (threads: Thread[], search: string, locale: string): Thread[] {
  const query = search.trim().toLowerCase()
  if (query === '') return threads
  return threads.filter((thread) => {
    if (resolveFlatText(thread.title, locale).toLowerCase().includes(query)) return true
    return thread.turns.some((turn) => turn.text.toLowerCase().includes(query))
  })
}

function dateRange (thread: Thread, locale: string): string {
  if (thread.firstTime === undefined) return ''
  const first = formatDay(thread.firstTime, locale)
  if (thread.lastTime === undefined || thread.lastTime === thread.firstTime) return first
  return `${first} – ${formatDay(thread.lastTime, locale)}`
}

function formatDay (iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatTime (iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })
}

function turnCountLabel (count: number, text: Record<string, string>): string {
  return `${count} ${count === 1 ? text.turnSingular : text.turnPlural}`
}

// text.truncatedNotice carries '{count}'/'{total}' placeholders (this file's
// own tiny templating -- prepareThreadData.ts's truncated/totalThreads are
// the only two fields here that ever need one).
function truncationMessage (text: Record<string, string>, count: number, total: number): string {
  return text.truncatedNotice.replace('{count}', String(count)).replace('{total}', String(total))
}

function prepareTexts (locale: string): Record<string, string> {
  const texts = {
    noResults: { en: 'No conversations match your search', nl: 'Geen gesprekken komen overeen met je zoekopdracht' },
    searchPlaceholder: { en: 'Search conversations', nl: 'Zoek in je gesprekken' },
    selectPrompt: { en: 'Select a conversation to read it', nl: 'Kies een gesprek om te lezen' },
    previous: { en: 'Previous', nl: 'Vorige' },
    next: { en: 'Next', nl: 'Volgende' },
    of: { en: 'of', nl: 'van' },
    jumpToLatest: { en: 'Jump to latest', nl: 'Naar het laatste bericht' },
    turnSingular: { en: 'message', nl: 'bericht' },
    turnPlural: { en: 'messages', nl: 'berichten' },
    truncatedNotice: {
      en: 'Showing the first {count} of {total} conversations',
      nl: 'De eerste {count} van {total} gesprekken worden getoond'
    }
  }

  const resolved: Record<string, string> = {}
  for (const [key, bundle] of Object.entries(texts)) resolved[key] = resolveFlatText(bundle, locale)
  return resolved
}
