import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
const publicHost = process.env.PUBLIC_HOST

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: publicHost ? [publicHost] : [],
    hmr: publicHost ? { host: publicHost, clientPort: 443, protocol: 'wss' } : undefined,
    proxy: {
      '/health': { target: proxyTarget, changeOrigin: false },
      '/api': { target: proxyTarget, changeOrigin: false }
    }
  }
})
