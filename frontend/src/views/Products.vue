<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">产品管理</h3>
      <el-button type="primary" @click="openCreate()">+ 添加产品</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="data" v-loading="loading">
        <el-table-column label="图片" width="70">
          <template #default="{ row }">
            <el-image
              v-if="row.image"
              :src="row.image"
              fit="cover"
              style="width:40px;height:40px;border-radius:4px"
              :preview-src-list="[row.image]"
              preview-teleported
            />
            <span v-else class="text-muted" style="font-size:11px">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="category" label="品类" width="120" />
        <el-table-column label="知识库" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.kb_doc_count > 0 ? 'success' : 'info'" size="small" effect="plain">
              {{ row.kb_doc_count || 0 }} 篇 MD
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="语调风格" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-muted">{{ row.tone_config?.style || row.tone_config || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="敏感词" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-muted">{{ Array.isArray(row.forbidden_words) ? row.forbidden_words.join(', ') : (row.forbidden_words || '-') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }"><span class="text-muted">{{ row.created_at }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="remove(row.id)">删除</el-button>
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
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="620px" destroy-on-close>
      <el-form :model="form" label-width="100px" label-position="left">
        <el-form-item label="产品图片">
          <div class="image-upload-row">
            <div class="image-preview-box" v-if="form.image">
              <el-image
                :src="form.image"
                fit="cover"
                style="width:80px;height:80px;border-radius:6px;border:1px solid var(--el-border-color-light)"
                :preview-src-list="[form.image]"
                preview-teleported
              />
              <el-button
                type="danger"
                size="small"
                circle
                :icon="Delete"
                class="image-remove-btn"
                @click="form.image = ''; imageUploading = false; imageSource = ''"
              />
            </div>
            <div v-else class="image-placeholder">暂无图片</div>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="image/jpeg,image/png,image/webp,image/gif"
              :on-change="handleImageUpload"
              :disabled="imageUploading"
            >
              <el-button :loading="imageUploading" size="small" type="default">
                {{ imageUploading ? '上传中...' : '选择图片' }}
              </el-button>
            </el-upload>
            <span class="kb-hint" v-if="imageSource">{{ imageSource }}</span>
          </div>
        </el-form-item>
        <el-form-item label="所属公司">
          <el-select v-model="form.company_id" placeholder="选择公司（可选）" clearable style="width:100%">
            <el-option
              v-for="c in companies"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="产品名称" required>
          <el-input v-model="form.name" placeholder="如：某某精华液" />
        </el-form-item>
        <el-form-item label="品类">
          <el-input v-model="form.category" placeholder="如：护肤品" />
        </el-form-item>
        <el-form-item label="语调风格">
          <el-input v-model="form.tone" placeholder="如：亲切专业" />
        </el-form-item>
        <el-form-item label="敏感词">
          <el-input v-model="form.sensitive_words" type="textarea" :rows="3" placeholder="逗号分隔，如：违禁词1,违禁词2" />
        </el-form-item>

        <!-- 知识库文档 (MD) — 编辑模式下可管理，新建模式下提示 -->
        <el-divider content-position="left">知识库文档 (MD)</el-divider>
        <template v-if="isEdit">
          <div class="kb-doc-list">
            <div v-for="doc in kbDocs" :key="doc.id" class="kb-doc-item">
              <div class="kb-doc-info">
                <span class="kb-doc-title mono">{{ doc.title }}</span>
                <span class="text-muted" style="font-size:11px">{{ doc.category }} · {{ doc.word_count }}字</span>
              </div>
              <div class="kb-doc-actions">
                <el-button text size="small" @click.stop="openDocEdit(doc)">编辑</el-button>
                <el-button text size="small" type="danger" @click.stop="deleteDoc(doc.id)">删除</el-button>
              </div>
            </div>
            <div v-if="kbDocs.length === 0" class="text-muted" style="padding:8px 0;font-size:13px">
              暂无知识库文档，点击下方按钮新建
            </div>
          </div>
          <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <el-button size="small" type="primary" @click="openDocCreate()">+ 新建 MD 文档</el-button>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".docx,.xlsx"
              :on-change="handleKBUpload"
              :disabled="kbUploading"
            >
              <el-button size="small" :loading="kbUploading">
                {{ kbUploading ? '解析中...' : '📄 上传 Word / Excel' }}
              </el-button>
            </el-upload>
          </div>
        </template>
        <div v-else class="text-muted" style="font-size:13px;padding:8px 0">
          保存产品后可添加 Markdown 知识库文档
        </div>
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
            <el-option label="产品介绍" value="product" />
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
            placeholder="# 产品概述&#10;&#10;正文内容，支持 Markdown 格式..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="docDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="docSaving" @click="saveDoc">保存文档</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProducts, createProduct, updateProduct, deleteProduct, uploadProductImage } from '@/api/products'
import { getCompanies } from '@/api/companies'
import { getKBDocs, getKBDoc, createKBDoc, updateKBDoc, deleteKBDoc, uploadKBDoc } from '@/api/knowledge'
import { useCrud } from '@/composables/useCrud'

