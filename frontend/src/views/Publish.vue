<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">发布管理</h3>
      <div style="display:flex;gap:8px">
        <el-button type="primary" @click="openPublishDialog">+ 提交发布</el-button>
        <el-button @click="crud.fetch()">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="data" v-loading="loading">
        <el-table-column prop="content_title" label="内容标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }"><el-tag size="small">{{ platformLabel(row.platform) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="发布状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="pubStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="publish_strategy" label="策略" width="100" />
        <el-table-column prop="external_id" label="外部ID" width="160" show-overflow-tooltip />
        <el-table-column prop="error_message" label="失败原因" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" class="text-danger" style="font-size:12px">{{ row.error_message }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="150">
          <template #default="{ row }"><span class="text-muted">{{ fmtTime(row.published_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'failed'"
              text type="warning" size="small"
              :loading="retryingId === row.id"
              @click="doRetry(row)"
            >重试</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Publish Dialog -->
    <el-dialog v-model="pubVisible" title="提交发布" width="520px" destroy-on-close>
      <el-form :model="pubForm" label-width="90px" label-position="left">
        <el-form-item label="选择内容" required>
          <el-select
            v-model="pubForm.content_id"
            placeholder="搜索内容标题…"
            style="width:100%"
            filterable
            remote
            :remote-method="searchContents"
            :loading="contentLoading"
            clearable
          >
            <el-option v-for="c in contentOptions" :key="c.id" :label="c.label" :value="c.id" />
            <template #empty v-if="!contentLoading && contentOptions.length === 0">
              <span class="text-muted">输入关键词搜索内容</span>
            </template>
          </el-select>
        </el-form-item>

        <el-form-item label="发布账号" required>
          <el-select
            v-model="pubForm.account_id"
            placeholder="选择账号"
            style="width:100%"
            clearable
          >
            <el-option v-for="a in accountOptions" :key="a.id" :label="a.label" :value="a.id" />
            <template #empty>
              <span class="text-muted">暂无可用账号，请先在「账号管理」添加</span>
            </template>
          </el-select>
        </el-form-item>

        <el-form-item label="发布策略">
          <el-select v-model="pubForm.publish_strategy" style="width:100%">
            <el-option label="立即发布" value="immediate" />
            <el-option label="定时发布" value="scheduled" />
            <el-option label="存为草稿" value="draft" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pubVisible = false">取消</el-button>
        <el-button type="primary" :loading="pubLoading" @click="doPublish">提交发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getPublishRecords, submitPublish, retryPublish } from '@/api/publish'
import { getContents } from '@/api/contents'
import { getAccounts } from '@/api/accounts'
import { useCrud } from '@/composables/useCrud'

const crud = useCrud(getPublishRecords, null, null, null)
const { data, loading } = crud

const platforms = {
  xiaohongshu: '小红书', zhihu: '知乎', weibo: '微博',
  wechat: '微信公众号', toutiao: '今日头条', douyin: '抖音图文'
}
function platformLabel(k) { return platforms[k] || k }
function pubStatusType(s) {
  return s === 'success' ? 'success' : s === 'failed' ? 'danger' : s === 'pending' ? 'warning' : 'info'
}
function fmtTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ── 发布弹窗 ──
const pubVisible = ref(false)
const pubLoading = ref(false)
const pubForm = reactive({ content_id: null, account_id: null, publish_strategy: 'immediate' })

// 内容搜索（远程）+ 初始加载
const contentOptions = ref([])
const contentLoading = ref(false)
async function searchContents(keyword) {
  contentLoading.value = true
  try {
    const params = keyword ? { keyword, page_size: 20 } : { page_size: 50 }
    const res = await getContents(params)
    contentOptions.value = (res.items || res.data?.items || []).map(c => ({
      id: c.id, label: `${c.title} — ${platformLabel(c.platform)} [#${c.id}]`
    }))
  } finally { contentLoading.value = false }
}

// 账号列表（加载全部，含过期提示）
const accountOptions = ref([])
async function loadAccounts() {
  try {
    const res = await getAccounts()
    accountOptions.value = (res || []).map(a => {
      const expired = a.status === 'expired' ? ' [已过期]' : ''
      return {
        id: a.id,
        label: `${a.account_name}（${platformLabel(a.platform)}）${expired}`,
        disabled: a.status === 'expired',
      }
    })
  } catch {}
}

function openPublishDialog() {
  pubForm.content_id = null
  pubForm.account_id = null
  pubForm.publish_strategy = 'immediate'
  contentOptions.value = []
  searchContents('')     // ← 预加载最新 50 条内容
  loadAccounts()         // ← 加载全部账号
  pubVisible.value = true
}

async function doPublish() {
  if (!pubForm.content_id || !pubForm.account_id) return ElMessage.warning('请选择内容和账号')
  pubLoading.value = true
  try {
    await submitPublish({
      content_id: pubForm.content_id,
      account_id: pubForm.account_id,
      publish_strategy: pubForm.publish_strategy,
    })
    ElMessage.success('发布已提交')
    pubVisible.value = false
    crud.fetch()
  } finally { pubLoading.value = false }
}

function viewDetail(row) {
  const msg = row.error_message
    ? `失败原因：${row.error_message}`
    : row.external_id
      ? `发布链接：${row.external_id}`
      : `发布ID: ${row.id}，状态: ${row.status}`
  ElMessage.info({ message: msg, duration: 6000 })
}

const retryingId = ref(null)
async function doRetry(row) {
  retryingId.value = row.id
  try {
    await retryPublish(row.id)
    ElMessage.success('重试任务已提交，稍后刷新查看结果')
    setTimeout(() => crud.fetch(), 3000)
  } catch (e) {
    ElMessage.error('重试失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    retryingId.value = null
  }
}

onMounted(() => crud.fetch())
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.text-danger { color: var(--el-color-danger); }
.text-muted { color: var(--el-text-color-secondary); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
