import './setupMonitorEnv.js';

import { createApp } from 'vue';

import * as MonitorSdk from 'error-monitor-sdk';
import * as BrowserIntegration from 'error-monitor-sdk/integrations/browser';
import * as VueMonitor from 'error-monitor-sdk/integrations/vue';

import App from './App.vue';

MonitorSdk.initMonitor({
  endpoint: (import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000').replace(/\/$/, ''),
  projectId: import.meta.env.VITE_MONITOR_PROJECT_ID || '00000000-0000-4000-8000-000000000001',
  apiKey: (import.meta.env.VITE_MONITOR_API_KEY || '').trim(),
  debug: true,
});

BrowserIntegration.enableBrowserIntegration({
  captureGlobalErrors: true,
  captureUnhandledRejections: true,
});

const app = createApp(App);
VueMonitor.installVue3Monitor(app);
app.mount('#app');
