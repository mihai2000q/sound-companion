import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Shared root .env (in compose the same values arrive as real environment variables).
  const env = loadEnv(mode, '..', '')
  return {
    // Only VITE_-prefixed variables reach browser code.
    envDir: '..',
    server: { port: Number(env.CLIENT_PORT), strictPort: true },
    plugins: [
      react(),
      tailwindcss(),
      babel({ presets: [reactCompilerPreset()] })
    ],
  }
})
