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
        <el-table-column prop="product_name" label="主体" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.content_mode === 'company'" style="color:#409eff">
              🏢 {{ row.company_name || '—' }}
            </span>
            <span v-else-if="row.content_mode === 'mixed'" style="color:#67c23a">
              🔀 {{ row.company_name || row.product_name || '—' }}
            </span>
            <span v-else style="color:var(--brand)">
              {{ row.product_name || '—' }}
            </span>
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
    <el-dialog v-model="genVisible" title="AI 生成内容" width="580px" destroy-on-close>
      <el-form :model="genForm" label-width="100px" label-position="left">

        <!-- 生成模式 -->
        <el-form-item label="生成模式" required>
          <el-radio-group v-model="genForm.content_mode" @change="onModeChange">
            <el-radio-button value="product">
              <span>📦 纯产品</span>
            </el-radio-button>
            <el-radio-button value="company">
              <span>🏢 纯公司</span>
            </el-radio-button>
            <el-radio-button value="mixed">
              <span>🔀 混合</span>
            </el-radio-button>
          </el-radio-group>
          <div style="margin-top:6px;font-size:12px;color:var(--text-muted)">
            <span v-if="genForm.content_mode==='product'">以产品为主体，深度推介产品特性与卖点</span>
            <span v-else-if="genForm.content_mode==='company'">以品牌/公司为主体，展示企业形象与行业地位</span>
            <span v-else>以品牌为主体，系统自主判断是否引用产品（基于历史广告密度分析）</span>
          </div>
        </el-form-item>

        <!-- 选择公司（公司/混合模式必填） -->
        <el-form-item
          v-if="genForm.content_mode === 'company' || genForm.content_mode === 'mixed'"
          label="选择公司"
          required
        >
          <el-select v-model="genForm.company_id" style="width:100%" filterable placeholder="选择品牌/公司">
            <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id">
              <span>{{ c.name }}</span>
              <span style="color:var(--text-muted);font-size:12px;margin-left:8px">{{ c.industry || '' }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 选择产品（混合模式不显示，由系统自主决策） -->
        <el-form-item
          v-if="genForm.content_mode !== 'mixed'"
          label="选择产品"
          required
        >
          <el-select
            v-model="genForm.product_id"
            style="width:100%"
            filterable
            placeholder="选择产品"
          >
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>

        <!-- 目标平台 -->
        <el-form-item label="目标平台">
          <el-select v-model="genForm.platforms" style="width:100%" multiple placeholder="全部平台（不选=全平台）">
            <el-option v-for="p in platforms" :key="p.key" :label="p.label" :value="p.key" />
          </el-select>
        </el-form-item>

        <!-- 选题方向 -->
        <el-form-item label="选题方向">
          <div style="display:flex;gap:8px;width:100%">
            <el-select v-model="genForm.topic_category" style="flex:1" clearable placeholder="自动推荐">
              <el-option v-for="t in topicOptions" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-tooltip content="智能推荐选题方向" placement="top">
              <el-button
                type="primary"
                :loading="topicLoading"
                :disabled="!canSuggestTopic"
                @click="getSuggestedTopic"
                size="small"
              >✨ 推荐</el-button>
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
        <el-form-item label="选项">
          <el-checkbox v-model="genForm.auto_publish">生成后自动发布（需先配置平台账号）</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">开始生成</el-button>
      </template>
    </el-dialog>

    <!-- 自动发布：账号选择对话框 -->
    <el-dialog v-model="autoPubVisible" title="选择发布账号" width="650px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom:16px"
      >
        <template #title>以下内容已生成完成，请为每个平台选择发布账号</template>
        <template #default>
          <span style="font-size:12px;color:var(--text-muted)">
            将按所选账号依次提交发布任务。如某平台暂无可用账号，请先在「账号管理」中添加。
          </span>
        </template>
      </el-alert>

      <el-table :data="autoPubContents" size="small" style="width:100%">
        <el-table-column label="平台" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.platformLabel }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="发布账号" width="240">
          <template #default="{ row }">
            <el-select
              :model-value="autoPubAccountMap[row.id]"
              @update:model-value="val => autoPubAccountMap[row.id] = val"
              placeholder="选择账号"
              style="width:100%"
              size="small"
            >
              <el-option
                v-for="a in getAccountsForPlatform(row.platform)"
                :key="a.id"
                :label="a.label"
                :value="a.id"
                :disabled="a.disabled"
              />
              <template #empty>
                <span style="font-size:12px;color:var(--el-text-color-placeholder)">
                  暂无 {{ row.platformLabel }} 可用账号
                </span>
              </template>
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="skipAutoPublish">跳过发布</el-button>
        <el-button type="primary" :loading="autoPubLoading" :disabled="!canAutoPublish()" @click="doBatchPublish">
          确认发布 ({{ autoPubContents.length }} 篇)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/contents'
