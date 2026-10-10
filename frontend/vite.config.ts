import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const LOCAL_HOST = /^(https?:\/\/)?(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])([:/]|$)/i

// A production bundle bakes its configuration in at build time. Building one
// without it does not fail - it ships a site that points every visitor's
// browser at their own machine and (without a Clerk key) leaves sign-in
// unconfigured. Fail the build instead.
//
//   ALLOW_LOCAL_BUILD=1 npm run build   skips the check (local smoke builds only)
function assertProductionEnv(env: Record<string, string>) {
  const problems: string[] = []
  const api = env.VITE_API_BASE_URL
  if (!api) problems.push('VITE_API_BASE_URL is not set (the public URL of the backend API)')
  else if (LOCAL_HOST.test(api)) problems.push(`VITE_API_BASE_URL points at localhost (${api})`)
  else if (api.startsWith('http://')) problems.push(`VITE_API_BASE_URL uses plain http (${api})`)
  if (!env.VITE_CLERK_PUBLISHABLE_KEY) problems.push('VITE_CLERK_PUBLISHABLE_KEY is not set')
  if (env.VITE_DEMO_MODE) problems.push('VITE_DEMO_MODE is set - demo mode renders fake data and must never ship')
  if (problems.length) {
    throw new Error(
      'Refusing to build for production:\n  - ' + problems.join('\n  - ') +
        '\nSet them in the host\'s environment (e.g. `insforge deployments env set`), or ALLOW_LOCAL_BUILD=1 for a local smoke build.'
    )
  }
  if (!env.VITE_STRIPE_PUBLISHABLE_KEY) {
    console.warn('\n[build] VITE_STRIPE_PUBLISHABLE_KEY is not set - the payment page will say checkout is unavailable.\n')
  }
  if (env.VITE_CLERK_PUBLISHABLE_KEY.startsWith('pk_test_')) {
    console.warn('\n[build] VITE_CLERK_PUBLISHABLE_KEY is a pk_test_ key - fine for staging, not for real users.\n')
  }
}

// The hero's frame files are cached for a year (vercel.json), so their URLs carry a content
// version (`?v=`, written into frames.manifest.json by scripts/build-scroll-frames.py). The scrub
// engine reads it from the manifest; index.html's poster preload gets it from here.
function heroFramesVersion(): Plugin {
  const manifestPath = resolve(process.cwd(), 'src/components/hero/frames.manifest.json')
  return {
    name: 'hero-frames-version',
    transformIndexHtml(html) {
      const version = JSON.parse(readFileSync(manifestPath, 'utf-8')).reception?.desktop?.v ?? ''
      return html.split('__FRAMES_V__').join(version)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  if (mode === 'production' && !process.env.ALLOW_LOCAL_BUILD) {
    assertProductionEnv(loadEnv(mode, process.cwd(), 'VITE_'))
  }

  return {
    plugins: [react(), heroFramesVersion()],
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
            // React core - rarely changes, max cache benefit
            "vendor-react": ["react", "react-dom", "react-router-dom"],
            // Clerk auth - heavy (~80-100 KB gz), only needed on auth/dashboard
            "vendor-clerk": ["@clerk/clerk-react"],
            // framer-motion - heavy animation lib (~42-60 KB gz)
            "vendor-framer": ["framer-motion"],
            // OGL - WebGL library (~60 KB gz), only used on landing page
            "vendor-ogl": ["ogl"],
            // Sentry - imported statically in index.tsx so it can catch boot
            // errors, but cached on its own so it never invalidates with app code.
            "vendor-sentry": ["@sentry/react"],
            // PostHog - dynamically imported on idle in index.tsx. Listed here
            // so the lazy chunk keeps a stable, cacheable name instead of an
            // inline blob riding along with the entry chunk's hash.
            "vendor-analytics": ["posthog-js"],
          },
        },
      },
      // esbuild is the default Vite minifier - much faster than terser
      target: "es2020",
      minify: "esbuild",
    },
  }
})
