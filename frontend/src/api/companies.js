import api from './index.js'

export function getCompanies() {
  return api.get('/companies')
}
export function getCompany(id) {
  return api.get(`/companies/${id}`)
}
export function createCompany(data) {
  return api.post('/companies', data)
}
export function updateCompany(id, data) {
  return api.put(`/companies/${id}`, data)
}
export function deleteCompany(id) {
  return api.delete(`/companies/${id}`)
}
