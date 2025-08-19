import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/dd-education/',
  server: {
    port: 3000,
    open: true
  },
  build: {
    outDir: 'build'
  },
  assetsInclude: ['**/*.whl']
})
