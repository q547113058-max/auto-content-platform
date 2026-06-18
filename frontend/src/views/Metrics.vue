<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">数据分析</h3>
      <div style="display:flex;gap:8px;align-items:center">
        <el-select v-model="selectedProduct" placeholder="选择产品" clearable style="width:200px" @change="onProductChange">
          <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button @click="handleScrapeAll" :loading="scrapingAll">全量抓取</el-button>
        <el-button @click="handleScrapeProduct" :loading="scraping" :disabled="!selectedProduct">产品抓取</el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :xs="12" :sm="6" v-for="card in overviewCards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value mono" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表行 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <!-- 平台分布饼图 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-header">平台内容分布</span></template>
          <v-chart :option="platformPieOption" style="height:300px" autoresize v-loading="chartLoading" />
        </el-card>
      </el-col>

      <!-- 趋势折线图 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-header">数据趋势</span></template>
          <v-chart v-if="selectedProduct" :option="trendOption" style="height:300px" autoresize v-loading="chartLoading" />
          <el-empty v-else description="请选择产品查看趋势" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 效果排行 -->
    <el-card shadow="never" class="chart-card" style="margin-bottom:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="card-header">内容效果排行</span>
          <el-radio-group v-model="sortBy" size="small" @change="fetchTopContents">
            <el-radio-button value="views">浏览</el-radio-button>
            <el-radio-button value="likes">点赞</el-radio-button>
            <el-radio-button value="comments">评论</el-radio-button>
            <el-radio-button value="engagement">互动率</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="topContents" v-loading="topLoading">
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="90">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.platform }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="views" label="浏览" width="100" sortable>
          <template #default="{ row }"><span class="mono" style="color:var(--accent)">{{ formatNum(row.views) }}</span></template>
        </el-table-column>
        <el-table-column prop="likes" label="点赞" width="80" />
        <el-table-column prop="comments" label="评论" width="80" />
        <el-table-column prop="shares" label="分享" width="80" />
        <el-table-column prop="engagement_rate" label="互动率" width="90">
          <template #default="{ row }"><span class="mono">{{ row.engagement_rate }}%</span></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart, LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getMetricsOverview, getPlatformDistribution, getTrends, getTopContents,
  triggerScrapeAll, triggerScrapeProduct,
} from '@/api/metrics'
import { getProducts } from '@/api/products'

use([PieChart, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const chartLoading = ref(false)
const topLoading = ref(false)
const scraping = ref(false)
const scrapingAll = ref(false)
const selectedProduct = ref(null)
const products = ref([])
const sortBy = ref('views')
const topContents = ref([])

// 概览数据
const overview = ref({ product_count: 0, content_count: 0, published_count: 0, total_views: 0, total_likes: 0, total_comments: 0, total_shares: 0, total_collects: 0 })

const overviewCards = computed(() => [
  { label: '产品数', value: overview.value.product_count, color: 'var(--accent)' },
  { label: '内容数', value: overview.value.content_count, color: '#67c23a' },
  { label: '已发布', value: overview.value.published_count, color: '#409eff' },
  { label: '总浏览量', value: formatNum(overview.value.total_views), color: '#e6a23c' },
])

// 平台分布
const platformData = ref([])
const platformPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 篇 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: '#8892a4' } },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['50%', '45%'],
    itemStyle: { borderRadius: 4, borderColor: '#0f1117', borderWidth: 3 },
    label: { color: '#8892a4' },
    data: platformData.value.map(d => ({ name: d.platform, value: d.content_count })),
  }],
}))

// 趋势图
const trends = ref({ dates: [], series: {} })
const trendOption = computed(() => {
  const series = trends.value.series || {}
  const colors = { xiaohongshu: '#ff2442', zhihu: '#0066ff', weibo: '#ff8200', toutiao: '#e8453c', douyin: '#111111', wechat: '#07c160', bilibili: '#fb7299' }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: Object.keys(series), bottom: 0, textStyle: { color: '#8892a4' } },
    grid: { left: 50, right: 20, top: 10, bottom: 40 },
    xAxis: { type: 'category', data: trends.value.dates, axisLabel: { color: '#8892a4', rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { color: '#8892a4', formatter: v => formatNum(v) } },
    series: Object.entries(series).map(([name, data]) => ({
      name,
      type: 'line',
      data: data.map(d => d.views),
      smooth: true,
      lineStyle: { color: colors[name] || '#e8c547', width: 2 },
      itemStyle: { color: colors[name] || '#e8c547' },
    })),
  }
})

function formatNum(n) {
  if (!n && n !== 0) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

async function loadOverview() {
  try {
    const res = await getMetricsOverview()
    overview.value = res
  } catch (e) { /* ignore */ }
}

async function loadPlatformDist() {
  chartLoading.value = true
  try {
    platformData.value = await getPlatformDistribution()
  } finally { chartLoading.value = false }
}

async function loadTrends() {
  if (!selectedProduct.value) return
  chartLoading.value = true
  try {
    trends.value = await getTrends(selectedProduct.value)
  } finally { chartLoading.value = false }
}

async function fetchTopContents() {
  topLoading.value = true
  try {
    topContents.value = await getTopContents(10, sortBy.value)
  } finally { topLoading.value = false }
}

async function onProductChange() {
  loadTrends()
}

async function handleScrapeProduct() {
  if (!selectedProduct.value) return
  scraping.value = true
  try {
    await triggerScrapeProduct(selectedProduct.value)
    ElMessage.success('产品数据抓取已触发')
    loadTrends()
  } finally { scraping.value = false }
}

async function handleScrapeAll() {
  scrapingAll.value = true
  try {
    const res = await triggerScrapeAll()
    ElMessage.success(res.message || '全量抓取已触发')
    loadOverview()
    loadPlatformDist()
  } finally { scrapingAll.value = false }
}

onMounted(async () => {
  // 加载产品列表
  try {
    const res = await getProducts()
    products.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {}

  loadOverview()
  loadPlatformDist()
  fetchTopContents()
})
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap:wrap; gap:8px }

.stat-card {
  text-align: center;
  .stat-label { font-size: 12px; color: #8892a4; margin-bottom: 6px; }
  .stat-value { font-size: 22px; font-weight: 700; }
}

.chart-card {
  :deep(.el-card__header) { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
}
.card-header { font-size: 13px; font-weight: 600; color: #c0c8d8; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
