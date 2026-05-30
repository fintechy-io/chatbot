import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 48291, // Set to a random port as requested
    strictPort: true, // Fail if the port is already in use
  }
})
