import './setupMonitorEnv.js';

import { createRoot } from 'react-dom/client';

import * as MonitorSdk from 'error-monitor-sdk';
import * as BrowserIntegration from 'error-monitor-sdk/integrations/browser';

import App from './App.jsx';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Нет элемента #root');
}

let monitorReady = false;
try {
  MonitorSdk.initMonitor({
    endpoint: (import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000').replace(/\/$/, ''),
    projectId: "edb9ac0b-c0a5-45ee-829d-91ed250d4cd3",
    apiKey: "pLD-lQWqPiPQfIvDUNLNE_2ohTCgfIjzDPUSZHPLrLY",
    debug: true,
  });
  monitorReady = true;

  try {
    BrowserIntegration.enableBrowserIntegration({
      captureGlobalErrors: true,
      captureUnhandledRejections: true,
    });
  } catch (e) {
    console.warn('[demo] enableBrowserIntegration:', e);
  }
} catch (e) {
  console.error('[demo] initMonitor failed', e);
  rootEl.innerHTML = `<pre style="padding:1rem;color:#b91c1c;font-family:system-ui">initMonitor: ${String(
    e && e.message ? e.message : e,
  )}</pre>`;
}

if (monitorReady) {
  createRoot(rootEl).render(<App />);
}
