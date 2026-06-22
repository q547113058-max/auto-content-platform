<template>
  <div class="page">
    <el-tabs v-model="activeTab" type="card" class="content-tabs" @tab-change="onTabChange">
      <el-tab-pane name="contents">
        <template #label>
          <el-icon><Document /></el-icon>
          <span>内容管理</span>
        </template>
        <ContentsView v-if="activeTab === 'contents'" />
      </el-tab-pane>

      <el-tab-pane name="publish">
        <template #label>
          <el-icon><Promotion /></el-icon>
          <span>发布管理</span>
        </template>
        <PublishView v-if="activeTab === 'publish'" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ContentsView from './Contents.vue'
import PublishView from './Publish.vue'

const route = useRoute()
const router = useRouter()

const tabMap = {
  contents: 0,
  publish: 1
}

const activeTab = ref(route.query.tab || 'contents')

watch(() => route.query.tab, (val) => {
  if (val && tabMap.hasOwnProperty(val)) {
    activeTab.value = val
  }
})

function onTabChange(tab) {
  activeTab.value = tab
  if (route.query.tab !== tab) {
    router.replace({ query: { tab } })
  }
}
</script>

<style scoped>
.page {
  animation: fadeIn 0.3s ease;
}

.content-tabs {
  --el-tabs-header-height: 40px;
}

.content-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
  background: var(--bg-panel);
  border-radius: 8px;
  padding: 4px 8px 0;
}

.content-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.content-tabs :deep(.el-tabs__item) {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  font-size: 13px;
  height: 36px;
  line-height: 36px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
