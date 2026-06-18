<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">会话管理</h3>
      <div style="display:flex;gap:8px">
        <el-button @click="handleCheck">检测全部</el-button>
        <el-button @click="fetchSessions">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="sessionList" v-loading="loading">
        <el-table-column label="平台" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="dark">{{ row.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="会话状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status || 'unknown' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="详情" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.isBrowser"
              text
              type="warning"
              size="small"
              @click="doLogin(row.key)"
            >
              触发登录
            </el-button>
            <span v-else class="text-muted" style="font-size:12px">API Token</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/sessions'

const loading = ref(false)
const sessionData = ref({})

const platforms = [
  { key: 'xiaohongshu', label: '小红书', isBrowser: true },
  { key: 'zhihu', label: '知乎', isBrowser: true },
  { key: 'weibo', label: '微博', isBrowser: true },
  { key: 'wechat', label: '微信公众号', isBrowser: false },
  { key: 'toutiao', label: '今日头条', isBrowser: true },
  { key: 'douyin', label: '抖音图文', isBrowser: true }
]

const sessionList = computed(() => {
  return platforms.map(p => {
    const info = sessionData.value[p.key] || {}
    return {
      ...p,
      status: info.status || (info.exists ? 'active' : 'inactive'),
      message: info.message || (info.exists ? '会话正常' : '未检测'),
      storage_state_path: info.storage_state_path || ''
    }
  })
})

async function fetchSessions() {
  loading.value = true
  try {
    const res = await api.getSessionsStatus()
    sessionData.value = res.data || res || {}
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}

async function handleCheck() {
  loading.value = true
  try {
    await api.checkSessions(platforms.map(p => p.key))
    ElMessage.success('检测完成')
  } catch { /* */ }
  await fetchSessions()
}

async function doLogin(platform) {
  try {
    const res = await api.triggerLogin(platform)
    ElMessage.success(res.message || '登录页面已打开')
  } catch { /* */ }
}

onMounted(() => fetchSessions())
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
