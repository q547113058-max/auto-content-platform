import api from './index.js'

// 改动记录 CRUD
export function getChanges(params) {
  return api.get('/optimizer/changes', { params })
}
export function createChange(data) {
  return api.post('/optimizer/changes', data)
}
export function updateChangeStatus(changeId, status, approvedBy) {
  return api.put('/optimizer/changes/' + changeId + '/status', null, { params: { status, approved_by: approvedBy } })
}

// 优化分析
export function analyzeProduct(productId) {
  return api.post('/optimizer/analyze/' + productId)
}
export function analyzeAll() {
  return api.post('/optimizer/analyze-all')
}

// 效果验证
export function verifyEffect(changeId) {
  return api.get('/optimizer/changes/' + changeId + '/verify')
}

// 自动闭环
export function triggerAutoLoop() {
  return api.post('/optimizer/auto-loop')
}

// 统计 + 建议
export function getOptimizerStats(productId) {
  return api.get('/optimizer/stats', { params: { product_id: productId } })
}
export function getProductSuggestions(productId, status) {
  return api.get('/optimizer/suggestions/' + productId, { params: { status } })
}
