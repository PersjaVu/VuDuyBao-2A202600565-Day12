import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/messages': {
        target: 'http://localhost:10100',
        changeOrigin: true,
        rewrite: () => '/'
      }
    }
  }
})
