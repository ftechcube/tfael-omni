import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'

// TFAEL-OMNI — air-gap ready build
// `npm run build` produces static dist/ that Python stdlib server can serve
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    // Single-chunk for air-gap simplicity — Python serves these as static files
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  server: {
    // Dev proxy to Python backend
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
