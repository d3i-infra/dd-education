import { ReactElement } from 'react'
import { resolveFlatText } from '../../../../locale/text'
import { StatsVisualizationData } from '../types'

interface Props {
  visualizationData: StatsVisualizationData
  locale: string
}

// A responsive grid of cards: wraps on narrow (phone) viewports instead of
// squeezing tiles, and grows to fill the row on wide (laptop) viewports. A
// real CSS grid (not flex-wrap) so every tile in a row stretches to the
// tallest one instead of sitting at its own content height (Task 8 polish) —
// grid's default `align-items: stretch` does that for free; each tile then
// centres its own content vertically within that stretched height.
export default function StatTiles ({ visualizationData, locale }: Props): ReactElement | null {
  const { tiles } = visualizationData
  if (tiles.length === 0) return null

  return (
    <div className='w-full h-full grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] items-stretch gap-3 p-1 overflow-auto'>
      {tiles.map((tile, i) => (
        <div
          key={i}
          className='flex flex-col items-center justify-center text-center gap-1 rounded-md border-[0.2rem] border-grey4 bg-white py-4 px-2'
        >
          <div className='text-title4 font-bodybold text-primary leading-none'>{tile.value}</div>
          <div className='text-captionsmall text-grey2'>{resolveFlatText(tile.label, locale)}</div>
        </div>
      ))}
    </div>
  )
}
