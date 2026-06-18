import http from './index.js'

export function getEngagementPlatforms() {
  return http.get('/engagement/platforms')
}

export function getEngagementStats(platform) {
  return http.get('/engagement/stats', { params: { platform } })
}

export function getEngagementHistory(params = {}) {
  return http.get('/engagement/history', { params })
}

export function triggerEngagement(params = {}) {
  return http.post('/engagement/run', null, { params })
}

export function triggerAllPlatforms(params = {}) {
  return http.post('/engagement/run-all', null, { params })
}
