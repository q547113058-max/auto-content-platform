import api, { aiApi } from './index.js'

export function getContents(params) {
  return api.get('/contents', { params })
}
export function getContent(id) {
  return api.get(`/contents/${id}`)
}
export function generateContent(data) {
  return aiApi.post('/contents/generate', data)  // ← AI 长耗时，专用 5 分钟超时
}
export function updateContent(id, data) {
  return api.put(`/contents/${id}`, data)
}
export function deleteContent(id) {
  return api.delete(`/contents/${id}`)
}

// ===== 批量操作 =====
export function batchDeleteContent(ids) {
  return api.post('/contents/batch-delete', { ids })
}
export function batchUpdateStatus(ids, status) {
  return api.post('/contents/batch-status', { ids, status })
}

// ===== 选题相关 =====
export function getTopicCategories() {
  return api.get('/topics/categories')
}
export function getPlatformTopics(platform) {
  return api.get(`/topics/platforms/${platform}`)
}
export function suggestTopic(productId, platform) {
  return api.post('/topics/suggest', null, { params: { product_id: productId, platform } })
}
export function getTopicHistory(productId) {
  return api.get(`/topics/history/${productId}`)
}
