import api from './index.js'

// 概览 + 分布 + 趋势
export function getMetricsOverview() {
  return api.get('/metrics/overview')
}
export function getPlatformDistribution() {
  return api.get('/metrics/platform-distribution')
}
export function getTrends(productId, days = 30) {
  return api.get('/metrics/trends/' + productId, { params: { days } })
}
export function getTopContents(limit = 10, sortBy = 'views') {
  return api.get('/metrics/top-contents', { params: { limit, sort_by: sortBy } })
}

// 摘要
export function getMetricsSummary(productId) {
  return api.get('/metrics/summary/' + productId)
}
export function getContentMetrics(publishRecordId) {
  return api.get('/metrics/content/' + publishRecordId)
}

// 触发抓取
export function triggerScrape(publishRecordId) {
  return api.post('/metrics/scrape/' + publishRecordId)
}
export function triggerScrapeAll() {
  return api.post('/metrics/scrape-all')
}
export function triggerScrapeProduct(productId) {
  return api.post('/metrics/scrape-product/' + productId)
}
