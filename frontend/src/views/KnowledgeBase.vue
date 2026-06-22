<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">知识库管理</h3>
      <div style="display:flex;gap:8px">
        <el-button type="success" @click="openUploadDialog()">
          <el-icon style="margin-right:4px"><Upload /></el-icon>上传 MD/文档
        </el-button>
        <el-button type="primary" @click="openCreateDialog()">+ 新建文档</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-row :gutter="16" style="display:flex;align-items:center;flex-wrap:wrap;gap:8px">
        <el-col :span="6">
          <el-select v-model="filter.company_id" placeholder="筛选公司" clearable style="width:100%" @change="handleFilterChange">
            <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select v-model="filter.product_id" placeholder="筛选产品" clearable style="width:100%" @change="handleFilterChange">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select v-model="filter.category" placeholder="筛选分类" clearable style="width:100%" @change="handleFilterChange">
            <el-option label="company" value="company" />
            <el-option label="product" value="product" />
            <el-option label="standalone" value="standalone" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-input v-model="search" placeholder="搜索标题..." clearable @clear="handleFilterChange" @keyup.enter="handleFilterChange">
            <template #append>
              <el-button @click="handleFilterChange"><el-icon><Search /></el-icon></el-button>
            </template>
          </el-input>
        </el-col>
      </el-row>
    </el-card>

    <!-- 文档列表 -->
    <el-card shadow="never">
      <el-table :data="docs" v-loading="loading" empty-text="暂无知识库文档，点击「上传」或「新建」添加">
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="关联" width="180">
          <template #default="{ row }">
            <el-tag v-if="row.company_name" size="small" type="info">{{ row.company_name }}</el-tag>
            <el-tag v-if="row.product_name" size="small" type="success">{{ row.product_name }}</el-tag>
            <span v-if="!row.company_name && !row.product_name" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.category || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="90">
          <template #default="{ row }">
            <span class="text-muted" style="font-size:12px">{{ sourceLabel(row.source) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="word_count" label="字数" width="80" align="right">
          <template #default="{ row }">
            <span class="text-muted">{{ row.word_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="160">
          <template #default="{ row }">
            <span class="text-muted">{{ row.updated_at || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openPreview(row)">查看</el-button>
            <el-button text type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > query.page_size"
        style="margin-top:16px;justify-content:flex-end"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50]"
        @size-change="fetchDocs"
        @current-change="fetchDocs"
      />
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="560px" destroy-on-close>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :accept="'.md,.docx,.xlsx'"
        :on-change="handleFileChange"
        drag
        style="width:100%"
      >
        <el-icon style="font-size:40px;color:var(--el-color-primary)"><Upload /></el-icon>
        <div style="margin-top:8px">
          拖拽文件到此处，或 <em>点击选择</em>
        </div>
        <div class="el-upload__tip">
          支持 .md / .docx / .xlsx 格式，自动转为 Markdown 知识库文档
        </div>
      </el-upload>

      <el-form :model="uploadForm" label-width="90px" label-position="left" style="margin-top:16px">
        <el-form-item label="关联公司">
          <el-select v-model="uploadForm.company_id" placeholder="可选" clearable style="width:100%">
            <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联产品">
          <el-select v-model="uploadForm.product_id" placeholder="可选" clearable style="width:100%">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload()">上传并导入</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="editDialogVisible" :title="editMode === 'create' ? '新建文档' : '编辑文档'" width="800px" destroy-on-close>
      <el-form :model="editForm" label-width="90px" label-position="left">
        <el-form-item label="标题" required>
          <el-input v-model="editForm.title" placeholder="文档标题" />
        </el-form-item>
        <el-form-item label="关联公司">
          <el-select v-model="editForm.company_id" placeholder="可选" clearable style="width:100%">
            <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联产品">
          <el-select v-model="editForm.product_id" placeholder="可选" clearable style="width:100%">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editForm.category" placeholder="如：product、company、faq" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input
            v-model="editForm.content"
            type="textarea"
            :rows="18"
            placeholder="Markdown 格式内容..."
            style="font-family:monospace"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit()">保存</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" title="文档预览" width="800px" destroy-on-close>
      <div v-if="previewDoc">
        <div style="margin-bottom:12px">
          <el-tag v-if="previewDoc.company_name" size="small" type="info">{{ previewDoc.company_name }}</el-tag>
          <el-tag v-if="previewDoc.product_name" size="small" type="success">{{ previewDoc.product_name }}</el-tag>
          <el-tag size="small" effect="plain" style="margin-left:8px">{{ previewDoc.category }}</el-tag>
        </div>
        <div class="md-preview" style="max-height:60vh;overflow:auto;padding:16px;border:1px solid var(--el-border-color-light);border-radius:6px;background:#fafafa">
          <pre style="white-space:pre-wrap;font-family:monospace;font-size:13px;line-height:1.7;color:#333;margin:0">{{ previewDoc.content }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Search } from '@element-plus/icons-vue'
import {
  getKBDocs, getKBDoc, createKBDoc, updateKBDoc, deleteKBDoc, uploadKBDoc
} from '@/api/knowledge.js'
import { getCompanies } from '@/api/companies.js'
import { getProducts } from '@/api/products.js'

const docs = ref([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const search = ref('')

const filter = ref({
  company_id: null,
  product_id: null,
  category: null,
})
const query = ref({
  page: 1,
  page_size: 20,
})

const companies = ref([])
const products = ref([])

// 上传对话框
const uploadDialogVisible = ref(false)
const uploadForm = ref({ company_id: null, product_id: null })
const selectedFiles = ref([])

// 编辑对话框
const editDialogVisible = ref(false)
const editMode = ref('create')
const editForm = ref({ id: null, title: '', content: '', company_id: null, product_id: null, category: 'product' })

// 预览
const previewVisible = ref(false)
const previewDoc = ref(null)

async function fetchDocs() {
  loading.value = true
  try {
    const params = {
      page: query.value.page,
      page_size: query.value.page_size,
    }
    if (filter.value.company_id) params.company_id = filter.value.company_id
    if (filter.value.product_id) params.product_id = filter.value.product_id
    if (filter.value.category) params.category = filter.value.category
    const res = await getKBDocs(params)
    const d = res.data || res
    docs.value = d.items || []
    total.value = d.total || 0
  } catch (e) {
    ElMessage.error('获取知识库列表失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function fetchCompanies() {
  try {
    const res = await getCompanies({ page_size: 100 })
    const d = res.data || res
    companies.value = d.items || d || []
  } catch {}
}
async function fetchProducts() {
  try {
    const res = await getProducts({ page_size: 100 })
    const d = res.data || res
    products.value = d.items || d || []
  } catch {}
}

function handleFilterChange() {
  query.value.page = 1
  fetchDocs()
}

function sourceLabel(s) {
  const m = { manual: '手动创建', scanned: '文件夹扫描', uploaded: '文件上传', import: '导入' }
  return m[s] || s || '-'
}

// 上传
function openUploadDialog() {
  uploadForm.value = { company_id: null, product_id: null }
  selectedFiles.value = []
  uploadDialogVisible.value = true
}
function handleFileChange(file) {
  if (file.raw) {
    selectedFiles.value.push(file.raw)
  }
}
async function submitUpload() {
  const files = selectedFiles.value
  if (files.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  if (!uploadForm.value.company_id && !uploadForm.value.product_id) {
    ElMessage.warning('请至少关联一个公司或产品')
    return
  }
  uploading.value = true
  try {
    const res = await uploadKBDoc(files, {
      companyId: uploadForm.value.company_id,
      productId: uploadForm.value.product_id,
    })
    const d = res.data || res
    const results = d.results || []
    const errors = d.errors || []
    if (results.length > 0) {
      ElMessage.success(`成功上传 ${results.length} 个文件`)
    }
    if (errors.length > 0) {
      const msg = errors.map(e => `${e.file}: ${e.error}`).join('; ')
      nextTick(() => ElMessage.warning(`上传失败 ${errors.length} 个：${msg}`))
    }
    uploadDialogVisible.value = false
    fetchDocs()
  } catch (e) {
    let msg = '上传失败'
    const detail = e.response?.data?.detail
    if (Array.isArray(detail)) {
      msg += '：' + detail.map(d => d.msg || JSON.stringify(d)).join('; ')
    } else if (detail) {
      msg += '：' + detail
    } else if (e.message) {
      msg += '：' + e.message
    }
    ElMessage.error(msg)
  } finally {
    uploading.value = false
  }
}

// 新建
function openCreateDialog() {
  editMode.value = 'create'
  editForm.value = { id: null, title: '', content: '', company_id: null, product_id: null, category: 'product' }
  editDialogVisible.value = true
}
// 编辑
function openEditDialog(row) {
  editMode.value = 'edit'
  editForm.value = {
    id: row.id,
    title: row.title,
    content: '',
    company_id: row.company_id,
    product_id: row.product_id,
    category: row.category || 'product',
  }
  // 获取完整内容
  getKBDoc(row.id).then(res => {
    const d = res.data || res
    editForm.value.content = d.content || ''
  })
  editDialogVisible.value = true
}
async function submitEdit() {
  if (!editForm.value.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (!editForm.value.content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  if (!editForm.value.company_id && !editForm.value.product_id) {
    ElMessage.warning('请至少关联一个公司或产品')
    return
  }
  saving.value = true
  try {
    if (editMode.value === 'create') {
      await createKBDoc({
        title: editForm.value.title,
        content: editForm.value.content,
        company_id: editForm.value.company_id,
        product_id: editForm.value.product_id,
        category: editForm.value.category,
      })
      ElMessage.success('创建成功')
    } else {
      await updateKBDoc(editForm.value.id, {
        title: editForm.value.title,
        content: editForm.value.content,
        company_id: editForm.value.company_id,
        product_id: editForm.value.product_id,
        category: editForm.value.category,
      })
      ElMessage.success('更新成功')
    }
    editDialogVisible.value = false
    fetchDocs()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

// 预览
async function openPreview(row) {
  try {
    const res = await getKBDoc(row.id)
    previewDoc.value = res.data || res
    previewVisible.value = true
  } catch (e) {
    ElMessage.error('获取文档失败：' + (e.response?.data?.detail || e.message))
  }
}

// 删除
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？`, '确认删除', { type: 'warning' })
    await deleteKBDoc(row.id)
    ElMessage.success('已删除')
    fetchDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  fetchCompanies()
  fetchProducts()
  fetchDocs()
})
</script>

<style scoped>
.page { padding: 20px; }
.page-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.mono { font-family: monospace; }
.text-muted { color: #999; font-size: 13px; }
.md-preview { font-size: 13px; line-height: 1.7; }
</style>
