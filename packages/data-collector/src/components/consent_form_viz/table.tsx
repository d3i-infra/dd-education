import {
    useEffect,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
    ReactNode,
    ReactElement,
    Dispatch,
    SetStateAction
} from 'react'
import Highlighter from 'react-highlight-words'
import {
    TableWithContext,
} from './types'
import UndoSvg from './assets/images/undo.svg'
import DeleteSvg from './assets/images/delete.svg'
import { Pagination } from './pagination'
import TextBundle from '@eyra/feldspar'
import { resolveAll } from '../../locale/text'
import { CheckBox } from "./check_box"
import { PropsUITableRow } from "./types"
import { distributeColumnWidths, longestCellChars, CHECKBOX_COLUMN_PX } from './column_widths'


export interface Props {
  table: TableWithContext
  show: boolean
  locale: string
  search: string
  unfilteredRows: number
  handleDelete?: (rowIds: string[]) => void
  handleUndo?: () => void
  pageSize?: number
}

interface Tooltip {
  show: boolean
  content: ReactNode
  x: number
  y: number
}

export const Table = ({
  table,
  show,
  locale,
  search,
  unfilteredRows,
  handleDelete,
  handleUndo,
  pageSize = 7
}: Props): ReactElement => {
  const [page, setPage] = useState(0)
  const columnNames = table.head.cells
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const ref = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [availableWidth, setAvailableWidth] = useState(0)
  const nPages = Math.ceil(table.body.rows.length / pageSize)
  const selectedLabel = selected.size.toLocaleString(locale, { useGrouping: true })
  const text = useMemo(() => getTranslations(locale), [locale])

  const [tooltip, setTooltip] = useState<Tooltip>({
    show: false,
    content: null,
    x: 0,
    y: 0
  })

  const cellClass = 'min-h-[2.1rem] md:min-h-[2.5rem] px-3 flex items-center font-table-row'
  // Task 8 polish: the header row is visually distinct from data rows via
  // weight, not a zebra background — font-table-header instead of the body
  // cells' font-table-row.
  const headerCellClass = 'min-h-[2.1rem] md:min-h-[2.5rem] px-3 flex items-center font-table-header'
  // Hairline separators (1px), not the heavier 2px rule the rest of the
  // fork's tables use elsewhere -- review tables read denser, so a lighter
  // rule keeps rows from looking boxed in.
  const rowBorderClass = 'border-b border-grey4'

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- PENDING_ISSUES "lint hygiene" entry 2026-08-26: pagination reset on table swap; fix needs ADR-0031-safe redesign
    setSelected(new Set())
    setPage((page) => Math.max(0, Math.min(page, nPages - 1)))
  }, [table, nPages])

  useLayoutEffect(() => {
    // Column widths are laid out in pixels, so they have to follow the width the
    // table actually gets.
    if (typeof ResizeObserver === 'undefined') return // jsdom
    const element = scrollRef.current
    if (element == null) return
    const observer = new ResizeObserver((entries) => {
      setAvailableWidth(entries[entries.length - 1].contentRect.width)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    // rm tooltip on scroll
    function rmTooltip (): void {
      setTooltip((tooltip: Tooltip) => (tooltip.show ? { ...tooltip, show: false } : tooltip))
    }
    window.addEventListener('scroll', rmTooltip)
    return () => window.removeEventListener('scroll', rmTooltip)
  })

  useLayoutEffect(() => {
    // set exact height of grid row for height transition
    if (ref.current == null || innerRef.current == null) return
    if (!show || unfilteredRows === 0) {
      ref.current.style.gridTemplateRows = '0rem'
      return
    }

    function responsiveHeight (): void {
      if (ref.current == null || innerRef.current == null) return
      ref.current.style.gridTemplateRows = `${innerRef.current.scrollHeight}px`
    }
    responsiveHeight()
    // just as a precaution, update height every second in case it changes
    const interval = setInterval(responsiveHeight, 1000)
    return () => clearInterval(interval)
  }, [ref, innerRef, show, nPages, unfilteredRows])

  // Length of the longest value per column, which drives the column widths
  // below. Taken from originalBody (ADR-0031) so the layout does not jump
  // around while the participant searches, deletes rows or pages through the
  // table.
  const charCounts = useMemo(
    () => longestCellChars(table, columnNames),
    [table.originalBody, table.headers, columnNames]
  )

  const columnWidths = useMemo(() => {
    if (availableWidth === 0 || charCounts.length === 0) return null
    const forColumns = availableWidth - (table.deleteOption ? CHECKBOX_COLUMN_PX : 0)
    return distributeColumnWidths(charCounts, forColumns)
  }, [charCounts, availableWidth, table.deleteOption])

  // Wider than the container when the columns did not fit, which is what makes
  // the table scroll horizontally instead of squeezing the values further.
  const tableWidth =
    columnWidths == null
      ? 0
      : columnWidths.reduce((sum, width) => sum + width, table.deleteOption ? CHECKBOX_COLUMN_PX : 0)

  const items = useMemo(() => {
    const items: Array<PropsUITableRow | null> = new Array(pageSize).fill(null)
    for (let i = 0; i < pageSize; i++) {
      const index = page * pageSize + i
      if (table.body.rows[index] !== undefined) items[i] = table.body.rows[index]
    }
    return items
  }, [table, page, pageSize])

  function renderHeaderCell (value: string, i: number): ReactElement {
    // Display translated header if available, fall back to raw column name
    const displayName = table.headers?.[value] ?? value
    return (
      <th key={`header ${i}`}>
        <div className={`text-left ${headerCellClass}`}>
          <div>{displayName}</div>
        </div>
      </th>
    )
  }

  function renderRow (item: PropsUITableRow | null, i: number): ReactElement | null {
    if (item == null && i >= unfilteredRows) return null
    if (item == null) {
      return (
        <tr key={`{empty ${i}`} className={rowBorderClass}>
          <td>
            <div className={cellClass} />
          </td>
        </tr>
      )
    }
    return (
      <tr key={item.id} className={rowBorderClass}>
        {table.deleteOption &&
          (
            <td key='select'>
              <CheckBox
                id={item.id}
                size='w-6 h-6'
                selected={selected.has(item.id)}
                onSelect={() => toggleSelected(item.id)}
              />
            </td>
          )
        }

        {item.cells.map((cell, j) => (
          <td key={j}>
            <Cell cell={cell} search={search} cellClass={cellClass} setTooltip={setTooltip} layoutKey={tableWidth} />
          </td>
        ))}
      </tr>
    )
  }

  function toggleSelected (id: string): void {
    if (selected.has(id)) {
      selected.delete(id)
    } else {
      selected.add(id)
    }
    setSelected(new Set(selected))
  }

  function toggleSelectAll (): void {
    if (selected.size === table.body.rows.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(table.body.rows.map((row) => row.id)))
    }
  }

  return (
    <div
      ref={ref}
      className='grid grid-cols-1 transition-[grid,color] duration-500 relative overflow-hidden text-sm md:text-base'
    >
      <div ref={innerRef} className={`h-min ${unfilteredRows === 0 ? 'invisible' : ''}`}>
        <div className='my-2 bg-grey6 rounded-md border-grey4 border-[0.2rem]'>
          {/* relative wrapper is NOT the scrolling element itself -- an
              absolutely-positioned child of the overflow-x-auto div below
              would scroll away with the content instead of staying pinned to
              the visible right edge, defeating the hint. */}
          <div className='relative'>
            <div ref={scrollRef} className='p-3 pt-1 pb-2 max-w-full overflow-x-auto'>
              <table
                className='table-fixed'
                // Widths are only known once the container has been measured; until
                // then fall back to letting the browser divide the space evenly.
                style={columnWidths == null ? { width: '100%' } : { width: `${tableWidth}px` }}
              >
                {columnWidths != null && (
                  <colgroup>
                    {table.deleteOption && <col style={{ width: `${CHECKBOX_COLUMN_PX}px` }} />}
                    {columnWidths.map((width, i) => (
                      <col key={`col ${i}`} style={{ width: `${width}px` }} />
                    ))}
                  </colgroup>
                )}
                <thead className=''>
                  <tr className={rowBorderClass}>
                    {table.deleteOption &&
                      (
                        <td className='w-8'>
                          <CheckBox
                            id='selectAll'
                            size='w-6 h-6'
                            selected={table.body.rows.length > 0 && selected.size === table.body.rows.length}
                            onSelect={toggleSelectAll}
                          />
                        </td>
                      )
                    }
                    {columnNames.map(renderHeaderCell)}
                  </tr>
                </thead>
                <tbody>{items.map(renderRow)}</tbody>
              </table>
            </div>
            {/* Sideways-scroll hint: only when the table is actually wider than
                the space it has (jsdom has no ResizeObserver, so availableWidth
                stays 0 and this branch never renders there). */}
            {tableWidth > availableWidth && (
              <div
                aria-hidden='true'
                className='pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-grey6'
              />
            )}
          </div>
          <div className='px-3 pb-1 flex justify-between min-h-[2.5rem]'>
            <div className='pt-2 pb-2'>
              {selected.size > 0 || table.deletedRowCount === 0
                ? (
                  <IconButton
                    icon={DeleteSvg}
                    label={`${text.delete} ${selected.size > 0 ? selectedLabel : ''}`}
                    color='text-delete'
                    disabled={selected.size === 0}
                    hidden={!table.deleteOption}
                    onClick={() => handleDelete?.(Array.from(selected))}
                  />
                  )
                : (
                  <IconButton icon={UndoSvg} label={text.undo} color='text-primary' onClick={() => handleUndo?.()} />
                  )}
            </div>
            <Pagination page={page} setPage={setPage} nPages={nPages} />
          </div>
        </div>
        <div
          className={`${
            tooltip.show ? '' : 'invisible'
          } break-all fixed bg-[#222a] -translate-x-2 -translate-y-2 p-2  rounded text-white backdrop-blur-[2px] z-20 max-w-[20rem] pointer-events-none overflow-auto font-table-row`}
          style={{ left: tooltip.x, top: tooltip.y } as any}
        >
          {tooltip.content}
        </div>
      </div>
    </div>
  )
}

