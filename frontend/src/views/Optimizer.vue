<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">优化学习</h3>
      <div style="display:flex;gap:8px;align-items:center">
        <el-select v-model="filterProduct" placeholder="产品" clearable style="width:180px" @change="fetchChanges">
          <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width:120px" @change="fetchChanges">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已应用" value="applied" />
          <el-option label="已验证" value="verified" />
          <el-option label="已拒绝" value="rejected" />
        </el-select>
        <el-button type="primary" @click="handleAutoLoop" :loading="loopRunning">自动闭环</el-button>
        <el-button @click="handleAnalyzeAll" :loading="analyzingAll">全量分析</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value mono" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 改动记录列表 -->
    <el-card shadow="never">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="card-header">优化改动记录</span>
          <el-button size="small" @click="fetchChanges">刷新</el-button>
        </div>
      </template>

      <el-table :data="changes" v-loading="loading">
        <el-table-column type="index" width="50" />
        <el-table-column prop="change_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="typeColor(row.change_type)">{{ row.change_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="90" />
        <el-table-column prop="issue_description" label="问题描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="hypothesis" label="假设原因" min-width="180" show-overflow-tooltip>
          <template #default="{ row }"><span class="text-muted">{{ row.hypothesis || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="action_taken" label="建议动作" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusColor(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_duplicate" label="去重" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_duplicate ? 'warning' : 'success'">
              {{ row.is_duplicate ? '重复' : '新' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleVerify(row)" :disabled="row.effect_verified">验证效果</el-button>
            <el-button size="small" type="primary" @click="handleApprove(row)" v-if="row.status === 'pending'">通过</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchChanges"
        style="margin-top:16px;justify-content:center"
      />
      <el-empty v-if="!loading && changes.length === 0" description="暂无优化记录，请先执行数据分析" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProducts } from '@/api/products'
import { getChanges, updateChangeStatus, verifyEffect, triggerAutoLoop, analyzeAll, getOptimizerStats } from '@/api/optimizer'

const changes = ref([])
const loading = ref(false)
const loopRunning = ref(false)
const analyzingAll = ref(false)
const products = ref([])
const filterProduct = ref(null)
const filterStatus = ref(null)
const currentPage = ref(1)
const total = ref(0)
const pageSize = 20

// 统计
const stats = ref({ total: 0, by_status: {}, verified: 0, duplicates: 0, unique_changes: 0 })
const statCards = computed(() => [
  { label: '总改动', value: stats.value.total, color: 'var(--accent)' },
  { label: '已验证', value: stats.value.verified, color: '#67c23a' },
  { label: '有效改动', value: stats.value.unique_changes, color: '#409eff' },
  { label: '去重拦截', value: stats.value.duplicates, color: '#e6a23c' },
])

function typeColor(type) {
  const map = { prompt: 'primary', structure: 'warning', keyword: 'success', timing: 'info', image: 'danger' }
  return map[type] || ''
}
function statusColor(status) {
  const map = { pending: 'warning', approved: 'primary', applied: 'success', verified: 'success', rejected: 'danger' }
  return map[status] || 'info'
}
function statusLabel(status) {
  const map = { pending: '待审核', approved: '已通过', applied: '已应用', verified: '已验证', rejected: '已拒绝' }
  return map[status] || status
}

async function fetchChanges() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize }
    if (filterProduct.value) params.product_id = filterProduct.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getChanges(params)
    changes.value = Array.isArray(res) ? res : (res.items || [])
    total.value = res.total || changes.value.length
  } finally { loading.value = false }
}

async function fetchStats() {
  try {
    stats.value = await getOptimizerStats(filterProduct.value)
  } catch (e) { /* ignore */ }
}

async function handleApprove(row) {
  try {
    await updateChangeStatus(row.id, 'approved')
    ElMessage.success('已通过')
    fetchChanges()
    fetchStats()
  } catch (e) {}
}

async function handleVerify(row) {
  try {
    const res = await verifyEffect(row.id)
    ElMessageBox.alert(
      `改动前: 均浏览 ${Math.round(res.data.before_avg_views)}, 均互动 ${res.data.before_avg_engagement?.toFixed(1)}%\n` +
      `改动后: 均浏览 ${Math.round(res.data.after_avg_views)}, 均互动 ${res.data.after_avg_engagement?.toFixed(1)}%`,
      '效果对比',
      { confirmButtonText: '确定' }
    )
    fetchChanges()
    fetchStats()
  } catch (e) {}
}

async function handleAutoLoop() {
  loopRunning.value = true
  try {
    const res = await triggerAutoLoop()
    ElMessage.success(res.message || '闭环执行完成')
    fetchChanges()
    fetchStats()
  } finally { loopRunning.value = false }
}

async function handleAnalyzeAll() {
  analyzingAll.value = true
  try {
    await analyzeAll()
    ElMessage.success('全量分析已触发')
    fetchChanges()
    fetchStats()
  } finally { analyzingAll.value = false }
}

onMounted(async () => {
  try {
    const res = await getProducts()
    products.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {}
  fetchChanges()
  fetchStats()
})
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap:wrap; gap:8px }

.stat-card {
  text-align: center;
  .stat-label { font-size: 12px; color: #8892a4; margin-bottom: 6px; }
  .stat-value { font-size: 22px; font-weight: 700; }
}

.card-header { font-size: 13px; font-weight: 600; color: #c0c8d8; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
