import api from './index'

/** 读取当前后端配置（API Key 脱敏） */
export function getSettings() {
  return api.get('/settings')
}

/** 更新 .env 配置（需重启后端生效） */
export function updateSettings(data) {
  return api.put('/settings', data)
}
