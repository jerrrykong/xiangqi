import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      dts: 'src/components.d.ts',
    }),
  ],
  base: '/xiangqi/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/xiangqi/ws': {
        target: 'ws://localhost:8765',
        ws: true,
        rewrite: (path) => path.replace(/^\/xiangqi\/ws/, '/ws'), // 🛠️ 将前端路径重写为后端的 /ws
      },
    },
  },
})
