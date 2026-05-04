import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Split Three.js + drei + fiber into a separate chunk so the demo shell
// (catalog list, ingest form, panels) loads before the heavy 3D viewer.
export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (
              id.includes('three') ||
              id.includes('@react-three') ||
              id.includes('@monogrid')
            ) {
              return 'three-vendor';
            }
            if (id.includes('react') || id.includes('scheduler')) {
              return 'react-vendor';
            }
          }
        },
      },
    },
  },
});
