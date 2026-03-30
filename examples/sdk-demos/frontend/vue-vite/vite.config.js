import path from 'node:path';
import { fileURLToPath } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

const dir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      os: path.join(dir, 'src/shims/os.cjs'),
    },
  },
  optimizeDeps: {
    include: ['error-monitor-sdk', 'axios'],
  },
  server: {
    port: 5174,
    strictPort: false,
  },
});
