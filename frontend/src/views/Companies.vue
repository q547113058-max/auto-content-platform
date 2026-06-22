<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">公司/品牌管理</h3>
      <el-button type="primary" @click="openCreate()">+ 添加公司</el-button>
    </div>

    <!-- 公司卡片列表 -->
    <div v-loading="loading" class="company-grid">
      <div
        v-for="c in data"
        :key="c.id"
        class="company-card"
        @click="openEdit(c)"
      >
        <div class="company-card-header">
          <el-avatar :size="48" shape="square" :src="c.logo" style="background:var(--accent);color:#111;font-weight:700;font-size:20px">
            {{ c.name?.charAt(0) || '?' }}
          </el-avatar>
          <div class="company-info">
            <div class="company-name mono">{{ c.name }}</div>
            <div class="company-slug text-muted">slug: {{ c.slug }}</div>
          </div>
        </div>
        <div class="company-desc" v-if="c.description">{{ c.description }}</div>
        <div class="company-meta">
          <el-tag v-if="c.industry" size="small" type="info" effect="plain">{{ c.industry }}</el-tag>
          <span class="text-muted" style="font-size:12px;margin-left:auto">
            {{ c.product_count || 0 }} 产品 · {{ c.doc_count || 0 }} 知识库文档
          </span>
        </div>
      </div>
      <el-empty v-if="!loading && data.length === 0" description="暂无公司/品牌" />
    </div>

    <!-- 编辑/新增 Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form :model="form" label-width="100px" label-position="left">
        <el-form-item label="公司名称" required>
          <el-input v-model="form.name" placeholder="如：鱼开心智能科技" />
        </el-form-item>
        <el-form-item label="行业领域">
          <el-input v-model="form.industry" placeholder="如：智慧渔业、智能硬件" />
        </el-form-item>
        <el-form-item label="Logo URL">
          <el-input v-model="form.logo" placeholder="图片链接（可选）" />
        </el-form-item>
        <el-form-item label="公司简介">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简要描述公司品牌..." />
        </el-form-item>

        <!-- 知识库文档 Tab（编辑模式） -->
        <template v-if="isEdit">
          <el-divider content-position="left">知识库文档</el-divider>
          <div class="kb-doc-list">
            <div
              v-for="doc in kbDocs"
              :key="doc.id"
              class="kb-doc-item"
            >
              <div class="kb-doc-info">
                <span class="kb-doc-title mono">{{ doc.title }}</span>
                <span class="text-muted" style="font-size:11px">{{ doc.category }} · {{ doc.word_count }}字</span>
              </div>
              <div class="kb-doc-actions">
                <el-button text size="small" @click.stop="openDocEdit(doc)">编辑</el-button>
                <el-button text size="small" type="danger" @click.stop="deleteDoc(doc.id)">删除</el-button>
              </div>
            </div>
            <div v-if="kbDocs.length === 0" class="text-muted" style="padding:12px 0;font-size:13px">暂无知识库文档</div>
          </div>
          <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <el-button size="small" type="primary" @click="openDocCreate()">+ 新建文档</el-button>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".docx,.xlsx,.md"
              :on-change="handleKBUpload"
              :disabled="kbUploading"
            >
              <el-button size="small" :loading="kbUploading" :icon="kbUploading ? '' : undefined">
                {{ kbUploading ? '解析中...' : '📄 上传文档' }}
              </el-button>
            </el-upload>
            <el-button size="small" @click="scanKB()">📂 扫描文件夹</el-button>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 知识库文档编辑 Dialog -->
    <el-dialog v-model="docDialogVisible" title="编辑知识库文档" width="640px" destroy-on-close>
      <el-form label-width="80px" label-position="left">
        <el-form-item label="标题">
          <el-input v-model="docForm.title" placeholder="文档标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="docForm.category" style="width:100%">
            <el-option label="公司介绍" value="company" />
            <el-option label="行业背景" value="industry" />
            <el-option label="产品相关" value="product" />
            <el-option label="FAQ" value="faq" />
            <el-option label="案例" value="case" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="Markdown">
          <el-input
            v-model="docForm.content"
            type="textarea"
            :rows="14"
            placeholder="# 标题&#10;&#10;正文内容，支持 Markdown 格式..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="docDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="docSaving" @click="saveDoc">保存文档</el-button>
      </template>
    </el-dialog>

    <!-- 知识库文档内容预览 Dialog -->
    <el-dialog v-model="previewVisible" title="文档预览" width="700px">
      <div class="kb-preview" v-html="renderedContent"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCompanies, createCompany, updateCompany, deleteCompany } from '@/api/companies'
import { getKBDocs, getKBDoc, createKBDoc, updateKBDoc, deleteKBDoc, scanKnowledgeBase, uploadKBDoc } from '@/api/knowledge'

// ========== 公司 CRUD ==========
const data = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增公司')
const isEdit = ref(false)
const editId = ref(null)
const formLoading = ref(false)

const form = ref({
  name: '', slug: '', industry: '', logo: '', description: ''
})

// 自动根据名称生成 slug（仅新增模式）
function slugify(name) {
  // 简单中英文混合 slug：保留字母数字和中文，其他字符替换为连字符
  let slug = name.toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-+/g, '-')
  if (!slug) slug = 'company-' + Date.now().toString(36)
  return slug
}
watch(() => form.value.name, (val) => {
  if (!isEdit.value && val) {
    form.value.slug = slugify(val)
  }
})