// 将后端字段映射回前端表单字段
function rowToForm(row) {
  return {
    name: row.name || '',
    category: row.category || '',
    company_id: row.company_id || null,
    image: row.image || '',
    tone: row.tone_config?.style || (typeof row.tone_config === 'string' ? row.tone_config : ''),
    sensitive_words: Array.isArray(row.forbidden_words) ? row.forbidden_words.join(', ') : (row.forbidden_words || '')
  }
}

const crud = useCrud(getProducts, createProduct, updateProduct, deleteProduct)

// 重写 openCreate 设置表单默认值
function openCreate(defaults = {}) {
  crud.form.value = {
    name: '',
    category: '',
    company_id: null,
    image: '',
    tone: '',
    sensitive_words: '',
    ...defaults
  }
  crud.isEdit.value = false
  crud.editId.value = null
  crud.dialogTitle.value = '新增'
  crud.dialogVisible.value = true
  imageUploading.value = false
  imageSource.value = ''
  kbDocs.value = []
}

// 重写 openEdit 转换后端数据到表单字段
async function openEdit(row) {
  crud.isEdit.value = true
  crud.editId.value = row.id
  crud.dialogTitle.value = '编辑'
  crud.form.value = rowToForm(row)
  crud.dialogVisible.value = true
  imageUploading.value = false
  imageSource.value = ''
  // 加载关联知识库文档
  await loadKBDocs(row.id)
}

const { data, total, loading, query, dialogVisible, dialogTitle, form, formLoading, isEdit,
        submit, remove, handleSizeChange, handlePageChange } = crud

// ========== 图片上传 ==========
const imageUploading = ref(false)
const imageSource = ref('')

async function handleImageUpload(file) {
  const name = (file.name || '').toLowerCase()
  const allowed = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
  if (!allowed.some(ext => name.endsWith(ext))) {
    ElMessage.warning('请选择 JPG/PNG/WebP/GIF 格式的图片')
    return
  }
  if (file.raw.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }

  imageUploading.value = true
  imageSource.value = ''

  try {
    const res = await uploadProductImage(file.raw)
    if (res.success && res.data) {
      form.value.image = res.data.url
      imageSource.value = file.name
      ElMessage.success('图片上传成功')
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '上传失败'
    ElMessage.error(msg)
  } finally {
    imageUploading.value = false
  }
}

// ========== 公司列表 ==========
const companies = ref([])
async function loadCompanies() {
  try {
    const res = await getCompanies()
    companies.value = res || []
  } catch { companies.value = [] }
}

// ========== 知识库文档管理 ==========
const kbDocs = ref([])
const kbUploading = ref(false)
const docDialogVisible = ref(false)
const docSaving = ref(false)
const docEditId = ref(null)
const docForm = ref({ title: '', content: '', category: 'product' })

async function loadKBDocs(productId) {
  try {
    const res = await getKBDocs({ product_id: productId, page_size: 100 })
    kbDocs.value = res.items || []
  } catch { kbDocs.value = [] }
}

function openDocCreate() {
  docEditId.value = null
  docForm.value = { title: '', content: '', category: 'product' }
  docDialogVisible.value = true
}

async function openDocEdit(doc) {
  docEditId.value = doc.id
  try {
    const res = await getKBDoc(doc.id)
    docForm.value = {
      title: res.title || '',
      content: res.content || '',
      category: res.category || 'product'
    }
    docDialogVisible.value = true
  } catch { /* */ }
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
        product_id: crud.editId.value
      })
      ElMessage.success('文档已创建')
    }
    docDialogVisible.value = false
    await loadKBDocs(crud.editId.value)
  } catch { /* */ }
  finally { docSaving.value = false }
}

async function deleteDoc(docId) {
  try {
    await ElMessageBox.confirm('确定删除该知识库文档？', '确认删除', { type: 'warning' })
    await deleteKBDoc(docId)
    ElMessage.success('已删除')
    await loadKBDocs(crud.editId.value)
  } catch { /* cancelled */ }
}

async function handleKBUpload(file) {
  const name = (file.name || '').toLowerCase()
  if (!name.endsWith('.docx') && !name.endsWith('.xlsx')) {
    ElMessage.warning('请选择 .docx 或 .xlsx 格式的文件')
    return
  }
  kbUploading.value = true
  try {
    const res = await uploadKBDoc(file.raw, { productId: crud.editId.value })
    ElMessage.success(`已上传并生成知识库文档：${res.title}`)
    await loadKBDocs(crud.editId.value)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '上传失败'
    ElMessage.error(msg)
  } finally {
    kbUploading.value = false
  }
}

onMounted(() => { crud.fetch(); loadCompanies() })
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.image-upload-row {
  display: flex; align-items: flex-start; gap: 12px;
  flex-wrap: wrap;
}
.image-preview-box {
  position: relative;
  .image-remove-btn {
    position: absolute; top: -6px; right: -6px;
    width: 20px; height: 20px;
    font-size: 10px;
    opacity: 0;
    transition: opacity 0.2s;
  }
  &:hover .image-remove-btn {
    opacity: 1;
  }
}
.image-placeholder {
  width: 80px; height: 80px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--el-text-color-placeholder);
}
.kb-hint {
  font-size: 12px;
  color: var(--el-color-success);
}
.kb-doc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
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
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
