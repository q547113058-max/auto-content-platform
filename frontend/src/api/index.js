import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// AI 生成长耗时接口（DeepSeek + Seedream 配图，可能超 60s）
export const aiApi = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,  // 5 分钟
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
