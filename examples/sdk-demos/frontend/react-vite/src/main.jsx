import './setupMonitorEnv.js';

import { createRoot } from 'react-dom/client';

import * as MonitorSdk from 'error-monitor-sdk';
import * as BrowserIntegration from 'error-monitor-sdk/integrations/browser';

import App from './App.jsx';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Нет элемента #root');
}

const url = (import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const projectId = (import.meta.env.VITE_MONITOR_PROJECT_ID || '').trim();
const apiKey = (import.meta.env.VITE_MONITOR_API_KEY || '').trim();

let initError = null;
let browserIntegWarning = null;

if (!projectId) {
  initError = new Error(
    'В .env (рядом с package.json) задайте VITE_MONITOR_PROJECT_ID=… и перезапустите npm run dev. При COLLECTOR_REQUIRE_API_KEY — также VITE_MONITOR_API_KEY.',
  );
} else {
  try {
    MonitorSdk.initMonitor({
      endpoint: url,
      projectId,
      apiKey: apiKey || undefined,
      debug: true,
    });
    try {
      BrowserIntegration.enableBrowserIntegration({
        captureGlobalErrors: true,
        captureUnhandledRejections: true,
      });
    } catch (e) {
      browserIntegWarning = e;
      console.warn('[demo] enableBrowserIntegration:', e);
    }
  } catch (e) {
    initError = e;
    console.error('[demo] initMonitor failed', e);
  }
}

const root = createRoot(rootEl);
root.render(
  <App initError={initError} browserIntegWarning={browserIntegWarning} />,
);