import { getProducts } from '@/api/products'
import { getCompanies } from '@/api/companies'
import { getAccounts } from '@/api/accounts'
import { submitPublish } from '@/api/publish'

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

const statusMap = { draft: '草稿', generating: '生成中', generated: '已生成', published: '已发布' }
function statusLabel(s) { return statusMap[s] || s }
function statusType(s) {
  if (s === 'generating') return 'warning'
  return s === 'published' ? 'success' : s === 'generated' ? 'warning' : 'info'
}

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
const companies = ref([])
const genForm = reactive({
  content_mode: 'product',
  product_id: null,
  company_id: null,
  platforms: [],
  topic_category: '',
  auto_publish: false,
})

// 记录最近一次生成任务的信息
const generatedContentIds = ref([])
const autoPublishRequested = ref(false)
const suggestedTopic = reactive({ category: '', name: '', subtitle: '' })

// ── 自动发布：生成完成后选择账号 ──
const autoPubVisible = ref(false)
const autoPubLoading = ref(false)
const autoPubContents = ref([])          // [{ id, title, platform, ... }]
const autoPubAccountMap = reactive({})   // { contentId: accountId }
const autoPubAccounts = ref([])          // [{ id, label, platform, disabled }]
const autoPubAccountsByPlatform = ref({})// { platform: [{ id, label, ... }] }

// 当选择公司时，过滤该公司旗下的产品
const filteredProducts = computed(() => {
  if (genForm.content_mode === 'product') return products.value
  if (genForm.company_id) {
    const filtered = products.value.filter(p => p.company_id === genForm.company_id)
    return filtered.length ? filtered : products.value
  }
  return products.value
})

// 推荐选题需要有产品 ID
const canSuggestTopic = computed(() => {
  if (genForm.content_mode === 'company') return false // 纯公司无产品选题
  return !!genForm.product_id
})

function onModeChange() {
  genForm.product_id = null
  genForm.company_id = null
  suggestedTopic.category = ''
}

async function openGenDialog() {
  try {
    const [pRes, cRes] = await Promise.all([getProducts(), getCompanies()])
    products.value = pRes.items || pRes || []
    companies.value = Array.isArray(cRes) ? cRes : (cRes.items || [])
  } catch { products.value = []; companies.value = [] }
  genForm.content_mode = 'product'
  genForm.product_id = null
  genForm.company_id = null
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
  const mode = genForm.content_mode
  if (mode === 'product' && !genForm.product_id) return ElMessage.warning('请选择产品')
  if ((mode === 'company' || mode === 'mixed') && !genForm.company_id) return ElMessage.warning('请选择公司')

  genLoading.value = true
  try {
    const payload = {
      content_mode: mode,
      platforms: genForm.platforms.length ? genForm.platforms : undefined,
      topic_category: genForm.topic_category || undefined,
      auto_publish: genForm.auto_publish,
    }
    if (genForm.product_id) payload.product_id = genForm.product_id
    if (genForm.company_id) payload.company_id = genForm.company_id

    const res = await api.generateContent(payload)
    const d = res.data || res
    const ids = d.content_ids || []
    const errors = d.errors || []

    if (ids.length > 0) {
      ElMessage.success(`已提交生成任务，${ids.length} 篇内容生成中…`)
      generatedContentIds.value = ids
      autoPublishRequested.value = genForm.auto_publish
      genVisible.value = false
      fetchData()
      startPolling()
    } else {
      const errMsg = errors.length
        ? errors.map(e => `${e.platform}: ${e.error}`).join('; ')
        : '生成失败，请检查 AI 配置'
      ElMessage.warning(errMsg)
    }
  } catch (e) {
    if (e?.code === 'ECONNABORTED') {
      ElMessage.warning('AI 生成耗时较长，仍在后端处理中，请刷新列表查看结果')
    }
  } finally {
    genLoading.value = false
  }
}

