import { ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

/**
 * Generic CRUD composable.
 * `apiModule` should export: { getList, getOne, create, update, remove }
 * or be a callable object with those methods.
 *
 * For standard API modules (exporting getXxx, createXxx, etc.),
 * pass them as separate named functions, e.g.:
 *   useCrud(getProducts, createProduct, updateProduct, deleteProduct)
 */
export function useCrud(getFn, createFn, updateFn, deleteFn, { listKey = 'items' } = {}) {
  const data = ref([])
  const total = ref(0)
  const loading = ref(false)
  const query = reactive({ page: 1, page_size: 20 })
  const dialogVisible = ref(false)
  const dialogTitle = ref('')
  const form = ref({})
  const formLoading = ref(false)
  const isEdit = ref(false)
  const editId = ref(null)

  async function fetch() {
    loading.value = true
    try {
      const res = await getFn(query)
      data.value = Array.isArray(res) ? res : (res?.[listKey] || res || [])
      total.value = res?.total || data.value.length
    } catch (e) {
      data.value = []
    } finally {
      loading.value = false
    }
  }

  function openCreate(defaults = {}) {
    isEdit.value = false
    editId.value = null
    dialogTitle.value = '新增'
    form.value = { ...defaults }
    dialogVisible.value = true
  }

  function openEdit(row) {
    isEdit.value = true
    editId.value = row.id
    dialogTitle.value = '编辑'
    form.value = { ...row }
    dialogVisible.value = true
  }

  async function submit() {
    formLoading.value = true
    try {
      if (isEdit.value) {
        await updateFn(editId.value, form.value)
        ElMessage.success('更新成功')
      } else {
        await createFn(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      await fetch()
    } finally {
      formLoading.value = false
    }
  }

  async function remove(id) {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await deleteFn(id)
    ElMessage.success('已删除')
    await fetch()
  }

  function handleSizeChange(size) {
    query.page_size = size
    query.page = 1
    fetch()
  }
  function handlePageChange(page) {
    query.page = page
    fetch()
  }

  return {
    data, total, loading, query,
    dialogVisible, dialogTitle, form, formLoading, isEdit, editId,
    fetch, openCreate, openEdit, submit, remove,
    handleSizeChange, handlePageChange
  }
}
