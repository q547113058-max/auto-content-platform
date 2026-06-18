import api from './index.js'

export function getSessionsStatus() {
  return api.get('/sessions/status')
}
export function checkSessions(platforms) {
  return api.post('/sessions/check', { platforms })
}
export function triggerLogin(platform) {
  return api.get(`/sessions/${platform}/login`)
}
