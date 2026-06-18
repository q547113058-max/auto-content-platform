<template>
  <el-container class="app-layout">
    <!-- Sidebar -->
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="app-sidebar">
      <div class="sidebar-header">
        <div class="brand" @click="router.push('/dashboard')">
          <span class="brand-icon mono" v-if="isCollapsed">ACP</span>
          <template v-else>
            <span class="brand-icon mono">ACP</span>
            <span class="brand-text mono">AutoContentPlatform</span>
          </template>
        </div>
      </div>

      <el-scrollbar>
        <el-menu
          :default-active="activeMenu"
          :collapse="isCollapsed"
          :collapse-transition="false"
          router
          class="sidebar-menu"
        >
          <el-menu-item index="/dashboard">
            <el-icon><Odometer /></el-icon>
            <span>功能列表</span>
          </el-menu-item>
          <el-menu-item index="/products">
            <el-icon><Goods /></el-icon>
            <span>产品管理</span>
          </el-menu-item>
          <el-menu-item index="/companies">
            <el-icon><OfficeBuilding /></el-icon>
            <span>公司管理</span>
          </el-menu-item>
          <el-menu-item index="/accounts">
            <el-icon><Avatar /></el-icon>
            <span>账号管理</span>
          </el-menu-item>
          <el-menu-item index="/contents">
            <el-icon><Document /></el-icon>
            <span>内容管理</span>
          </el-menu-item>
          <el-menu-item index="/publish">
            <el-icon><Promotion /></el-icon>
            <span>发布管理</span>
          </el-menu-item>
          <el-menu-item index="/metrics">
            <el-icon><DataAnalysis /></el-icon>
            <span>数据分析</span>
          </el-menu-item>
          <el-menu-item index="/optimizer">
            <el-icon><TrendCharts /></el-icon>
            <span>优化学习</span>
          </el-menu-item>
          <el-menu-item index="/prompts">
            <el-icon><EditPen /></el-icon>
            <span>提示词管理</span>
          </el-menu-item>
          <el-menu-item index="/sessions">
            <el-icon><Connection /></el-icon>
            <span>会话管理</span>
          </el-menu-item>
          <el-menu-item index="/engagement">
            <el-icon><ChatDotRound /></el-icon>
            <span>评论互动</span>
          </el-menu-item>
          <el-menu-item index="/database">
            <el-icon><Coin /></el-icon>
            <span>数据库浏览</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
        </el-menu>
      </el-scrollbar>

      <div class="sidebar-footer" @click="toggleCollapse">
        <el-icon :size="18">
          <DArrowLeft v-if="!isCollapsed" />
          <DArrowRight v-else />
        </el-icon>
        <span v-if="!isCollapsed" class="text-muted" style="margin-left:8px">收起菜单</span>
      </div>
    </el-aside>

    <!-- Main -->
    <el-container class="main-container">
      <!-- Header -->
      <el-header class="app-header">
        <div class="header-left">
          <h2 class="page-title mono">{{ currentTitle }}</h2>
        </div>
        <div class="header-right">
          <el-tag size="small" type="warning" effect="dark" class="mono">v1.0.0</el-tag>
        </div>
      </el-header>

      <!-- Content -->
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const isCollapsed = ref(false)
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '仪表盘')

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}
</script>

<style lang="scss" scoped>
.app-layout {
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.app-sidebar {
  background: var(--bg-panel) !important;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-normal);
  overflow: hidden;
}

.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.brand-icon {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 2px;
}

.brand-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.sidebar-menu {
  padding: 8px 0;
  flex: 1;
}

.sidebar-footer {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid var(--border-color);
  cursor: pointer;
  color: var(--text-muted);
  transition: color var(--transition-fast);
  flex-shrink: 0;
  font-size: 13px;
  &:hover {
    color: var(--text-secondary);
  }
}

/* Header */
.main-container {
  flex-direction: column;
}

.app-header {
  height: var(--header-height) !important;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Content */
.app-main {
  padding: 24px;
  overflow-y: auto;
  background: var(--bg-deep);
}

/* Page transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    width: 240px !important;
    transform: translateX(-100%);
    transition: transform var(--transition-normal);
    &.open {
      transform: translateX(0);
    }
  }
  .app-main {
    padding: 16px;
  }
}
</style>
