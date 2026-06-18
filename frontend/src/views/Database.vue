<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">数据库浏览</h3>
      <div style="display:flex;gap:8px">
        <el-select v-model="selectedTable" style="width:200px" @change="loadTable">
          <el-option v-for="t in tables" :key="t" :label="t" :value="t" />
        </el-select>
        <el-button @click="loadTable">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" max-height="calc(100vh - 260px)">
        <el-table-column
          v-for="col in columns"
          :key="col"
          :prop="col"
          :label="col"
          :min-width="140"
          show-overflow-tooltip
        />
      </el-table>
      <el-empty v-if="!loading && rows.length === 0" description="选择表查看数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index.js'

const tables = ['products', 'platform_accounts', 'contents', 'publish_records', 'content_metrics', 'optimization_changes', 'prompt_versions', 'scheduled_tasks']
const selectedTable = ref('products')
const columns = ref([])
const rows = ref([])
const loading = ref(false)

async function loadTable() {
  loading.value = true
  try {
    const res = await api.get(`/db/tables/${selectedTable.value}`, { params: { page_size: 100 } })
    const data = res.data || res || []
    const list = Array.isArray(data) ? data : []
    rows.value = list
    if (list.length > 0) {
      columns.value = Object.keys(list[0])
    } else {
      columns.value = []
    }
  } catch (e) {
    ElMessage.error('加载失败')
    rows.value = []
    columns.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
