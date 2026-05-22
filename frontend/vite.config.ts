import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Vite 配置
// - 开发时把后端 API 路径代理到本地 FastAPI（默认 8000）
// - 允许通过 VITE_BACKEND_URL 环境变量覆盖
export default defineConfig(({ mode }) => {
  const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        '/v1': { target: backend, changeOrigin: true },
        '/memory': { target: backend, changeOrigin: true },
        '/info': { target: backend, changeOrigin: true },
        '/healthz': { target: backend, changeOrigin: true },
        '/readyz': { target: backend, changeOrigin: true },
        '/debug': { target: backend, changeOrigin: true },
        '/setup': { target: backend, changeOrigin: true },
        '/images': { target: backend, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
    },
  }
})
