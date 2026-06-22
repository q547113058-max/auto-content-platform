<template>
  <div class="page">
    <el-tabs v-model="activeTab" type="card" class="resource-tabs" @tab-change="onTabChange">
      <el-tab-pane name="companies">
        <template #label>
          <el-icon><OfficeBuilding /></el-icon>
          <span>公司管理</span>
        </template>
        <CompaniesView v-if="activeTab === 'companies'" />
      </el-tab-pane>

      <el-tab-pane name="products">
        <template #label>
          <el-icon><Goods /></el-icon>
          <span>产品管理</span>
        </template>
        <ProductsView v-if="activeTab === 'products'" />
      </el-tab-pane>

      <el-tab-pane name="knowledge">
        <template #label>
          <el-icon><Notebook /></el-icon>
          <span>知识库</span>
        </template>
        <KnowledgeBaseView v-if="activeTab === 'knowledge'" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CompaniesView from './Companies.vue'
import ProductsView from './Products.vue'
import KnowledgeBaseView from './KnowledgeBase.vue'

const route = useRoute()
const router = useRouter()

const tabMap = {
  companies: 0,
  products: 1,
  knowledge: 2
}

const activeTab = ref(route.query.tab || 'companies')

// 支持通过 query 参数切换 tab
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

.resource-tabs {
  --el-tabs-header-height: 40px;
}

.resource-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
  background: var(--bg-panel);
  border-radius: 8px;
  padding: 4px 8px 0;
}

.resource-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.resource-tabs :deep(.el-tabs__item) {
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
