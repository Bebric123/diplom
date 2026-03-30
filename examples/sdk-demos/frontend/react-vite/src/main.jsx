import './setupMonitorEnv.js';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import * as MonitorSdk from 'error-monitor-sdk';
import * as BrowserIntegration from 'error-monitor-sdk/integrations/browser';

import App from './App.jsx';

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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
