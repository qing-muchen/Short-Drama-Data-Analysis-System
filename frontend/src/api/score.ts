import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  DramaScore,
  ScoreCalculationResult,
  ScoreLevel,
  ScoreLevelDistribution,
  ScoreRankingPage,
} from '../types/score'

const SCORE_REQUEST_TIMEOUT_MS = 60_000

export interface ScoreRankingParams {
  score_date: string
  page?: number
  page_size?: number
  level?: ScoreLevel
}

export async function getScoreRanking(
  params: ScoreRankingParams,
): Promise<ScoreRankingPage> {
  const response = await apiClient.get<ApiResponse<ScoreRankingPage>>('/scores/ranking', {
    params,
    timeout: SCORE_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}
export async function getScoreLevelDistribution(
  scoreDate: string,
): Promise<ScoreLevelDistribution> {
  const response = await apiClient.get<ApiResponse<ScoreLevelDistribution>>(
    '/scores/level-distribution',
    {
      params: { score_date: scoreDate },
      timeout: SCORE_REQUEST_TIMEOUT_MS,
    },
  )
  return response.data.data
}

export async function getDramaScore(dramaId: number): Promise<DramaScore> {
  const response = await apiClient.get<ApiResponse<DramaScore>>(`/scores/${dramaId}`, {
    timeout: SCORE_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function calculateScores(scoreDate: string): Promise<ScoreCalculationResult> {
  const response = await apiClient.post<ApiResponse<ScoreCalculationResult>>(
    '/scores/calculate',
    { score_date: scoreDate },
    { timeout: SCORE_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}
