import { ChartVisualization, TextVisualization, StatsVisualization, HeatmapVisualization, VisualizationType, VisualizationData, Table } from '../types'
import { prepareChartData } from './prepareChartData'
import { prepareTextData } from './prepareTextData'
import { prepareStatsData } from './prepareStatsData'
import { prepareHeatmapData } from './prepareHeatmapData'

interface Input {
  table: Table
  visualization: VisualizationType
}

self.onmessage = (e: MessageEvent<Input>) => {
  createVisualizationData(e.data.table, e.data.visualization)
    .then((visualizationData) => {
      self.postMessage({ status: 'success', visualizationData })
    })
    .catch((error) => {
      console.error(error)
      self.postMessage({ status: 'error', visualizationData: undefined })
    })
}

async function createVisualizationData (table: Table, visualization: VisualizationType): Promise<VisualizationData> {
  if (table === undefined || visualization === undefined) throw new Error('Table and visualization are required')

  if (['line', 'bar', 'area'].includes(visualization.type)) { return await prepareChartData(table, visualization as ChartVisualization) }

  if (['wordcloud'].includes(visualization.type)) { return await prepareTextData(table, visualization as TextVisualization) }

  if (visualization.type === 'stats') { return await prepareStatsData(table, visualization as StatsVisualization) }

  if (visualization.type === 'heatmap') { return await prepareHeatmapData(table, visualization as HeatmapVisualization) }

  throw new Error(`Visualization type ${visualization.type} not supported`)
}
