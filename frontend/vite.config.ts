import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(() => {
  const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
        dts: 'src/auto-imports.d.ts',
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        directives: true,
        dts: false,
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            if (
              id.includes('/zrender/')
              || id.includes('\\zrender\\')
              || id.includes('/echarts/')
              || id.includes('\\echarts\\')
            ) return 'charts'
            if (id.includes('/@pixiv/three-vrm') || id.includes('\\@pixiv\\three-vrm')) return 'vrm-runtime'
            if (id.includes('/three/') || id.includes('\\three\\')) return 'three-runtime'
            return undefined
          },
        },
      },
    },
  }
})