function isCoarsePointer (): boolean {
  return window.matchMedia?.('(pointer: coarse)')?.matches === true
}

function Cell ({
  cell,
  search,
  cellClass,
  setTooltip,
  layoutKey
}: {
  cell: string
  search: string
  cellClass: string
  setTooltip: Dispatch<SetStateAction<Tooltip>>
  layoutKey: number
}): ReactElement {
  const textRef = useRef<HTMLDivElement>(null)
  const [overflows, setOverflows] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const isUrl = /^https?:\/\//.test(cell)

  const searchWords = useMemo(() => {
    return [search]
    // return search.split(' ') // alternative: highlight individual words
  }, [search])

  useEffect(() => {
    if (textRef.current == null) return
    setOverflows(textRef.current.scrollWidth > textRef.current.clientWidth)
    // Column widths (layoutKey) settle after the first paint, and the value a
    // cell is truncated at only changes once they do.
  }, [textRef, layoutKey])

  function onSetTooltip (): void {
    if (isUrl) return
    if (textRef.current == null) return
    if (!overflows) return

    const rect = textRef.current.getBoundingClientRect()

    const content = (
      <Highlighter
        searchWords={searchWords}
        autoEscape
        textToHighlight={cell}
        highlightClassName='bg-tertiary rounded-sm'
      />
    )

    setTooltip({
      show: true,
      content,
      x: rect.x,
      y: rect.y
    })
  }

  function onRmTooltip (): void {
    setTooltip((tooltip: Tooltip) => (tooltip.show ? { ...tooltip, show: false } : tooltip))
  }

  function onClick (): void {
    // Touch devices have no hover tooltip; tap the truncated cell to expand
    // it in place instead. Fine pointers keep the existing tooltip behaviour.
    // An expanded cell always collapses on tap: once expanded its text wraps,
    // so `overflows` reads false and could otherwise never let it close
    // (Task 6 review).
    if (isCoarsePointer() && (expanded || overflows)) {
      setExpanded((expanded) => !expanded)
      return
    }
    onSetTooltip()
  }

  return (
    <div
      className={`relative ${cellClass}`}
      onMouseEnter={onSetTooltip}
      onMouseLeave={onRmTooltip}
      onClick={onClick}
    >
      <div
        ref={textRef}
        className={
          expanded
            ? 'whitespace-normal break-words min-w-0 flex-1'
            : 'whitespace-nowrap min-w-0 flex-1 overflow-hidden overflow-ellipsis z-10'
        }
      >
        {isUrl
          ? (
            <a href={cell} className='text-primary' target='_blank' rel='noopener noreferrer'>
              <Highlighter
                searchWords={searchWords}
                autoEscape
                textToHighlight={cell}
                highlightClassName='bg-tertiary rounded-sm'
              />
            </a>
            )
          : (
            <Highlighter
              searchWords={searchWords}
              autoEscape
              textToHighlight={cell}
              highlightClassName='bg-tertiary rounded-sm'
            />
            )}
      </div>
      {overflows && !isUrl && <TooltipIcon />}
    </div>
  )
}

