<template>
  <div class="engagement-page">
    <div class="page-header">
      <h2>评论互动</h2>
      <el-tag type="info" effect="dark" round>知乎 · 今日头条</el-tag>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :xs="12" :sm="6" v-for="s in statsCards" :key="s.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" :class="s.color">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作区 -->
    <el-card class="action-card">
      <template #header>
        <span>互动执行</span>
      </template>
      <el-row :gutter="12" align="middle">
        <el-col :xs="24" :sm="6">
          <el-select v-model="runPlatform" placeholder="选择平台" clearable>
            <el-option label="知乎" value="zhihu" />
            <el-option label="今日头条" value="toutiao" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="3">
          <span class="param-label">每篇上限</span>
          <el-input-number v-model="runLimit" :min="1" :max="50" size="small" controls-position="right" />
        </el-col>
        <el-col :xs="12" :sm="3">
          <span class="param-label">最多篇数</span>
          <el-input-number v-model="runMaxContents" :min="1" :max="20" size="small" controls-position="right" />
        </el-col>
        <el-col :xs="24" :sm="12" class="action-btns">
          <el-button type="primary" @click="runEngagement" :loading="running" :disabled="!runPlatform">
            {{ running ? '执行中...' : '对选中平台执行' }}
          </el-button>
          <el-button type="warning" plain @click="runAll" :loading="runningAll">
            {{ runningAll ? '全量执行中...' : '全量执行（知乎+头条）' }}
          </el-button>
        </el-col>
      </el-row>
      <div v-if="lastResult" class="result-summary">
        <el-alert
          :type="lastResult.total_failed > 0 ? 'warning' : 'success'"
          :closable="false"
          show-icon
        >
          <template #title>
            执行完成：共发现 <b>{{ lastResult.total_found }}</b> 条评论，
            回复 <b>{{ lastResult.total_replied }}</b> 条，
            失败 <b>{{ lastResult.total_failed }}</b> 条，
            跳过 <b>{{ lastResult.total_skipped }}</b> 条
          </template>
        </el-alert>
      </div>
    </el-card>

    <!-- 回复历史表 -->
    <el-card class="history-card">
      <template #header>
        <div class="card-header-flex">
          <span>回复历史</span>
          <el-select v-model="filterPlatform" placeholder="平台筛选" clearable size="small" @change="loadHistory">
            <el-option label="知乎" value="zhihu" />
            <el-option label="今日头条" value="toutiao" />
          </el-select>
        </div>
      </template>
      <el-table :data="history" v-loading="historyLoading" size="small">
        <el-table-column prop="platform" label="平台" width="90">
          <template #default="{ row }">
            <el-tag :type="row.platform === 'zhihu' ? 'primary' : 'warning'" size="small" effect="dark">
              {{ row.platform === 'zhihu' ? '知乎' : '头条' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="commenter_name" label="评论者" width="100" />
        <el-table-column prop="comment_text" label="评论内容" min-width="180" show-overflow-tooltip />
        <el-table-column prop="reply_text" label="回复内容" min-width="180" show-overflow-tooltip />
        <el-table-column prop="ai_generated" label="AI" width="55" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.ai_generated" color="#67c23a"><Check /></el-icon>
            <el-icon v-else color="#909399"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="replied_at" label="回复时间" width="170">
          <template #default="{ row }">{{ formatTime(row.replied_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
import * as api from '@/api/engagement'
import dayjs from 'dayjs'

const runPlatform = ref('zhihu')
const runLimit = ref(10)
const runMaxContents = ref(5)
const running = ref(false)
const runningAll = ref(false)
const lastResult = ref(null)

const stats = ref({ total: 0, success: 0, failed: 0, ai_generated: 0, by_platform: {} })
const history = ref([])
const historyLoading = ref(false)
const filterPlatform = ref('')

const statsCards = computed(() => [
  { label: '总回复', value: stats.value.total, color: 'primary' },
  { label: '成功', value: stats.value.success, color: 'success' },
  { label: '失败', value: stats.value.failed, color: 'danger' },
  { label: 'AI 生成', value: stats.value.ai_generated, color: 'warning' },
])

function formatTime(t) {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

async function loadStats() {
  try {
    const res = await api.getEngagementStats()
    stats.value = res.data || {}
  } catch (e) { /* fail silently */ }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await api.getEngagementHistory({ platform: filterPlatform.value || undefined })
    history.value = res.data || []
  } catch (e) {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

async function runEngagement() {
  running.value = true
  lastResult.value = null
  try {
    const res = await api.triggerEngagement({
      platform: runPlatform.value,
      limit_per_content: runLimit.value,
      max_contents: runMaxContents.value,
    })
    lastResult.value = res.data || res
    if (res.success) {
      ElMessage.success(`互动完成：回复 ${lastResult.value.total_replied} 条`)
    } else {
      ElMessage.warning(res.message || '执行完成')
    }
    await loadStats()
    await loadHistory()
  } catch (e) {
    ElMessage.error('互动执行失败: ' + (e.message || '未知错误'))
  } finally {
    running.value = false
  }
}

async function runAll() {
  runningAll.value = true
  try {
    const res = await api.triggerAllPlatforms({
      limit_per_content: runLimit.value,
      max_contents: runMaxContents.value,
    })
    const total = res.data?.total_replied || 0
    ElMessage.success(`全平台互动完成：共回复 ${total} 条`)
    await loadStats()
    await loadHistory()
  } catch (e) {
    ElMessage.error('全量执行失败: ' + (e.message || '未知错误'))
  } finally {
    runningAll.value = false
  }
}

onMounted(() => {
  loadStats()
  loadHistory()
})
</script>

<style scoped>
.engagement-page { padding: 4px; }
.page-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 20px;
}
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; color: #e0e0e0; }
.stats-row { margin-bottom: 20px; }
.stat-card { text-align: center; }
.stat-value { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.stat-value.primary { color: #e8c547; }
.stat-value.success { color: #67c23a; }
.stat-value.danger { color: #f56c6c; }
.stat-value.warning { color: #e6a23c; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.action-card { margin-bottom: 20px; }
.action-btns { display: flex; gap: 8px; justify-content: flex-end; }
.result-summary { margin-top: 12px; }
.history-card { }
.card-header-flex {
  display: flex; align-items: center; justify-content: space-between;
}
.param-label { font-size: 12px; color: #909399; margin-right: 4px; }
</style>
