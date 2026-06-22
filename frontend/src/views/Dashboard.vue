<template>
  <div class="dashboard">
    <!-- Stats Row -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="12" :sm="6" v-for="stat in stats" :key="stat.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon" :style="{ color: stat.color }">
              <el-icon :size="28"><component :is="stat.icon" /></el-icon>
            </div>
            <div class="stat-body">
              <div class="stat-value mono">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top:20px">
      <!-- Recent Contents -->
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <span class="mono">最近内容</span>
              <el-button text type="primary" @click="router.push('/content-publish')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentContents" style="width:100%" size="small" v-loading="store.loading">
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="platform" label="平台" width="100">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ platformLabel(row.platform) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                <span class="text-muted">{{ formatDate(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!store.loading && recentContents.length === 0" description="暂无内容" />
        </el-card>
      </el-col>

      <!-- Platform Overview -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="content-card">
          <template #header>
            <span class="mono">平台概览</span>
          </template>
          <div class="platform-list">
            <div v-for="p in platforms" :key="p.key" class="platform-item">
              <div class="platform-info">
                <span class="platform-name">{{ p.label }}</span>
                <span class="text-muted" style="font-size:12px">{{ p.desc }}</span>
              </div>
              <el-tag size="small" :type="p.method === 'api' ? 'success' : 'warning'" effect="dark">
                {{ p.method === 'api' ? 'API' : 'Browser' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import dayjs from 'dayjs'

const router = useRouter()
const store = useAppStore()

const recentContents = computed(() => store.dashboard.recentContents || [])

const stats = computed(() => [
  { label: '产品数量', value: store.dashboard.productCount, icon: 'Goods', color: '#e8c547' },
  { label: '内容数量', value: store.dashboard.contentCount, icon: 'Document', color: '#60a5fa' },
  { label: '发布次数', value: store.dashboard.publishCount, icon: 'Promotion', color: '#34d399' },
  { label: '支持平台', value: 6, icon: 'Connection', color: '#f59e0b' }
])

const platforms = [
  { key: 'xiaohongshu', label: '小红书', desc: '种草笔记', method: 'playwright' },
  { key: 'zhihu', label: '知乎', desc: '专业深度', method: 'playwright' },
  { key: 'weibo', label: '微博', desc: '短图文', method: 'playwright' },
  { key: 'wechat', label: '微信公众号', desc: '品牌深度', method: 'api' },
  { key: 'toutiao', label: '今日头条', desc: '信息密度', method: 'playwright' },
  { key: 'douyin', label: '抖音图文', desc: '大字报', method: 'playwright' }
]

const platformMap = {
  xiaohongshu: '小红书', zhihu: '知乎', weibo: '微博',
  wechat: '微信公众号', toutiao: '今日头条', douyin: '抖音图文'
}
function platformLabel(key) {
  return platformMap[key] || key
}
function statusType(status) {
  return status === 'published' ? 'success' : status === 'draft' ? 'info' : 'warning'
}
function formatDate(d) {
  return d ? dayjs(d).format('MM-DD HH:mm') : '-'
}

onMounted(() => store.fetchDashboard())
</script>

<style lang="scss" scoped>
.stats-row {
  .stat-card {
    :deep(.el-card__body) { padding: 20px; }
  }
}
.stat-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stat-icon {
  width: 48px; height: 48px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-input);
  border-radius: 10px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.platform-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.platform-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-input);
  border-radius: 6px;
  border: 1px solid var(--border-color);
}
.platform-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
.platform-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.content-card {
  min-height: 320px;
}
</style>
