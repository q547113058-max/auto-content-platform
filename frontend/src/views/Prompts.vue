<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">提示词管理</h3>
      <el-button type="primary" @click="openCreate()">+ 新建版本</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="data" v-loading="loading">
        <el-table-column prop="platform" label="平台" width="120">
          <template #default="{ row }"><el-tag size="small">{{ platformLabel(row.platform) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="version" label="版本号" width="100">
          <template #default="{ row }"><span class="mono" style="color:var(--accent)">v{{ row.version }}</span></template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '使用中' : '未激活' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="system_prompt" label="系统提示词" min-width="260" show-overflow-tooltip />
        <el-table-column prop="change_log" label="变更日志" min-width="160" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="160">
          <template #default="{ row }"><span class="text-muted">{{ row.updated_at }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_active" text type="warning" size="small" @click="doActivate(row.id)">激活</el-button>
            <el-button text type="danger" size="small" @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" destroy-on-close>
      <el-form :model="form" label-width="100px" label-position="left">
        <el-form-item label="平台" required>
          <el-select v-model="form.platform" style="width:100%">
            <el-option v-for="p in platforms" :key="p.key" :label="p.label" :value="p.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本号" required>
          <el-input-number v-model="form.version" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="form.system_prompt" type="textarea" :rows="6" placeholder="系统级提示词" />
        </el-form-item>
        <el-form-item label="模板">
          <el-input v-model="form.template" type="textarea" :rows="4" placeholder="内容模板" />
        </el-form-item>
        <el-form-item label="变更日志">
          <el-input v-model="form.change_log" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/prompts'
import { useCrud } from '@/composables/useCrud'

const crud = useCrud(api.getPrompts, api.createPrompt, api.updatePrompt, api.deletePrompt)
const { data, loading, dialogVisible, dialogTitle, form, formLoading,
        openCreate, openEdit, submit, remove } = crud

const platforms = [
  { key: 'xiaohongshu', label: '小红书' }, { key: 'zhihu', label: '知乎' },
  { key: 'weibo', label: '微博' }, { key: 'wechat', label: '微信公众号' },
  { key: 'toutiao', label: '今日头条' }, { key: 'douyin', label: '抖音图文' }
]
const platformMap = Object.fromEntries(platforms.map(p => [p.key, p.label]))
function platformLabel(k) { return platformMap[k] || k }

async function doActivate(id) {
  try {
    await api.activatePrompt(id)
    ElMessage.success('已激活')
    crud.fetch()
  } catch { /* handled by interceptor */ }
}

onMounted(() => crud.fetch())
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
