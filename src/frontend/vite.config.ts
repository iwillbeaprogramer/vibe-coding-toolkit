import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

const frontendSetup = fileURLToPath(new URL('../../tests/frontend/setup.ts', import.meta.url)).replace(/\\/g, '/');
const repoRoot = fileURLToPath(new URL('../..', import.meta.url)).replace(/\\/g, '/');

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@testing-library/jest-dom/vitest': fileURLToPath(
        new URL('./node_modules/@testing-library/jest-dom/vitest.js', import.meta.url)
      ).replace(/\\/g, '/'),
      '@testing-library/react': fileURLToPath(
        new URL('./node_modules/@testing-library/react', import.meta.url)
      ).replace(/\\/g, '/'),
      '@testing-library/user-event': fileURLToPath(
        new URL('./node_modules/@testing-library/user-event', import.meta.url)
      ).replace(/\\/g, '/')
    }
  },
  server: {
    port: 5173,
    fs: {
      allow: [repoRoot]
    },
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['../../tests/frontend/**/*.test.tsx'],
    setupFiles: [frontendSetup]
  }
});
