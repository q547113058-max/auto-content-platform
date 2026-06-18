import api from './index.js'

export function getAccounts(params) {
  return api.get('/accounts', { params })
}
export function getAccount(id) {
  return api.get(`/accounts/${id}`)
}
export function createAccount(data) {
  return api.post('/accounts', data)
}
export function updateAccount(id, data) {
  return api.put(`/accounts/${id}`, data)
}
export function deleteAccount(id) {
  return api.delete(`/accounts/${id}`)
}
export function checkSession(id) {
  return api.post(`/accounts/${id}/check`)
}
export function importAccountCookie(id, cookieString, platform) {
  return api.post(`/accounts/${id}/import-cookie`, {
    cookie_string: cookieString,
    platform
  })
}
