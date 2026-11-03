import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: 'localhost', port: 5177, strictPort: true, proxy: { '/api': { target: process.env.MEDISAATHI_PROXY_TARGET || 'http://127.0.0.1:8005' } } },
})