const kbDocs = ref([])
const kbUploading = ref(false)

function openCreate() {
  isEdit.value = false
  editId.value = null
  dialogTitle.value = '新增公司'
  form.value = { name: '', slug: '', industry: '', logo: '', description: '' }
  kbDocs.value = []
  dialogVisible.value = true
}

async function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  dialogTitle.value = '编辑公司'
  form.value = {
    name: row.name || '',
    slug: row.slug || '',
    industry: row.industry || '',
    logo: row.logo || '',
    description: row.description || ''
  }
  // 加载关联的知识库文档
  await loadKBDocs(row.id)
  dialogVisible.value = true
}

async function loadKBDocs(companyId) {
  try {
    const res = await getKBDocs({ company_id: companyId, page_size: 100 })
    kbDocs.value = res.items || []
  } catch { kbDocs.value = [] }
}

async function submit() {
  if (!form.value.name) {
    ElMessage.warning('请填写公司名称')
    return
  }
  formLoading.value = true
  try {
    if (isEdit.value) {
      await updateCompany(editId.value, form.value)
      ElMessage.success('公司信息已更新')
    } else {
      await createCompany(form.value)
      ElMessage.success('公司已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    formLoading.value = false
  }
}

async function remove(id) {
  try {
    await ElMessageBox.confirm('确定删除该公司？关联的知识库文档将一并删除。', '确认删除', { type: 'warning' })
    await deleteCompany(id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* cancelled */ }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getCompanies()
    data.value = res || []
  } catch { data.value = [] }
  finally { loading.value = false }
}

// ========== 知识库文档管理 ==========
const docDialogVisible = ref(false)
const docSaving = ref(false)
const docEditId = ref(null)
const docForm = ref({ title: '', content: '', category: 'company' })

function openDocCreate() {
  docEditId.value = null
  docForm.value = { title: '', content: '', category: 'company' }
  docDialogVisible.value = true
}

async function openDocEdit(doc) {
  docEditId.value = doc.id
  try {
    const res = await getKBDoc(doc.id)
    docForm.value = {
      title: res.title || '',
      content: res.content || '',
      category: res.category || 'company'
    }
    docDialogVisible.value = true
  } catch { /* error handled by interceptor */ }
}

async function saveDoc() {
  if (!docForm.value.title.trim()) {
    ElMessage.warning('请输入文档标题')
    return
  }
  docSaving.value = true
  try {
    if (docEditId.value) {
      await updateKBDoc(docEditId.value, docForm.value)
      ElMessage.success('文档已更新')
    } else {
      await createKBDoc({
        ...docForm.value,
        company_id: editId.value
      })
      ElMessage.success('文档已创建')
    }
    docDialogVisible.value = false
    await loadKBDocs(editId.value)
  } catch { /* */ }
  finally { docSaving.value = false }
}

async function deleteDoc(docId) {
  try {
    await ElMessageBox.confirm('确定删除该知识库文档？', '确认删除', { type: 'warning' })
    await deleteKBDoc(docId)
    ElMessage.success('已删除')
    await loadKBDocs(editId.value)
  } catch { /* cancelled */ }
}

async function scanKB() {
  try {
    const res = await scanKnowledgeBase()
    ElMessage.success(res.message || '扫描完成')
    await loadKBDocs(editId.value)
  } catch { /* */ }
}

async function handleKBUpload(file) {
  const name = (file.name || '').toLowerCase()
  if (!name.endsWith('.docx') && !name.endsWith('.xlsx') && !name.endsWith('.md')) {
    ElMessage.warning('请选择 .docx、.xlsx 或 .md 格式的文件')
    return
  }
  kbUploading.value = true
  try {
    const res = await uploadKBDoc([file.raw], { companyId: editId.value })
    ElMessage.success(`已上传并生成知识库文档：${res.title}`)
    await loadKBDocs(editId.value)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '上传失败'
    ElMessage.error(msg)
  } finally {
    kbUploading.value = false
  }
}

// ========== 预览 ==========
const previewVisible = ref(false)
const renderedContent = computed(() => {
  // 简单 Markdown 渲染
  const md = docForm.value.content || ''
  return md
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
})

onMounted(fetchData)
</script>

<style scoped>
.company-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.company-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.company-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}
.company-card-header {
  display: flex;
  align-items: center;
  gap: 14px;
}
.company-info {
  flex: 1;
  min-width: 0;
}
.company-name {
  font-size: 16px;
  font-weight: 600;
}
.company-slug {
  font-size: 12px;
  margin-top: 2px;
}
.company-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 12px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.company-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}
.kb-doc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kb-doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-deep);
  border-radius: 6px;
}
.kb-doc-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kb-doc-title {
  font-size: 13px;
  font-weight: 500;
}
.kb-preview {
  max-height: 60vh;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}
.kb-preview h2 { font-size: 18px; margin: 16px 0 8px; }
.kb-preview h3 { font-size: 16px; margin: 12px 0 6px; }
.kb-preview h4 { font-size: 14px; margin: 10px 0 4px; }
.kb-preview p { margin: 8px 0; }
.kb-preview li { margin-left: 20px; }
</style>
