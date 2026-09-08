import { Fragment, ReactElement } from 'react'
import { HeatmapVisualizationData } from '../types'

interface Props {
  visualizationData: HeatmapVisualizationData
}

// A single hue, light -> dark, sequential scale for a magnitude encoding
// (never a rainbow): grey4 for "no data", four steps up to the app's primary
// blue for the busiest cell. Exact values always ride along in the <title>
// tooltip, so color is never the only carrier of the number.
const SCALE_COLORS = ['#EEEEEE', '#D6E0FB', '#AEC2F7', '#7FA0F2', '#4272EF']

function colorFor (value: number, max: number): string {
  if (max <= 0 || value <= 0) return SCALE_COLORS[0]
  const ratio = value / max
  if (ratio > 0.75) return SCALE_COLORS[4]
  if (ratio > 0.5) return SCALE_COLORS[3]
  if (ratio > 0.25) return SCALE_COLORS[2]
  return SCALE_COLORS[1]
}

const CELL = 12
const GAP = 2
const STEP = CELL + GAP
const ROW_LABEL_W = 20
const COL_LABEL_H = 14
const GROUP_LABEL_H = 12

export default function Heatmap ({ visualizationData }: Props): ReactElement | null {
  const { grids, max, mode } = visualizationData
  if (grids.length === 0) return null

  // The column-label band only exists for weekday_hour's hour ticks; a
  // calendar grid never draws one (its colLabels are blank), so reserving
  // COL_LABEL_H for it there would leave dead space above the grid.
  const topPad = mode === 'calendar' ? GROUP_LABEL_H : COL_LABEL_H

  return (
    <div className='w-full h-full flex flex-col gap-4 p-2 overflow-auto'>
      {grids.map((grid) => {
        const cols = grid.colLabels.length
        const width = ROW_LABEL_W + cols * STEP
        const height = topPad + 7 * STEP

        return (
          <div key={grid.key || 'grid'} className='flex flex-col gap-1'>
            {grid.key !== '' && <div className='text-caption font-bodybold text-grey1'>{grid.key}</div>}
            <svg
              viewBox={`0 0 ${width} ${height}`}
              width='100%'
              style={{ maxWidth: width * 1.6, height: 'auto' }}
              role='img'
            >
              {grid.colGroups?.map((group, i) => (
                <text key={i} x={ROW_LABEL_W + group.col * STEP} y={GROUP_LABEL_H - 2} fontSize={8} fill='#999999'>
                  {group.label}
                </text>
              ))}
              {mode === 'weekday_hour' && grid.colLabels.map((label, col) => (
                label === '' ? null : (
                  <text
                    key={col}
                    x={ROW_LABEL_W + col * STEP + CELL / 2}
                    y={topPad - 3}
                    fontSize={8}
                    fill='#999999'
                    textAnchor='middle'
                  >
                    {label}
                  </text>
                )
              ))}
              {grid.rowLabels.map((label, row) => (
                <text key={row} x={0} y={topPad + row * STEP + CELL - 2} fontSize={8} fill='#999999'>
                  {label}
                </text>
              ))}
              {grid.values.map((rowValues, row) => (
                <Fragment key={row}>
                  {rowValues.map((value, col) => {
                    const dateLabel = grid.cellDates?.[row]?.[col]
                    // A calendar grid pads out incomplete weeks at the start/end
                    // of the year; those cells carry no date and are left blank.
                    if (grid.cellDates !== undefined && dateLabel === '') return null

                    const x = ROW_LABEL_W + col * STEP
                    const y = topPad + row * STEP
                    // weekday_hour has no cellDates; label every hour in the
                    // tooltip even though only every 3rd hour gets an axis tick.
                    // The tooltip always spells out the full weekday name --
                    // the axis only has room for its two-letter abbreviation.
                    const title = dateLabel !== undefined
                      ? `${dateLabel}: ${value}`
                      : `${grid.rowTooltipLabels[row]} ${col}:00: ${value}`

                    return (
                      <rect key={col} x={x} y={y} width={CELL} height={CELL} rx={2} fill={colorFor(value, max)}>
                        <title>{title}</title>
                      </rect>
                    )
                  })}
                </Fragment>
              ))}
            </svg>
          </div>
        )
      })}
    </div>
  )
}
