<template>
  <div class="page">
    <!-- Toolbar -->
    <div class="page-toolbar">
      <div class="toolbar-left">
        <h3 class="mono" style="font-size:15px;font-weight:600">内容管理</h3>
        <span class="count-badge">{{ total }} 条</span>
      </div>
      <div style="display:flex;gap:8px">
        <el-button type="primary" @click="openGenDialog">+ AI 生成内容</el-button>
        <el-button @click="fetchData">刷新</el-button>
      </div>
    </div>

    <!-- Filters -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" size="small" class="filter-form">
        <el-form-item label="">
          <el-input
            v-model="filters.keyword"
            placeholder="搜索标题/正文..."
            clearable
            style="width:220px"
            @keyup.enter="fetchData"
            @clear="fetchData"
          />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="filters.platform" clearable placeholder="全部" style="width:130px" @change="fetchData">
            <el-option v-for="p in platforms" :key="p.key" :label="p.label" :value="p.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="选题">
          <el-select v-model="filters.topic" clearable placeholder="全部" style="width:140px" @change="fetchData">
            <el-option v-for="t in topicOptions" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width:110px" @change="fetchData">
            <el-option label="草稿" value="draft" />
            <el-option label="已生成" value="generated" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Batch toolbar -->
    <div v-if="selectedIds.length" class="batch-bar">
      <span>已选 <strong>{{ selectedIds.length }}</strong> 条</span>
      <el-select v-model="batchStatus" size="small" placeholder="批量改状态" style="width:130px" @change="doBatchStatus">
        <el-option label="草稿" value="draft" />
        <el-option label="已生成" value="generated" />
        <el-option label="已发布" value="published" />
      </el-select>
      <el-button size="small" type="danger" @click="doBatchDelete">批量删除</el-button>
      <el-button size="small" @click="selectedIds=[]">取消选择</el-button>
    </div>

    <!-- Table -->
    <el-card shadow="never">
      <el-table
        :data="data"
        v-loading="loading"
        @selection-change="onSelectionChange"
        ref="tableRef"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tooltip :content="row.body" placement="right" :show-after="500" :hide-after="0" effect="light">
              <span style="cursor:pointer" @click="viewContent(row)">{{ row.title }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="product_name" label="产品" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.product_name" style="color:var(--brand)">{{ row.product_name }}</span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="95">
          <template #default="{ row }"><el-tag size="small">{{ platformLabel(row.platform) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="选题" width="95">
          <template #default="{ row }"><el-tag size="small" type="warning">{{ topicLabel(row.topic_category) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="85">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="配图" width="75" align="center">
          <template #default="{ row }">
            <template v-if="row.image_paths?.length">
              <el-image
                :src="row.image_paths[0]"
                :preview-src-list="row.image_paths"
                fit="cover"
                style="width:40px;height:40px;border-radius:4px;cursor:pointer"
                lazy
              />
            </template>
            <span v-else class="text-muted" style="font-size:11px">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="150">
          <template #default="{ row }"><span class="text-muted">{{ fmtTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewContent(row)">详情</el-button>
            <el-button text size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrap" v-if="total > 0">
        <el-pagination
          v-model:current-page="paging.page"
          v-model:page-size="paging.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- View Dialog -->
    <el-dialog v-model="viewVisible" title="内容详情" width="720px" destroy-on-close>
      <div v-if="viewItem" class="content-detail">
        <div class="detail-meta">
          <span class="detail-label">产品</span>
          <span class="detail-val brand">{{ viewItem.product_name || '—' }}</span>
          <span class="detail-label">平台</span>
          <el-tag size="small">{{ platformLabel(viewItem.platform) }}</el-tag>
          <span class="detail-label">状态</span>
          <el-tag size="small" :type="statusType(viewItem.status)">{{ statusLabel(viewItem.status) }}</el-tag>
          <span class="detail-label">选题</span>
          <el-tag size="small" type="warning">{{ topicLabel(viewItem.topic_category) }}</el-tag>
        </div>
        <div class="detail-title">{{ viewItem.title }}</div>
        <div class="detail-body" v-html="renderedBody"></div>
        <div v-if="viewItem.tags?.length" class="detail-tags">
          <el-tag v-for="t in viewItem.tags" :key="t" size="small" style="margin-right:6px;margin-bottom:4px">{{ t }}</el-tag>
        </div>
        <div v-if="viewItem.image_paths?.length" class="detail-images">
          <div class="detail-label" style="margin-bottom:8px;font-weight:600">配图 ({{ viewItem.image_paths.length }})</div>
          <div class="image-grid">
            <el-image
              v-for="(url, idx) in viewItem.image_paths"
              :key="idx"
              :src="url"
              :preview-src-list="viewItem.image_paths"
              :initial-index="idx"
              fit="cover"
              style="width:160px;height:160px;border-radius:8px;cursor:pointer"
              lazy
            />
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- Edit Dialog -->
    <el-dialog v-model="editVisible" title="编辑内容" width="620px" destroy-on-close>
      <el-form :model="editForm" label-width="70px" label-position="left">
        <el-form-item label="标题" required>
          <el-input v-model="editForm.title" placeholder="内容标题" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="editForm.body" type="textarea" :rows="14" placeholder="内容正文" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editForm.tags" placeholder="逗号分隔，如：渔业,智慧水产" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width:100%">
            <el-option label="草稿" value="draft" />
            <el-option label="已生成" value="generated" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI Generate Dialog -->
    <el-dialog v-model="genVisible" title="AI 生成内容" width="560px" destroy-on-close>
      <el-form :model="genForm" label-width="100px" label-position="left">
        <el-form-item label="选择产品" required>
          <el-select v-model="genForm.product_id" style="width:100%" filterable placeholder="选择产品">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标平台">
          <el-select v-model="genForm.platforms" style="width:100%" multiple placeholder="全部平台（不选=全平台）">
            <el-option v-for="p in platforms" :key="p.key" :label="p.label" :value="p.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="选题方向">
          <div style="display:flex;gap:8px;width:100%">
            <el-select v-model="genForm.topic_category" style="flex:1" clearable placeholder="自动推荐">
              <el-option v-for="t in topicOptions" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-tooltip content="智能推荐选题方向" placement="top">
              <el-button type="primary" :loading="topicLoading" @click="getSuggestedTopic" size="small">✨ 推荐</el-button>
            </el-tooltip>
          </div>
        </el-form-item>
        <el-alert
          v-if="suggestedTopic.category"
          :title="`推荐：${suggestedTopic.name}`"
          type="success"
          :closable="false"
          show-icon
          style="margin-top:8px"
        >
          <template #default>
            <div style="font-size:12px;color:var(--text-muted)">{{ suggestedTopic.subtitle }}</div>
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">开始生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/contents'
import { getProducts } from '@/api/products'

// ========== Data & Pagination ==========
const data = ref([])
const total = ref(0)
const loading = ref(false)
const paging = reactive({ page: 1, pageSize: 20 })

// ========== Filters ==========
const filters = reactive({ keyword: '', platform: '', topic: '', status: '' })

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: paging.page,
      page_size: paging.pageSize,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.platform) params.platform = filters.platform
    if (filters.topic) params.topic_category = filters.topic
    if (filters.status) params.status = filters.status

    const res = await api.getContents(params)
    // 兼容新旧格式
    if (res.items) {
      data.value = res.items
      total.value = res.total
    } else if (Array.isArray(res)) {
      data.value = res
      total.value = res.length
    } else {
      data.value = []
      total.value = 0
    }
  } catch {
    data.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// ========== Selection / Batch ==========
const selectedIds = ref([])
const batchStatus = ref('')
const tableRef = ref(null)

function onSelectionChange(rows) {
  selectedIds.value = rows.map(r => r.id)
}

async function doBatchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 条内容？`, '批量删除', { type: 'warning' })
    await api.batchDeleteContent(selectedIds.value)
    ElMessage.success('已批量删除')
    selectedIds.value = []
    fetchData()
  } catch { /* canceled */ }
}

async function doBatchStatus(val) {
  if (!val || !selectedIds.value.length) return
  try {
    await api.batchUpdateStatus(selectedIds.value, val)
    ElMessage.success(`已更新 ${selectedIds.value.length} 条状态`)
    batchStatus.value = ''
    selectedIds.value = []
    fetchData()
  } catch {
    batchStatus.value = ''
  }
}

// ========== Delete ==========
async function remove(id) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await api.deleteContent(id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* canceled */ }
}

// ========== View ==========
const viewVisible = ref(false)
const viewItem = ref(null)

// 解析正文中的内联图片标记 [配图:url]
const renderedBody = computed(() => {
  if (!viewItem.value?.body) return ''
  const raw = viewItem.value.body
  // 将 [配图:url] 替换为 HTML img 标签
  return raw.replace(
    /\[配图:(https?:\/\/[^\]]+)\]/g,
    (_, url) => `<img src="${url}" class="inline-image" loading="lazy" onclick="window.open('${url}')" />`
  ).replace(/\n/g, '<br>')
})

function viewContent(row) {
  viewItem.value = row
  viewVisible.value = true
}

// ========== Edit ==========
const editVisible = ref(false)
const editLoading = ref(false)
const editForm = reactive({ id: null, title: '', body: '', tags: '', status: 'draft' })
const editId = ref(null)

function openEdit(row) {
  editId.value = row.id
  editForm.id = row.id
  editForm.title = row.title || ''
  editForm.body = row.body || ''
  editForm.tags = Array.isArray(row.tags) ? row.tags.join(', ') : (row.tags || '')
  editForm.status = row.status || 'draft'
  editVisible.value = true
}

async function submitEdit() {
  editLoading.value = true
  try {
    await api.updateContent(editId.value, {
      title: editForm.title,
      body: editForm.body,
      tags: editForm.tags.split(',').map(t => t.trim()).filter(Boolean),
      status: editForm.status,
    })
    ElMessage.success('已更新')
    editVisible.value = false
    fetchData()
  } finally {
    editLoading.value = false
  }
}

// ========== Labels & Helpers ==========
const platforms = [
  { key: 'xiaohongshu', label: '小红书' },
  { key: 'zhihu', label: '知乎' },
  { key: 'weibo', label: '微博' },
  { key: 'wechat', label: '微信公众号' },
  { key: 'toutiao', label: '今日头条' },
  { key: 'douyin', label: '抖音' }
]
const platformMap = Object.fromEntries(platforms.map(p => [p.key, p.label]))
function platformLabel(k) { return platformMap[k] || k }

const statusMap = { draft: '草稿', generated: '已生成', published: '已发布' }
function statusLabel(s) { return statusMap[s] || s }
function statusType(s) { return s === 'published' ? 'success' : s === 'generated' ? 'warning' : 'info' }

const topicOptions = [
  { id: 'tech_explanation', name: '技术解析' },
  { id: 'product_guide', name: '产品指南' },
  { id: 'case_study', name: '增效案例' },
  { id: 'industry_trend', name: '行业趋势' },
  { id: 'pain_point', name: '痛点共鸣' },
  { id: 'comparison', name: '对比选型' },
  { id: 'seasonal', name: '季节专题' }
]
const topicMap = Object.fromEntries(topicOptions.map(t => [t.id, t.name]))
function topicLabel(id) { return topicMap[id] || (id ? id.slice(0, 8) : '—') }

function fmtTime(t) {
  if (!t) return '—'
  return t.replace('T', ' ').slice(0, 19)
}

// ========== AI Generate ==========
const genVisible = ref(false)
const genLoading = ref(false)
const topicLoading = ref(false)
const products = ref([])
const genForm = reactive({ product_id: null, platforms: [], topic_category: '' })
const suggestedTopic = reactive({ category: '', name: '', subtitle: '' })

async function openGenDialog() {
  try {
    const res = await getProducts()
    products.value = res.items || res || []
  } catch { products.value = [] }
  genForm.product_id = null
  genForm.platforms = []
  genForm.topic_category = ''
  suggestedTopic.category = ''
  genVisible.value = true
}

async function getSuggestedTopic() {
  if (!genForm.product_id) return ElMessage.warning('请先选择产品')
  const platform = genForm.platforms.length ? genForm.platforms[0] : 'zhihu'
  topicLoading.value = true
  try {
    const res = await api.suggestTopic(genForm.product_id, platform)
    const d = res.data || res
    genForm.topic_category = d.topic_category
    suggestedTopic.category = d.topic_category
    suggestedTopic.name = d.topic_name
    suggestedTopic.subtitle = d.topic_subtitle || ''
  } catch {
    ElMessage.warning('推荐失败，请手动选择')
  } finally {
    topicLoading.value = false
  }
}

async function doGenerate() {
  if (!genForm.product_id) return ElMessage.warning('请选择产品')
  genLoading.value = true
  try {
    const res = await api.generateContent({
      product_id: genForm.product_id,
      platforms: genForm.platforms.length ? genForm.platforms : undefined,
      topic_category: genForm.topic_category || undefined
    })
    const d = res.data || res
    const ids = d.generated_ids || []
    const errors = d.errors || []

    if (ids.length > 0) {
      ElMessage.success(`已生成 ${ids.length} 篇内容`)
      genVisible.value = false
      fetchData()
    } else {
      const errMsg = errors.length
        ? errors.map(e => `${e.platform}: ${e.error}`).join('; ')
        : '生成失败，请检查 AI 配置'
      ElMessage.warning(errMsg)
    }
  } catch (e) {
    // 超时或网络错误已在拦截器中提示，此处静默处理
    if (e?.code === 'ECONNABORTED') {
      ElMessage.warning('AI 生成耗时较长，仍在后端处理中，请刷新列表查看结果')
    }
    // 其他错误已由拦截器 ElMessage.error 处理
  } finally {
    genLoading.value = false
  }
}

onMounted(() => fetchData())
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;
}
.toolbar-left {
  display: flex; align-items: center; gap: 12px;
}
.count-badge {
  font-size: 12px; color: var(--text-muted); background: var(--bg-input);
  padding: 2px 10px; border-radius: 10px;
}
.filter-card { margin-bottom: 16px; }
.filter-form :deep(.el-form-item) { margin-bottom: 0; }

// Batch bar
.batch-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 16px; margin-bottom: 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 6px; font-size: 13px;
}

// Pagination
.pagination-wrap {
  display: flex; justify-content: flex-end; margin-top: 16px; padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

// Content detail
.content-detail {
  display: flex; flex-direction: column; gap: 16px;
}
.detail-meta {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter);
}
.detail-label {
  font-size: 12px; color: var(--text-muted); min-width: fit-content;
  &:not(:first-child) { margin-left: 12px; }
}
.detail-val {
  font-size: 13px;
  &.brand { color: var(--brand); font-weight: 500; }
}
.detail-title {
  font-size: 16px; font-weight: 600; line-height: 1.5; color: var(--text-primary);
}
.detail-body {
  background: var(--bg-input); border-radius: 8px; padding: 20px;
  white-space: pre-wrap; line-height: 1.8; color: var(--text-primary); font-size: 14px;
  max-height: 500px; overflow-y: auto;

  :deep(.inline-image) {
    display: block;
    max-width: 100%;
    max-height: 320px;
    margin: 16px auto;
    border-radius: 10px;
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);

    &:hover {
      transform: scale(1.02);
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
  }
}
.detail-tags {
  display: flex; flex-wrap: wrap; gap: 4px;
}
.detail-images {
  padding-top: 4px;
}
.image-grid {
  display: flex; flex-wrap: wrap; gap: 8px;
}

.text-muted { color: var(--text-muted); font-size: 12px; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
