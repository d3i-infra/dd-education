import { ReactElement } from 'react'
import { resolveFlatText } from '../../../../locale/text'
import { StatsVisualizationData } from '../types'

interface Props {
  visualizationData: StatsVisualizationData
  locale: string
}

// A responsive row of cards: wraps on narrow (phone) viewports instead of
// squeezing tiles, and grows to fill the row on wide (laptop) viewports.
export default function StatTiles ({ visualizationData, locale }: Props): ReactElement | null {
  const { tiles } = visualizationData
  if (tiles.length === 0) return null

  return (
    <div className='w-full h-full flex flex-wrap content-start gap-3 p-1 overflow-auto'>
      {tiles.map((tile, i) => (
        <div
          key={i}
          className='flex-1 basis-[120px] min-w-[120px] flex flex-col items-center justify-center text-center gap-1 rounded-md border-[0.2rem] border-grey4 bg-white py-4 px-2'
        >
          <div className='text-title4 font-bodybold text-primary leading-none'>{tile.value}</div>
          <div className='text-captionsmall text-grey2'>{resolveFlatText(tile.label, locale)}</div>
        </div>
      ))}
    </div>
  )
}
