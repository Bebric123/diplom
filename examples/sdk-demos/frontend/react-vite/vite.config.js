import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const dir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Условие browser → index.browser.mjs (ESM) вместо index.js (require)
    conditions: ['browser', 'module', 'import', 'default'],
    // Иначе SDK подтянет второй экземпляр React → белый экран / Invalid hook call
    // Один экземпляр SDK — иначе initMonitor() в main и getClient() в integrations/browser.mjs рассинхрон
    dedupe: ['react', 'react-dom', 'error-monitor-sdk'],
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
