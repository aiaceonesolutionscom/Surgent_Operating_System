import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Split heavy vendor libraries into their own chunks so the browser
    // caches them independently from app code (version bumps don't bust
    // the vendor cache).
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — rarely changes, max cache benefit
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // Clerk auth — heavy (~80-100 KB gz), only needed on auth/dashboard
          "vendor-clerk": ["@clerk/clerk-react"],
          // framer-motion — heavy animation lib (~42-60 KB gz)
          "vendor-framer": ["framer-motion"],
          // OGL — WebGL library (~60 KB gz), only used on landing page
          "vendor-ogl": ["ogl"],
        },
      },
    },
    // esbuild is the default Vite minifier — much faster than terser
    target: "es2020",
    minify: "esbuild",
  },
})
