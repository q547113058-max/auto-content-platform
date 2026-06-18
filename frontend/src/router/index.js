import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' }
      },
      {
        path: 'products',
        name: 'Products',
        component: () => import('@/views/Products.vue'),
        meta: { title: '产品管理', icon: 'Goods' }
      },
      {
        path: 'companies',
        name: 'Companies',
        component: () => import('@/views/Companies.vue'),
        meta: { title: '公司管理', icon: 'OfficeBuilding' }
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/Accounts.vue'),
        meta: { title: '账号管理', icon: 'Avatar' }
      },
      {
        path: 'contents',
        name: 'Contents',
        component: () => import('@/views/Contents.vue'),
        meta: { title: '内容管理', icon: 'Document' }
      },
      {
        path: 'publish',
        name: 'Publish',
        component: () => import('@/views/Publish.vue'),
        meta: { title: '发布管理', icon: 'Promotion' }
      },
      {
        path: 'metrics',
        name: 'Metrics',
        component: () => import('@/views/Metrics.vue'),
        meta: { title: '数据分析', icon: 'DataAnalysis' }
      },
      {
        path: 'optimizer',
        name: 'Optimizer',
        component: () => import('@/views/Optimizer.vue'),
        meta: { title: '优化学习', icon: 'TrendCharts' }
      },
      {
        path: 'prompts',
        name: 'Prompts',
        component: () => import('@/views/Prompts.vue'),
        meta: { title: '提示词管理', icon: 'EditPen' }
      },
      {
        path: 'sessions',
        name: 'Sessions',
        component: () => import('@/views/Sessions.vue'),
        meta: { title: '会话管理', icon: 'Connection' }
      },
      {
        path: 'engagement',
        name: 'Engagement',
        component: () => import('@/views/Engagement.vue'),
        meta: { title: '评论互动', icon: 'ChatDotRound' }
      },
      {
        path: 'database',
        name: 'Database',
        component: () => import('@/views/Database.vue'),
        meta: { title: '数据库浏览', icon: 'Coin' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置', icon: 'Setting' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
