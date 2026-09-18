export type PredictionMetric = 'PLAY_COUNT'
export type PredictionAlgorithmVersion = 'Moving Average V1.0'

export interface Prediction {
  prediction_id: number
  drama_id: number
  metric_type: PredictionMetric
  algorithm_version: PredictionAlgorithmVersion
  analysis_as_of: string
  target_date: string
  predicted_value: number
  created_at: string
}

export interface PredictionHistoryResponse {
  drama_id: number
  metric_type: PredictionMetric
  algorithm_version: PredictionAlgorithmVersion
  items: Prediction[]
}

export type PredictionCalculateResponse = Prediction
