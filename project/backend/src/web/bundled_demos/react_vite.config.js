import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const dir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Иначе SDK подтянет второй экземпляр React → белый экран / Invalid hook call
    dedupe: ['react', 'react-dom'],
    alias: {
      // SDK тянет Node-модуль `os` — в браузере подменяем заглушкой
      os: path.join(dir, 'src/shims/os.cjs'),
    },
  },
  optimizeDeps: {
    include: ['error-monitor-sdk', 'axios', 'react', 'react-dom'],
  },
  server: {
    port: 5173,
    strictPort: false,
  },
});
