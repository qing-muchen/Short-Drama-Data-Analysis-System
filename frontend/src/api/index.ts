export { default as apiClient } from './axios'
export { createActor, deactivateActor, getActors, updateActor } from './actor'
export { getCurrentUser, login } from './auth'
export {
  getGrowthRanking,
  getHeatRanking,
  getOverview,
  getPotentialRanking,
  getQuality,
  getTrend,
} from './dashboard'
export { createDrama, deactivateDrama, getDramas, updateDrama } from './drama'
export { createPlatform, deactivatePlatform, getPlatforms, updatePlatform } from './platform'
