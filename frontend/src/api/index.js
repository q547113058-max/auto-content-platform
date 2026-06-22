import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// AI 生成长耗时接口（DeepSeek + Seedream 配图，可能超 5 分钟）
export const aiApi = axios.create({
  baseURL: '/api/v1',
  timeout: 600000,  // 10 分钟（生成 6 个平台 + 配图耗时较长）
  headers: { 'Content-Type': 'application/json' }
})
aiApi.interceptors.response.use(
  (res) => res.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (res) => res.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default api
