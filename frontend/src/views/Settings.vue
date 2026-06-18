<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">系统设置</h3>
    </div>

    <el-card shadow="never" style="margin-bottom:20px">
      <template #header><span class="mono">AI 模型配置</span></template>
      <el-form label-width="120px" label-position="left">
        <el-form-item label="LLM Provider">
          <el-select v-model="settings.llm_provider" style="width:200px">
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="Qwen (通义千问)" value="qwen" />
            <el-option label="OpenAI" value="openai" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="settings.api_key" type="password" show-password style="width:400px" />
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="settings.api_base" style="width:400px" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="settings.model" style="width:300px" placeholder="deepseek-chat" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveAi">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-bottom:20px">
      <template #header><span class="mono">图片生成配置</span></template>
      <el-form label-width="120px" label-position="left">
        <el-form-item label="Provider">
          <el-select v-model="settings.image_provider" style="width:200px">
            <el-option label="DashScope" value="dashscope" />
            <el-option label="ARK" value="ark" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="settings.image_api_key" type="password" show-password style="width:400px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveImage">保存配置</el-button>
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
          <el-button type="primary" @click="saveDb">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const SETTINGS_KEY = 'auto-content-platform-settings'

const settings = reactive({
  llm_provider: 'deepseek',
  api_key: '',
  api_base: '',
  model: '',
  image_provider: 'dashscope',
  image_api_key: '',
  db_type: 'postgresql',
  db_host: '',
  db_port: '5433',
  db_name: ''
})

onMounted(() => {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY)
    if (saved) {
      Object.assign(settings, JSON.parse(saved))
    }
  } catch {}
})

function persistSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
}

function saveAi() {
  persistSettings()
  ElMessage.success('AI 配置已保存到本地')
}
function saveImage() {
  persistSettings()
  ElMessage.success('图片生成配置已保存到本地')
}
function saveDb() {
  persistSettings()
  ElMessage.success('数据库配置已保存到本地')
}
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
