import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router']
    }),
    Components({
      resolvers: [ElementPlusResolver()]
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
        // 生成长内容时 DeepSeek + 配图可能耗时 5-10 分钟，代理不能先断
        proxyTimeout: 600000,   // 代理等待后端响应超时：10 分钟
        timeout: 600000,         // 整体请求超时：10 分钟
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('[Vite Proxy Error]', err.message, req.url)
          })
        }
      },
      '/uploads': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true
      },
      '/generated_images': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true
      }
    }
  }
})
