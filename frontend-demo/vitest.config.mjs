// Standalone vitest config so it does NOT try to load vite.config.js
// (which is ESM-only via @vitejs/plugin-react and breaks vitest's CJS loader).
// We only need a minimal node-environment runner for pure-JS helper tests.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}'],
  },
});
