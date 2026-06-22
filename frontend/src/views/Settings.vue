<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">系统设置</h3>
      <el-tag v-if="loading" type="info" size="small">加载中...</el-tag>
      <el-tag v-else-if="loadError" type="danger" size="small">加载失败</el-tag>
    </div>

    <!-- 重启提示 -->
    <el-alert
      v-if="needRestart"
      title="配置已更新，请重启后端服务使新配置生效"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom:16px"
    />

    <el-card shadow="never" style="margin-bottom:20px">
      <template #header><span class="mono">AI 模型配置</span></template>
      <el-form label-width="120px" label-position="left">
        <el-form-item label="LLM Provider">
          <el-select v-model="settings.ai_provider" style="width:200px">
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="Qwen (通义千问)" value="qwen" />
            <el-option label="OpenAI" value="openai" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="settings.ai_api_key" type="password" show-password style="width:440px">
            <template #suffix>
              <el-tag v-if="settings.ai_api_key_set" type="success" size="small" style="margin-right:4px">已配置</el-tag>
              <el-tag v-else type="warning" size="small">未配置</el-tag>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="settings.ai_api_base" style="width:440px" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="settings.ai_model" style="width:300px" placeholder="deepseek-chat" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveAi" :loading="savingAi">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-bottom:20px">
      <template #header><span class="mono">图片生成配置</span></template>
      <el-form label-width="120px" label-position="left">
        <el-form-item label="Provider">
          <el-select v-model="settings.image_gen_provider" style="width:200px">
            <el-option label="Seedream (豆包)" value="seedream" />
            <el-option label="通义万象" value="tongyi-wanxiang" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="settings.image_gen_api_key" type="password" show-password style="width:440px">
            <template #suffix>
              <el-tag v-if="settings.image_gen_api_key_set" type="success" size="small" style="margin-right:4px">已配置</el-tag>
              <el-tag v-else type="warning" size="small">未配置</el-tag>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="settings.image_gen_api_base" style="width:440px" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="settings.image_gen_model" style="width:300px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveImage" :loading="savingImage">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="mono">数据库连接</span></template>
      <el-form label-width="120px" label-position="left">
        <el-form-item label="数据库类型">
          <el-select v-model="settings.db_type" style="width:200px">
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="SQLite" value="sqlite" />
          </el-select>
        </el-form-item>
        <el-form-item label="Host">
          <el-input v-model="settings.db_host" style="width:300px" placeholder="192.168.0.170" />
        </el-form-item>
        <el-form-item label="Port">
          <el-input v-model="settings.db_port" style="width:150px" placeholder="5433" />
        </el-form-item>
        <el-form-item label="Database">
          <el-input v-model="settings.db_name" style="width:300px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveDb" :loading="savingDb">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings } from '@/api/settings'

const loading = ref(true)
const loadError = ref(false)
const needRestart = ref(false)
const savingAi = ref(false)
const savingImage = ref(false)
const savingDb = ref(false)

const settings = reactive({
  ai_provider: 'deepseek',
  ai_api_key: '',
  ai_api_key_set: false,
  ai_api_base: '',
  ai_model: '',
  image_gen_provider: 'seedream',
  image_gen_api_key: '',
  image_gen_api_key_set: false,
  image_gen_api_base: '',
  image_gen_model: '',
  db_type: 'postgresql',
  db_host: '',
  db_port: 5433,
  db_name: ''
})

onMounted(async () => {
  loading.value = true
  try {
    const res = await getSettings()
    if (res.success !== false) {
      const data = res.success === undefined ? res : res
      Object.keys(settings).forEach(k => {
        if (k in data) settings[k] = data[k]
      })
    } else {
      loadError.value = true
    }
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
})

async function saveAi() {
  savingAi.value = true
  try {
    const res = await updateSettings({
      ai_provider: settings.ai_provider,
      ai_api_key: settings.ai_api_key,
      ai_api_base: settings.ai_api_base,
      ai_model: settings.ai_model
    })
    needRestart.value = true
    ElMessage.success(res.message || 'AI 配置已保存')
  } catch {
    // 错误已在 interceptor 中提示
  } finally {
    savingAi.value = false
  }
}

async function saveImage() {
  savingImage.value = true
  try {
    const res = await updateSettings({
      image_gen_provider: settings.image_gen_provider,
      image_gen_api_key: settings.image_gen_api_key,
      image_gen_api_base: settings.image_gen_api_base,
      image_gen_model: settings.image_gen_model
    })
    needRestart.value = true
    ElMessage.success(res.message || '图片生成配置已保存')
  } catch {
  } finally {
    savingImage.value = false
  }
}

async function saveDb() {
  savingDb.value = true
  try {
    const res = await updateSettings({
      db_type: settings.db_type,
      db_host: settings.db_host,
      db_port: Number(settings.db_port),
      db_name: settings.db_name
    })
    needRestart.value = true
    ElMessage.success(res.message || '数据库配置已保存')
  } catch {
  } finally {
    savingDb.value = false
  }
}
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
