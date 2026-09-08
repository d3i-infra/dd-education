import { selectVisualizationColumns } from './selectVisualizationColumns'
import { Table, VisualizationType } from '../types'

function makeTable (): Table {
  return {
    id: 'tiktok_videos',
    head: { cells: ['date', 'title', 'url', 'duration', 'category'] },
    body: {
      rows: [
        { id: 'r1', cells: ['2024-01-01', 'video one', 'https://a.example', '10', 'music'] },
        { id: 'r2', cells: ['2024-01-02', 'video two', 'https://b.example', '20', 'sports'] }
      ]
    }
  }
}

describe('selectVisualizationColumns', () => {
  it('keeps only the columns a chart visualization reads', () => {
    const visualization: VisualizationType = {
      title: { en: 'per day' },
      type: 'line',
      group: { column: 'date' },
      values: [{ column: 'duration', aggregate: 'sum', group_by: 'category' }]
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['date', 'duration', 'category'])
    expect(projected.body.rows).toEqual([
      { id: 'r1', cells: ['2024-01-01', '10', 'music'] },
      { id: 'r2', cells: ['2024-01-02', '20', 'sports'] }
    ])
    expect(projected.id).toBe('tiktok_videos')
  })

  it('does not materialize the .COUNT pseudo-column', () => {
    const visualization: VisualizationType = {
      title: { en: 'count per day' },
      type: 'bar',
      group: { column: 'date' },
      values: [{ column: '.COUNT' }]
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['date'])
  })

  it('keeps textColumn and valueColumn for a wordcloud', () => {
    const visualization: VisualizationType = {
      title: { en: 'words' },
      type: 'wordcloud',
      textColumn: 'title',
      valueColumn: 'duration'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['title', 'duration'])
    expect(projected.body.rows[0].cells).toEqual(['video one', '10'])
  })

  it('keeps excludeColumn for a wordcloud alongside textColumn', () => {
    const visualization: VisualizationType = {
      title: { en: 'words' },
      type: 'wordcloud',
      textColumn: 'title',
      excludeColumn: 'category'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['title', 'category'])
  })

  it('drops referenced columns that do not exist in the table (worker reports the error)', () => {
    const visualization: VisualizationType = {
      title: { en: 'bad' },
      type: 'bar',
      group: { column: 'no_such_column' },
      values: [{ column: 'duration' }]
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['duration'])
  })

  it('keeps only the columns referenced by stat tiles, skipping tiles with no column (e.g. count)', () => {
    const visualization: VisualizationType = {
      title: { en: 'stats' },
      type: 'stats',
      tiles: [
        { label: { en: 'total' }, aggregate: 'count' },
        { label: { en: 'platforms' }, aggregate: 'distinct', column: 'category' }
      ]
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['category'])
  })

  it('keeps dateColumn and valueColumn for a heatmap', () => {
    const visualization: VisualizationType = {
      title: { en: 'activity' },
      type: 'heatmap',
      mode: 'calendar',
      dateColumn: 'date',
      valueColumn: 'duration'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['date', 'duration'])
  })

  it('keeps only dateColumn for a heatmap with no valueColumn', () => {
    const visualization: VisualizationType = {
      title: { en: 'activity' },
      type: 'heatmap',
      mode: 'weekday_hour',
      dateColumn: 'date'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['date'])
  })

  it('keeps groupColumn, roleColumn, textColumn, timeColumn and badgeColumn for a thread', () => {
    const visualization: VisualizationType = {
      title: { en: 'chats' },
      type: 'thread',
      groupColumn: 'category',
      roleColumn: 'title',
      textColumn: 'url',
      timeColumn: 'date',
      badgeColumn: 'duration'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['category', 'title', 'url', 'date', 'duration'])
  })

  it('keeps only roleColumn and textColumn for a thread with no groupColumn (single-thread mode)', () => {
    const visualization: VisualizationType = {
      title: { en: 'chat' },
      type: 'thread',
      singleThreadTitle: { en: 'The chat' },
      roleColumn: 'title',
      textColumn: 'url'
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.head.cells).toEqual(['title', 'url'])
  })

  it('preserves row ids so rowId-based deletion still works', () => {
    const visualization: VisualizationType = {
      title: { en: 'per day' },
      type: 'area',
      group: { column: 'date' },
      values: [{ column: 'duration' }]
    }
    const projected = selectVisualizationColumns(makeTable(), visualization)
    expect(projected.body.rows.map((r) => r.id)).toEqual(['r1', 'r2'])
  })
})
