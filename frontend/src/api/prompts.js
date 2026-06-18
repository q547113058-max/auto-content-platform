import api from './index.js'

export function getPrompts(params) {
  return api.get('/prompts', { params })
}
export function getPrompt(id) {
  return api.get(`/prompts/${id}`)
}
export function createPrompt(data) {
  return api.post('/prompts', data)
}
export function updatePrompt(id, data) {
  return api.put(`/prompts/${id}`, data)
}
export function deletePrompt(id) {
  return api.delete(`/prompts/${id}`)
}
export function activatePrompt(id) {
  return api.post(`/prompts/${id}/activate`)
}
