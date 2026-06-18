import { defineStore } from 'pinia'
import { getProducts }      from '@/api/products'
import { getContents }      from '@/api/contents'
import { getPublishRecords } from '@/api/publish'

export const useAppStore = defineStore('app', {
  state: () => ({
    dashboard: {
      productCount: 0,
      contentCount: 0,
      publishCount: 0,
      recentContents: [],
      recentPublish: []
    },
    loading: false
  }),
  actions: {
    async fetchDashboard() {
      this.loading = true
      try {
        const [products, contents, publish] = await Promise.all([
          getProducts({}),
          getContents({}),
          getPublishRecords({})
        ])
        // Backend returns plain arrays
        const prodArr  = Array.isArray(products) ? products : (products?.items || [])
        const contArr  = Array.isArray(contents) ? contents : (contents?.items || [])
        const pubArr   = Array.isArray(publish)   ? publish   : (publish?.items   || [])

        this.dashboard.productCount  = prodArr.length
        this.dashboard.contentCount  = contArr.length
        this.dashboard.publishCount  = pubArr.length
        this.dashboard.recentContents = contArr.slice(0, 5)
        this.dashboard.recentPublish  = pubArr.slice(0, 5)
      } catch (e) {
        console.error('Dashboard fetch error:', e)
      } finally {
        this.loading = false
      }
    }
  }
})
