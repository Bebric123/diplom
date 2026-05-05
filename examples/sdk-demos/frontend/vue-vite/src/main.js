import './setupMonitorEnv.js';

import { createApp } from 'vue';

import * as MonitorSdk from 'error-monitor-sdk';
import * as BrowserIntegration from 'error-monitor-sdk/integrations/browser';
import * as VueMonitor from 'error-monitor-sdk/integrations/vue';

import App from './App.vue';

const url = (import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const projectId = (import.meta.env.VITE_MONITOR_PROJECT_ID || '').trim();
const apiKey = (import.meta.env.VITE_MONITOR_API_KEY || '').trim();

let initError = null;
let browserIntegWarning = null;

if (!projectId) {
  initError = new Error(
    'В .env задайте VITE_MONITOR_PROJECT_ID=… и перезапустите npm run dev. При API-ключе — VITE_MONITOR_API_KEY.',
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

const app = createApp(App);
app.provide('monitorDemoInitError', initError);
app.provide('monitorDemoBrowserError', initError ? null : browserIntegWarning);
if (!initError) {
  VueMonitor.installVue3Monitor(app);
}
app.mount('#app');