// ── 轮询刷新 ──
let pollTimer = null
function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    await fetchData()
    const still = data.value.some(item => item.status === 'generating')
    if (!still) {
      stopPolling()
      ElMessage.success('内容生成完成！')
      // 如果勾选了"自动发布"，弹出账号选择对话框
      if (autoPublishRequested.value && generatedContentIds.value.length > 0) {
        setTimeout(() => openAutoPublishDialog(), 500)
      }
    }
  }, 3000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// ── 自动发布：账号选择 ──
async function openAutoPublishDialog() {
  // 1. 从当前列表中找出刚刚生成的内容
  const ids = generatedContentIds.value
  const found = data.value.filter(item => ids.includes(item.id) && item.status !== 'generating')
  if (found.length === 0) {
    // 可能不在当前页，直接 fetchById
    autoPubContents.value = []
    ElMessage.warning('未找到已生成的内容，请手动刷新后发布')
    return
  }

  autoPubContents.value = found.map(item => ({
    id: item.id,
    title: item.title || '（标题为空）',
    platform: item.platform,
    platformLabel: platformLabel(item.platform),
  }))

  // 2. 加载账号列表
  await loadAutoPubAccounts()

  // 3. 清空之前的映射
  for (const key of Object.keys(autoPubAccountMap)) {
    delete autoPubAccountMap[key]
  }
  // 自动预选：为每个平台匹配第一个 active 账号
  for (const content of autoPubContents.value) {
    const accts = autoPubAccountsByPlatform.value[content.platform] || []
    const activeAcct = accts.find(a => !a.disabled)
    if (activeAcct) {
      autoPubAccountMap[content.id] = activeAcct.id
    }
  }

  autoPubVisible.value = true
}

async function loadAutoPubAccounts() {
  try {
    const res = await getAccounts()
    const raw = Array.isArray(res) ? res : (res.items || res.data || [])
    const byPlatform = {}
    const all = raw.map(a => {
      const expired = a.status === 'expired'
      const item = {
        id: a.id,
        label: `${a.account_name || a.platform}（${platformLabel(a.platform)}）${expired ? ' [已过期]' : ''}`,
        platform: a.platform,
        disabled: expired,
      }
      if (!byPlatform[a.platform]) byPlatform[a.platform] = []
      byPlatform[a.platform].push(item)
      return item
    })
    autoPubAccounts.value = all
    autoPubAccountsByPlatform.value = byPlatform
  } catch {
    autoPubAccounts.value = []
    autoPubAccountsByPlatform.value = {}
  }
}

function getAccountsForPlatform(platform) {
  return autoPubAccountsByPlatform.value[platform] || []
}

function canAutoPublish() {
  // 需要每个内容都选了账号
  return autoPubContents.value.every(c => autoPubAccountMap[c.id])
}

async function doBatchPublish() {
  if (!canAutoPublish()) return ElMessage.warning('请为每个内容选择发布账号')

  autoPubLoading.value = true
  let success = 0
  let fail = 0
  const errors = []

  for (const content of autoPubContents.value) {
    const accountId = autoPubAccountMap[content.id]
    if (!accountId) continue
    try {
      await submitPublish({
        content_id: content.id,
        account_id: accountId,
        publish_strategy: 'immediate',
      })
      success++
    } catch (e) {
      fail++
      errors.push(`${content.platformLabel}: ${e?.response?.data?.detail || e.message}`)
    }
  }

  autoPubLoading.value = false
  autoPubVisible.value = false
  autoPublishRequested.value = false
  generatedContentIds.value = []

  if (fail === 0) {
    ElMessage.success(`已提交 ${success} 篇内容发布任务`)
  } else {
    ElMessage.warning(`发布结果：${success} 成功，${fail} 失败。${errors.join('; ')}`)
  }
  fetchData()
}

function skipAutoPublish() {
  autoPubVisible.value = false
  autoPublishRequested.value = false
  generatedContentIds.value = []
  ElMessage.info('已跳过发布，可稍后在发布管理中手动发布')
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
