import api from './index.js'

export function getProducts(params) {
  return api.get('/products', { params })
}
export function getProduct(id) {
  return api.get(`/products/${id}`)
}
export function createProduct(data) {
  return api.post('/products', data)
}
export function updateProduct(id, data) {
  return api.put(`/products/${id}`, data)
}
export function deleteProduct(id) {
  return api.delete(`/products/${id}`)
}
export function uploadProductImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/products/upload-image', fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
