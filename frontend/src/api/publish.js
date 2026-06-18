import api from './index.js'

export function getPublishRecords(params) {
  return api.get('/publish/records', { params })
}
export function submitPublish(data) {
  return api.post('/publish', data)
}
export function getPublishRecord(id) {
  return api.get(`/publish/records/${id}`)
}
export function retryPublish(id) {
  return api.post(`/publish/records/${id}/retry`)
}
