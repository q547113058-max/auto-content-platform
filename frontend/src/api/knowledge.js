import api from './index.js'

// 知识库文档管理
export function getKBDocs(params) {
  return api.get('/knowledge/docs', { params })
}
export function getKBDoc(id) {
  return api.get(`/knowledge/docs/${id}`)
}
export function createKBDoc(data) {
  return api.post('/knowledge/docs', data)
}
export function updateKBDoc(id, data) {
  return api.put(`/knowledge/docs/${id}`, data)
}
export function deleteKBDoc(id) {
  return api.delete(`/knowledge/docs/${id}`)
}

// 文件上传解析 (.docx/.xlsx) → 保留兼容旧 JSON 接口
export function uploadKnowledgeFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/knowledge/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// Word/Excel/MD 上传 → 直接生成 MD 知识库文档（支持多文件）
export function uploadKBDoc(files, { companyId = null, productId = null } = {}) {
  const fd = new FormData()
  for (const f of files) {
    fd.append('files', f)
  }
  const params = {}
  if (companyId) params.company_id = companyId
  if (productId) params.product_id = productId
  return api.post('/knowledge/upload-doc', fd, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 文件夹扫描导入
export function scanKnowledgeBase(data = {}) {
  return api.post('/knowledge/scan', data)
}
