<script setup>
import { inject } from 'vue';

import * as MonitorSdk from 'error-monitor-sdk';

const initError = inject('monitorDemoInitError', null);
const browserError = inject('monitorDemoBrowserError', null);
const canUseSdk = !initError;
const monitorUrl = (import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000').toString();

function boom() {
  throw new Error('Vue 3 demo: ошибка через app.config.errorHandler');
}

function track() {
  MonitorSdk.trackEvent('vue_demo_manual', { source: 'vite-demo' }, window.location.href);
}

function globalErr() {
  setTimeout(() => {
    throw new Error('Vue demo: глобальная ошибка (browser.js)');
  }, 0);
}
</script>

<template>
  <div style="font-family: system-ui; padding: 1rem; max-width: 36rem">
    <div
      v-if="initError"
      style="
        margin-bottom: 1rem;
        padding: 0.75rem 1rem;
        background: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
        border-radius: 6px;
        font-size: 0.9rem;
        white-space: pre-wrap;
      "
    >
      <strong>Коллектор / SDK</strong><br />
      {{ initError && initError.message ? initError.message : String(initError) }}
    </div>
    <div
      v-else-if="browserError"
      style="margin-bottom: 0.75rem; color: #9a3412; font-size: 0.85rem"
    >
      enableBrowserIntegration: {{ browserError.message || String(browserError) }}
    </div>
    <h1 style="font-size: 1.25rem">Error Monitor — Vue 3 + Vite</h1>
    <p style="color: #555; font-size: 0.9rem">
      <code>{{ monitorUrl }}</code> · CORS, <code>VITE_*</code> в .env, F12 → Console при «пусто».
    </p>
    <p style="color: #0f172a; font-size: 0.8rem; max-width: 34rem; line-height: 1.5">
      <strong>Telegram:</strong> после <code>/track</code> сообщение в чат шлёт <strong>воркер Celery</strong>
      (нужны Redis + <code>celery worker</code> и <code>telegram_chat_id</code> у проекта). См.
      <code>project/docker</code>, раздел <code>frontend/README.md</code> в <code>examples/sdk-demos</code>.
    </p>
    <ul v-if="canUseSdk" style="line-height: 2">
      <li>
        <button type="button" @click="boom">Ошибка рендера → errorHandler → /track</button>
      </li>
      <li>
        <button type="button" @click="track">Отправить track_event</button>
      </li>
      <li>
        <button type="button" @click="globalErr">Глобальная ошибка (setTimeout)</button>
      </li>
    </ul>
    <p v-else style="color: #666">Заполните .env и перезапустите dev — кнопки появятся снова.</p>
  </div>
</template>