function TooltipIcon (): ReactElement {
  return (
    <svg
      className='w-3 h-3 mb-1 shrink-0 text-gray-800 dark:text-white'
      aria-hidden='true'
      xmlns='http://www.w3.org/2000/svg'
      fill='none'
      viewBox='0 0 10 16'
    >
      <path
        stroke='currentColor'
        strokeLinecap='round'
        strokeLinejoin='round'
        strokeWidth='2'
        d='m2.707 14.293 5.586-5.586a1 1 0 0 0 0-1.414L2.707 1.707A1 1 0 0 0 1 2.414v11.172a1 1 0 0 0 1.707.707Z'
      />
    </svg>
  )
}

function IconButton (props: {
  icon: string
  label: string
  onClick: () => void
  color: string
  disabled?: boolean
  hidden?: boolean
}): ReactElement | null {
  if (props.hidden ?? false) return null
  const disabled = props.disabled ?? false
  return (
    <div
      className={`flex items-center gap-2 cursor-pointer  ${props.color} animate-fadeIn md:text-button ${
        disabled ? 'opacity-50' : ''
      }`}
      onClick={() => !disabled && props.onClick()}
    >
      <img src={props.icon} className='w-7 h-7 ml-1 md:w-9 md:h-9 md:ml-0 -translate-x-[3px]' />
      {props.label}
    </div>
  )
}

function getTranslations (locale: string): Record<string, string> {
  return resolveAll(translations, locale)
}

const translations = {
  delete: new TextBundle()
    .add('en', 'Delete')
    .add('nl', 'Verwijder')
    .add('de', 'Löschen')
    .add('it', 'Elimina')
    .add('es', 'Eliminar'),
  undo: new TextBundle()
    .add('en', 'Undo')
    .add('nl', 'Herstel')
    .add('de', 'Rückgängig')
    .add('it', 'Annulla')
    .add('es', 'Deshacer')
}
